# -*- coding:utf-8 -*-

import errno
import glob
import hashlib
import inspect
import io
import os
import re
import time
import sys
from pkg_resources import resource_filename, parse_version
from random import Random
from subprocess import Popen, PIPE
from tempfile import mkstemp

try:
    import ConfigParser as configparser
except ImportError:
    import configparser

try:
    import json
except ImportError:
    import simplejson as json

from trac import __version__
from trac.core import Component, implements
from trac.admin import IAdminPanelProvider
from trac.config import (Configuration, Option, BoolOption, IntOption,
                         ListOption, FloatOption, ChoiceOption)
from trac.env import Environment, IEnvironmentSetupParticipant
from trac.perm import PermissionSystem
from trac.util.html import tag
from trac.util.text import to_unicode, exception_to_unicode
from trac.util.translation import dgettext, domain_functions, tgettext_noop
from trac.web.chrome import (Chrome, ITemplateProvider, add_stylesheet,
                             add_script, add_script_data)


try:
    hashlib.sha1(usedforsecurity=False)
except TypeError:
    sha1 = hashlib.sha1
else:
    sha1 = lambda *args: hashlib.sha1(*args, usedforsecurity=False)


if hasattr(inspect, 'getfullargspec'):
    getargspec = inspect.getfullargspec
else:
    getargspec = inspect.getargspec


PY2 = sys.version_info[0] == 2
if PY2:
    unicode = unicode
    iteritems = lambda d: d.iteritems()
else:
    unicode = str
    iteritems = lambda d: d.items()


_, gettext, N_, add_domain = domain_functions(
    'tracworkflowadmin', '_', 'gettext', 'N_', 'add_domain')


if 'doc_domain' not in getargspec(Option.__init__)[0]:
    def _option_with_tx(Base): # Trac 0.12.x
        class Option(Base):
            def __getattribute__(self, name):
                if name == '__class__':
                    return Base
                val = Base.__getattribute__(self, name)
                if name == '__doc__':
                    val = dgettext('tracworkflowadmin', val)
                return val
        return Option
else:
    def _option_with_tx(Base): # Trac 1.0 or later
        def fn(*args, **kwargs):
            kwargs['doc_domain'] = 'tracworkflowadmin'
            return Base(*args, **kwargs)
        return fn


Option = _option_with_tx(Option)
BoolOption = _option_with_tx(BoolOption)
ListOption = _option_with_tx(ListOption)
FloatOption = _option_with_tx(FloatOption)
ChoiceOption = _option_with_tx(ChoiceOption)


__all__ = ['TracWorkflowAdminModule']


_use_jinja2 = hasattr(Chrome, 'jenv')
if _use_jinja2:
    _template_dir = resource_filename(__name__, 'templates/jinja2')
else:
    _template_dir = resource_filename(__name__, 'templates/genshi')
_htdoc_dir = resource_filename(__name__, 'htdocs')
try:
    _locale_dir = resource_filename(__name__, 'locale')
except:
    _locale_dir = None


def _default_operations():
    operations = ['del_owner', 'set_owner', 'set_owner_to_self',
                  'del_resolution', 'set_resolution', 'leave_status']
    if parse_version(__version__) >= parse_version('1.2'):
        operations.append('may_set_owner')
    return ', '.join(operations)

_default_operations = _default_operations()


def _help(href):
    text = _("Please refer to [1:TracWorkflow] for the setting method of a "
             "workflow.")
    kwargs = {'arg1': 'TracWorkflow'}
    def repl(match):
        idx = 'arg%d' % int(match.group(1))
        kwargs[idx] = match.group(2)
        return '%(' + idx + ')s'
    fmt = re.sub(r'\[(\d+):([^]]*)\]', repl, text)
    kwargs['arg1'] = tag.a(kwargs['arg1'], href=href.wiki('TracWorkflow'))
    return tgettext_noop(fmt, **kwargs)


def _msgjs_locales(dir_=None):
    if dir_ is None:
        dir_ = _htdoc_dir
        dir_ = os.path.join(dir_, 'scripts', 'messages')
    if not os.path.isdir(dir_):
        return frozenset()
    return frozenset(filename[0:-3] for filename in os.listdir(dir_)
                                    if filename.endswith('.js'))

_msgjs_locales = _msgjs_locales()


if PY2:
    from cStringIO import StringIO

    def _conf_to_str(conf):
        tmp = configparser.RawConfigParser()
        tmp.add_section('ticket-workflow')
        for name, value in conf.options('ticket-workflow'):
            name = name.encode('utf-8')
            value = value.encode('utf-8')
            tmp.set('ticket-workflow', name, value)

        f = StringIO()
        tmp.write(f)
        f.flush()
        f.seek(0)
        lines = sorted(line.decode('utf-8')
                       for line in f if not line.startswith('['))
        return ''.join(lines)
else:
    def _conf_to_str(conf):
        tmp = configparser.RawConfigParser()
        tmp.add_section('ticket-workflow')
        for name, value in conf.options('ticket-workflow'):
            tmp.set('ticket-workflow', name, value)

        f = io.StringIO()
        tmp.write(f)
        f.flush()
        f.seek(0)
        lines = sorted(line for line in f if not line.startswith('['))
        return ''.join(lines)


class TracWorkflowAdminModule(Component):
    implements(IAdminPanelProvider, ITemplateProvider,
               IEnvironmentSetupParticipant)

    operations = ListOption('workflow-admin', 'operations',
        _default_operations, doc=N_("Operations in workflow admin"))
    dot_path = Option('workflow-admin', 'dot_path', 'dot',
        doc=N_("Path to the dot executable"))
    diagram_cache = BoolOption('workflow-admin', 'diagram_cache', 'false',
        doc=N_("Enable cache of workflow diagram image"))
    diagram_size = Option('workflow-admin', 'diagram_size', '6, 6',
        doc=N_("Image size in workflow diagram"))
    diagram_font = Option('workflow-admin', 'diagram_font', 'sans-serif',
        doc=N_("Font name in workflow diagram"))
    diagram_fontsize = FloatOption('workflow-admin', 'diagram_fontsize', '10',
        doc=N_("Font size in workflow diagram"))
    diagram_colors = ListOption('workflow-admin', 'diagram_colors',
        '#0000ff, #006600, #ff0000, #666600, #ff00ff',
        doc=N_("Colors of arrows in workflow diagram"))
    default_editor = ChoiceOption(
        'workflow-admin', 'default_editor', ['gui', 'text'],
        doc=N_("Default mode of the workflow editor"))
    auto_update_interval = IntOption(
        'workflow-admin', 'auto_update_interval', '3000',
        doc=N_("An automatic-updating interval for text mode is specified by "
               "a milli second bit. It is not performed when 0 is specified."))

    _action_name_re = re.compile(r'\A[A-Za-z0-9_-]+\Z')
    _number_re = re.compile(r'\A[0-9]+\Z')

    def __init__(self):
        if _locale_dir:
            add_domain(self.env.path, _locale_dir)

    # IEnvironmentSetupParticipant
    def environment_created(self):
        pass

    def environment_needs_upgrade(self, db=None):
        return False

    def upgrade_environment(self, db=None):
        pass

    # ITemplateProvider method
    def get_htdocs_dirs(self):
        return [('tracworkflowadmin', _htdoc_dir)]

    def get_templates_dirs(self):
        return [_template_dir]

    # IAdminPanelProvider methods
    def get_admin_panels(self, req):
        if 'TICKET_ADMIN' in req.perm('admin', 'ticket/workflowadmin'):
            yield ('ticket', dgettext("messages", ("Ticket System")),
                   'workflowadmin', _("Workflow Admin"))

    def render_admin_panel(self, req, cat, page, path_info):
        req.perm('admin', 'ticket/workflowadmin').require('TICKET_ADMIN')

        if req.method == 'POST':
            self._parse_request(req)

        action, status = self._conf_to_inner_format(self.config)
        operations = self.operations
        permissions = self._get_permissions(req)
        add_stylesheet(req, 'tracworkflowadmin/css/tracworkflowadmin.css')
        self._add_jquery_ui(req)
        add_stylesheet(req, 'tracworkflowadmin/css/jquery.multiselect.css')
        add_script(req, 'tracworkflowadmin/scripts/jquery.json-2.2.js')
        add_script(req, self._jquery_multiselect)
        add_script(req, 'tracworkflowadmin/scripts/main.js')
        add_script_data(req,
                        {'auto_update_interval': self.auto_update_interval})
        if req.locale and str(req.locale) in _msgjs_locales:
            add_script(req, 'tracworkflowadmin/scripts/messages/%s.js' % req.locale)
        data = {
            'actions': action,
            'status': status,
            'perms': permissions,
            'operations': operations,
            'editor_mode': req.args.get('editor_mode') or self.default_editor,
            'text': self._conf_to_str(self.config),
        }
        if _use_jinja2:
            data['help'] = _help(req.href)
        return 'tracworkflowadmin.html', data

    if hasattr(Chrome, 'add_jquery_ui'):
        def _add_jquery_ui(self, req):
            Chrome(self.env).add_jquery_ui(req)
        _jquery_multiselect = 'tracworkflowadmin/scripts/jquery.multiselect.js'
    else:
        def _add_jquery_ui(self, req):
            add_stylesheet(req, 'tracworkflowadmin/themes/base/jquery-ui.css')
            add_script(req, 'tracworkflowadmin/scripts/jquery-ui.js')
        _jquery_multiselect = \
            'tracworkflowadmin/scripts/jquery.multiselect-1.9.js'

    if hasattr(Environment, 'htdocs_dir'):
        _env_htdocs_dir = property(lambda self: self.env.htdocs_dir)
    else:
        _env_htdocs_dir = property(lambda self: self.env.get_htdocs_dir())

    def _conf_to_inner_format(self, conf):
        statuses = []
        for name, value in conf.options('ticket-workflow'):
            if not name.endswith('.operations'):
                continue
            if not any('leave_status' == v.strip() for v in value.split(',')):
                continue
            values = conf.get('ticket-workflow', name[0:-11]).split('->')
            if values[1].strip() == '*':
                for name in values[0].split(','):
                    st = name.strip()
                    if st != '*':
                        statuses.append(st)
                break
        actions = {}

        count = 1
        for name, value in conf.options('ticket-workflow'):
            param = name.split('.')
            actionName = param[0].strip()
            regValue = ''
            if len(param) == 1:
                pieces = [val.strip() for val in value.split('->')]
                before = pieces[0]
                next = '*'
                if len(pieces) > 1:
                    next = pieces[1]
                regValue = {'next': next, 'before': {}}
                if next != '*' and next not in statuses:
                        statuses.append(next)
                if before != '*':
                    for val in before.split(','):
                        tmp = val.strip()
                        if tmp != '':
                            regValue['before'][tmp] = 1
                            if tmp != '*' and tmp not in statuses:
                                statuses.append(tmp)
                else:
                    regValue['before'] = '*'
                if actionName not in actions:
                    actions[actionName] = {'tempName': actionName, 'lineInfo': {}}
                actions[actionName]['next'] = regValue['next']
                actions[actionName]['before'] = regValue['before']
            else:
                regKey = param[1].strip()
                if regKey == 'permissions' or regKey == 'operations':
                    tmp = []
                    for v in value.strip().split(','):
                        tmp2 = v.strip()
                        if  tmp2 != '':
                            tmp.append(v.strip())
                    regValue = tmp
                else:
                    regValue = value.strip()
                if actionName not in actions:
                    actions[actionName] = {'tempName': actionName, 'lineInfo': {}}
                actions[actionName][regKey] = regValue
            count = count + 1

        action_elements = []
        for key in actions:
            tmp = actions[key]
            tmp['action'] = key
            if 'default' not in tmp:
                tmp['default'] = 0
            elif not self._number_re.match(tmp['default']):
                tmp['default'] = -1
            if 'permissions' not in tmp:
                tmp['permissions'] = ['All Users']
            tmp.setdefault('name', '')
            if tmp.get('before') == '*':
                tmp['before'] = dict((st, 1) for st in statuses)
            action_elements.append(tmp)
        action_elements.sort(key=lambda v: int(v['default']), reverse=True)
        return (action_elements, statuses)

    def _conf_to_str(self, conf):
        return _conf_to_str(conf)

    def _str_to_inner_format(self, string, out):
        lines = string.splitlines(False)
        errors = []
        lineInfo = {}
        firstLineInfo = {}  # dict of (action, lineno)
        others = {}
        for idx, line in enumerate(lines):
            lineno = idx + 1
            line = line.strip()
            lines[idx] = line
            if not line or line.startswith('#') or line.startswith(';'):
                continue
            if line.startswith('['):
                errors.append(_("Line %(num)d: Could not use section.",
                                num=lineno))
                continue
            if '=' not in line:
                errors.append(_(
                    "Line %(num)d: This line is not pair of key and value.",
                    num=lineno))
                continue
            key, value = line.split('=', 1)
            key = key.strip().lower()
            value = value.strip()
            if key in lineInfo:
                errors.append(_(
                    "Line %(num)d: There is a same key in line %(num2)d.",
                    num=lineno, num2=lineInfo[key]))
                continue
            lineInfo[key] = lineno
            keys = key.split('.', 1)
            firstLineInfo.setdefault(keys[0], lineno)
            if len(keys) == 1:
                if '->' not in value:
                    errors.append(_(
                        "Line %(num)d: Must be \"<action> = <status-list> -> "
                        "<new-status>\" format.", num=lineno))
                    continue
                stats = [stat.strip()
                         for stat in value.split('->')[0].split(',')]
                for n, stat in enumerate(stats):
                    if not stat:
                        errors.append(_(
                            "Line %(num)d: #%(n)d status is empty.",
                            num=lineno, n=n + 1))
            else:
                attr = keys[1]
                if '.' in attr:
                    errors.append(_(
                        "Line %(num)d: Must be \"<action>.<attribute> = "
                        "<value>\" format.", num=lineno))
                    continue
                if attr not in ('default', 'name', 'operations', 'permissions'):
                    others.setdefault(keys[0], {})
                    others[keys[0]][attr] = value

        if not firstLineInfo:
            errors.append(_("There is no valid description."))

        for key in sorted(firstLineInfo):
            if key not in lineInfo:
                errors.append(_(
                    "Line %(num)d: Require \"%(action)s = <status-list> -> "
                    "<new-status>\" line.",
                    num=firstLineInfo[key], action=key))

        if len(errors) != 0:
            out['textError'] = errors;
            return

        contents = os.linesep.join(['[ticket-workflow]'] + lines)
        contents = contents.encode('utf-8')
        tmp_fd, tmp_file = mkstemp('.ini', 'workflow-admin')
        try:
            tmp_fp = os.fdopen(tmp_fd, 'wb')
        except:
            os.close(tmp_fd)
            raise
        else:
            try:
                tmp_fp.write(contents)
            finally:
                tmp_fp.close()
            tmp_conf = Configuration(tmp_file)
        finally:
            os.remove(tmp_file)

        try:
            out['actions'], out['status'] = self._conf_to_inner_format(tmp_conf)
        except configparser.Error as e:
            out['textError'] = [to_unicode(e)]
        else:
            out['lineInfo'] = lineInfo
            out['firstLineInfo'] = firstLineInfo
            out['others'] = others

    def _json_to_inner_format(self, out):
        out['lineInfo'] = {}
        out['firstLineInfo'] = {}
        out['others'] = {}
        if 'actions' not in out:
            return
        count = 1
        for act in out['actions']:
            act['tempName'] = act['action']
            out['firstLineInfo'][act['action']] = count
            for subparam in ('', '.default', '.name', '.operations',
                             '.permissions'):
                out['lineInfo'][act['action'] + subparam] = count
            count += 1

    def _get_permissions(self, req):
        actions = ['All Users']
        actions.extend(sorted(
            PermissionSystem(self.env).get_actions(),
            key=lambda act: (not act.startswith('TICKET_'), act)))
        return actions

    def _create_dot_script(self, params):
        def dot_escape(text):
            return text.replace('\\', '\\\\').replace('"', '\\"')

        script = u'digraph workflow {\n'
        size = self.diagram_size.split(',')
        colors = self.diagram_colors

        script += ' size="%g, %g";\n' % (float(size[0]), float(size[1]))
        node_attrs = ['style=rounded', 'shape=box',
                      'fontsize="%g"' % self.diagram_fontsize]
        if self.diagram_font:
            node_attrs.append('fontname="%s"' % dot_escape(self.diagram_font))
        script += ' node [%s];\n' % ', '.join(node_attrs)
        statusRev = {}
        for idx, stat in enumerate(params['status']):
            script +=  ' node_%d [label="%s"]' % (idx, dot_escape(stat))
            script +=  " {rank = same; node_%d}\n" % idx
            statusRev[stat] = idx
        script += "\n"
        count = 0
        for action in params['actions']:
            next_ = action['next'].strip()
            if next_ == '*':
                continue
            edgeParams = []
            name = action['name'].strip()
            if name == '':
                name = action['tempName']
            edgeParams.append('label="%s"' % dot_escape(name))
            if self.diagram_font:
                edgeParams.append('fontname="%s"' % dot_escape(self.diagram_font))
            edgeParams.append('fontsize="%g"' % self.diagram_fontsize)
            color = colors[count % len(colors)]
            edgeParams.append('color="%s"' % dot_escape(color))
            edgeParams.append('fontcolor="%s"' % dot_escape(color))
            for before in action['before']:
                edgeParams2 = edgeParams[:]
                if before in statusRev and next_ in statusRev:
                    if statusRev[next_] - statusRev[before] == 1:
                        edgeParams2.append('weight=50')
                    script += " node_%d -> node_%d [" % (statusRev[before], statusRev[next_])
                    script += ','.join(edgeParams2)
                    script += '];\n'
            count += 1
        script += '}\n'

        return script.encode('utf-8')

    @property
    def _image_dir(self):
        return os.path.join(self._env_htdocs_dir, 'tracworkflowadmin')

    _old_images_removed = 0
    _old_images_threshold = 86400  # 1 day

    def _image_path_setup(self):
        dir_ = self._image_dir
        if not os.path.isdir(dir_):
            os.mkdir(dir_)

        threshold = self._old_images_threshold
        now = time.time()
        if self._old_images_removed + threshold < now:
            self._old_images_removed = now
            for filename in glob.glob(os.path.join(dir_, '*')):
                try:
                    if os.stat(filename).st_mtime + threshold < now:
                        os.unlink(filename)
                except OSError:
                    pass

    def _image_tmp_path(self, basename):
        return os.path.join(self._image_dir, basename)

    def _image_tmp_url(self, req, basename, timestamp):
        kwargs = {}
        if timestamp is not None:
            kwargs['_'] = str(timestamp)
        return req.href.chrome('site/tracworkflowadmin', basename, **kwargs)

    def _send_json(self, req, data):
        content = json.dumps(data)
        if isinstance(content, unicode):
            content = content.encode('utf-8')
        req.send(content, 'application/json')

    def _update_diagram(self, req, params):
        options, errors = self._validate_workflow(req, params)
        data = {'result': (1, 0)[len(errors) == 0],     # 0 if cond else 1
                'errors': errors}
        if len(errors) == 0:
            script = self._create_dot_script(params)
            self._image_path_setup()
            dir_ = self._image_dir
            basename = '%s.png' % sha1(script).hexdigest()
            path = os.path.join(dir_, basename)
            if not self.diagram_cache or not os.path.isfile(path):
                self._create_diagram_image(path, script, errors)
            timestamp = int(os.path.getmtime(path))
            data['image_url'] = self._image_tmp_url(req, basename, timestamp)

        self._send_json(req, data)
        # NOTREACHED

    _random = Random()

    def _create_diagram_image(self, path, script, errors):
        flags = os.O_CREAT + os.O_WRONLY + os.O_EXCL
        while True:
            tmp = '%s.%08x' % (path, self._random.randint(0, 0xffffffff))
            try:
                fd = os.open(tmp, flags, 0o666)
            except OSError as e:
                if e.errno != errno.EEXIST:
                    raise
                continue
            os.close(fd)
            break
        try:
            args = [self.dot_path, '-Tpng', '-o', tmp]
            try:
                proc = Popen(args, stdin=PIPE)
            except OSError as e:
                message = exception_to_unicode(e)
                self.log.warning('Cannot execute dot: %s: %r', message, args)
                errors.append(_(
                    "The dot command '%(path)s' is not available: %(e)s",
                    path=self.dot_path, e=message))
                os.remove(tmp)
                return
            try:
                proc.stdin.write(script)
            finally:
                proc.stdin.close()
                proc.wait()
        except:
            os.remove(tmp)
            raise
        else:
            try:
                os.rename(tmp, path)
            except OSError:
                os.remove(path)
                os.rename(tmp, path)

    _default_workflow = (
        ('leave', 'new,assigned,accepted,reopened,closed -> *'),
        ('leave.default', '9'),
        ('leave.name', N_("Leave")),
        ('leave.operations', 'leave_status'),
        ('accept', 'new,assigned,reopened -> accepted'),
        ('accept.default', '7'),
        ('accept.name', N_("Accept")),
        ('accept.operations', 'set_owner_to_self'),
        ('accept.permissions', 'TICKET_MODIFY'),
        ('reassign', 'new,accepted,reopened -> assigned'),
        ('reassign.default', '5'),
        ('reassign.name', N_("Reassign")),
        ('reassign.operations', 'set_owner'),
        ('reassign.permissions', 'TICKET_MODIFY'),
        ('reopen', 'closed -> reopened'),
        ('reopen.default', '3'),
        ('reopen.name', N_("Reopen")),
        ('reopen.operations', 'del_resolution'),
        ('reopen.permissions', 'TICKET_CREATE'),
        ('resolve', 'new,assigned,accepted,reopened -> closed'),
        ('resolve.default', '1'),
        ('resolve.name', N_("Resolve")),
        ('resolve.operations', 'set_resolution'),
        ('resolve.permissions', 'TICKET_MODIFY'),
    )

    def _get_default_workflow(self):
        has_init = False
        for name, value in self.config.options('workflow-admin-init'):
            yield name, value
            has_init = True
        if not has_init:
            for name, value in self._default_workflow:
                if name.endswith('.name'):
                    value = gettext(value)
                yield name, value

    def _initialize_workflow(self, req):
        for name, value in self.config.options('ticket-workflow'):
            self.config.remove('ticket-workflow', name)
        for name, value in self._get_default_workflow():
            self.config.set('ticket-workflow', name, value)
        self.config.save()

    def _validate_workflow(self, req, params):
        if 'textError' in params:
            return {}, params['textError']

        errors = []
        if not 'actions' in params:
            errors.append(_("Invalid request without actions. Please restart "
                            "your browser and retry."))
        if len(params['actions']) == 0:
            errors.append(_("Need at least one action."))
        if not 'status' in params:
            errors.append(_("Invalid request without statuses. Please restart "
                            "your browser and retry."))
        if len(params['status']) == 0:
            errors.append(_("Need at least one status."))

        if not errors:
            if not any(act['next'] == '*' and \
                           'leave_status' in act.get('operations', ())
                       for act in params['actions']):
                errors.append(_("The action with operation 'leave_status' and "
                                "next status '*' is certainly required."))
        if errors:
            return {}, errors

        newOptions = {}
        lineInfo = params['lineInfo']
        perms = self._get_permissions(req)
        perms.append('All Users')
        operations = self.operations
        actionNames = []
        for act in params['actions']:
            lineErrors = []
            tempName = act.get('tempName')
            action = act.get('action')
            if tempName not in lineInfo:
                lineErrors.append(_(
                    "Line %(num)d:  The definition of '%(aname)s' is not found.",
                    aname=tempName,
                    num=params['firstLineInfo'][tempName]))
            elif action == '':
                lineErrors.append(_("Line %(num)d: Action cannot be emptied.",
                                    num=lineInfo[tempName]))
            elif not self._action_name_re.match(action):
                lineErrors.append(_(
                    "Line %(num)d: Use alphanumeric, dash, and underscore "
                    "characters in the action name.",
                    num=lineInfo[tempName]))
            elif action in actionNames:
                lineErrors.append(_(
                    "Line %(num)d: Action name is duplicated. The name "
                    "must be unique.",
                    num=lineInfo[tempName]))
            elif not 'next' in act:
                lineErrors.append(_("Line %(num)d: No next status.",
                                    num=lineInfo[tempName]))
            elif not act['next'] in params['status'] and act['next'] != '*':
                lineErrors.append(_(
                    "Line %(num)d: '%(status)s' is invalid next status.",
                    num=lineInfo[tempName], status=act['next']))
            elif not act.get('before'):
                lineErrors.append(_("Line %(num)d: Statuses is empty.",
                                    num=lineInfo[tempName]))
            else:
                for stat in act['before']:
                    if not stat in params['status'] and stat != '*':
                        lineErrors.append(_(
                            "Line %(num)d: Status '%(status)s' is invalid.",
                            num=lineInfo[tempName], status=stat))

            lineErrors.extend(_("Line %(num)d: Unknown operator "
                                "'%(name)s'", name=operation,
                                num=lineInfo[tempName + '.operations'])
                              for operation in act.get('operations', ())
                              if operation not in operations)

            lineErrors.extend(_("Line %(num)d: Unknown permission "
                                "'%(name)s'", name=perm,
                                num=lineInfo[tempName + '.permissions'])
                              for perm in act.get('permissions', ())
                              if not perm in perms)

            if 'default' in act and act['default'] == -1:
                lineErrors.append(_(
                    "Line %(num)d: specify a numerical value to 'default'.",
                    num=lineInfo[tempName + '.default']))

            if len(lineErrors) == 0:
                key = action
                if 'before' in act:
                    tmp = []
                    for stat in params['status']:
                        if stat in act['before']:
                            tmp.append(stat)
                    before = ','.join(tmp)
                else:
                    before = '*'

                newOptions[key] = before + ' -> ' + act['next']
                newOptions[key + '.name'] = act['name']
                newOptions[key + '.default'] = act['default']
                if not 'All Users' in act['permissions']:
                    newOptions[key + '.permissions'] = ','.join(act['permissions'])
                if act.get('operations'):
                    newOptions[key + '.operations'] = ','.join(act['operations'])
                if action in params['others']:
                    for otherKey, otherValue in iteritems(params['others'][action]):
                        newOptions[key + '.' + otherKey] = otherValue
            else:
                errors.extend(lineErrors)
            actionNames.append(action)

        count = 1
        for stat in params['status']:
            if len(stat) == 0:
                errors.append(_("Status column %(num)d: Status name is empty.",
                                num=count))
            elif ';' in stat or '#' in stat:
                errors.append(_(
                    "Status column %(num)d: The characters '#' and ';' "
                    "cannot be used for status name.", num=count))
            if stat in params['status'][:count - 1]:
                errors.append(_(
                    "Status column %(num)d: Status name is duplicated. "
                    "The name must be unique.", num=count))
            count += 1

        return newOptions, errors

    def _update_workflow(self, req, params):
        options, errors = self._validate_workflow(req, params)
        out = {}
        if len(errors) != 0:
            out['result'] = 1
            out['errors'] = errors
        else:
            try:
                for (name, value) in self.config.options('ticket-workflow'):
                    self.config.remove('ticket-workflow', name)
                out['result'] = 0
                for key, val in iteritems(options):
                    if key.endswith('.name') and not val:
                        continue
                    self.config.set('ticket-workflow', key, val)
                self.config.save()
            except Exception as e:
                self.log.error('Exception caught while saving trac.ini%s',
                               exception_to_unicode(e, traceback=True))
                self.config.parse_if_needed(force=True)
                out['result'] = 1
                out['errors'] = [exception_to_unicode(e)]

        self._send_json(req, out)
        # NOTREACHED

    def _parse_request(self, req):
        params = json.loads(req.args.get('params'))
        if not 'mode' in params:
            return
        if 'text' in params:
            self._str_to_inner_format(params['text'], params)
        else:
            self._json_to_inner_format(params)
        mode = params['mode']
        if mode == 'update':
            self._update_workflow(req, params)
            # NOTREACHED
        if mode == 'update-chart':
            self._update_diagram(req, params)
            # NOTREACHED
        if mode == 'init':
            self._initialize_workflow(req)
        elif mode == 'change-textmode':
            req.args['editor_mode'] = 'text'
        elif mode == 'change-guimode':
            req.args['editor_mode'] = 'gui'

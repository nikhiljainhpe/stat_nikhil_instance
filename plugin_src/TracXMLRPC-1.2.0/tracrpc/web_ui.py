# -*- coding: utf-8 -*-
"""
License: BSD

(c) 2005-2008 ::: Alec Thomas (alec@swapoff.org)
(c) 2009      ::: www.CodeResort.com - BV Network AS (simon-code@bvnetwork.no)
"""

import pkg_resources
import types

from trac.core import Component, ExtensionPoint, TracError, implements
from trac.env import IEnvironmentSetupParticipant
from trac.perm import PermissionError
from trac.resource import ResourceNotFound
from trac.util.html import tag
from trac.util.text import exception_to_unicode, to_unicode
from trac.util.translation import dtgettext
from trac.web.api import RequestDone, HTTPUnsupportedMediaType
from trac.web.main import IRequestHandler
from trac.web.chrome import ITemplateProvider, INavigationContributor, \
                            add_stylesheet, add_script, Chrome
from trac.wiki.formatter import format_to_oneliner

from . import __version__
from .api import (XMLRPCSystem, IRPCProtocol, ProtocolException,
                  ServiceException, api_version)
from .util import (accepts_mimetype, to_b, i18n_domain, add_domain, _,
                   web_context)

try:
    from trac.web.api import HTTPInternalError as HTTPInternalServerError
except ImportError:  # Trac 1.3.1+
    from trac.web.api import HTTPInternalServerError


__all__ = ['RPCWeb']

_use_jinja2 = hasattr(Chrome, 'jenv')


class RPCWeb(Component):
    """ Handle RPC calls from HTTP clients, as well as presenting a list of
        methods available to the currently logged in user. Browsing to
        <trac>/rpc or <trac>/login/rpc will display this list. """

    implements(IEnvironmentSetupParticipant, IRequestHandler,
               ITemplateProvider, INavigationContributor)

    protocols = ExtensionPoint(IRPCProtocol)

    def __init__(self):
        try:
            locale_dir = pkg_resources.resource_filename(__name__, 'locale')
        except KeyError:
            pass
        else:
            add_domain(self.env.path, locale_dir)

    # IEnvironmentSetupParticipant methods

    def environment_created(self, *args, **kwargs):
        pass

    def environment_needs_upgrade(self, *args, **kwargs):
        return False

    def upgrade_environment(self, *args, **kwargs):
        pass

    # IRequestHandler methods

    def match_request(self, req):
        """ Look for available protocols serving at requested path and
            content-type. """
        content_type = req.get_header('Content-Type')
        if content_type:
            content_type = content_type.split(';', 1)[0].strip().lower()
        must_handle_request = req.path_info in ('/rpc', '/login/rpc')
        for protocol in self.protocols:
            for p_path, p_type in protocol.rpc_match():
                if req.path_info in ['/%s' % p_path, '/login/%s' % p_path]:
                    must_handle_request = True
                    if content_type == p_type:
                        req.args['protocol'] = protocol
                        return True
        # No protocol call, need to handle for docs or error if handled path
        return must_handle_request

    def process_request(self, req):
        protocol = req.args.get('protocol', None)
        content_type = req.get_header('Content-Type') or ''
        if protocol:
            # Perform the method call
            self.log.debug("RPC incoming request of content type %r "
                           "dispatched to %r", content_type, protocol)
            self._rpc_process(req, protocol, content_type)
        elif accepts_mimetype(req, 'text/html'):
            return self._dump_docs(req)
        else:
            # Attempt at API call gone wrong. Raise a plain-text 415 error
            body = "No protocol matching Content-Type '%s' at path '%s'." % \
                   (content_type, req.path_info)
            self.log.error(body)
            # Close connection without reading request body
            req.send_header('Connection', 'close')
            req.send(to_b(body), 'text/plain', HTTPUnsupportedMediaType.code)

    # Internal methods

    def _dump_docs(self, req):
        self.log.debug("Rendering docs")

        # Dump RPC documentation
        req.perm.require('XML_RPC')  # Need at least XML_RPC
        namespaces = {}
        ctxt = web_context(req)
        for method in XMLRPCSystem(self.env).all_methods(req):
            namespace = method.namespace.replace('.', '_')
            if namespace not in namespaces:
                namespaces[namespace] = {
                    'description': format_to_oneliner(self.env, ctxt,
                                    method.namespace_description),
                    'methods': [],
                    'namespace': method.namespace,
                    }
            try:
                namespaces[namespace]['methods'].append(
                        (method.signature,
                        format_to_oneliner(self.env, ctxt,
                            method.description),
                        method.permission))
            except Exception as e:
                raise Exception('%s: %s%s' % (method.name, e,
                                exception_to_unicode(e, traceback=True)))
        add_stylesheet(req, 'common/css/wiki.css')
        add_stylesheet(req, 'tracrpc/rpc.css')
        add_script(req, 'tracrpc/rpc.js')
        data = {
            'rpc': {
                'functions': namespaces,
                'protocols': [self._rpc_protocol(req, protocol)
                              for protocol in self.protocols],
                'version': __version__,
            },
            'domain': i18n_domain,
        }
        if _use_jinja2:
            data['dtgettext'] = dtgettext
            return 'rpc_jinja.html', data
        else:
            data['tag'] = tag
            return 'rpc.html', data, None

    def _rpc_protocol(self, req, protocol):
        label, desc = protocol.rpc_info()
        desc %= {
            'url_anon': req.abs_href('rpc'),
            'url_auth': req.abs_href('login', 'rpc') \
                        .replace('//', '//%s:your_password@' % req.authname),
            'version': list(api_version),
        }
        return label, desc, list(protocol.rpc_match())

    def _rpc_process(self, req, protocol, content_type):
        """Process incoming RPC request and finalize response."""
        proto_id = protocol.rpc_info()[0]
        rpcreq = req.rpc = {'mimetype': content_type}
        self.log.debug("RPC(%s) call by '%s'", proto_id, req.authname)
        try:
            if req.path_info.startswith('/login/') and \
                    req.authname == 'anonymous':
                raise TracError("Authentication information not available")
            rpcreq = req.rpc = protocol.parse_rpc_request(req, content_type)
            rpcreq['mimetype'] = content_type

            # Important ! Check after parsing RPC request to add
            #             protocol-specific fields in response
            #             (e.g. JSON-RPC response `id`)
            req.perm.require('XML_RPC')  # Need at least XML_RPC

            method_name = rpcreq.get('method')
            if method_name is None:
                raise ProtocolException('Missing method name')
            args = rpcreq.get('params') or []
            self.log.debug("RPC(%s) call by '%s' %s", proto_id,
                           req.authname, method_name)
            try:
                result = (XMLRPCSystem(self.env).get_method(method_name)(req, args))[0]
                if isinstance(result, types.GeneratorType):
                    result = list(result)
            except (TracError, PermissionError, ResourceNotFound):
                raise
            except Exception as e:
                self.log.error("RPC(%s) [%s] Exception caught while calling "
                               "%s(*%r) by %s%s", proto_id, req.remote_addr,
                               method_name, args, req.authname,
                               exception_to_unicode(e, traceback=True))
                raise ServiceException(e)
            else:
                protocol.send_rpc_result(req, result)
        except RequestDone:
            raise
        except (TracError, PermissionError, ResourceNotFound) as e:
            if type(e) is not ServiceException:
                self.log.warning("RPC(%s) [%s] %s", proto_id, req.remote_addr,
                                 exception_to_unicode(e))
            try:
                protocol.send_rpc_error(req, e)
            except RequestDone:
                raise
            except Exception as e:
                self.log.exception("RPC(%s) Unhandled protocol error", proto_id)
                self._send_unknown_error(req, e)
        except Exception as e:
            self.log.exception("RPC(%s) Unhandled protocol error", proto_id)
            self._send_unknown_error(req, e)

    def _send_unknown_error(self, req, e):
        """Last recourse if protocol cannot handle the RPC request | error"""
        method_name = req.rpc and req.rpc.get('method') or '(undefined)'
        body = "Unhandled protocol error calling '%s': %s" % (
                                        method_name, to_unicode(e))
        req.send(to_b(body), 'text/plain', HTTPInternalServerError.code)

    # ITemplateProvider methods

    def get_htdocs_dirs(self):
        yield ('tracrpc', pkg_resources.resource_filename(__name__, 'htdocs'))

    def get_templates_dirs(self):
        yield pkg_resources.resource_filename(__name__, 'templates')

    # INavigationContributor methods

    def get_active_navigation_item(self, req):
        pass

    def get_navigation_items(self, req):
        if req.perm.has_permission('XML_RPC'):
            yield ('metanav', 'rpc',
                   tag.a(_("API"), href=req.href.rpc(), accesskey=1))

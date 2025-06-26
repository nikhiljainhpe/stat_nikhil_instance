# -*- coding: utf-8 -*-
"""
License: BSD

(c) 2005-2008 ::: Alec Thomas (alec@swapoff.org)
(c) 2009      ::: www.CodeResort.com - BV Network AS (simon-code@bvnetwork.no)
"""

import inspect
import io
from datetime import datetime

from trac.attachment import Attachment
from trac.core import Component, TracError, implements
from trac.resource import Resource, ResourceNotFound
from trac.ticket import model, query
from trac.ticket.api import TicketSystem
from trac.ticket.web_ui import TicketModule
from trac.web.chrome import add_warning
from trac.util.datefmt import from_utimestamp, to_datetime, to_utimestamp, utc
from trac.util.html import Element, Fragment, Markup
from trac.util.text import exception_to_unicode, to_unicode

try:
    from trac.notification.api import NotificationSystem
except ImportError:
    from trac.ticket.notification import TicketNotifyEmail
    NotificationSystem = TicketChangeEvent = None
else:
    from trac.ticket.notification import TicketChangeEvent
    TicketNotifyEmail = None

from .api import IXMLRPCHandler, Binary
from .util import iteritems

__all__ = ['TicketRPC']

class TicketRPC(Component):
    """ An interface to Trac's ticketing system. """

    implements(IXMLRPCHandler)

    # IXMLRPCHandler methods
    def xmlrpc_namespace(self):
        return 'ticket'

    def xmlrpc_methods(self):
        yield (None, ((list,), (list, str)), self.query)
        yield (None, ((list, datetime),), self.getRecentChanges)
        yield (None, ((list, int),), self.getAvailableActions)
        yield (None, ((list, int),), self.getActions)
        yield (None, ((list, int),), self.get)
        yield ('TICKET_CREATE', ((int, str, str),
                                 (int, str, str, dict),
                                 (int, str, str, dict, bool),
                                 (int, str, str, dict, bool, datetime)),
                      self.create)
        yield (None, ((list, int, str),
                      (list, int, str, dict),
                      (list, int, str, dict, bool),
                      (list, int, str, dict, bool, str),
                      (list, int, str, dict, bool, str, datetime)),
                      self.update)
        yield (None, ((None, int),), self.delete)
        yield (None, ((dict, int), (dict, int, int)), self.changeLog)
        yield (None, ((list, int),), self.listAttachments)
        yield (None, ((Binary, int, str),), self.getAttachment)
        yield (None,
               ((str, int, str, str, Binary, bool),
                (str, int, str, str, Binary)),
               self.putAttachment)
        yield (None, ((bool, int, str),), self.deleteAttachment)
        yield ('TICKET_VIEW', ((list,),), self.getTicketFields)

    # Exported methods
    def query(self, req, qstr='status!=closed'):
        """
        Perform a ticket query, returning a list of ticket ID's.
        All queries will use stored settings for maximum number of results per
        page and paging options. Use `max=n` to define number of results to
        receive, and use `page=n` to page through larger result sets. Using
        `max=0` will turn off paging and return all results.
        """
        q = query.Query.from_string(self.env, qstr)
        ticket_realm = Resource('ticket')
        out = []
        for t in q.execute(req):
            tid = t['id']
            if 'TICKET_VIEW' in req.perm(ticket_realm(id=tid)):
                out.append(tid)
        return out

    def getRecentChanges(self, req, since):
        """Returns a list of IDs of tickets that have changed since timestamp."""
        since = to_utimestamp(since)
        query = 'SELECT id FROM ticket WHERE changetime >= %s'
        if hasattr(self.env, 'db_query'):
            generator = self.env.db_query(query, (since,))
        else:
            db = self.env.get_db_cnx()
            cursor = db.cursor()
            cursor.execute(query, (since,))
            generator = cursor
        result = []
        ticket_realm = Resource('ticket')
        for row in generator:
            tid = int(row[0])
            if 'TICKET_VIEW' in req.perm(ticket_realm(id=tid)):
                result.append(tid)
        return result

    def getAvailableActions(self, req, id):
        """ Deprecated - will be removed. Replaced by `getActions()`. """
        self.log.warning("Rpc ticket.getAvailableActions is deprecated")
        return [action[0] for action in self.getActions(req, id)]

    def getActions(self, req, id):
        """Returns the actions that can be performed on the ticket as a list of
        `[action, label, hints, [input_fields]]` elements, where `input_fields` is
        a list of `[name, value, [options]]` for any required action inputs."""
        ts = TicketSystem(self.env)
        t = model.Ticket(self.env, id)
        actions = []
        for action in ts.get_available_actions(req, t):
            widgets = Fragment()
            hints = []
            first_label = None
            for controller in ts.action_controllers:
                if action in [c_action for c_weight, c_action \
                                in controller.get_ticket_actions(req, t)]:
                    label, widget, hint = \
                        controller.render_ticket_action_control(req, t, action)
                    widgets.append(widget)
                    hints.append(to_unicode(hint).rstrip('.') + '.')
                    first_label = first_label == None and label or first_label
            controls = self._extract_action_controls(widgets)
            actions.append((action, first_label, " ".join(hints), controls))
        return actions

    def get(self, req, id):
        """ Fetch a ticket. Returns [id, time_created, time_changed, attributes]. """
        t = model.Ticket(self.env, id)
        req.perm(t.resource).require('TICKET_VIEW')
        changetime = t['changetime']
        t['_ts'] = str(to_utimestamp(changetime))
        return (t.id, t['time'], changetime, t.values)

    def create(self, req, summary, description, attributes={}, notify=False, when=None):
        """ Create a new ticket, returning the ticket ID.
        Overriding 'when' requires admin permission. """
        if not summary:
            raise TracError("Tickets must contain a summary.")
        t = model.Ticket(self.env)
        t['summary'] = summary
        t['description'] = description
        t['reporter'] = req.authname
        for k, v in iteritems(attributes):
            t[k] = v
        t['status'] = 'new'
        t['resolution'] = ''
        # custom create timestamp?
        if when and not 'TICKET_ADMIN' in req.perm:
            self.log.warn("RPC ticket.create: %r not allowed to create with "
                          "non-current timestamp (%r)", req.authname, when)
            when = to_datetime(None, utc)
        t.insert(when=when)
        if notify:
            self._notify_created_event(t, when, req.authname)
        return t.id

    def update(self, req, id, comment, attributes={}, notify=False, author='', when=None):
        """ Update a ticket, returning the new ticket in the same form as
        get(). 'New-style' call requires two additional items in attributes:
        (1) 'action' for workflow support (including any supporting fields
        as retrieved by getActions()),
        (2) '_ts' changetime token for detecting update collisions (as received
        from get() or update() calls).
        ''Calling update without 'action' and '_ts' changetime token is
        deprecated, and will raise errors in a future version.'' """
        t = model.Ticket(self.env, id)
        # custom author?
        if author and not (req.authname == 'anonymous' \
                            or 'TICKET_ADMIN' in req.perm(t.resource)):
            # only allow custom author if anonymous is permitted or user is admin
            self.log.warn("RPC ticket.update: %r not allowed to change author "
                          "to %r for comment on #%d", req.authname, author, id)
            author = ''
        author = author or req.authname
        # custom change timestamp?
        if when and not 'TICKET_ADMIN' in req.perm(t.resource):
            self.log.warn("RPC ticket.update: %r not allowed to update #%d "
                          "with non-current timestamp (%r)", author, id, when)
            when = None
        when = when or to_datetime(None, utc)
        # never try to update 'time' and 'changetime' attributes directly
        if 'time' in attributes:
            del attributes['time']
        if 'changetime' in attributes:
            del attributes['changetime']
        ts = TicketSystem(self.env)
        all_fields = set(field['name'] for field in ts.get_ticket_fields())
        # and action...
        if not 'action' in attributes:
            # FIXME: Old, non-restricted update - remove soon!
            self.log.warning("Rpc ticket.update for ticket %d by user %s "
                             "has no workflow 'action'.", id, req.authname)
            req.perm(t.resource).require('TICKET_MODIFY')
            time_changed = attributes.pop('_ts', None)
            if time_changed and \
                    str(time_changed) != str(to_utimestamp(t['changetime'])):
                raise TracError("Ticket has been updated since last get().")
            for k, v in iteritems(attributes):
                if k in all_fields:
                    t[k] = v
            t.save_changes(author, comment, when=when)
        else:
            tm = TicketModule(self.env)
            # TODO: Deprecate update without time_changed timestamp
            time_changed = attributes.pop('_ts',
                                          to_utimestamp(t['changetime']))
            try:
                time_changed = int(time_changed)
            except ValueError:
                raise TracError("RPC ticket.update: Wrong '_ts' token " \
                                "in attributes (%r)." % time_changed)
            action = attributes.get('action')
            avail_actions = ts.get_available_actions(req, t)
            if not action in avail_actions:
                raise TracError("Rpc: Ticket %d by %s " \
                        "invalid action '%s'" % (id, req.authname, action))
            controllers = list(tm._get_action_controllers(req, t, action))
            for k, v in iteritems(attributes):
                if k in all_fields and k != 'status':
                    t[k] = v
            # TicketModule reads req.args - need to move things there...
            req.args.update(attributes)
            req.args['comment'] = comment
            # Collision detection: 0.11+0.12 timestamp
            req.args['ts'] = str(from_utimestamp(time_changed))
            # Collision detection: 0.13/1.0+ timestamp
            req.args['view_time'] = str(time_changed)
            changes, problems = tm.get_ticket_changes(req, t, action)
            for warning in problems:
                add_warning(req, "Rpc ticket.update: %s" % warning)
            valid = problems and False or tm._validate_ticket(req, t)
            if not valid:
                raise TracError(
                    " ".join([warning for warning in req.chrome['warnings']]))
            else:
                tm._apply_ticket_changes(t, changes)
                self.log.debug("Rpc ticket.update save: %r", t.values)
                t.save_changes(author, comment, when=when)
                # Apply workflow side-effects
                for controller in controllers:
                    controller.apply_action_side_effects(req, t, action)
        if notify:
            self._notify_changed_event(t, when, author, comment)
        return self.get(req, t.id)

    def delete(self, req, id):
        """ Delete ticket with the given id. """
        t = model.Ticket(self.env, id)
        req.perm(t.resource).require('TICKET_ADMIN')
        t.delete()

    def changeLog(self, req, id, when=0):
        t = model.Ticket(self.env, id)
        req.perm(t.resource).require('TICKET_VIEW')
        for date, author, field, old, new, permanent in t.get_changelog(when):
            yield (date, author, field, old, new, permanent)
    # Use existing documentation from Ticket model
    changeLog.__doc__ = inspect.getdoc(model.Ticket.get_changelog)

    def listAttachments(self, req, ticket):
        """ Lists attachments for a given ticket. Returns (filename,
        description, size, time, author) for each attachment."""
        for a in Attachment.select(self.env, 'ticket', ticket):
            if 'ATTACHMENT_VIEW' in req.perm(a.resource):
                yield (a.filename, a.description, a.size, a.date, a.author)

    def getAttachment(self, req, ticket, filename):
        """ returns the content of an attachment. """
        attachment = Attachment(self.env, 'ticket', ticket, filename)
        req.perm(attachment.resource).require('ATTACHMENT_VIEW')
        return Binary(attachment.open().read())

    def putAttachment(self, req, ticket, filename, description, data, replace=True):
        """ Add an attachment, optionally (and defaulting to) overwriting an
        existing one. Returns filename."""
        if not model.Ticket(self.env, ticket).exists:
            raise ResourceNotFound('Ticket "%s" does not exist' % ticket)
        if replace:
            try:
                attachment = Attachment(self.env, 'ticket', ticket, filename)
                req.perm(attachment.resource).require('ATTACHMENT_DELETE')
                attachment.delete()
            except TracError:
                pass
        attachment = Attachment(self.env, 'ticket', ticket)
        req.perm(attachment.resource).require('ATTACHMENT_CREATE')
        attachment.author = req.authname
        attachment.description = description
        attachment.insert(filename, io.BytesIO(data.data), len(data.data))
        return attachment.filename

    def deleteAttachment(self, req, ticket, filename):
        """ Delete an attachment. """
        if not model.Ticket(self.env, ticket).exists:
            raise ResourceNotFound('Ticket "%s" does not exists' % ticket)
        attachment = Attachment(self.env, 'ticket', ticket, filename)
        req.perm(attachment.resource).require('ATTACHMENT_DELETE')
        attachment.delete()
        return True

    def getTicketFields(self, req):
        """ Return a list of all ticket fields fields. """
        return TicketSystem(self.env).get_ticket_fields()

    # Internal methods

    def _extract_action_controls(self, widgets):

        def unescape(value):
            if isinstance(value, Markup):
                return value.unescape()
            return value

        def walk(fragment, controls):
            for child in fragment.children:
                if isinstance(child, Element):
                    tag = child.tag
                    if tag == 'input':
                        attrib = child.attrib
                        controls.append((unescape(attrib.get('name')),
                                         unescape(attrib.get('value')), []))
                    elif tag == 'select':
                        selected = ''
                        options = []
                        for opt in child.children:
                            if opt.tag != 'option':
                                continue
                            if 'value' in opt.attrib:
                                option = unescape(opt.attrib.get('value'))
                            else:
                                option = ''.join(map(unescape, opt.children))
                            options.append(option)
                            if 'selected' in opt.attrib:
                                selected = option
                        controls.append((unescape(child.attrib.get('name')),
                                         selected, options))
                    continue
                if isinstance(child, Fragment):
                    walk(child, controls)
                    continue
            return controls

        return walk(widgets, [])

    def _notify_created_event(self, ticket, when, author):
        try:
            self._notify_event(ticket, when, author, True, None)
        except Exception as e:
            self.log.warning("Failure sending notification on creation of "
                             "ticket #%s: %s",
                             ticket.id, exception_to_unicode(e))

    def _notify_changed_event(self, ticket, when, author, comment):
        try:
            self._notify_event(ticket, when, author, False, comment)
        except Exception as e:
            self.log.warning("Failure sending notification on changed of "
                             "ticket #%s: %s",
                             ticket.id, exception_to_unicode(e))

    if NotificationSystem:
        def _notify_event(self, ticket, when, author, newticket, comment):
            if newticket:
                event = TicketChangeEvent('created', ticket, when, author)
            else:
                event = TicketChangeEvent('changed', ticket, when, author,
                                          comment)
            NotificationSystem(self.env).notify(event)

    else:
        def _notify_event(self, ticket, when, author, newticket, comment):
            tn = TicketNotifyEmail(self.env)
            tn.notify(ticket, newticket=newticket, modtime=when)


class StatusRPC(Component):
    """ An interface to Trac ticket status objects.
    Note: Status is defined by workflow, and all methods except `getAll()`
    are deprecated no-op methods - these will be removed later. """

    implements(IXMLRPCHandler)

    # IXMLRPCHandler methods
    def xmlrpc_namespace(self):
        return 'ticket.status'

    def xmlrpc_methods(self):
        yield ('TICKET_VIEW', ((list,),), self.getAll)
        yield ('TICKET_VIEW', ((dict, str),), self.get)
        yield ('TICKET_ADMIN', ((None, str,),), self.delete)
        yield ('TICKET_ADMIN', ((None, str, dict),), self.create)
        yield ('TICKET_ADMIN', ((None, str, dict),), self.update)

    def getAll(self, req):
        """ Returns all ticket states described by active workflow. """
        return TicketSystem(self.env).get_all_status()

    def get(self, req, name):
        """ Deprecated no-op method. Do not use. """
        # FIXME: Remove
        return '0'

    def delete(self, req, name):
        """ Deprecated no-op method. Do not use. """
        # FIXME: Remove
        return 0

    def create(self, req, name, attributes):
        """ Deprecated no-op method. Do not use. """
        # FIXME: Remove
        return 0

    def update(self, req, name, attributes):
        """ Deprecated no-op method. Do not use. """
        # FIXME: Remove
        return 0


def ticketModelFactory(cls, cls_attributes):
    """ Return a class which exports an interface to trac.ticket.model.<cls>. """
    class TicketModelImpl(Component):
        implements(IXMLRPCHandler)

        def xmlrpc_namespace(self):
            return 'ticket.' + cls.__name__.lower()

        def xmlrpc_methods(self):
            yield ('TICKET_VIEW', ((list,),), self.getAll)
            yield ('TICKET_VIEW', ((dict, str),), self.get)
            yield ('TICKET_ADMIN', ((None, str,),), self.delete)
            yield ('TICKET_ADMIN', ((None, str, dict),), self.create)
            yield ('TICKET_ADMIN', ((None, str, dict),), self.update)

        def getAll(self, req):
            for i in cls.select(self.env):
                yield i.name
        getAll.__doc__ = """ Get a list of all ticket %s names. """ % cls.__name__.lower()

        def get(self, req, name):
            i = cls(self.env, name)
            attributes= {}
            for k, default in iteritems(cls_attributes):
                v = getattr(i, k)
                if v is None:
                    v = default
                attributes[k] = v
            return attributes
        get.__doc__ = """ Get a ticket %s. """ % cls.__name__.lower()

        def delete(self, req, name):
            cls(self.env, name).delete()
        delete.__doc__ = """ Delete a ticket %s """ % cls.__name__.lower()

        def create(self, req, name, attributes):
            i = cls(self.env)
            i.name = name
            for k, v in iteritems(attributes):
                setattr(i, k, v)
            i.insert()
        create.__doc__ = """ Create a new ticket %s with the given attributes. """ % cls.__name__.lower()

        def update(self, req, name, attributes):
            self._updateHelper(name, attributes).update()
        update.__doc__ = """ Update ticket %s with the given attributes. """ % cls.__name__.lower()

        def _updateHelper(self, name, attributes):
            i = cls(self.env, name)
            for k, v in iteritems(attributes):
                setattr(i, k, v)
            return i
    TicketModelImpl.__doc__ = """ Interface to ticket %s objects. """ % cls.__name__.lower()
    TicketModelImpl.__name__ = '%sRPC' % cls.__name__
    return TicketModelImpl


def ticketEnumFactory(cls):
    """ Return a class which exports an interface to one of the Trac ticket abstract enum types. """
    class AbstractEnumImpl(Component):
        implements(IXMLRPCHandler)

        def xmlrpc_namespace(self):
            return 'ticket.' + cls.__name__.lower()

        def xmlrpc_methods(self):
            yield ('TICKET_VIEW', ((list,),), self.getAll)
            yield ('TICKET_VIEW', ((str, str),), self.get)
            yield ('TICKET_ADMIN', ((None, str,),), self.delete)
            yield ('TICKET_ADMIN', ((None, str, str),), self.create)
            yield ('TICKET_ADMIN', ((None, str, str),), self.update)

        def getAll(self, req):
            for i in cls.select(self.env):
                yield i.name
        getAll.__doc__ = """ Get a list of all ticket %s names. """ % cls.__name__.lower()

        def get(self, req, name):
            if (cls.__name__ == 'Status'):
               i = cls(self.env)
               x = name
            else:
               i = cls(self.env, name)
               x = i.value
            return x
        get.__doc__ = """ Get a ticket %s. """ % cls.__name__.lower()

        def delete(self, req, name):
            cls(self.env, name).delete()
        delete.__doc__ = """ Delete a ticket %s """ % cls.__name__.lower()

        def create(self, req, name, value):
            i = cls(self.env)
            i.name = name
            i.value = value
            i.insert()
        create.__doc__ = """ Create a new ticket %s with the given value. """ % cls.__name__.lower()

        def update(self, req, name, value):
            self._updateHelper(name, value).update()
        update.__doc__ = """ Update ticket %s with the given value. """ % cls.__name__.lower()

        def _updateHelper(self, name, value):
            i = cls(self.env, name)
            i.value = value
            return i

    AbstractEnumImpl.__doc__ = """ Interface to ticket %s. """ % cls.__name__.lower()
    AbstractEnumImpl.__name__ = '%sRPC' % cls.__name__
    return AbstractEnumImpl


ticketModelFactory(model.Component, {'name': '', 'owner': '', 'description': ''})
ticketModelFactory(model.Version, {'name': '', 'time': 0, 'description': ''})
ticketModelFactory(model.Milestone, {'name': '', 'due': 0, 'completed': 0, 'description': ''})

ticketEnumFactory(model.Type)
ticketEnumFactory(model.Resolution)
ticketEnumFactory(model.Priority)
ticketEnumFactory(model.Severity)

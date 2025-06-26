# -*- coding: utf-8 -*-
"""
License: BSD

(c) 2009-2013 ::: www.CodeResort.com - BV Network AS (simon-code@bvnetwork.no)
"""

import datetime
import time
import unittest

from trac.util.datefmt import to_datetime, to_utimestamp, utc

from ..util import unicode, xmlrpclib
from ..xml_rpc import from_xmlrpc_datetime, to_xmlrpc_datetime
from . import (Request, TracRpcTestCase, TracRpcTestSuite, b64encode, urlopen,
               makeSuite)


class RpcTicketTestCase(TracRpcTestCase):

    def setUp(self):
        TracRpcTestCase.setUp(self)
        self.anon = xmlrpclib.ServerProxy(self._testenv.url_anon)
        self.user = xmlrpclib.ServerProxy(self._testenv.url_user)
        self.admin = xmlrpclib.ServerProxy(self._testenv.url_admin)

    def tearDown(self):
        for proxy in (self.anon, self.user, self.admin):
            proxy('close')()
        TracRpcTestCase.tearDown(self)

    def test_create_get_delete(self):
        tid = self.admin.ticket.create("create_get_delete", "fooy", {})
        tid, time_created, time_changed, attributes = self.admin.ticket.get(tid)
        self.assertEqual('fooy', attributes['description'])
        self.assertEqual('create_get_delete', attributes['summary'])
        self.assertEqual('new', attributes['status'])
        self.assertEqual('admin', attributes['reporter'])
        self.admin.ticket.delete(tid)

    def test_create_empty_summary(self):
        try:
            self.admin.ticket.create("", "the description", {})
            self.fail("Exception not raised creating ticket with empty summary")
        except xmlrpclib.Fault as e:
            self.assertIn("Tickets must contain a summary.", unicode(e))

    def test_getActions(self):
        tid = self.admin.ticket.create("ticket_getActions", "kjsald",
                                        {'owner': ''})
        try:
            actions = self.admin.ticket.getActions(tid)
        finally:
            self.admin.ticket.delete(tid)
        default = [['leave', 'leave', '.', []], ['resolve', 'resolve',
                    "The resolution will be set. Next status will be 'closed'.",
                   [['action_resolve_resolve_resolution', 'fixed',
                  ['fixed', 'invalid', 'wontfix', 'duplicate', 'worksforme']]]],
                  ['reassign', 'reassign',
                  "The owner will change from (none). Next status will be 'assigned'.",
                  [['action_reassign_reassign_owner', 'admin', []]]],
                  ['accept', 'accept',
                  "The owner will change from (none) to admin. Next status will be 'accepted'.", []]]
        # Adjust for trac:changeset:9041
        if 'will be changed' in actions[2][2]:
            default[2][2] = default[2][2].replace('will change', 'will be changed')
            default[3][2] = default[3][2].replace('will change', 'will be changed')
        # Adjust for trac:changeset:11777
        if not 'from (none).' in actions[2][2]:
            default[2][2] = default[2][2].replace('from (none).',
                    'from (none) to the specified user.')
        # Adjust for trac:changeset:11778
        if actions[0][2] != '.':
            default[0][2] = 'The ticket will remain with no owner.'
        # Adjust for trac:changeset:13203 and trac:changeset:14393
        if '<span class=' in actions[2][2]:
            default[2][2] = default[2][2].replace(' (none)',
                    ' <span class="trac-author-none">(none)</span>')
            default[3][2] = default[3][2].replace(' (none)',
                    ' <span class="trac-author-none">(none)</span>')
            default[3][2] = default[3][2].replace(' admin',
                    ' <span class="trac-author-user">admin</span>')
        self.assertEqual(actions, default)

    # From sample-plugins/workflow/DeleteTicket.py in Trac source
    _delete_ticket_action_controller = r"""# -*- coding: utf-8 -*-
from trac.core import Component, implements
from trac.perm import IPermissionRequestor
from trac.ticket.api import ITicketActionController
class DeleteTicketActionController(Component):
    implements(IPermissionRequestor, ITicketActionController)
    def get_permission_actions(self):
        return ['TICKET_DELETE']
    def get_ticket_actions(self, req, ticket):
        actions = []
        if ticket.exists and 'TICKET_DELETE' in req.perm(ticket.resource):
            actions.append((0, 'delete'))
        return actions
    def get_all_status(self):
        return []
    def render_ticket_action_control(self, req, ticket, action):
        return 'delete', None, "The ticket will be deleted."
    def get_ticket_changes(self, req, ticket, action):
        return {}
    def apply_action_side_effects(self, req, ticket, action):
        if action == 'delete':
            ticket.delete()
"""

    def test_getAvailableActions_DeleteTicket(self):
        # http://trac-hacks.org/ticket/5387
        tktapi = self.admin.ticket
        env = self._testenv.get_trac_environment()
        tid = tktapi.create('abc', 'def', {})
        try:
            self.assertNotIn('delete', tktapi.getAvailableActions(tid))
            env.config.set('ticket', 'workflow',
                'ConfigurableTicketWorkflow,DeleteTicketActionController')
            env.config.save()
            with self._plugin(self._delete_ticket_action_controller,
                              'DeleteTicket.py'):
                self.assertIn('delete', tktapi.getAvailableActions(tid))
        finally:
            env.config.set('ticket', 'workflow', 'ConfigurableTicketWorkflow')
            env.config.save()
            self.assertEqual(0, tktapi.delete(tid))

    def test_FineGrainedSecurity(self):
        self.assertEqual(1, self.admin.ticket.create('abc', '123', {}))
        self.assertEqual(2, self.admin.ticket.create('def', '456', {}))
        # First some non-restricted tests for comparison:
        self.assertRaises(xmlrpclib.Fault, self.anon.ticket.create, 'abc', 'def')
        self.assertEqual([1,2], self.user.ticket.query())
        self.assertTrue(self.user.ticket.get(2))
        self.assertTrue(self.user.ticket.update(1, "ok"))
        self.assertTrue(self.user.ticket.update(2, "ok"))
        # Enable security policy and test
        source = r"""# -*- coding: utf-8 -*-
from trac.core import Component, implements
from trac.perm import IPermissionPolicy
class TicketPolicy(Component):
    implements(IPermissionPolicy)
    def check_permission(self, action, username, resource, perm):
        if username == 'user' and resource and resource.id == 2:
            return False
        if username == 'anonymous' and action == 'TICKET_CREATE':
            return True
"""
        env = self._testenv.get_trac_environment()
        _old_conf = env.config.get('trac', 'permission_policies')
        env.config.set('trac', 'permission_policies',
                       'TicketPolicy,' + _old_conf)
        env.config.save()
        try:
            with self._plugin(source, 'TicketPolicy.py'):
                self._testenv.restart()
                self.assertEqual([1], self.user.ticket.query())
                self.assertTrue(self.user.ticket.get(1))
                self.assertRaises(xmlrpclib.Fault, self.user.ticket.get, 2)
                self.assertTrue(self.user.ticket.update(1, "ok"))
                self.assertRaises(xmlrpclib.Fault, self.user.ticket.update, 2,
                                  "not ok")
                self.assertEqual(3, self.anon.ticket.create('efg', '789', {}))
        finally:
            # Clean, reset and simple verification
            env.config.set('trac', 'permission_policies', _old_conf)
            env.config.save()

        self.assertEqual([1,2,3], self.user.ticket.query())
        self.assertEqual(0, self.admin.ticket.delete(1))
        self.assertEqual(0, self.admin.ticket.delete(2))
        self.assertEqual(0, self.admin.ticket.delete(3))

    def test_getRecentChanges(self):
        tid1 = self.admin.ticket.create("ticket_getRecentChanges", "one", {})
        time.sleep(1)
        tid2 = self.admin.ticket.create("ticket_getRecentChanges", "two", {})
        try:
            _id, created, modified, attributes = self.admin.ticket.get(tid2)
            changes = self.admin.ticket.getRecentChanges(created)
            self.assertEqual(changes, [tid2])
        finally:
            self.admin.ticket.delete(tid1)
            self.admin.ticket.delete(tid2)

    def test_query_group_order_col(self):
        t1 = self.admin.ticket.create("1", "",
                        {'type': 'enhancement', 'owner': 'A'})
        t2 = self.admin.ticket.create("2", "", {'type': 'task', 'owner': 'B'})
        t3 = self.admin.ticket.create("3", "", {'type': 'defect', 'owner': 'A'})
        # order
        self.assertEqual([3,1,2], self.admin.ticket.query("order=type"))
        self.assertEqual([1,3,2], self.admin.ticket.query("order=owner"))
        self.assertEqual([2,1,3],
                        self.admin.ticket.query("order=owner&desc=1"))
        # group
        self.assertEqual([1,3,2], self.admin.ticket.query("group=owner"))
        self.assertEqual([2,1,3],
                        self.admin.ticket.query("group=owner&groupdesc=1"))
        # group + order
        self.assertEqual([2,3,1],
                self.admin.ticket.query("group=owner&groupdesc=1&order=type"))
        # col should just be ignored
        self.assertEqual([3,1,2],
                self.admin.ticket.query("order=type&col=status&col=reporter"))
        # clean
        self.assertEqual(0, self.admin.ticket.delete(t1))
        self.assertEqual(0, self.admin.ticket.delete(t2))
        self.assertEqual(0, self.admin.ticket.delete(t3))

    def test_query_special_character_escape(self):
        summary = ["here&now", "maybe|later", r"back\slash"]
        search = [r"here\&now", r"maybe\|later", r"back\slash"]
        tids = []
        for s in summary:
            tids.append(self.admin.ticket.create(s,
                            "test_special_character_escape", {}))
        try:
            for i in range(0, 3):
                self.assertEqual([tids[i]],
                    self.admin.ticket.query("summary=%s" % search[i]))
            self.assertEqual(tids.sort(),
                    self.admin.ticket.query("summary=%s" % "|".join(search)).sort())
        finally:
            for tid in tids:
                self.admin.ticket.delete(tid)

    def test_update_author(self):
        tid = self.admin.ticket.create("ticket_update_author", "one", {})
        self.admin.ticket.update(tid, 'comment1', {})
        time.sleep(1)
        self.admin.ticket.update(tid, 'comment2', {}, False, 'foo')
        time.sleep(1)
        self.user.ticket.update(tid, 'comment3', {}, False, 'should_be_rejected')
        changes = self.admin.ticket.changeLog(tid)
        self.assertEqual(3, len(changes))
        for when, who, what, cnum, comment, _tid in changes:
            self.assertIn(comment, ('comment1', 'comment2', 'comment3'))
            if comment == 'comment1':
                self.assertEqual('admin', who)
            if comment == 'comment2':
                self.assertEqual('foo', who)
            if comment == 'comment3':
                self.assertEqual('user', who)
        self.admin.ticket.delete(tid)

    def test_create_at_time(self):
        now = to_datetime(None, utc)
        minus1 = to_xmlrpc_datetime(now - datetime.timedelta(days=1))
        # create the tickets (user ticket will not be permitted to change time)
        one = self.admin.ticket.create("create_at_time1", "ok", {}, False,
                                        minus1)
        two = self.user.ticket.create("create_at_time3", "ok", {}, False,
                                        minus1)
        # get the tickets
        t1 = self.admin.ticket.get(one)
        t2 = self.admin.ticket.get(two)
        # check timestamps
        self.assertTrue(t1[1] < t2[1])
        self.admin.ticket.delete(one)
        self.admin.ticket.delete(two)

    def test_update_at_time(self):
        now = to_datetime(None, utc)
        minus1 = to_xmlrpc_datetime(now - datetime.timedelta(hours=1))
        minus2 = to_xmlrpc_datetime(now - datetime.timedelta(hours=2))
        tid = self.admin.ticket.create("ticket_update_at_time", "ok", {})
        self.admin.ticket.update(tid, 'one', {}, False, '', minus2)
        self.admin.ticket.update(tid, 'two', {}, False, '', minus1)
        self.user.ticket.update(tid, 'three', {}, False, '', minus1)
        time.sleep(1)
        self.user.ticket.update(tid, 'four', {})
        changes = self.admin.ticket.changeLog(tid)
        self.assertEqual(4, len(changes))
        # quick test to make sure each is older than previous
        self.assertTrue(changes[0][0] < changes[1][0] < changes[2][0])
        # margin of 2 seconds for tests
        justnow = to_xmlrpc_datetime(now - datetime.timedelta(seconds=1))
        self.assertTrue(justnow <= changes[2][0])
        self.assertTrue(justnow <= changes[3][0])
        self.admin.ticket.delete(tid)

    def test_update_non_existing(self):
        try:
            self.admin.ticket.update(3344, "a comment", {})
            self.fail("Allowed to update non-existing ticket???")
            self.admin.ticket.delete(3234)
        except Exception as e:
            self.assertIn("Ticket 3344 does not exist.", str(e))

    def test_update_basic(self):
        # Basic update check, no 'action' or 'time_changed'
        tid = self.admin.ticket.create('test_update_basic1', 'ieidnsj', {
                        'owner': 'osimons'})
        # old-style (deprecated)
        self.admin.ticket.update(tid, "comment1", {'component': 'component2'})
        self.assertEqual(2, len(self.admin.ticket.changeLog(tid)))
        # new-style with 'action'
        time.sleep(1)  # avoid "columns ticket, time, field are not unique"
        self.admin.ticket.update(tid, "comment2", {'component': 'component1',
                                                   'action': 'leave'})
        self.assertEqual(4, len(self.admin.ticket.changeLog(tid)))
        self.admin.ticket.delete(tid)

    def test_update_time_changed(self):
        # Update with collision check
        tid = self.admin.ticket.create('test_update_time_changed', '...', {})
        tid, created, modified, attrs = self.admin.ticket.get(tid)
        then = from_xmlrpc_datetime(modified) - datetime.timedelta(minutes=1)
        # Unrestricted old-style update (to be removed soon)
        try:
            self.admin.ticket.update(tid, "comment1",
                    {'_ts': str(to_utimestamp(then))})
        except Exception as e:
            self.assertIn("Ticket has been updated since last get", str(e))
        # Update with 'action' to test new-style update.
        try:
            self.admin.ticket.update(tid, "comment1",
                    {'_ts': str(to_utimestamp(then)),
                     'action': 'leave'})
        except Exception as e:
            self.assertTrue("Your changes have not been saved" in str(e) or
                            "modified by someone else" in str(e), str(e))
        self.admin.ticket.delete(tid)

    def test_update_time_same(self):
        # Unrestricted old-style update (to be removed soon)
        tid = self.admin.ticket.create('test_update_time_same', '...', {})
        tid, created, modified, attrs = self.admin.ticket.get(tid)
        ts = attrs['_ts']
        self.admin.ticket.update(tid, "comment1",
                    {'_ts': ts})
        self.admin.ticket.delete(tid)

        # Update with 'action' to test new-style update.
        tid = self.admin.ticket.create('test_update_time_same', '...', {})
        tid, created, modified, attrs = self.admin.ticket.get(tid)
        ts = attrs['_ts']
        self.admin.ticket.update(tid, "comment1",
                    {'_ts': ts, 'action': 'leave'})
        self.admin.ticket.delete(tid)

    def test_update_action(self):
        # Updating with 'action' in attributes
        tid = self.admin.ticket.create('test_update_action', 'ss',
                                       {'owner': ''})
        current = self.admin.ticket.get(tid)
        self.assertEqual('', current[3].get('owner', ''))
        updated = self.admin.ticket.update(tid, "comment1",
                {'action': 'reassign',
                 'action_reassign_reassign_owner': 'user'})
        self.assertEqual('user', updated[3].get('owner'))
        self.admin.ticket.delete(tid)

    def test_update_action_non_existing(self):
        # Updating with non-existing 'action' in attributes
        tid = self.admin.ticket.create('test_update_action_wrong', 'ss')
        try:
            self.admin.ticket.update(tid, "comment1",
                {'action': 'reassign',
                 'action_reassign_reassign_owner': 'user'})
        except Exception as e:
            self.assertIn("invalid action", str(e))
        self.admin.ticket.delete(tid)

    def test_update_field_non_existing(self):
        tid = self.admin.ticket.create('test_update_field_non_existing', 'yw3')
        rv = self.admin.ticket.get(tid)
        self.assertEqual('defect', rv[3]['type'])
        rv = self.admin.ticket.update(tid, "comment1",
            {'does_not_exist': 'eiwrjoer', 'type': 'enhancement'})
        self.assertEqual('enhancement', rv[3]['type'])
        self.assertFalse('does_not_exist' in rv[3])
        rv = self.admin.ticket.update(tid, "comment2",
            {'action': 'leave', 'does_not_exist': 'eiwrjoer', 'type': 'task'})
        self.assertEqual('task', rv[3]['type'])
        self.assertFalse('does_not_exist' in rv[3])
        self.admin.ticket.delete(tid)

    def test_create_ticket_9096(self):
        # See http://trac-hacks.org/ticket/9096
        body = (b'<?xml version="1.0"?>\n'
                b'<methodCall>\n'
                b'    <methodName>ticket.create</methodName>\n'
                b'    <params>\n'
                b'        <param><string>test summary</string></param>\n'
                b'        <param><string>test desc</string></param>\n'
                b'    </params>\n'
                b'</methodCall>')
        request = Request(self._testenv.url_auth, data=body)
        request.add_header('Content-Type', 'application/xml')
        request.add_header('Content-Length', str(len(body)))
        request.add_header('Authorization',
                           'Basic %s' % b64encode('admin:admin'))
        self.assertEqual('POST', request.get_method())
        response = urlopen(request)
        self.assertEqual(200, response.code)
        self.assertEqual(b"<?xml version='1.0'?>\n"
                         b"<methodResponse>\n"
                         b"<params>\n"
                         b"<param>\n"
                         b"<value><int>1</int></value>\n"
                         b"</param>\n"
                         b"</params>\n"
                         b"</methodResponse>\n", response.read())
        self.admin.ticket.delete(1)

    def test_update_ticket_12430(self):
        # What if ticket 'time' and 'changetime' are part of attributes?
        # See https://trac-hacks.org/ticket/12430
        tid1 = self.admin.ticket.create('test_update_ticket_12430', 'ok?', {
                        'owner': 'osimons1'})
        try:
            # Get a fresh full copy
            tid2, created, changed, values = self.admin.ticket.get(tid1)
            self.assertIn('time', values, "'time' field not returned?")
            self.assertIn('changetime', values,
                            "'changetime' field not returned?")
            self.assertIn('_ts', values, "No _ts in values?")
            # Update
            values['action'] = 'leave'
            values['owner'] = 'osimons2'
            self.admin.ticket.update(tid2, "updating", values)
        finally:
            self.admin.ticket.delete(tid1)


class RpcTicketVersionTestCase(TracRpcTestCase):

    def setUp(self):
        TracRpcTestCase.setUp(self)
        self.anon = xmlrpclib.ServerProxy(self._testenv.url_anon)
        self.user = xmlrpclib.ServerProxy(self._testenv.url_user)
        self.admin = xmlrpclib.ServerProxy(self._testenv.url_admin)

    def tearDown(self):
        for proxy in (self.anon, self.user, self.admin):
            proxy('close')()
        TracRpcTestCase.tearDown(self)

    def test_create(self):
        dt = to_xmlrpc_datetime(to_datetime(None, utc))
        desc = "test version"
        self.admin.ticket.version.create(
            '9.99', {'time': dt, 'description': desc})
        self.assertIn('9.99', self.admin.ticket.version.getAll())
        self.assertEqual({'time': dt, 'description': desc, 'name': '9.99'},
                           self.admin.ticket.version.get('9.99'))


class RpcTicketTypeTestCase(TracRpcTestCase):

    def setUp(self):
        TracRpcTestCase.setUp(self)
        self.anon = xmlrpclib.ServerProxy(self._testenv.url_anon)
        self.user = xmlrpclib.ServerProxy(self._testenv.url_user)
        self.admin = xmlrpclib.ServerProxy(self._testenv.url_admin)

    def tearDown(self):
        for proxy in (self.anon, self.user, self.admin):
            proxy('close')()
        TracRpcTestCase.tearDown(self)

    def test_getall_default(self):
        self.assertEqual(['defect', 'enhancement', 'task'],
                sorted(self.anon.ticket.type.getAll()))
        self.assertEqual(['defect', 'enhancement', 'task'],
                sorted(self.admin.ticket.type.getAll()))


def test_suite():
    suite = TracRpcTestSuite()
    suite.addTest(makeSuite(RpcTicketTestCase))
    suite.addTest(makeSuite(RpcTicketVersionTestCase))
    suite.addTest(makeSuite(RpcTicketTypeTestCase))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

# -*- coding: utf-8 -*-
"""
License: BSD

(c) 2009      ::: www.CodeResort.com - BV Network AS (simon-code@bvnetwork.no)
"""

from datetime import datetime
import base64
import codecs
import io
import json
import pkg_resources
import sys
import unittest

from trac.test import EnvironmentStub
from trac.util.datefmt import FixedOffset, timezone, utc

from ..util import to_b, unicode
from ..json_rpc import TracRpcJSONDecoder, TracRpcJSONEncoder, json_load
from . import (MockRequest, Request, TracRpcTestCase, TracRpcTestSuite,
               b64encode, urlopen, makeSuite)


class JsonTestCase(TracRpcTestCase):

    def _anon_req(self, data):
        req = Request(self._testenv.url_anon, data=json_data(data),
                      headers={'Content-Type': 'application/json'})
        resp = urlopen(req)
        return _raw_json_load(resp)

    def _auth_req(self, data, user='user'):
        url = self._testenv.url_auth
        req = Request(url, data=json_data(data),
                      headers={'Content-Type': 'application/json'})
        opener = self._opener_auth(url, user, user)
        resp = opener.open(req)
        return _raw_json_load(resp)

    def setUp(self):
        TracRpcTestCase.setUp(self)

    def tearDown(self):
        TracRpcTestCase.tearDown(self)

    def test_jsonclass(self):
        image = pkg_resources.resource_string('trac', 'htdocs/feed.png')
        data = to_b(json.dumps({
            'id': 42,
            'method': 'system.getAPIVersion',
            'params': [
                1234,
                0.125,
                {'__jsonclass__': ['datetime', '2023-03-01T16:07:59']},
                {'__jsonclass__': ['binary', b64encode(image)]},
            ],
        }))
        body = io.BytesIO(data)
        env = EnvironmentStub()
        req = MockRequest(env)
        req.environ['CONTENT_LENGTH'] = str(len(data))
        req.environ['wsgi.input'] = body
        decoded = json_load(req)
        self.assertEqual(42, decoded['id'])
        self.assertEqual('system.getAPIVersion', decoded['method'])
        params = decoded['params']
        self.assertEqual(1234, params[0])
        self.assertEqual(0.125, params[1])
        self.assertEqual(datetime(2023, 3, 1, 16, 7, 59, tzinfo=utc),
                         params[2])
        self.assertEqual(image, params[3])
        self.assertEqual(4, len(params))

    def test_parse_datetime(self):
        def test(expected, value):
            actual = TracRpcJSONDecoder._parse_datetime(value)
            self.assertEqual(expected, actual)
            self.assertEqual(expected.tzinfo.utcoffset(None),
                             actual.tzinfo.utcoffset(None))

        gmt09 = FixedOffset(540, 'GMT +9:00')
        gmt0845 = FixedOffset(525, 'GMT +8:45')

        test(datetime(2023, 3, 6, 0, 0, 0, 0, utc), '2023-03-06')
        test(datetime(2023, 3, 6, 8, 41, 32, 0, utc), '2023-03-06T08:41:32Z')
        test(datetime(2023, 3, 6, 8, 41, 32, 700000, utc),
                      '2023-03-06T08:41:32.7Z')
        test(datetime(2023, 3, 6, 8, 41, 32, 730000, utc),
                      '2023-03-06T08:41:32.73Z')
        test(datetime(2023, 3, 6, 8, 41, 32, 737000, utc),
                      '2023-03-06T08:41:32.737Z')
        test(datetime(2023, 3, 6, 8, 41, 32, 737368, utc),
                      '2023-03-06T08:41:32.737368Z')
        test(datetime(2023, 3, 6, 8, 41, 32, 0, utc), '2023-03-06t08:41:32z')
        test(datetime(2023, 3, 6, 8, 41, 32, 737000, utc),
                      '2023-03-06t08:41:32.737z')
        test(datetime(2023, 3, 6, 17, 41, 32, 0, gmt09),
                      '2023-03-06T17:41:32+09:00')
        test(datetime(2023, 3, 6, 17, 41, 32, 737000, gmt09),
                      '2023-03-06T17:41:32.737+09:00')
        test(datetime(2023, 3, 6, 17, 41, 32, 737368, gmt09),
                      '2023-03-06T17:41:32.737368+09:00')
        test(datetime(2023, 3, 6, 17, 41, 32, 0, gmt09),
                      '2023-03-06 17:41:32+09:00')
        test(datetime(2023, 3, 6, 17, 41, 32, 700000, gmt09),
                      '2023-03-06 17:41:32.7+09:00')
        test(datetime(2023, 3, 6, 17, 41, 32, 730000, gmt09),
                      '2023-03-06 17:41:32.73+09:00')
        test(datetime(2023, 3, 6, 17, 41, 32, 737000, gmt09),
                      '2023-03-06 17:41:32.737+09:00')
        test(datetime(2023, 3, 6, 17, 41, 32, 737368, gmt09),
                      '2023-03-06 17:41:32.737368+09:00')
        test(datetime(2023, 3, 6, 8, 41, 32, 0, utc),
                      '2023-03-06 08:41:32Z')
        test(datetime(2023, 3, 6, 8, 41, 32, 0, utc),
                      '2023-03-06_08:41:32Z')
        test(datetime(2023, 3, 6, 8, 41, 32, 0, utc),
                      '2023-03-06 08:41:32z')
        test(datetime(2023, 3, 6, 8, 41, 32, 0, utc),
                      '2023-03-06_08:41:32z')
        test(datetime(2023, 3, 6, 8, 41, 32, 700000, utc),
                      '2023-03-06 08:41:32.7Z')
        test(datetime(2023, 3, 6, 8, 41, 32, 730000, utc),
                      '2023-03-06 08:41:32.73Z')
        test(datetime(2023, 3, 6, 8, 41, 32, 737000, utc),
                      '2023-03-06 08:41:32.737Z')
        test(datetime(2023, 3, 6, 8, 41, 32, 737000, utc),
                      '2023-03-06_08:41:32.737Z')
        test(datetime(2023, 3, 6, 8, 41, 32, 737368, utc),
                      '2023-03-06 08:41:32.737368Z')
        test(datetime(2023, 3, 6, 8, 41, 32, 737368, utc),
                      '2023-03-06_08:41:32.737368Z')
        test(datetime(2023, 3, 6, 8, 41, 32, 737000, utc),
                      '2023-03-06 08:41:32.737z')
        test(datetime(2023, 3, 6, 8, 41, 32, 737000, utc),
                      '2023-03-06_08:41:32.737z')
        test(datetime(2023, 3, 6, 8, 41, 32, 737368, utc),
                      '2023-03-06 08:41:32.737368z')
        test(datetime(2023, 3, 6, 8, 41, 32, 737368, utc),
                      '2023-03-06_08:41:32.737368z')
        test(datetime(2023, 3, 6, 8, 41, 32, 0, utc),
                      '2023-03-06 08:41:32-00:00')
        test(datetime(2023, 3, 6, 8, 41, 32, 737000, utc),
                      '2023-03-06 08:41:32.737-00:00')
        test(datetime(2023, 3, 6, 8, 41, 32, 0, utc),
                      '2023-03-06T08:41:32-00:00')
        test(datetime(2023, 3, 6, 8, 41, 32, 737000, utc),
                      '2023-03-06T08:41:32.737-00:00')
        test(datetime(2023, 3, 6, 17, 26, 32, 0, gmt0845),
                      '2023-03-06T17:26:32+08:45')
        test(datetime(2023, 3, 6, 8, 41, 32, 0, utc),
                      '2023-03-06T08:41:32+00:00')
        test(datetime(2023, 3, 6, 8, 41, 32, 737000, utc),
                      '2023-03-06T08:41:32.737+00:00')

    def test_dump_datetime(self):
        def test(expected, value):
            actual = json.dumps(value, cls=TracRpcJSONEncoder)
            self.assertEqual(expected, actual)

        test('{"__jsonclass__": ["datetime", "2023-03-06T00:00:00"]}',
             datetime(2023, 3, 6, 0, 0, 0, 0, utc))
        test('{"__jsonclass__": ["datetime", "2023-03-06T20:21:00"]}',
             datetime(2023, 3, 6, 20, 21, 0, 0, utc))
        test('{"__jsonclass__": ["datetime", "2023-03-06T20:21:42"]}',
             datetime(2023, 3, 6, 20, 21, 42, 0, utc))
        test('{"__jsonclass__": ["datetime", "2023-03-06T20:21:42.900000"]}',
             datetime(2023, 3, 6, 20, 21, 42, 900000, utc))
        test('{"__jsonclass__": ["datetime", "2023-03-06T20:21:42.975000"]}',
             datetime(2023, 3, 6, 20, 21, 42, 975000, utc))
        test('{"__jsonclass__": ["datetime", "2023-03-06T20:21:42.975321"]}',
             datetime(2023, 3, 6, 20, 21, 42, 975321, utc))
        test('{"__jsonclass__": ["datetime", "2023-03-06T18:21:42.975321"]}',
             datetime(2023, 3, 6, 20, 21, 42, 975321, timezone('GMT +2:00')))
        test('{"__jsonclass__": ["datetime", "2023-03-07T00:21:42.975321"]}',
             datetime(2023, 3, 6, 20, 21, 42, 975321, timezone('GMT -4:00')))

    def test_call(self):
        result = self._anon_req(
                {'method': 'system.listMethods', 'params': [], 'id': 244})
        self.assertIn('system.methodHelp', result['result'])
        self.assertEqual(None, result['error'])
        self.assertEqual(244, result['id'])

    def test_multicall(self):
        data = {'method': 'system.multicall', 'params': [
                {'method': 'wiki.getAllPages', 'params': [], 'id': 1},
                {'method': 'wiki.getPage', 'params': ['WikiStart', 1], 'id': 2},
                {'method': 'ticket.status.getAll', 'params': [], 'id': 3},
                {'method': 'nonexisting', 'params': []}
            ], 'id': 233}
        result = self._anon_req(data)
        self.assertEqual(None, result['error'])
        self.assertEqual(4, len(result['result']))
        items = result['result']
        self.assertEqual(1, items[0]['id'])
        self.assertEqual(233, items[3]['id'])
        self.assertIn('WikiStart', items[0]['result'])
        self.assertEqual(None, items[0]['error'])
        self.assertIn('Welcome', items[1]['result'])
        self.assertEqual(['accepted', 'assigned', 'closed', 'new',
                                'reopened'], items[2]['result'])
        self.assertEqual(None, items[3]['result'])
        self.assertEqual('JSONRPCError', items[3]['error']['name'])

    def test_datetime(self):
        # read and write datetime values
        dt_str = "2009-06-19T16:46:00"
        data = {'method': 'ticket.milestone.update',
            'params': ['milestone1', {'due': {'__jsonclass__':
                ['datetime', dt_str]}}]}
        result = self._auth_req(data, user='admin')
        self.assertEqual(None, result['error'])
        result = self._auth_req({'method': 'ticket.milestone.get',
            'params': ['milestone1']}, user='admin')
        self.assertTrue(result['result'])
        self.assertEqual(dt_str,
                    result['result']['due']['__jsonclass__'][1])

    def test_binary(self):
        # read and write binaries values
        image_in = pkg_resources.resource_string('trac', 'htdocs/feed.png')
        data = {'method': 'wiki.putAttachmentEx',
            'params': ['TitleIndex', "feed2.png", "test image",
            {'__jsonclass__': ['binary', b64encode(image_in)]}]}
        result = self._auth_req(data, user='admin')
        self.assertEqual(None, result['error'])
        self.assertEqual('feed2.png', result['result'])
        # Now try to get the attachment, and verify it is identical
        result = self._auth_req({'method': 'wiki.getAttachment',
                        'params': ['TitleIndex/feed2.png']}, user='admin')
        self.assertTrue(result['result'])
        image_out = base64.b64decode(result['result']['__jsonclass__'][1])
        self.assertEqual(image_in, image_out)

    def test_large_file(self):
        pagename = 'SandBox/LargeJsonrpc'
        filename = 'large.dat'
        payload = {'method': 'wiki.putPage',
                   'params': [pagename, 'attachment:' + filename, {}]}
        rv = self._auth_req(payload, user='admin')
        self.assertEqual({'error': None, 'id': None, 'result': True}, rv)

        content = bytes(bytearray(range(256))) * 4 * 1024 * 4  # 4 MB
        payload = {'method': 'wiki.putAttachmentEx',
                   'params': [pagename, filename, 'Large file',
                   {'__jsonclass__': ['binary', b64encode(content)]}]}
        rv = self._auth_req(payload, user='admin')
        self.assertEqual({'error': None, 'id': None, 'result': filename}, rv)

        payload = {'method': 'wiki.getAttachment',
                   'params': ['%s/%s' % (pagename, filename)]}
        rv = self._auth_req(payload, user='admin')
        self.assertEqual(None, rv['error'])
        result = rv['result']
        self.assertIsInstance(result, dict)
        self.assertEqual(['__jsonclass__'], sorted(result))
        self.assertEqual('binary', result['__jsonclass__'][0])
        self.assertEqual(content, base64.b64decode(result['__jsonclass__'][1]))
        self.assertIsInstance(result['__jsonclass__'], list)

    def test_fragment(self):
        data = {'method': 'ticket.create',
                'params': ['ticket10786', '',
                           {'type': 'enhancement', 'owner': 'A'}]}
        result = self._auth_req(data, user='admin')
        self.assertEqual(None, result['error'])
        tktid = result['result']

        data = {'method': 'search.performSearch',
                'params': ['ticket10786']}
        result = self._auth_req(data, user='admin')
        self.assertEqual(None, result['error'])
        self.assertEqual('<span class="new">#%d</span>: enhancement: '
                          'ticket10786 (new)' % tktid,
                          result['result'][0][1])
        self.assertEqual(1, len(result['result']))

        data = {'method': 'ticket.delete', 'params': [tktid]}
        result = self._auth_req(data, user='admin')
        self.assertEqual(None, result['error'])

    def test_xmlrpc_permission(self):
        # Test returned response if not XML_RPC permission
        self._revoke_perm('anonymous', 'XML_RPC')
        try:
            result = self._anon_req({'method': 'system.listMethods',
                                     'id': 'no-perm'})
            self.assertEqual(None, result['result'])
            self.assertEqual('no-perm', result['id'])
            self.assertEqual(403, result['error']['code'])
            self.assertIn('XML_RPC', result['error']['message'])
        finally:
            # Add back the default permission for further tests
            self._grant_perm('anonymous', 'XML_RPC')

    def test_method_not_found(self):
        result = self._anon_req({'method': 'system.doesNotExist',
                                 'id': 'no-method'})
        self.assertTrue(result['error'])
        self.assertEqual(result['id'], 'no-method')
        self.assertEqual(None, result['result'])
        self.assertEqual(-32601, result['error']['code'])
        self.assertIn('not found', result['error']['message'])

    def test_wrong_argspec(self):
        result = self._anon_req({'method': 'system.listMethods',
                        'params': ['hello'], 'id': 'wrong-args'})
        self.assertTrue(result['error'])
        self.assertEqual(result['id'], 'wrong-args')
        self.assertEqual(None, result['result'])
        self.assertEqual(-32603, result['error']['code'])
        message = result['error']['message']
        if sys.version_info[0] == 2:
            self.assertIn('listMethods() takes exactly 2 arguments', message)
        else:
            self.assertIn('listMethods() takes 2 positional arguments but 3 '
                          'were given', message)

    def test_call_permission(self):
        # Test missing call-specific permission
        result = self._anon_req({'method': 'ticket.component.delete',
                'params': ['component1'], 'id': 2332})
        self.assertEqual(None, result['result'])
        self.assertEqual(2332, result['id'])
        self.assertEqual(403, result['error']['code'])
        self.assertIn('TICKET_ADMIN privileges are required to perform this '
                      'operation', result['error']['message'])

    def test_resource_not_found(self):
        # A Ticket resource
        result = self._anon_req({'method': 'ticket.get',
                'params': [2147483647], 'id': 3443})
        self.assertEqual(result['id'], 3443)
        self.assertEqual(result['error']['code'], 404)
        self.assertEqual(result['error']['message'],
                 'Ticket 2147483647 does not exist.')
        # A Wiki resource
        result = self._anon_req({'method': 'wiki.getPage',
                'params': ["Test", 10], 'id': 3443})
        self.assertEqual(result['error']['code'], 404)
        self.assertEqual(result['error']['message'],
                 'Wiki page "Test" does not exist at version 10')

    def test_invalid_json(self):
        result = self._anon_req('invalid-json')
        self.assertEqual(result['id'], None)
        self.assertEqual(result['error']['code'], -32700)
        self.assertEqual(result['error']['name'], 'JSONRPCError')
        self.assertIn('JsonProtocolException details: No JSON object could be '
                      'decoded', result['error']['message'])

    def test_not_a_dict(self):
        result = self._anon_req('42')
        self.assertEqual(result['id'], None)
        self.assertEqual(result['error']['code'], -32700)
        self.assertEqual(result['error']['name'], 'JSONRPCError')
        self.assertIn('JSON object is not a dict', result['error']['message'])


def json_data(data):
    if isinstance(data, bytes):
        return data
    if isinstance(data, unicode):
        return data.encode('utf-8')
    return to_b(json.dumps(data))


def _raw_json_load(fp):
    reader = codecs.getreader('utf-8')(fp)
    return json.load(reader)


def test_suite():
    suite = TracRpcTestSuite()
    suite.addTest(makeSuite(JsonTestCase))
    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

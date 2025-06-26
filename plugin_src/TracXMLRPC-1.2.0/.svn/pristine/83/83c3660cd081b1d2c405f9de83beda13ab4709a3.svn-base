# -*- coding: utf-8 -*-
"""
License: BSD

(c) 2009-2013 ::: www.CodeResort.com - BV Network AS (simon-code@bvnetwork.no)
"""

import unittest

from ..xml_rpc import XmlRpcProtocol
from . import (HTTPError, Request, TracRpcTestCase, TracRpcTestSuite, urlopen,
               makeSuite)


class ProtocolProviderTestCase(TracRpcTestCase):

    def setUp(self):
        TracRpcTestCase.setUp(self)

    def tearDown(self):
        TracRpcTestCase.tearDown(self)

    def test_invalid_content_type(self):
        req = Request(self._testenv.url_anon,
                    headers={'Content-Type': 'text/plain'},
                    data=b'Fail! No RPC for text/plain')
        try:
            urlopen(req)
            self.fail("Expected urllib2.HTTPError")
        except HTTPError as e:
            self.assertEqual(e.code, 415)
            self.assertEqual(e.msg, "Unsupported Media Type")
            self.assertEqual(b"No protocol matching Content-Type 'text/plain' "
                             b"at path '/rpc'.", e.fp.read())

    def test_rpc_info(self):
        # Just try getting the docs for XML-RPC to test, it should always exist
        xmlrpc = XmlRpcProtocol(self._testenv.get_trac_environment())
        name, docs = xmlrpc.rpc_info()
        self.assertEqual(name, 'XML-RPC')
        self.assertIn('Content-Type: application/xml', docs)

    def test_valid_provider(self):
        # Confirm the request won't work before adding plugin
        req = Request(self._testenv.url_anon,
                        headers={'Content-Type': 'application/x-tracrpc-test'},
                        data=b"Fail! No RPC for application/x-tracrpc-test")
        try:
            resp = urlopen(req)
            self.fail("Expected urllib2.HTTPError")
        except HTTPError as e:
            self.assertEqual(e.code, 415)

        # Make a new plugin
        source = r"""# -*- coding: utf-8 -*-
from trac.core import *
from tracrpc.api import *
class DummyProvider(Component):
    implements(IRPCProtocol)
    def rpc_info(self):
        return ('TEST-RPC', 'No Docs!')
    def rpc_match(self):
        yield ('rpc', 'application/x-tracrpc-test')
    def parse_rpc_request(self, req, content_type):
        return {'method' : 'system.getAPIVersion'}
    def send_rpc_error(self, req, e):
        rpcreq = req.rpc
        req.send((u'Test failure: %s' % e).encode('utf-8'),
                 rpcreq['mimetype'], 500)
    def send_rpc_result(self, req, result):
        rpcreq = req.rpc
        # raise KeyError('Here')
        response = b'Got a result!'
        req.send(response, rpcreq['mimetype'], 200)
"""
        with self._plugin(source, 'DummyProvider.py'):
            req = Request(self._testenv.url_anon,
                        headers={'Content-Type': 'application/x-tracrpc-test'})
            resp = urlopen(req)
            self.assertEqual(200, resp.code)
            self.assertEqual(b"Got a result!", resp.read())
            self.assertEqual('application/x-tracrpc-test;charset=utf-8',
                             resp.headers['Content-Type'])

    def test_general_provider_error(self):
        # Make a new plugin and restart server
        source = r"""# -*- coding: utf-8 -*-
from trac.core import *
from tracrpc.api import *
from tracrpc.util import to_b
class DummyProvider(Component):
    implements(IRPCProtocol)
    def rpc_info(self):
        return ('TEST-RPC', 'No Docs!')
    def rpc_match(self):
        yield ('rpc', 'application/x-tracrpc-test')
    def parse_rpc_request(self, req, content_type):
        return {'method' : 'system.getAPIVersion'}
    def send_rpc_error(self, req, e):
        data = e.message if isinstance(e, RPCError) else b'Test failure'
        req.send(to_b(data), 'text/plain', 500)
    def send_rpc_result(self, req, result):
        raise RPCError('No good.')
"""
        with self._plugin(source, 'DummyProvider.py'):
            self._testenv.restart()
            req = Request(self._testenv.url_anon,
                    headers={'Content-Type': 'application/x-tracrpc-test'})
            try:
                urlopen(req)
            except HTTPError as e:
                self.assertEqual(500, e.code)
                self.assertEqual(b"No good.", e.fp.read())
                self.assertTrue(e.hdrs['Content-Type'].startswith('text/plain'))
            else:
                self.fail('HTTPError not raised')


def test_suite():
    suite = TracRpcTestSuite()
    suite.addTest(makeSuite(ProtocolProviderTestCase))
    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

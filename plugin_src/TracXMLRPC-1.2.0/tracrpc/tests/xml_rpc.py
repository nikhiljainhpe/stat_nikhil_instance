# -*- coding: utf-8 -*-
"""
License: BSD

(c) 2009      ::: www.CodeResort.com - BV Network AS (simon-code@bvnetwork.no)
"""

import sys
import unittest
from datetime import datetime

from trac.util.datefmt import to_datetime, utc

from ..util import xmlrpclib
from ..xml_rpc import (to_xmlrpc_datetime, from_xmlrpc_datetime,
                       _illegal_unichrs, REPLACEMENT_CHAR)
from . import (Request, TracRpcTestCase, TracRpcTestSuite, b64encode, urlopen,
               makeSuite)


class RpcXmlTestCase(TracRpcTestCase):

    def setUp(self):
        TracRpcTestCase.setUp(self)
        self.anon = xmlrpclib.ServerProxy(self._testenv.url_anon)
        self.user = xmlrpclib.ServerProxy(self._testenv.url_user)
        self.admin = xmlrpclib.ServerProxy(self._testenv.url_admin)

    def tearDown(self):
        for proxy in (self.anon, self.user, self.admin):
            proxy('close')()
        TracRpcTestCase.tearDown(self)

    def test_xmlrpc_permission(self):
        # Test returned response if not XML_RPC permission
        self._revoke_perm('anonymous', 'XML_RPC')
        try:
            self.anon.system.listMethods()
        except xmlrpclib.Fault as e:
            self.assertEqual(403, e.faultCode)
            self.assertIn('XML_RPC', e.faultString)
        else:
            self.fail('xmlrpclib.Fault not raised')
        finally:
            self._grant_perm('anonymous', 'XML_RPC')

    def test_method_not_found(self):
        try:
            self.admin.system.doesNotExist()
        except xmlrpclib.Fault as e:
            self.assertEqual(-32601, e.faultCode)
            self.assertIn("not found", e.faultString)
        else:
            self.fail('xmlrpclib.Fault not raised')

    def test_wrong_argspec(self):
        try:
            self.admin.system.listMethods("hello")
        except xmlrpclib.Fault as e:
            self.assertEqual(1, e.faultCode)
            if sys.version_info[0] == 2:
                self.assertIn('listMethods() takes exactly 2 arguments',
                              e.faultString)
            else:
                self.assertIn('listMethods() takes 2 positional arguments but '
                              '3 were given', e.faultString)
        else:
            self.fail('xmlrpclib.Fault not raised')

    def test_content_encoding(self):
        test_bytes = u'øæåØÆÅàéüoö'.encode('utf-8')
        body = (b'<?xml version="1.0"?>\n'
                b'<methodCall>\n'
                b'  <methodName>ticket.create</methodName>\n'
                b'  <params>\n'
                b'    <param><string>%s</string></param>\n'
                b'    <param><string>%s</string></param>\n'
                b'  </params>\n'
                b'</methodCall>' % (test_bytes, test_bytes[::-1]))
        request = Request(self._testenv.url_auth, data=body)
        request.add_header('Content-Type', 'application/xml')
        request.add_header('Content-Length', str(len(body)))
        request.add_header('Authorization',
                           'Basic %s' % b64encode('admin:admin'))
        self.assertEqual('POST', request.get_method())
        response = urlopen(request)
        self.assertEqual(200, response.code)
        self.assertIn(b'<member>\n'
                      b'<name>faultCode</name>\n'
                      b'<value><int>-32700</int></value>\n'
                      b'</member>', response.read())

    def test_to_and_from_datetime(self):
        now = to_datetime(None, utc)
        now_timetuple = now.timetuple()[:6]
        xmlrpc_now = to_xmlrpc_datetime(now)
        self.assertTrue(isinstance(xmlrpc_now, xmlrpclib.DateTime),
                "Expected xmlprc_now to be an xmlrpclib.DateTime")
        self.assertEqual(str(xmlrpc_now), now.strftime("%Y%m%dT%H:%M:%S"))
        now_from_xmlrpc = from_xmlrpc_datetime(xmlrpc_now)
        self.assertTrue(isinstance(now_from_xmlrpc, datetime),
                "Expected now_from_xmlrpc to be a datetime")
        self.assertEqual(now_from_xmlrpc.timetuple()[:6], now_timetuple)
        self.assertEqual(now_from_xmlrpc.tzinfo, utc)

    def test_resource_not_found(self):
        # A Ticket resource
        try:
            self.admin.ticket.get(2147483647)
        except xmlrpclib.Fault as e:
            self.assertEqual(e.faultCode, 404)
            self.assertEqual(e.faultString,
                              'Ticket 2147483647 does not exist.')
        else:
            self.fail('xmlrpclib.Fault not raised')
        # A Wiki resource
        try:
            self.admin.wiki.getPage("Test", 10)
        except xmlrpclib.Fault as e:
            self.assertEqual(e.faultCode, 404)
            self.assertEqual(e.faultString,
                              'Wiki page "Test" does not exist at version 10')
        else:
            self.fail('xmlrpclib.Fault not raised')

    @unittest.expectedFailure
    def test_xml_encoding_special_characters(self):
        tid1 = self.admin.ticket.create(
                            'One & Two < Four', 'Desc & ription\nLine 2', {})
        ticket = self.admin.ticket.get(tid1)
        try:
            self.assertEqual('One & Two < Four', ticket[3]['summary'])
            self.assertEqual('Desc & ription\r\nLine 2',
                            ticket[3]['description'])
        finally:
            self.admin.ticket.delete(tid1)

    def test_xml_encoding_invalid_characters(self):
        # Enable ticket manipulator
        source = r"""# -*- coding: utf-8 -*-
from trac.core import *
from tracrpc.api import IXMLRPCHandler
class UniChr(Component):
    implements(IXMLRPCHandler)
    def xmlrpc_namespace(self):
        return 'test_unichr'
    def xmlrpc_methods(self):
        yield ('XML_RPC', ((str, int),), self.unichr)
    def unichr(self, req, code):
        return (b'\\U%08X' % code).decode('unicode-escape')
"""
        with self._plugin(source, 'InvalidXmlCharHandler.py'):
            for low, high in _illegal_unichrs:
                for code in sorted(set([low, low + 1, high - 1, high])):
                    self.assertEqual(REPLACEMENT_CHAR,
                                     self.user.test_unichr.unichr(code),
                                     "Failed unichr with U+%04X" % code)
            # surrogate pair on narrow build
            self.assertEqual(u'\U0001D4C1',
                             self.user.test_unichr.unichr(0x1D4C1))

    def test_large_file(self):
        pagename = 'SandBox/LargeXmlrpc'
        filename = 'large.dat'
        rv = self.admin.wiki.putPage(pagename, 'attachment:' + filename, {})
        self.assertEqual(True, rv)

        content = bytes(bytearray(range(256))) * 4 * 1024 * 4  # 4 MB
        rv = self.admin.wiki.putAttachmentEx(pagename, filename, 'Large file',
                                             xmlrpclib.Binary(content))
        self.assertEqual(filename, rv)

        rv = self.admin.wiki.getAttachment('%s/%s' % (pagename, filename))
        self.assertIsInstance(rv, xmlrpclib.Binary)
        self.assertEqual(content, rv.data)


def test_suite():
    suite = TracRpcTestSuite()
    suite.addTest(makeSuite(RpcXmlTestCase))
    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

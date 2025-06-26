# -*- coding: utf-8 -*-
"""
License: BSD

(c) 2009      ::: www.CodeResort.com - BV Network AS (simon-code@bvnetwork.no)
"""

import sys
import unittest

from trac.util.text import exception_to_unicode

from ..util import to_b
from . import (HTTPError, Request, TracRpcTestCase, TracRpcTestSuite,
               form_urlencoded, makeSuite)


class DocumentationTestCase(TracRpcTestCase):

    def setUp(self):
        TracRpcTestCase.setUp(self)
        self.opener_user = self._opener_auth(self._testenv.url_auth, 'user',
                                             'user')

    def tearDown(self):
        TracRpcTestCase.tearDown(self)

    def test_get_with_content_type(self):
        req = Request(self._testenv.url_auth,
                    headers={'Content-Type': 'text/html'})
        self.assert_rpcdocs_ok(self.opener_user, req)

    def test_get_no_content_type(self):
        req = Request(self._testenv.url_auth)
        self.assert_rpcdocs_ok(self.opener_user, req)

    def test_post_accept(self):
        req = Request(self._testenv.url_auth,
                    headers={'Content-Type' : 'text/plain',
                              'Accept': 'application/x-trac-test,text/html'},
                    data=b'Pass since client accepts HTML')
        self.assert_rpcdocs_ok(self.opener_user, req)

        req = Request(self._testenv.url_auth,
                    headers={'Content-Type' : 'text/plain'},
                    data=b'Fail! No content type expected')
        self.assert_unsupported_media_type(self.opener_user, req)

    def test_form_submit(self):
        # Explicit content type
        form_vars = {'result' : 'Fail! __FORM_TOKEN protection activated'}
        req = Request(self._testenv.url_auth,
                    headers={'Content-Type': 'application/x-www-form-urlencoded'},
                    data=form_urlencoded(form_vars))
        self.assert_form_protect(self.opener_user, req)

        # Implicit content type
        req = Request(self._testenv.url_auth,
                    headers={'Accept': 'application/x-trac-test,text/html'},
                    data=b'Pass since client accepts HTML')
        self.assert_form_protect(self.opener_user, req)

    def test_get_dont_accept(self):
        req = Request(self._testenv.url_auth,
                      headers={'Accept': 'application/x-trac-test'})
        self.assert_unsupported_media_type(self.opener_user, req)

    def test_post_dont_accept(self):
        req = Request(self._testenv.url_auth,
                      headers={'Content-Type': 'text/plain',
                               'Accept': 'application/x-trac-test'},
                      data=b'Fail! Client cannot process HTML')
        self.assert_unsupported_media_type(self.opener_user, req)

    # Custom assertions
    def assert_rpcdocs_ok(self, opener, req):
        """Determine if RPC docs are ok"""
        try:
            resp = opener.open(req)
        except HTTPError as e:
            self.fail("Request to '%s' failed (%s) %s" % (e.geturl(),
                                                          e.code,
                                                          e.fp.read()))
        else:
            self.assertEqual(200, resp.code)
            body = resp.read()
            self.assertIn(b'<h3 id="XML-RPC" class="section">XML-RPC</h3>',
                          body)
            self.assertIn(b'<h3 id="rpc.ticket.status" class="section">',
                          body)

    def assert_unsupported_media_type(self, opener, req):
        """Ensure HTTP 415 is returned back to the client"""
        content_type = req.get_header('Content-type', '')
        # XXX Content-type header with text/plain is sent even if GET request
        #     in Python 2's urllib2.
        if not content_type and sys.version_info[0] == 2 and \
                req.get_method() == 'GET':
            content_type = 'text/plain'
        expected = to_b("No protocol matching Content-Type '%s' at path "
                        "'/login/rpc'." % content_type)
        try:
            resp = opener.open(req)
        except HTTPError as e:
            self.assertEqual(415, e.code)
            self.assertEqual(expected, e.fp.read())
        except Exception as e:
            self.fail('Expected HTTP error but %s raised instead: %s' %
                      exception_to_unicode(e))
        else:
            resp.read()
            self.fail('Expected HTTP error (415) but nothing raised')

    def assert_form_protect(self, opener, req):
        try:
            opener.open(req)
        except HTTPError as e:
            self.assertEqual(400, e.code)
            self.assertIn(b"Missing or invalid form token. Do you have "
                          b"cookies enabled?", e.fp.read())
        else:
            self.fail('HTTPError not raised')


def test_suite():
    suite = TracRpcTestSuite()
    suite.addTest(makeSuite(DocumentationTestCase))
    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

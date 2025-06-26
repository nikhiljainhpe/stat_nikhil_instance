# -*- coding: utf-8 -*-
"""
License: BSD

(c) 2009      ::: www.CodeResort.com - BV Network AS (simon-code@bvnetwork.no)
"""

import pkg_resources
import time
import unittest

from ..util import xmlrpclib
from . import TracRpcTestCase, TracRpcTestSuite, makeSuite


class RpcWikiTestCase(TracRpcTestCase):

    image_in = pkg_resources.resource_string('trac', 'htdocs/feed.png')

    def setUp(self):
        TracRpcTestCase.setUp(self)
        self.anon = xmlrpclib.ServerProxy(self._testenv.url_anon)
        self.user = xmlrpclib.ServerProxy(self._testenv.url_user)
        self.admin = xmlrpclib.ServerProxy(self._testenv.url_admin)

    def tearDown(self):
        for proxy in (self.anon, self.user, self.admin):
            proxy('close')()
        TracRpcTestCase.tearDown(self)

    def test_attachments(self):
        # Create attachment
        self.admin.wiki.putAttachmentEx('TitleIndex', 'feed2.png', 'test image',
                                        xmlrpclib.Binary(self.image_in))
        self.assertEqual(self.image_in, self.admin.wiki.getAttachment(
                                                'TitleIndex/feed2.png').data)
        # Update attachment (adding new)
        self.admin.wiki.putAttachmentEx('TitleIndex', 'feed2.png',
                                        'test image',
                                        xmlrpclib.Binary(self.image_in), False)
        self.assertEqual(self.image_in, self.admin.wiki.getAttachment(
                                                'TitleIndex/feed2.2.png').data)
        # List attachments
        self.assertEqual(['TitleIndex/feed2.2.png', 'TitleIndex/feed2.png'],
                        sorted(self.admin.wiki.listAttachments('TitleIndex')))
        # Delete both attachments
        self.admin.wiki.deleteAttachment('TitleIndex/feed2.png')
        self.admin.wiki.deleteAttachment('TitleIndex/feed2.2.png')
        # List attachments again
        self.assertEqual([], self.admin.wiki.listAttachments('TitleIndex'))

    def test_getRecentChanges(self):
        self.admin.wiki.putPage('WikiOne', 'content one', {})
        time.sleep(1)
        self.admin.wiki.putPage('WikiTwo', 'content two', {})
        attrs2 = self.admin.wiki.getPageInfo('WikiTwo')
        changes = self.admin.wiki.getRecentChanges(attrs2['lastModified'])
        self.assertEqual(1, len(changes))
        self.assertEqual('WikiTwo', changes[0]['name'])
        self.assertEqual('admin', changes[0]['author'])
        self.assertEqual(1, changes[0]['version'])
        self.admin.wiki.deletePage('WikiOne')
        self.admin.wiki.deletePage('WikiTwo')

    def test_getPageHTMLWithImage(self):
        # Create the wiki page (absolute image reference)
        self.admin.wiki.putPage('ImageTest',
                        '[[Image(wiki:ImageTest:feed.png, nolink)]]\n', {})
        # Create attachment
        self.admin.wiki.putAttachmentEx('ImageTest', 'feed.png', 'test image',
                                        xmlrpclib.Binary(self.image_in))
        # Check rendering absolute
        markup_1 = self.admin.wiki.getPageHTML('ImageTest')
        self.assertIn((' src="%s/raw-attachment/wiki/ImageTest/feed.png"' %
                       self._testenv.url), markup_1)
        # Change to relative image reference and check again
        self.admin.wiki.putPage('ImageTest',
                                '[[Image(feed.png, nolink)]]\n', {})
        markup_2 = self.admin.wiki.getPageHTML('ImageTest')
        self.assertEqual(markup_2, markup_1)

    def test_getPageHTMLWithManipulator(self):
        self.admin.wiki.putPage('FooBar', 'foo bar', {})
        # Enable wiki manipulator
        source = r"""# -*- coding: utf-8 -*-
from trac.core import *
from trac.wiki.api import IWikiPageManipulator
class WikiManipulator(Component):
    implements(IWikiPageManipulator)
    def prepare_wiki_page(self, req, page, fields):
        fields['text'] = 'foo bar baz'
    def validate_wiki_page(req, page):
        return []
"""
        with self._plugin(source, 'Manipulator.py'):
            self.assertEqual('<html><body><p>\nfoo bar baz\n</p>\n'
                             '</body></html>',
                             self.admin.wiki.getPageHTML('FooBar'))

def test_suite():
    suite = TracRpcTestSuite()
    suite.addTest(makeSuite(RpcWikiTestCase))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

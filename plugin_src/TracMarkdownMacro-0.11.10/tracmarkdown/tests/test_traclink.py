# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 Cinc
#
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.
#
import unittest
from markdown import Markdown
from trac.test import EnvironmentStub, MockRequest
from trac.web.chrome import web_context
from tracmarkdown.macro import TracLinkExtension


class TestTracLink(unittest.TestCase):

    def setUp(self):
        self.env = EnvironmentStub(default_data=True, enable=['trac.*'])
        req = MockRequest(self.env)
        self.context = web_context(req, 'wiki', 'WikiStart')
        self.formatter = None

    def prepare_markup_class(self, extensions):
        md = Markdown(extensions=extensions,
                      tab_length=4, output_format='html')
        md.trac_context = self.context
        md.trac_env = self.env
        return md

    def test_traclink_simple(self):
        trac_link = TracLinkExtension()
        md = self.prepare_markup_class(['tables', trac_link])
        self.assertEqual(u'<p>Foo <a class="missing ticket">123</a></p>',
                         md.convert("Foo [ticket:123]"))

    def test_traclink(self):
        # Trac links look like references, shortrefs or links.
        # Test a more complex document with all these items and see
        # if the Trac link survives.
        content = """# URL tests

This is [an example](http://example.com/foo#123 "Title") inline link.

Link defined with [an id][id]

Link without '<>' [foo][foo]

Link without '[]': [bar]

Trac link: [ticket:123]

## Links
[id]: <http://example.com/foo#12>  "Optional Title Here"

[foo]: http://example.com/foo#12  "Optional Title Here"

[bar]: http://example.com/bar#12  "Bar Title Here"
        """
        trac_link = TracLinkExtension()
        md = self.prepare_markup_class(['extra', trac_link])
        res = md.convert(content)
        # Check for Trac link
        self.assertTrue(u'<p>Trac link: <a class="missing ticket">123</a></p>' in res)
        # Check for markdown links
        self.assertTrue(u"""<p>This is <a href="http://example.com/foo#123" title="Title">an example</a> inline link.</p>""" in res)
        self.assertTrue(u"""<p>Link defined with <a href="http://example.com/foo#12" title="Optional Title Here">an id</a></p>""" in res)
        self.assertTrue(u"""<p>Link without '&lt;&gt;' <a href="http://example.com/foo#12" title="Optional Title Here">foo</a></p>""" in res)
        self.assertTrue(u"""<p>Link without '[]': <a href="http://example.com/bar#12" title="Bar Title Here">bar</a></p>""" in res)


if __name__ == '__main__':
    unittest.main()

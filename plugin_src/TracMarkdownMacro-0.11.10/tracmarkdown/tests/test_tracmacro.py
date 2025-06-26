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
from tracmarkdown.macro import TracMacroExtension, TracTicketExtension


class TestTracMacro(unittest.TestCase):

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

    def test_macro(self):
        expected = """<p>
<a class="missing wiki" href="/trac.cgi/wiki/FooBar()" rel="nofollow">FooBar()</a>
</p>"""
        trac_macro = TracMacroExtension()
        md = self.prepare_markup_class(['extra', trac_macro])
        self.assertEqual(expected, md.convert('[[FooBar()]]'))

    def test_macro_context(self):
        markdown = """
# Header
Text,
more text
## Header 2
[[FooBar()]]
        """
        expected = """<p>
<a class="missing wiki" href="/trac.cgi/wiki/FooBar()" rel="nofollow">FooBar()</a>
</p>"""
        trac_macro = TracMacroExtension()
        md = self.prepare_markup_class(['extra', trac_macro])
        self.assertTrue(expected in md.convert(markdown))


if __name__ == '__main__':
    unittest.main()

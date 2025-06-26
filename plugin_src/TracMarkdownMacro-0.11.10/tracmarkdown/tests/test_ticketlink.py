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


class TestTicketLink(unittest.TestCase):

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

    def test_ticketlink(self):
        trac_ticket = TracTicketExtension()
        md = self.prepare_markup_class(['extra', trac_ticket])
        self.assertEqual(u'<h1>Header 1</h1>', md.convert("# Header 1"))  # Just to test the setup
        self.assertEqual(u'<p>Foo <a class="missing ticket">#123</a> bar</p>', md.convert("Foo #123 bar"))
        self.assertEqual(u'<p>Foo<a class="missing ticket">#123</a></p>', md.convert("Foo#123"))
        self.assertEqual(u'<p>Foo <a class="missing ticket">#123</a> bar</p>', md.convert("\n\nFoo #123 bar"))

    def test_ticketlink_url_location(self):
        """Check if location hash # in url is preserved"""
        trac_ticket = TracTicketExtension()
        md = self.prepare_markup_class(['extra', trac_ticket])
        self.assertEqual(u'<p>Link <a href="http://example.com/foo#section" title="Title">example</a> inline</p>',
                         md.convert('Link [example](http://example.com/foo#section "Title") inline'))
        # location hash is like a ticket id here.
        self.assertEqual(u'<p>Link <a href="http://example.com/foo#123" title="Title #123">example</a> inline</p>',
                         md.convert('Link [example](http://example.com/foo#123 "Title #123") inline'))

    def test_ticketlink_macro(self):
        """Check if #xxx in macros is preserved"""
        trac_ticket = TracTicketExtension()
        trac_macro = TracMacroExtension()
        md = self.prepare_markup_class(['tables', trac_ticket, trac_macro])
        self.assertFalse(u'</a>' in md.convert('Foo [[TracIni(#123)]]'))

    def test_ticketlink_autolink(self):
        """Check if we interfere with markdown autolinks '<http://...>"""
        trac_ticket = TracTicketExtension()
        trac_macro = TracMacroExtension()
        md = self.prepare_markup_class(['extra', trac_ticket, trac_macro])
        self.assertEqual(u'<p>Foo <a href="http://example.com/foo#123">http://example.com/foo#123</a></p>',
                         md.convert('Foo <http://example.com/foo#123>'))


if __name__ == '__main__':
    unittest.main()

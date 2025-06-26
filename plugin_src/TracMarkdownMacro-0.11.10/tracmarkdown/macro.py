# -*- coding: utf-8 -*-
#
# Copyright (C) 2008 Douglas Clifton <dwclifton@gmail.com>
# Copyright (C) 2012-2013 Ryan J Ollos <ryan.j.ollos@gmail.com>
# Copyright (C) 2021 Cinc
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.
#
"""Components adding support for Markdown as a wiki language to Trac."""

""" @package MarkdownMacro
    @file macro.py
    @brief The markdownMacro class

    Implements Markdown syntax WikiProcessor as a Trac macro.

    From Markdown.py by Alex Mizrahi aka killer_storm
    See: http://trac-hacks.org/attachment/ticket/353/Markdown.py
    Get Python Markdown from:
        http://www.freewisdom.org/projects/python-markdown/

    @author Douglas Clifton <dwclifton@gmail.com>
    @date December, 2008
    @version 0.11.4
"""

from functools import partial
from pkg_resources import resource_filename
try:
    from markdown import markdown, Markdown
    from markdown.extensions import Extension
    from markdown.inlinepatterns import InlineProcessor
    from markdown.treeprocessors import Treeprocessor
    from markdown import util
    from .wikiprocessor import WikiProcessorExtension, WikiProcessorFenceExtension
except ImportError:
    markdown = None

from trac.config import IntOption, ListOption
from trac.core import Component, implements
from trac.resource import Resource
from trac.util.html import Markup, html as tag, TracHTMLSanitizer
from trac.web.api import IRequestFilter, IRequestHandler
from trac.web.chrome import add_stylesheet, ITemplateProvider, add_warning, web_context
from trac.wiki.api import WikiSystem
from trac.wiki.formatter import format_to_html, format_to_oneliner, Formatter, system_message
from trac.wiki.macros import WikiMacroBase


WARNING = tag('Error importing Python Markdown, install it from ',
              tag.a('here', href="https://pypi.python.org/pypi/Markdown"),
              '.')

tab_length = IntOption('markdown', 'tab_length', 4, """
    Specify the length of tabs in the markdown source. This affects
    the display of multiple paragraphs in list items, including sub-lists,
    blockquotes, code blocks, etc.
    """)

class MarkdownMacro(WikiMacroBase):
    """Implements Markdown syntax as a Trac macro.

    === Usage
    The macro can only be used as a [WikiProcessors WikiProcessor]:
    {{{
    {{{#!Markdown
    # A Header

    This `is` *all* Markdown.
    }}}
    }}}
    """

    tab_length = tab_length

    def expand_macro(self, formatter, name, content, args=None):
        if markdown:
            return format_to_markdown(self, formatter.context, content)
        else:
            return system_message(WARNING)


class MarkdownFormatter(Component):
    """Allow to use Markdown as wiki language for certain wiki pages.

    === Configuration
    [[TracIni(markdown)]]
    """
    if markdown:
        implements(IRequestFilter, IRequestHandler, ITemplateProvider)

    is_valid_default_handler = False

    tab_length = tab_length
    root_pages = ListOption('markdown', 'root_pages', [],
                            doc="List of wiki page names to be used as root pages for a page hierarchy. Wiki subpages "
                                "of these roots will use Markdown as the default wiki language.[[BR]][[BR]]"
                                "For example if the list contains `Docs, Note` the wiki pages `Docs/MyDocument` "
                                "and `Note/FirstNote` will use Markdown; the wiki page `NoteOne` will use Trac "
                                "WikiFormatting.\n\nExample:\n"
                                "{{{#!ini\n[markdown]\nroot_pages = Docs, Note\n}}}\n**Note:** page names are "
                                "case sensitive.")

    # IRequestHandler methods

    def match_request(self, req):
        # We don't have to check the request here because Trac is
        # calling process_request() directly from the returned handler
        # in pre_process_request() for wiki preview rendering.
        # But we allow for genuine Markup rendering here for the future and
        # for testing.
        return req.path_info == '/markup_render'

    def process_request(self, req):
        # This code is largely taken from WikiRenderer() in trac.wiki.web_api.
        # See there for extended features like 'flavour' or options like
        # 'escape_newlines' or 'shorten'.

        # Allow all POST requests (with a valid __FORM_TOKEN, ensuring that
        # the client has at least some permission). Additionally, allow GET
        # requests from TRAC_ADMIN for testing purposes.
        if req.method != 'POST':
            req.perm.require('TRAC_ADMIN')
        realm = req.args.get('realm', WikiSystem.realm)
        id = req.args.get('id')
        version = req.args.getint('version')
        text = req.args.get('text', '')
        resource = Resource(realm, id=id, version=version)
        context = web_context(req, resource)
        rendered = Markup(format_to_markdown(self, context, text))

        req.send(rendered.encode('utf-8'))

    def pre_process_request(self, req, handler):
        # This is coming for the wiki preview rendering. Redirect it to our handler
        # to use Markdown for rendering.
        if req.path_info == '/wiki_render':
            if req.args.get('realm', None) == 'wiki' and req.args.get('id'):
                path = req.args.get('id').split('/')
                if path[0] in self.root_pages:
                    return self
        return handler

    def post_process_request(self, req, template, data, content_type):

        def wiki_to_html(self, context, wikidom, escape_newlines=None):
            return Markup(format_to_markdown(self, context, wikidom))

        if template and data and 'page' in data:
            # We only handle wiki pages
            path = data['page'].name.split('/')
            if path[0] in self.root_pages:
                data['wiki_to_html'] = partial(wiki_to_html, self)

        add_stylesheet(req, 'markdown/css/markdown.css')
        return template, data, content_type

    # ITemplateProvider methods

    def get_templates_dirs(self):
        return []

    def get_htdocs_dirs(self):
        return [('markdown', resource_filename(__name__, 'htdocs'))]


def format_to_markdown(self, context, content):
    formatter = Formatter(self.env, context)
    _sanitizer = TracHTMLSanitizer(
        safe_schemes=formatter.wiki.safe_schemes,
        safe_origins=formatter.wiki.safe_origins)

    def sanitize(text):
        if WikiSystem(self.env).render_unsafe_content:
            return Markup(text)
        else:
            return _sanitizer.sanitize(text)

    trac_link = TracLinkExtension()
    trac_macro = TracMacroExtension()
    trac_tkt = TracTicketExtension()
    wiki_proc = WikiProcessorExtension()
    wp_fence = WikiProcessorFenceExtension()

    md = Markdown(extensions=['extra', wiki_proc, trac_link, trac_macro, trac_tkt, wp_fence],
                  tab_length=self.tab_length, output_format='html')

    md.treeprocessors.register(TracClassTreeprocessor(), 'trac_class', 30)

    # Added for use with format_to_html() and format_to_oneliner()
    md.trac_context = context
    md.trac_env = self.env
    return sanitize(md.convert(content))


class TracLinkInlineProcessor(InlineProcessor):
    """Render all kinds of Trac links ([wiki:...], [ticket:...], etc.).

    The Trac link is extracted from the text and converted using Tracs
    formatter to html. The html data is inserted eventually."""
    def handleMatch(self, m, data):
        if not m.group(1) or m.group(1)[0] == '[':
            # This is a Trac macro '[[FooBar()]]
            return None, None, None

        html = format_to_oneliner(self.md.trac_env, self.md.trac_context, '[%s]' % m.group(1))
        return self.md.htmlStash.store(html), m.start(0), m.end(0)


class TracLinkExtension(Extension):
    """For registering the Trac link processor"""

    TRAC_LINK_PATTERN = r'\[(.+?)\]'

    def extendMarkdown(self, md):
        # Use priority 115 so the markdown link processor with priority 160
        # may resolve links like [example](http://...) properly without our
        # extension breaking the link.
        # Same goes for shortrefs like [Google] with priority 130
        # and autolinks using priority 120.
        md.inlinePatterns.register(TracLinkInlineProcessor(self.TRAC_LINK_PATTERN, md), 'traclink', 115)


class TracMacroInlineProcessor(InlineProcessor):
    """Render Trac macros ('[FooBar()]').

    The macro is extracted from the text and formatted
    using Tracs wiki formatter.
    """
    def handleMatch(self, m, data):
        # This is a Trac macro '[[FooBar()]]
        # return None, None, None

        html = format_to_html(self.md.trac_env, self.md.trac_context, '[[%s]]' % m.group(1))
        return self.md.htmlStash.store(html), m.start(0), m.end(0)


class TracMacroExtension(Extension):
    """Register the Trac macro processor."""

    TRAC_MACRO_PATTERN = r'\[\[(.*?)\]\]'

    def extendMarkdown(self, md):
        md.inlinePatterns.register(TracMacroInlineProcessor(self.TRAC_MACRO_PATTERN, md), 'tracmacro', 172)


class TracTicketInlineProcessor(InlineProcessor):
    """Support simple Trac ticket links like '#123'."""
    def handleMatch(self, m, data):
        html = format_to_oneliner(self.md.trac_env, self.md.trac_context, '#%s' % m.group(1))
        return self.md.htmlStash.store(html), m.start(0), m.end(0)


class TracTicketExtension(Extension):
    """Register the ticket link extension."""

    TRAC_TICKET_PATTERN = r'#(\d+)'

    def extendMarkdown(self, md):
        # Use priority 115 so the markdown link processor with priority 160
        # may resolve links with location part like [example](http://example.com/foo#123) properly
        # without our extension breaking the link.
        # Same goes for autolinks <http://...> with priority 120.
        md.inlinePatterns.register(TracTicketInlineProcessor(self.TRAC_TICKET_PATTERN, md), 'tracticket', 115)


class TracClassTreeprocessor(Treeprocessor):
    """Tree processor which applies Trac classes to some elements
       so the styling is Trac like.
    """

    def run(self, root):
        elms = root.iter(None)
        for elm in elms:
            if elm.tag in ('table', 'pre'):
                elm.set('class', 'wiki')
            elif elm.tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
                elm.set('class', 'section')

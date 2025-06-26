# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 Cinc
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.
#
"""Add Markdown preview rendering."""
from trac.config import Component, implements
from trac.mimeview.api import content_to_unicode, IHTMLPreviewRenderer
from tracmarkdown.macro import format_to_markdown, tab_length


class MarkdownPreviewRenderer(Component):
    """Preview renderer for files in the repository."""

    implements(IHTMLPreviewRenderer)

    tab_length = tab_length

    # IHTMLPreviewRenderer methods

    def get_extra_mimetypes(self):
        yield 'text/markdown', ['md']

    def get_quality_ratio(self, mimetype):
        if mimetype in('text/markdown', 'text/x-markdown'):
            return 8
        return 0

    def render(self, context, mimetype, content, filename=None, url=None):
        return format_to_markdown(self, context, content_to_unicode(self.env, content, mimetype))

# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 Cinc
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.
#
import re
from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor
from trac.wiki.formatter import format_to_html


class WikiProcessorExtension(Extension):
    def extendMarkdown(self, md):
        """Add to the Markdown instance."""
        md.preprocessors.register(WikiProcessorPreprocessor(md), 'trac_wiki_processor', 25)


class WikiProcessorPreprocessor(Preprocessor):
    """Support for Trac WikiProcessors using Trac syntax.

    This supports nested WikiProcessors.
    """

    wp_open_re = re.compile(r'\{{3,3}#!|\{{3,3}[\s]*$')
    wp_close_re = re.compile(r'}{3,3}[\s]*$')

    def run(self, lines):
        """  """
        proc_lines = []
        wp_lines = []
        lvl = 0

        for idx, line in enumerate(lines):
            if re.match(self.wp_open_re, line):
                # Opening '{{{'
                lvl += 1
                wp_lines.append(line)
            elif lvl:
                # Inside a WikiProcessor
                wp_lines.append(line)
                if re.match(self.wp_close_re, line):
                    # Closing tag '}}}'
                    lvl -= 1
                    if not lvl:
                        # Outermost WikiProcessor was closed
                        html = format_to_html(self.md.trac_env, self.md.trac_context,
                                              '\n'.join(wp_lines))
                        proc_lines.append(self.md.htmlStash.store(html))
                        wp_lines = []
            else:
                proc_lines.append(line)

        return proc_lines


class WikiProcessorFenceExtension(Extension):

    def extendMarkdown(self, md):
        """Add to the Markdown instance."""

        # We register with higher priority as the code fence extension coming with markdown
        md.preprocessors.register(WikiProcessorFencePreprocessor(md), 'trac_wiki_processor_fence', 28)


class WikiProcessorFencePreprocessor(Preprocessor):
    """Special code fence processor replacing any code fences with Trac WikiProcessors.

    We are replacing any fence with braces:

        ```language
        Some code here
        ```

    is converted to:

        {{{#!language
        Some code here
        }}}

    This also preserves parameters of WikiProcessors like:

        ```div style="border: 1px solid blue;"
        Some text in a box.
        ```
    """
    FENCED_BLOCK_RE = re.compile(r'''
    (?P<fence>^(?:~{3,}|`{3,}))[ ]*    # Opening ``` or ~~~
    (?P<code>.*?)(?<=\n)
    (?P=fence)[ ]*$''', re.MULTILINE | re.DOTALL | re.VERBOSE)
    ALPHANUM = re.compile(r'[\w]')

    def run(self, lines):
        def callback(match):
            txt = match.group(2)
            if txt.startswith('\n#!'):
                # First line of content specifies the type of content
                return "{{{%s}}}\n" % match.group(2)
            elif self.ALPHANUM.match(txt):
                # Do we have any language specifier following? If yes add '#!'.
                # The re returns 'None' if the text holds a '\n' before any alphanums
                return "{{{#!%s}}}\n" % match.group(2)
            else:
                return "{{{%s}}}\n" % match.group(2)

        text = '\n'.join(lines)
        text = self.FENCED_BLOCK_RE.sub(callback, text)
        # text = self.FENCED_BLOCK_RE.sub(r"{{{#!\2}}}\n", text)
        return text.split('\n')

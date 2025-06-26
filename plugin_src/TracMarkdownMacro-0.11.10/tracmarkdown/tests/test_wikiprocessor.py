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
from tracmarkdown.macro import WikiProcessorExtension, WikiProcessorFenceExtension


class TestWikiProcessor(unittest.TestCase):

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

    def test_wikiprocessor(self):
        content = """{{{
content
}}}
"""
        expected = """<pre class="wiki">content
</pre>"""
        wp = WikiProcessorExtension()
        md = self.prepare_markup_class(['extra', wp])
        self.assertEqual(expected, md.convert(content))

    def test_codefence_empty(self):
        """Check code fence without contents."""
        content = """```
  
```
"""
        expected = """<pre class="wiki">
</pre>"""
        wp = WikiProcessorExtension()
        wf = WikiProcessorFenceExtension()
        md = self.prepare_markup_class(['extra', wp, wf])
        self.assertEqual(expected, md.convert(content))

    def test_codefence_no_lang(self):
        """Check naked code fence"""
        content = """```
content
```
"""
        expected = """<pre class="wiki">content
</pre>"""
        wp = WikiProcessorExtension()
        wf = WikiProcessorFenceExtension()
        md = self.prepare_markup_class(['extra', wp, wf])
        self.assertEqual(expected, md.convert(content))

    def test_codefence_language(self):
        """Check if a language specifier is working here"""
        content = """```python
content
```
"""
        expected = """<div class="wiki-code"><div class="code"><pre>content
</pre></div></div>"""
        wp = WikiProcessorExtension()
        wf = WikiProcessorFenceExtension()
        md = self.prepare_markup_class(['extra', wp, wf])
        self.assertEqual(expected, md.convert(content))

    def test_codefence_line_spec(self):
        """Check if a language specifier in the first lineis working here"""
        content = """```
#!python
content
```
"""
        expected = """<div class="wiki-code"><div class="code"><pre>content
</pre></div></div>"""
        wp = WikiProcessorExtension()
        wf = WikiProcessorFenceExtension()
        md = self.prepare_markup_class(['extra', wp, wf])
        self.assertEqual(expected, md.convert(content))


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/env python
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
import sys
import os.path
from setuptools import setup

if sys.version_info.major == 2:
    markdown = ['Markdown < 3.2']
else:
    markdown = ['Markdown']


setup(
    name='TracMarkdownMacro',
    packages=['tracmarkdown'],
    version='0.11.10',
    author='Douglas Clifton',
    author_email='dwclifton@gmail.com',
    maintainer='Cinc-th',
    maintainer_email='',
    description='Implements Markdown syntax WikiProcessor as a Trac macro.',
    long_description=open(
        os.path.join(os.path.dirname(__file__), 'README')).read(),
    long_description_content_type='text/markdown',
    keywords='0.11 dwclifton processor macro wiki',
    url='https://trac-hacks.org/wiki/MarkdownMacro',
    license='BSD 3-Clause',
    package_data={'tracmarkdown': ['htdocs/css/*.css',
                                 ]},
    entry_points={'trac.plugins': ['tracmarkdown.macro = tracmarkdown.macro',
                                   'tracmarkdown.preview_renderer = tracmarkdown.preview_renderer']},
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Plugins',
        'Environment :: Web Environment',
        'Framework :: Trac',
        'License :: OSI Approved :: BSD License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
    ],
    install_requires=['Trac'] + markdown,
)

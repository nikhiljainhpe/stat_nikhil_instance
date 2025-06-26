#! /usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import find_packages, setup

kwargs = dict(
    name = 'TracWorkflowAdmin',
    version = '0.12.0.7',
    packages = find_packages(exclude=['*.tests*']),
    package_data = {
        'tracworkflowadmin': [
            'templates/genshi/*.html',
            'templates/jinja2/*.html',
            'htdocs/*.gif',
            'htdocs/css/*.css',
            'htdocs/scripts/*.js',
            'htdocs/scripts/messages/*.js',
            'htdocs/themes/*/*.css',
            'htdocs/themes/*/images/*.png',
            'locale/*.*',
            'locale/*/LC_MESSAGES/*.mo',
        ],
    },
    entry_points = {
        'trac.plugins': [
            'tracworkflowadmin.web_ui = tracworkflowadmin.web_ui',
        ],
    },
    author = 'OpenGroove,Inc.',
    author_email = 'trac@opengroove.com',
    url = 'https://trac-hacks.org/wiki/TracWorkflowAdminPlugin',
    description = 'Web interface for workflow administration of Trac',
    license = 'BSD',  # the same license as Trac
    classifiers = [
        'Framework :: Trac',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
    ],
)

try:
    import babel
    from trac.util.dist import get_l10n_js_cmdclass
except ImportError:
    pass
else:
    kwargs['cmdclass'] = get_l10n_js_cmdclass()

if __name__ == '__main__':
    setup(**kwargs)

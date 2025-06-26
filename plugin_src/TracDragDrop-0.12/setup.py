#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

def main():
    extra = {}

    try:
        import babel
        from trac.util.dist import get_l10n_js_cmdclass
    except ImportError:
        pass
    else:
        extra['message_extractors'] = {
            'tracdragdrop': [('**.py', 'python', None)],
        }
        extra['cmdclass'] = get_l10n_js_cmdclass()

    setup(
        name = 'TracDragDrop',
        version = '0.12.0.17',
        description = 'Add drag-and-drop attachments feature to Trac',
        license = 'BSD', # the same as Trac
        url = 'https://trac-hacks.org/wiki/TracDragDropPlugin',
        author = 'Jun Omae',
        author_email = 'jun66j5@gmail.com',
        install_requires = ['Trac'],
        packages = find_packages(exclude=['*.tests*']),
        package_data = {
            'tracdragdrop': [
                'htdocs/*.js', 'htdocs/*.css', 'htdocs/*.gif',
                'templates/genshi/*.html', 'templates/jinja2/*.html',
                'htdocs/messages/*.js', 'locale/*/LC_MESSAGES/tracdragdrop.mo',
            ],
        },
        entry_points = {
            'trac.plugins': [
                'tracdragdrop.web_ui = tracdragdrop.web_ui',
            ],
        },
        **extra)

if __name__ == '__main__':
    main()

#!/usr/bin/env python

from setuptools import find_packages, setup

setup(
    author = 'Jonathan Ashley <trac@ifton.co.uk>',
    license = 'GPLv3',
    name = 'KeepInterfaceSimple2Plugin',
    version='2.6',
    description = 'Makes it easier for users when tickets have a complex workflow. Fields that don\'t need to be completed at a given time can be hidden, and commits can be prevented if not all the information required has been provided.',
    packages = ['kis2'],
    package_data = { 'kis2': ['htdocs/*.js'] },
    entry_points = """
        [trac.plugins]
        kis2 = kis2.kis
    """,
)

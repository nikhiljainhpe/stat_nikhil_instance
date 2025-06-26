#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2008 The Open Planning Project
#
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.

from setuptools import find_packages, setup

setup(name='TracBacks',
      version='0.3.0',
      packages=find_packages(exclude=['*.tests*']),
      url="https://trac-hacks.org/wiki/TracBacksPlugin",
      license='3-Clause BSD',
      entry_points="""
      [trac.plugins]
      tracbacks = tracbacks
      """,
      )


# -*- coding: utf-8 -*-
"""
License: BSD

(c) 2005-2008 ::: Alec Thomas (alec@swapoff.org)
(c) 2009-2013 ::: www.CodeResort.com - BV Network AS (simon-code@bvnetwork.no)
"""

import functools
import inspect
import sys

from trac.util.translation import dgettext, domain_functions


# Supported Python versions:
PY24 = sys.version_info[:2] == (2, 4)
PY25 = sys.version_info[:2] == (2, 5)
PY26 = sys.version_info[:2] == (2, 6)
PY27 = sys.version_info[:2] == (2, 7)
PY3 = sys.version_info[0] > 2


if sys.version_info[0] == 2:
    unicode = unicode
    basestring = basestring
    unichr = unichr
    iteritems = lambda d: d.iteritems()
    from itertools import izip
    import xmlrpclib
else:
    unicode = str
    basestring = str
    unichr = chr
    iteritems = lambda d: d.items()
    izip = zip
    from xmlrpc import client as xmlrpclib


i18n_domain = 'tracrpc'
add_domain, ngettext, tag_ = domain_functions(
    i18n_domain, ('add_domain', 'ngettext', 'tag_'))

# XXX Use directly `dgettext` instead of `gettext` returned from
# `domain_functions` because translation doesn't work caused by multiple
# white-spaces in msgid are replaced by single space.
_ = gettext = functools.partial(dgettext, i18n_domain)


try:
    from trac.util.translation import cleandoc_
except ImportError:
    cleandoc_ = lambda message: inspect.cleandoc(message).strip()


getargspec = inspect.getfullargspec \
             if hasattr(inspect, 'getfullargspec') else \
             inspect.getargspec


try:
    from trac.web.chrome import web_context
except ImportError:
    from trac.mimeview.api import Context
    web_context = Context.from_request
    del Context


def accepts_mimetype(req, mimetype):
    if isinstance(mimetype, basestring):
        mimetype = (mimetype,)
    accept = req.get_header('Accept')
    if accept is None:
        # Don't make judgements if no MIME type expected and method is GET
        return req.method == 'GET'
    else:
        accept = accept.split(',')
        return any(x.strip().startswith(y) for x in accept for y in mimetype)


def to_b(value):
    if isinstance(value, unicode):
        return value.encode('utf-8')
    if isinstance(value, bytes):
        return value
    raise TypeError(str(type(value)))

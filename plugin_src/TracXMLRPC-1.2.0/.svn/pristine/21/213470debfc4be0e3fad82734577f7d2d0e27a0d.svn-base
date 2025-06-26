# -*- coding: utf-8 -*-
"""
License: BSD

(c) 2013 ::: Jun Omae (jun66j5@gmail.com)
"""

import unittest

from ..util import xmlrpclib
from . import TracRpcTestCase, TracRpcTestSuite, makeSuite


class RpcSearchTestCase(TracRpcTestCase):

    def setUp(self):
        TracRpcTestCase.setUp(self)
        self.anon = xmlrpclib.ServerProxy(self._testenv.url_anon)
        self.user = xmlrpclib.ServerProxy(self._testenv.url_user)
        self.admin = xmlrpclib.ServerProxy(self._testenv.url_admin)

    def tearDown(self):
        for proxy in (self.anon, self.user, self.admin):
            proxy('close')()
        TracRpcTestCase.tearDown(self)

    def test_fragment_in_search(self):
        t1 = self.admin.ticket.create("ticket10786", "",
                        {'type': 'enhancement', 'owner': 'A'})
        results = self.user.search.performSearch("ticket10786")
        self.assertEqual(1, len(results))
        self.assertEqual('<span class="new">#%d</span>: enhancement: '
                         'ticket10786 (new)' % t1, results[0][1])
        self.assertEqual(0, self.admin.ticket.delete(t1))

    def test_search_none_result(self):
        # Some plugins may return None instead of empty iterator
        # https://trac-hacks.org/ticket/12950

        # Add custom plugin to provoke error
        source = r"""# -*- coding: utf-8 -*-
from trac.core import *
from trac.search.api import ISearchSource
class NoneSearch(Component):
    implements(ISearchSource)
    def get_search_filters(self, req):
        yield ('test', 'Test')
    def get_search_results(self, req, terms, filters):
        self.log.debug('Search plugin returning None')
        return None
"""
        with self._plugin(source, 'NoneSearchPlugin.py'):
            results = self.user.search.performSearch("nothing_should_be_found")
            self.assertEqual([], results)


def test_suite():
    suite = TracRpcTestSuite()
    suite.addTest(makeSuite(RpcSearchTestCase))
    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

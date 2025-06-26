# -*- coding: utf-8 -*-
"""
License: BSD

(c) 2009-2013 ::: www.CodeResort.com - BV Network AS (simon-code@bvnetwork.no)
"""
__all__ = ()

import base64
import contextlib
import os
import socket
import subprocess
import sys
import time
import unittest

if sys.version_info[0] == 2:
    from urllib2 import BaseHandler, HTTPError, Request, build_opener, urlopen
    from urllib import urlencode
    from urlparse import urlparse, urlsplit
    HTTPBasicAuthHandler = HTTPPasswordMgrWithPriorAuth = None
else:
    from urllib.error import HTTPError
    from urllib.parse import urlencode, urlparse, urlsplit
    from urllib.request import (HTTPBasicAuthHandler,
                                HTTPPasswordMgrWithPriorAuth, Request,
                                build_opener, urlopen)

from trac.env import Environment
from trac.util import create_file
from trac.util.compat import close_fds

from ..util import to_b

try:
    from trac.test import MockRequest
except ImportError:
    def MockRequest(env):
        import io
        from trac.test import MockPerm
        from trac.util.datefmt import utc
        from trac.web.api import Request as TracRequest
        from trac.web.main import FakeSession
        out = io.BytesIO()
        environ = {'wsgi.url_scheme': 'http', 'wsgi.input': io.BytesIO(b''),
                   'REQUEST_METHOD': 'GET', 'SERVER_NAME': 'example.org',
                   'SERVER_PORT': 80, 'SCRIPT_NAME': '/trac',
                   'trac.base_url': 'http://example.org/trac'}
        start_response = lambda status, headers: out.write
        req = TracRequest(environ, start_response)
        req.callbacks.update({
            'authname': lambda req: 'anonymous',
            'perm': lambda req: MockPerm(),
            'session': lambda req: FakeSession(),
            'chrome': lambda req: {},
            'tz': lambda req: utc,
            'locale': lambda req: None,
            'form_token': lambda req: 'A' * 20,
        })
        return req

try:
    from trac.test import rmtree
except ImportError:
    from shutil import rmtree


def _get_topdir():
    path = os.path.dirname(os.path.abspath(__file__))
    suffix = '/tracrpc/tests'.replace('/', os.sep)
    if not path.endswith(suffix):
        raise RuntimeError("%r doesn't end with %r" % (path, suffix))
    return path[:-len(suffix)]


def _get_testdir():
    dir_ = os.environ.get('TMP') or _get_topdir()
    if not os.path.isabs(dir_):
        raise RuntimeError('Non absolute directory: %s' % repr(dir_))
    return os.path.join(dir_, 'rpctestenv')


if HTTPPasswordMgrWithPriorAuth:
    def _build_opener_auth(url, user, password):
        manager = HTTPPasswordMgrWithPriorAuth()
        manager.add_password(None, url, user, password, is_authenticated=True)
        handler = HTTPBasicAuthHandler(manager)
        return build_opener(handler)
else:
    class HTTPBasicAuthPriorHandler(BaseHandler):

        def __init__(self, url, user, password):
            self.url = url
            self.user = user
            self.password = password

        def http_request(self, request):
            if not request.has_header('Authorization') and \
                    self.url == request.get_full_url():
                cred = '%s:%s' % (self.user, self.password)
                encoded = b64encode(to_b(cred))
                request.add_header('Authorization', 'Basic ' + encoded)
            return request

    def _build_opener_auth(url, user, password):
        handler = HTTPBasicAuthPriorHandler(url, user, password)
        return build_opener(handler)


class RpcTestEnvironment(object):

    _testdir = _get_testdir()
    _plugins_dir = os.path.join(_testdir, 'plugins')
    _devnull = None
    _log = None
    _port = None
    _envpath = None
    _htpasswd = None
    _env = None
    _tracd = None
    url = None
    url_anon = None
    url_auth = None
    url_user = None
    url_admin = None

    def __init__(self):
        if os.path.isdir(self._testdir):
            rmtree(self._testdir)
        os.mkdir(self._testdir)
        os.mkdir(self._plugins_dir)

    @property
    def tracdir(self):
        return self._envpath

    def init(self):
        self._devnull = os.open(os.devnull, os.O_RDWR)
        self._log = os.open(os.path.join(self._testdir, 'tracd.log'),
                            os.O_WRONLY | os.O_CREAT | os.O_APPEND)
        self._port = get_ephemeral_port()
        self.check_call([sys.executable, 'setup.py', 'develop', '-mxd',
                         self._plugins_dir])
        self._envpath = os.path.join(self._testdir, 'trac')
        self.url = 'http://127.0.0.1:%d/%s' % \
                   (self._port, os.path.basename(self._envpath))
        self._htpasswd = os.path.join(self._testdir, 'htpasswd.txt')
        create_file(self._htpasswd,
                    'admin:$apr1$CJoMFGDO$W5ERyxnTl6qAUa9BbE0QV1\n'
                    'user:$apr1$ZQuTwNFe$ReYgDiL/gduTvjO29qdYx0\n')
        inherit = os.path.join(self._testdir, 'inherit.ini')
        with open(inherit, 'w') as f:
            f.write('[inherit]\n'
                    'plugins_dir = %s\n'
                    '[components]\n'
                    'tracrpc.* = enabled\n'
                    '[logging]\n'
                    'log_type = file\n'
                    'log_level = INFO\n'
                    '[trac]\n'
                    'base_url = %s\n' %
                    (self._plugins_dir, self.url))
        args = [sys.executable, '-m', 'trac.admin.console', self._envpath]
        with self.popen(args, stdin=subprocess.PIPE) as proc:
            proc.stdin.write(
                b'initenv --inherit=%s project sqlite:db/trac.db\n'
                b'permission add admin TRAC_ADMIN\n'
                b'permission add anonymous XML_RPC\n'
                % to_b(inherit))
        self.url_anon = '%s/rpc' % self.url
        self.url_auth = '%s/login/rpc' % self.url
        self.url_user = '%s/login/xmlrpc' % \
                        self.url.replace('://', '://user:user@')
        self.url_admin = '%s/login/xmlrpc' % \
                         self.url.replace('://', '://admin:admin@')
        self.start()

    def cleanup(self):
        self.stop()
        if self._env:
            self._env.shutdown()
            self._env = None
        if self._devnull is not None:
            os.close(self._devnull)
            self._devnull = None
        if self._log is not None:
            os.close(self._log)
            self._log = None

    def start(self):
        if self._tracd and self._tracd.returncode is None:
            raise RuntimeError('tracd is running')
        args = [
            sys.executable, '-m', 'trac.web.standalone',
            '--port=%d' % self._port,
            '--basic-auth=*,%s,realm' % self._htpasswd, self._envpath,
        ]
        self._tracd = self.popen(args, stdout=self._log, stderr=self._log)
        start = time.time()
        while time.time() - start < 10:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                s.connect(('127.0.0.1', self._port))
            except socket.error:
                time.sleep(0.125)
            else:
                break
            finally:
                s.close()
        else:
            raise RuntimeError('Timed out waiting for tracd to start')

    def stop(self):
        if self._tracd:
            try:
                self._tracd.terminate()
            except EnvironmentError:
                pass
            self._tracd.wait()
            self._tracd = None

    def restart(self):
        self.stop()
        self.start()

    def popen(self, *args, **kwargs):
        kwargs.setdefault('stdin', self._devnull)
        kwargs.setdefault('stdout', self._devnull)
        kwargs.setdefault('stderr', self._devnull)
        kwargs.setdefault('close_fds', close_fds)
        return Popen(*args, **kwargs)

    def check_call(self, *args, **kwargs):
        kwargs.setdefault('stdin', self._devnull)
        kwargs.setdefault('stdout', subprocess.PIPE)
        kwargs.setdefault('stderr', subprocess.PIPE)
        with self.popen(*args, **kwargs) as proc:
            stdout, stderr = proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError('Exited with %d (stdout %r, stderr %r)' %
                                   (proc.returncode, stdout, stderr))

    def get_trac_environment(self):
        if not self._env:
            self._env = Environment(self._envpath)
        return self._env

    def _tracadmin(self, *args):
        self.check_call((sys.executable, '-m', 'trac.admin.console',
                         self._envpath) + args)


if hasattr(subprocess.Popen, '__enter__'):
    Popen = subprocess.Popen
else:
    class Popen(subprocess.Popen):

        def __enter__(self):
            return self

        def __exit__(self, *args):
            try:
                if self.stdin:
                    self.stdin.close()
            finally:
                self.wait()
            for f in (self.stdout, self.stderr):
                if f:
                    f.close()


def get_ephemeral_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('127.0.0.1', 0))
        s.listen(1)
        return s.getsockname()[1]
    finally:
        s.close()


_rpc_testenv = None


def _new_testenv():
    global _rpc_testenv
    if not _rpc_testenv:
        _rpc_testenv = RpcTestEnvironment()
        _rpc_testenv.init()


def _del_testenv():
    global _rpc_testenv
    if _rpc_testenv:
        _rpc_testenv.cleanup()
        _rpc_testenv = None


class TracRpcTestCase(unittest.TestCase):

    @property
    def _testenv(self):
        return _rpc_testenv

    def _opener_auth(self, url, user, password):
        return _build_opener_auth(url, user, password)

    @contextlib.contextmanager
    def _plugin(self, source, filename):
        filename = os.path.join(_rpc_testenv.tracdir, 'plugins', filename)
        create_file(filename, source)
        try:
            _rpc_testenv.restart()
            yield
        finally:
            os.unlink(filename)
            _rpc_testenv.restart()

    def _grant_perm(self, username, *actions):
        _rpc_testenv._tracadmin('permission', 'add', username, *actions)
        _rpc_testenv.restart()

    def _revoke_perm(self, username, *actions):
        _rpc_testenv._tracadmin('permission', 'remove', username, *actions)
        _rpc_testenv.restart()


class TracRpcTestSuite(unittest.TestSuite):

    def run(self, result):
        if _rpc_testenv:
            created = False
        else:
            _new_testenv()
            created = True
        try:
            return super(TracRpcTestSuite, self).run(result)
        finally:
            if created:
                _del_testenv()


def b64encode(s):
    if not isinstance(s, bytes):
        s = s.encode('utf-8')
    rv = base64.b64encode(s)
    if isinstance(rv, bytes):
        rv = rv.decode('ascii')
    return rv


def form_urlencoded(data):
    return to_b(urlencode(data))


def makeSuite(testCaseClass, suiteClass=unittest.TestSuite):
    loader = unittest.TestLoader()
    loader.suiteClass = suiteClass
    return loader.loadTestsFromTestCase(testCaseClass)


def test_suite():
    suite = TracRpcTestSuite()
    from . import api, xml_rpc, json_rpc, ticket, wiki, web_ui, search
    for mod in (api, xml_rpc, json_rpc, ticket, wiki, web_ui, search):
        suite.addTest(mod.test_suite())
    return suite

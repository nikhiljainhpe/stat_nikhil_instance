# -*- coding: utf-8 -*-
"""
License: BSD

(c) 2009      ::: www.CodeResort.com - BV Network AS (simon-code@bvnetwork.no)
"""

import base64
import datetime
import json
import re
import sys

try:
    import babel
except ImportError:
    babel = None

from trac.core import Component, implements
from trac.perm import PermissionError
from trac.resource import ResourceNotFound
from trac.util.datefmt import FixedOffset, utc
from trac.util.html import Fragment, Markup
from trac.util.text import empty, exception_to_unicode, to_unicode
from trac.web.api import HTTPBadRequest, RequestDone

from .api import IRPCProtocol, Binary, MethodNotFound, ProtocolException
from .util import cleandoc_, gettext, iteritems, unicode, izip


__all__ = ['JsonRpcProtocol']


class TracRpcJSONEncoder(json.JSONEncoder):
    """ Extending the JSON encoder to support some additional types:
    1. datetime.datetime => {'__jsonclass__': ["datetime", "<rfc3339str>"]}
    2. tracrpc.api.Binary => {'__jsonclass__': ["binary", "<base64str>"]}
    3. empty => ''
    4. Fragment|Markup => unicode
    5. babel.support.LazyProxy => unicode
    """

    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            # http://www.ietf.org/rfc/rfc3339.txt
            if obj.tzinfo is None:
                obj = obj.replace(tzinfo=utc)
            elif obj.tzinfo is not utc:
                obj = obj.astimezone(utc)
            value = obj.strftime('%Y-%m-%dT%H:%M:%S')
            if obj.microsecond != 0:
                value += '.%06d' % obj.microsecond
            return {'__jsonclass__': ["datetime", value]}
        if isinstance(obj, Binary):
            encoded = base64.b64encode(obj.data)
            if not isinstance(encoded, str):
                encoded = unicode(encoded, 'ascii')
            return {'__jsonclass__': ["binary", encoded]}
        if obj is empty:
            return ''
        if isinstance(obj, (Fragment, Markup)):
            return unicode(obj)
        if babel and isinstance(obj, babel.support.LazyProxy):
            return unicode(obj)
        return super(TracRpcJSONEncoder, self).default(obj)


class TracRpcJSONDecoder(json.JSONDecoder):
    """ Extending the JSON decoder to support some additional types:
    1. {'__jsonclass__': ["datetime", "<rfc3339str>"]} => datetime.datetime
    2. {'__jsonclass__': ["binary", "<base64str>"]} => tracrpc.api.Binary """

    _datetime_re = re.compile(r"""
        \A
        ([0-9]{4})-([0-9]{2})-([0-9]{2})
        (?:
            [Tt_ ]
            ([0-9]{2}):([0-9]{2}):([0-9]{2})
            (?:\.([0-9]{1,}))?
            ([Zz]|[-+][0-9]{2}:[0-5][0-9])?
        )?
        \Z
        """, re.VERBOSE)

    @classmethod
    def _parse_datetime(cls, val):
        match = cls._datetime_re.match(val)
        if not match:
            raise Exception("Invalid datetime string (%s)" % val)

        def convert(idx, arg):
            if idx < 3:
                return int(arg)
            if idx < 6:
                return int(arg) if arg else 0
            if idx == 6:
                return int((arg + '00000')[:6]) if arg else 0
            if idx == 7:
                if arg in (None, 'Z', 'z'):
                    return utc
                hour = int(arg[1:3])
                minute = int(arg[4:6])
                offset = hour * 60 + minute
                if offset == 0:
                    return utc
                if arg.startswith('-'):
                    offset = -offset
                name = '%s%d:%02d' % (arg[:1], hour, minute)
                return FixedOffset(offset, name)

        args = [convert(idx, arg) for idx, arg in enumerate(match.groups())]
        try:
            return datetime.datetime(*args)
        except:
            raise Exception("Invalid datetime string (%s)" % val)

    @classmethod
    def _parse_binary(cls, val):
        try:
            data = base64.b64decode(val)
        except:
            raise Exception("Invalid base64 string")
        else:
            return Binary(data)

    def _normalize(self, obj):
        """ Helper to traverse JSON decoded object for custom types. """
        normalize = self._normalize
        if isinstance(obj, tuple):
            return tuple(normalize(item) for item in obj)
        if isinstance(obj, list):
            return [normalize(item) for item in obj]
        if isinstance(obj, unicode):
            return obj
        if isinstance(obj, bytes):
            return to_unicode(obj)
        if isinstance(obj, dict):
            if len(obj) != 1 or tuple(obj) != ('__jsonclass__',):
                return dict(normalize(item) for item in iteritems(obj))
            kind, val = obj['__jsonclass__']
            if kind == 'datetime':
                return self._parse_datetime(val)
            if kind == 'binary':
                return self._parse_binary(val)
            raise Exception("Unknown __jsonclass__: %s" % kind)
        return obj

    def decode(self, obj, *args, **kwargs):
        obj = super(TracRpcJSONDecoder, self).decode(obj, *args, **kwargs)
        return self._normalize(obj)


class JsonProtocolException(ProtocolException):
    """Impossible to handle JSON-RPC request."""
    def __init__(self, details, code=-32603, title=None, show_traceback=False):
        ProtocolException.__init__(self, details, title, show_traceback)
        self.code = code


class JsonRpcProtocol(Component):

    _descritpion = cleandoc_(r"""
    Example `POST` request using `curl` with `Content-Type` header
    and body:

    {{{
    user: ~ > cat body.json
    {"params": ["WikiStart"], "method": "wiki.getPage", "id": 123}
    user: ~ > curl -H "Content-Type: application/json" --data @body.json %(url_anon)s
    {"id": 123, "error": null, "result": "= Welcome to....
    }}}

    Implementation details:

      * JSON-RPC has no formalized type system, so a class-hint system is used
        for input and output of non-standard types:
        * `{"__jsonclass__": ["datetime", "YYYY-MM-DDTHH:MM:SS"]} => DateTime (UTC)`
        * `{"__jsonclass__": ["binary", "<base64-encoded>"]} => Binary`
      * `"id"` is optional, and any marker value received with a
        request is returned with the response.
    """)

    implements(IRPCProtocol)

    # IRPCProtocol methods

    def rpc_info(self):
        return 'JSON-RPC', gettext(self._descritpion)

    def rpc_match(self):
        yield 'rpc', 'application/json'
        # Legacy path - provided for backwards compatibility:
        yield 'jsonrpc', 'application/json'

    def parse_rpc_request(self, req, content_type):
        """ Parse JSON-RPC requests"""
        try:
            data = json_load(req)
        except Exception as e:
            self.log.warning("RPC(json) decode error: %s",
                             exception_to_unicode(e))
            if sys.version_info[0] == 2:
                message = to_unicode(e)
            else:
                message = 'No JSON object could be decoded (%s)' % e
            raise JsonProtocolException(message, -32700)
        if not isinstance(data, dict):
            self.log.warning("RPC(json) decode error (not a dict)")
            raise JsonProtocolException('JSON object is not a dict', -32700)

        try:
            self.log.info("RPC(json) JSON-RPC request ID : %s.", data.get('id'))
            if data.get('method') == 'system.multicall':
                # Prepare for multicall
                self.log.debug("RPC(json) Multicall request %s", data)
                params = data.get('params', [])
                for signature in params:
                    signature['methodName'] = signature.get('method', '')
                data['params'] = [params]
            return data
        except Exception as e:
            # Abort with exception - no data can be read
            self.log.warning("RPC(json) decode error: %s",
                             exception_to_unicode(e))
            raise JsonProtocolException(e, -32700)

    def send_rpc_result(self, req, result):
        """Send JSON-RPC response back to the caller."""
        rpcreq = req.rpc
        r_id = rpcreq.get('id')
        try:
            if rpcreq.get('method') == 'system.multicall':
                # Custom multicall
                args = (rpcreq.get('params') or [[]])[0]
                mcresults = [self._json_result(
                                        isinstance(value, Exception) and \
                                                    value or value[0], \
                                        sig.get('id') or r_id) \
                              for sig, value in izip(args, result)]

                response = self._json_result(mcresults, r_id)
            else:
                response = self._json_result(result, r_id)
            self.log.debug("RPC(json) result: %r", response)
            try:  # JSON encoding
                response = json.dumps(response, cls=TracRpcJSONEncoder)
            except Exception as e:
                self.log.warning("RPC(json) dumps error: %s",
                                 exception_to_unicode(e))
                response = json.dumps(self._json_error(e, r_id=r_id),
                                        cls=TracRpcJSONEncoder)
        except Exception as e:
            self.log.error("RPC(json) error%s",
                           exception_to_unicode(e, traceback=True))
            response = json.dumps(self._json_error(e, r_id=r_id),
                            cls=TracRpcJSONEncoder)
        self._send_response(req, response + '\n', rpcreq['mimetype'])

    def send_rpc_error(self, req, e):
        """Send a JSON-RPC fault message back to the caller. """
        rpcreq = req.rpc
        r_id = rpcreq.get('id')
        response = json.dumps(self._json_error(e, r_id=r_id), \
                                  cls=TracRpcJSONEncoder)
        self._send_response(req, response + '\n', rpcreq['mimetype'])

    # Internal methods

    def _send_response(self, req, response, content_type='application/json'):
        self.log.debug("RPC(json) encoded response: %s", response)
        response = to_unicode(response).encode("utf-8")
        req.send_response(200)
        req.send_header('Content-Type', content_type)
        req.send_header('Content-Length', len(response))
        req.end_headers()
        req.write(response)
        raise RequestDone()

    def _json_result(self, result, r_id=None):
        """ Create JSON-RPC response dictionary. """
        if not isinstance(result, Exception):
            return {'result': result, 'error': None, 'id': r_id}
        else:
            return self._json_error(result, r_id=r_id)

    def _json_error(self, e, c=None, r_id=None):
        """ Makes a response dictionary that is an error. """
        if isinstance(e, MethodNotFound):
            c = -32601
        elif isinstance(e, PermissionError):
            c = 403
        elif isinstance(e, ResourceNotFound):
            c = 404
        else:
            c = c or hasattr(e, 'code') and e.code or -32603
        return {'result': None, 'id': r_id, 'error': {
                'name': hasattr(e, 'name') and e.name or 'JSONRPCError',
                'code': c,
                'message': to_unicode(e)}}


class RequestReader(object):

    req = None
    remaining = None

    def __init__(self, req):
        length = req.get_header('Content-Length')
        if length is None:
            raise HTTPBadRequest('Missing Content-Length')
        try:
            length = int(length)
        except:
            raise HTTPBadRequest('Invalid Content-Length %r' % length)
        self.req = req
        self.remaining = length

    def read(self, n=-1):
        if self.remaining <= 0:
            return b''
        if n == -1:
            n = self.remaining
        data = self.req.read(min(n, self.remaining))
        if data:
            self.remaining -= len(data)
        return data


if sys.version_info[:2] != (3, 5):
    def json_load(req):
        return json.load(RequestReader(req), cls=TracRpcJSONDecoder)
else:
    import codecs
    def json_load(req):
        reader = codecs.getreader('utf-8')(RequestReader(req))
        return json.load(reader, cls=TracRpcJSONDecoder)

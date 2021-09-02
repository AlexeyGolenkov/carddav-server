import base64
import datetime
import io
import logging
import posixpath
import pprint
import random
import sys
import time
import xml.etree.ElementTree as ET
import zlib
from http import client

import pkg_resources

from CDserver import (auth, httputils, log, pathutils, rights, storage, web,
                      xmlutils)
from CDserver.app.delete import ApplicationDeleteMixin
from CDserver.app.get import ApplicationGetMixin
from CDserver.app.head import ApplicationHeadMixin
from CDserver.app.mkcalendar import ApplicationMkcalendarMixin
from CDserver.app.mkcol import ApplicationMkcolMixin
from CDserver.app.move import ApplicationMoveMixin
from CDserver.app.options import ApplicationOptionsMixin
from CDserver.app.post import ApplicationPostMixin
from CDserver.app.propfind import ApplicationPropfindMixin
from CDserver.app.proppatch import ApplicationProppatchMixin
from CDserver.app.put import ApplicationPutMixin
from CDserver.app.report import ApplicationReportMixin
from CDserver.log import logger

import defusedxml.ElementTree as DefusedET  # isort: skip
sys.modules["xml.etree"].ElementTree = ET

VERSION = "3.0.6"


class Application(
        ApplicationDeleteMixin, ApplicationGetMixin, ApplicationHeadMixin,
        ApplicationMkcalendarMixin, ApplicationMkcolMixin,
        ApplicationMoveMixin, ApplicationOptionsMixin,
        ApplicationPropfindMixin, ApplicationProppatchMixin,
        ApplicationPostMixin, ApplicationPutMixin,
        ApplicationReportMixin):


    def __init__(self, configuration):
        super().__init__()
        self.configuration = configuration
        self._auth = auth.load(configuration)
        self._storage = storage.load(configuration)
        self._rights = rights.load(configuration)
        self._web = web.load(configuration)
        self._encoding = configuration.get("encoding", "request")

    def _headers_log(self, environ):
        request_environ = dict(environ)

        # Mask passwords
        mask_passwords = self.configuration.get("logging", "mask_passwords")
        authorization = request_environ.get("HTTP_AUTHORIZATION", "")
        if mask_passwords and authorization.startswith("Basic"):
            request_environ["HTTP_AUTHORIZATION"] = "Basic **masked**"
        if request_environ.get("HTTP_COOKIE"):
            request_environ["HTTP_COOKIE"] = "**masked**"

        return request_environ

    def __call__(self, environ, start_response):
        with log.register_stream(environ["wsgi.errors"]):
            try:
                status, headers, answers = self._handle_request(environ)
            except Exception as e:
                try:
                    method = str(environ["REQUEST_METHOD"])
                except Exception:
                    method = "unknown"
                try:
                    path = str(environ.get("PATH_INFO", ""))
                except Exception:
                    path = ""
                logger.error("An exception occurred during %s request on %r: "
                             "%s", method, path, e, exc_info=True)
                status, headers, answer = httputils.INTERNAL_SERVER_ERROR
                answer = answer.encode("ascii")
                status = "%d %s" % (
                    status.value, client.responses.get(status, "Unknown"))
                headers = [
                    ("Content-Length", str(len(answer)))] + list(headers)
                answers = [answer]
            start_response(status, headers)
        return answers

    def _handle_request(self, environ):
        def response(status, headers=(), answer=None):
            headers = dict(headers)
            # Set content length
            if answer:
                if hasattr(answer, "encode"):
                    logger.debug("Response content:\n%s", answer)
                    headers["Content-Type"] += "; charset=%s" % self._encoding
                    answer = answer.encode(self._encoding)
                accept_encoding = [
                    encoding.strip() for encoding in
                    environ.get("HTTP_ACCEPT_ENCODING", "").split(",")
                    if encoding.strip()]

                if "gzip" in accept_encoding:
                    zcomp = zlib.compressobj(wbits=16 + zlib.MAX_WBITS)
                    answer = zcomp.compress(answer) + zcomp.flush()
                    headers["Content-Encoding"] = "gzip"

                headers["Content-Length"] = str(len(answer))

            for key in self.configuration.options("headers"):
                headers[key] = self.configuration.get("headers", key)

            time_end = datetime.datetime.now()
            status = "%d %s" % (
                status, client.responses.get(status, "Unknown"))
            logger.info(
                "%s response status for %r%s in %.3f seconds: %s",
                environ["REQUEST_METHOD"], environ.get("PATH_INFO", ""),
                depthinfo, (time_end - time_begin).total_seconds(), status)
            return status, list(headers.items()), [answer] if answer else []

        remote_host = "unknown"
        if environ.get("REMOTE_HOST"):
            remote_host = repr(environ["REMOTE_HOST"])
        elif environ.get("REMOTE_ADDR"):
            remote_host = environ["REMOTE_ADDR"]
        if environ.get("HTTP_X_FORWARDED_FOR"):
            remote_host = "%s (forwarded for %r)" % (
                remote_host, environ["HTTP_X_FORWARDED_FOR"])
        remote_useragent = ""
        if environ.get("HTTP_USER_AGENT"):
            remote_useragent = " using %r" % environ["HTTP_USER_AGENT"]
        depthinfo = ""
        if environ.get("HTTP_DEPTH"):
            depthinfo = " with depth %r" % environ["HTTP_DEPTH"]
        time_begin = datetime.datetime.now()
        logger.info(
            "%s request for %r%s received from %s%s",
            environ["REQUEST_METHOD"], environ.get("PATH_INFO", ""), depthinfo,
            remote_host, remote_useragent)
        headers = pprint.pformat(self._headers_log(environ))
        logger.debug("Request headers:\n%s", headers)

        if "HTTP_X_SCRIPT_NAME" in environ:
            unsafe_base_prefix = environ["HTTP_X_SCRIPT_NAME"]
            logger.debug("Script name overwritten by client: %r",
                         unsafe_base_prefix)
        else:
            unsafe_base_prefix = environ.get("SCRIPT_NAME", "")
        base_prefix = pathutils.sanitize_path(unsafe_base_prefix).rstrip("/")
        logger.debug("Sanitized script name: %r", base_prefix)
        path = pathutils.sanitize_path(environ.get("PATH_INFO", ""))
        logger.debug("Sanitized path: %r", path)

        function = getattr(
            self, "do_%s" % environ["REQUEST_METHOD"].upper(), None)
        if not function:
            return response(*httputils.METHOD_NOT_ALLOWED)

        if path == "/.well-known" or path.startswith("/.well-known/"):
            return response(*httputils.NOT_FOUND)

        login = password = ""
        external_login = self._auth.get_external_login(environ)
        authorization = environ.get("HTTP_AUTHORIZATION", "")
        if external_login:
            login, password = external_login
            login, password = login or "", password or ""
        elif authorization.startswith("Basic"):
            authorization = authorization[len("Basic"):].strip()
            login, password = httputils.decode_request(
                self.configuration, environ, base64.b64decode(
                    authorization.encode("ascii"))).split(":", 1)

        user = self._auth.login(login, password) or "" if login else ""
        if user and login == user:
            logger.info("Successful login: %r", user)
        elif user:
            logger.info("Successful login: %r -> %r", login, user)
        elif login:
            logger.warning("Failed login attempt from %s: %r",
                           remote_host, login)
            delay = self.configuration.get("auth", "delay")
            if delay > 0:
                random_delay = delay * (0.5 + random.random())
                logger.debug("Sleeping %.3f seconds", random_delay)
                time.sleep(random_delay)

        if user and not pathutils.is_safe_path_component(user):
            logger.info("Refused unsafe username: %r", user)
            user = ""

        if user:
            principal_path = "/%s/" % user
            with self._storage.acquire_lock("r", user):
                principal = next(self._storage.discover(
                    principal_path, depth="1"), None)
            if not principal:
                if "W" in self._rights.authorization(user, principal_path):
                    with self._storage.acquire_lock("w", user):
                        try:
                            self._storage.create_collection(principal_path)
                        except ValueError as e:
                            logger.warning("Failed to create principal "
                                           "collection %r: %s", user, e)
                            user = ""
                else:
                    logger.warning("Access to principal path %r denied by "
                                   "rights backend", principal_path)

        if self.configuration.get("server", "_internal_server"):
            content_length = int(environ.get("CONTENT_LENGTH") or 0)
            if content_length:
                max_content_length = self.configuration.get(
                    "server", "max_content_length")
                if max_content_length and content_length > max_content_length:
                    logger.info("Request body too large: %d", content_length)
                    return response(*httputils.REQUEST_ENTITY_TOO_LARGE)

        if not login or user:
            status, headers, answer = function(
                environ, base_prefix, path, user)
            if (status, headers, answer) == httputils.NOT_ALLOWED:
                logger.info("Access to %r denied for %s", path,
                            repr(user) if user else "anonymous user")
        else:
            status, headers, answer = httputils.NOT_ALLOWED

        if ((status, headers, answer) == httputils.NOT_ALLOWED and not user and
                not external_login):
            logger.debug("Asking client for authentication")
            status = client.UNAUTHORIZED
            realm = self.configuration.get("auth", "realm")
            headers = dict(headers)
            headers.update({
                "WWW-Authenticate":
                "Basic realm=\"%s\"" % realm})

        return response(status, headers, answer)

    def _read_xml_request_body(self, environ):
        content = httputils.decode_request(
            self.configuration, environ,
            httputils.read_raw_request_body(self.configuration, environ))
        if not content:
            return None
        try:
            xml_content = DefusedET.fromstring(content)
        except ET.ParseError as e:
            logger.debug("Request content (Invalid XML):\n%s", content)
            raise RuntimeError("Failed to parse XML: %s" % e) from e
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("Request content:\n%s",
                         xmlutils.pretty_xml(xml_content))
        return xml_content

    def _xml_response(self, xml_content):
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("Response content:\n%s",
                         xmlutils.pretty_xml(xml_content))
        f = io.BytesIO()
        ET.ElementTree(xml_content).write(f, encoding=self._encoding,
                                          xml_declaration=True)
        return f.getvalue()

    def _webdav_error_response(self, status, human_tag):
        headers = {"Content-Type": "text/xml; charset=%s" % self._encoding}
        content = self._xml_response(xmlutils.webdav_error(human_tag))
        return status, headers, content


class Access:

    def __init__(self, rights, user, path):
        self._rights = rights
        self.user = user
        self.path = path
        self.parent_path = pathutils.unstrip_path(
            posixpath.dirname(pathutils.strip_path(path)), True)
        self.permissions = self._rights.authorization(self.user, self.path)
        self._parent_permissions = None

    @property
    def parent_permissions(self):
        if self.path == self.parent_path:
            return self.permissions
        if self._parent_permissions is None:
            self._parent_permissions = self._rights.authorization(
                self.user, self.parent_path)
        return self._parent_permissions

    def check(self, permission, item=None):
        if permission not in "rw":
            raise ValueError("Invalid permission argument: %r" % permission)
        if not item:
            permissions = permission + permission.upper()
            parent_permissions = permission
        elif isinstance(item, storage.BaseCollection):
            if item.get_meta("tag"):
                permissions = permission
            else:
                permissions = permission.upper()
            parent_permissions = ""
        else:
            permissions = ""
            parent_permissions = permission
        return bool(rights.intersect(self.permissions, permissions) or (
            self.path != self.parent_path and
            rights.intersect(self.parent_permissions, parent_permissions)))

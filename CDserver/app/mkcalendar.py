import posixpath
import socket
from http import client

from CDserver import httputils
from CDserver import item as CDserver_item
from CDserver import pathutils, storage, xmlutils
from CDserver.log import logger


class ApplicationMkcalendarMixin:
    def do_MKCALENDAR(self, environ, base_prefix, path, user):
        if "w" not in self._rights.authorization(user, path):
            return httputils.NOT_ALLOWED
        try:
            xml_content = self._read_xml_request_body(environ)
        except RuntimeError as e:
            logger.warning(
                "Bad MKCALENDAR request on %r: %s", path, e, exc_info=True)
            return httputils.BAD_REQUEST
        except socket.timeout:
            logger.debug("Client timed out", exc_info=True)
            return httputils.REQUEST_TIMEOUT
        props = xmlutils.props_from_request(xml_content)
        props = {k: v for k, v in props.items() if v is not None}
        props["tag"] = "VCALENDAR"
        try:
            CDserver_item.check_and_sanitize_props(props)
        except ValueError as e:
            logger.warning(
                "Bad MKCALENDAR request on %r: %s", path, e, exc_info=True)
            return httputils.BAD_REQUEST
        with self._storage.acquire_lock("w", user):
            item = next(self._storage.discover(path), None)
            if item:
                return self._webdav_error_response(
                    client.CONFLICT, "D:resource-must-be-null")
            parent_path = pathutils.unstrip_path(
                posixpath.dirname(pathutils.strip_path(path)), True)
            parent_item = next(self._storage.discover(parent_path), None)
            if not parent_item:
                return httputils.CONFLICT
            if (not isinstance(parent_item, storage.BaseCollection) or
                    parent_item.get_meta("tag")):
                return httputils.FORBIDDEN
            try:
                self._storage.create_collection(path, props=props)
            except ValueError as e:
                logger.warning(
                    "Bad MKCALENDAR request on %r: %s", path, e, exc_info=True)
                return httputils.BAD_REQUEST
            return client.CREATED, {}, None

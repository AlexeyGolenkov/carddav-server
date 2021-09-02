import posixpath
import socket
from http import client

from CDserver import httputils
from CDserver import item as CDserver_item
from CDserver import pathutils, rights, storage, xmlutils
from CDserver.log import logger


class ApplicationMkcolMixin:
    def do_MKCOL(self, environ, base_prefix, path, user):
        permissions = self._rights.authorization(user, path)
        if not rights.intersect(permissions, "Ww"):
            return httputils.NOT_ALLOWED
        try:
            xml_content = self._read_xml_request_body(environ)
        except RuntimeError as e:
            logger.warning(
                "Bad MKCOL request on %r: %s", path, e, exc_info=True)
            return httputils.BAD_REQUEST
        except socket.timeout:
            logger.debug("Client timed out", exc_info=True)
            return httputils.REQUEST_TIMEOUT
        props = xmlutils.props_from_request(xml_content)
        props = {k: v for k, v in props.items() if v is not None}
        try:
            CDserver_item.check_and_sanitize_props(props)
        except ValueError as e:
            logger.warning(
                "Bad MKCOL request on %r: %s", path, e, exc_info=True)
            return httputils.BAD_REQUEST
        if (props.get("tag") and "w" not in permissions or
                not props.get("tag") and "W" not in permissions):
            return httputils.NOT_ALLOWED
        with self._storage.acquire_lock("w", user):
            item = next(self._storage.discover(path), None)
            if item:
                return httputils.METHOD_NOT_ALLOWED
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
                    "Bad MKCOL request on %r: %s", path, e, exc_info=True)
                return httputils.BAD_REQUEST
            return client.CREATED, {}, None

import posixpath
from http import client
from urllib.parse import urlparse

from CDserver import app, httputils, pathutils, storage
from CDserver.log import logger


class ApplicationMoveMixin:
    def do_MOVE(self, environ, base_prefix, path, user):
        raw_dest = environ.get("HTTP_DESTINATION", "")
        to_url = urlparse(raw_dest)
        if to_url.netloc != environ["HTTP_HOST"]:
            logger.info("Unsupported destination address: %r", raw_dest)
            return httputils.REMOTE_DESTINATION
        access = app.Access(self._rights, user, path)
        if not access.check("w"):
            return httputils.NOT_ALLOWED
        to_path = pathutils.sanitize_path(to_url.path)
        if not (to_path + "/").startswith(base_prefix + "/"):
            logger.warning("Destination %r from MOVE request on %r doesn't "
                           "start with base prefix", to_path, path)
            return httputils.NOT_ALLOWED
        to_path = to_path[len(base_prefix):]
        to_access = app.Access(self._rights, user, to_path)
        if not to_access.check("w"):
            return httputils.NOT_ALLOWED

        with self._storage.acquire_lock("w", user):
            item = next(self._storage.discover(path), None)
            if not item:
                return httputils.NOT_FOUND
            if (not access.check("w", item) or
                    not to_access.check("w", item)):
                return httputils.NOT_ALLOWED
            if isinstance(item, storage.BaseCollection):
                return httputils.METHOD_NOT_ALLOWED

            to_item = next(self._storage.discover(to_path), None)
            if isinstance(to_item, storage.BaseCollection):
                return httputils.FORBIDDEN
            to_parent_path = pathutils.unstrip_path(
                posixpath.dirname(pathutils.strip_path(to_path)), True)
            to_collection = next(
                self._storage.discover(to_parent_path), None)
            if not to_collection:
                return httputils.CONFLICT
            tag = item.collection.get_meta("tag")
            if not tag or tag != to_collection.get_meta("tag"):
                return httputils.FORBIDDEN
            if to_item and environ.get("HTTP_OVERWRITE", "F") != "T":
                return httputils.PRECONDITION_FAILED
            if (to_item and item.uid != to_item.uid or
                    not to_item and
                    to_collection.path != item.collection.path and
                    to_collection.has_uid(item.uid)):
                return self._webdav_error_response(
                    client.CONFLICT, "%s:no-uid-conflict" % (
                        "C" if tag == "VCALENDAR" else "CR"))
            to_href = posixpath.basename(pathutils.strip_path(to_path))
            try:
                self._storage.move(item, to_collection, to_href)
            except ValueError as e:
                logger.warning(
                    "Bad MOVE request on %r: %s", path, e, exc_info=True)
                return httputils.BAD_REQUEST
            return client.NO_CONTENT if to_item else client.CREATED, {}, None

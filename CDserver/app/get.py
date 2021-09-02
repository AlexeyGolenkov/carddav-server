import posixpath
from http import client
from urllib.parse import quote

from CDserver import app, httputils, pathutils, storage, xmlutils
from CDserver.log import logger


def propose_filename(collection):
    tag = collection.get_meta("tag")
    if tag == "VADDRESSBOOK":
        fallback_title = "Address book"
        suffix = ".vcf"
    elif tag == "VCALENDAR":
        fallback_title = "Calendar"
        suffix = ".ics"
    else:
        fallback_title = posixpath.basename(collection.path)
        suffix = ""
    title = collection.get_meta("D:displayname") or fallback_title
    if title and not title.lower().endswith(suffix.lower()):
        title += suffix
    return title


class ApplicationGetMixin:
    def _content_disposition_attachement(self, filename):
        value = "attachement"
        try:
            encoded_filename = quote(filename, encoding=self._encoding)
        except UnicodeEncodeError:
            logger.warning("Failed to encode filename: %r", filename,
                           exc_info=True)
            encoded_filename = ""
        if encoded_filename:
            value += "; filename*=%s''%s" % (self._encoding, encoded_filename)
        return value

    def do_GET(self, environ, base_prefix, path, user):
        if not pathutils.strip_path(path):
            web_path = ".web"
            if not environ.get("PATH_INFO"):
                web_path = posixpath.join(posixpath.basename(base_prefix),
                                          web_path)
            return (client.FOUND,
                    {"Location": web_path, "Content-Type": "text/plain"},
                    "Redirected to %s" % web_path)
        if path == "/.web" or path.startswith("/.web/"):
            return self._web.get(environ, base_prefix, path, user)
        access = app.Access(self._rights, user, path)
        if not access.check("r") and "i" not in access.permissions:
            return httputils.NOT_ALLOWED
        with self._storage.acquire_lock("r", user):
            item = next(self._storage.discover(path), None)
            if not item:
                return httputils.NOT_FOUND
            if access.check("r", item):
                limited_access = False
            elif "i" in access.permissions:
                limited_access = True
            else:
                return httputils.NOT_ALLOWED
            if isinstance(item, storage.BaseCollection):
                tag = item.get_meta("tag")
                if not tag:
                    return (httputils.NOT_ALLOWED if limited_access else
                            httputils.DIRECTORY_LISTING)
                content_type = xmlutils.MIMETYPES[tag]
                content_disposition = self._content_disposition_attachement(
                    propose_filename(item))
            elif limited_access:
                return httputils.NOT_ALLOWED
            else:
                content_type = xmlutils.OBJECT_MIMETYPES[item.name]
                content_disposition = ""
            headers = {
                "Content-Type": content_type,
                "Last-Modified": item.last_modified,
                "ETag": item.etag}
            if content_disposition:
                headers["Content-Disposition"] = content_disposition
            answer = item.serialize()
            return client.OK, headers, answer

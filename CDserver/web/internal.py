import os
import posixpath
import time
from http import client

import pkg_resources

from CDserver import httputils, pathutils, web
from CDserver.log import logger

MIMETYPES = {
    ".css": "text/css",
    ".eot": "application/vnd.ms-fontobject",
    ".gif": "image/gif",
    ".html": "text/html",
    ".js": "application/javascript",
    ".manifest": "text/cache-manifest",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".ttf": "application/font-sfnt",
    ".txt": "text/plain",
    ".woff": "application/font-woff",
    ".woff2": "font/woff2",
    ".xml": "text/xml"}
FALLBACK_MIMETYPE = "application/octet-stream"


class Web(web.BaseWeb):
    def __init__(self, configuration):
        super().__init__(configuration)
        self.folder = pkg_resources.resource_filename(__name__,
                                                      "internal_data")

    def get(self, environ, base_prefix, path, user):
        assert path == "/.web" or path.startswith("/.web/")
        assert pathutils.sanitize_path(path) == path
        try:
            filesystem_path = pathutils.path_to_filesystem(
                self.folder, path[len("/.web"):].strip("/"))
        except ValueError as e:
            logger.debug("Web content with unsafe path %r requested: %s",
                         path, e, exc_info=True)
            return httputils.NOT_FOUND
        if os.path.isdir(filesystem_path) and not path.endswith("/"):
            location = posixpath.basename(path) + "/"
            return (client.FOUND,
                    {"Location": location, "Content-Type": "text/plain"},
                    "Redirected to %s" % location)
        if os.path.isdir(filesystem_path):
            filesystem_path = os.path.join(filesystem_path, "index.html")
        if not os.path.isfile(filesystem_path):
            return httputils.NOT_FOUND
        content_type = MIMETYPES.get(
            os.path.splitext(filesystem_path)[1].lower(), FALLBACK_MIMETYPE)
        with open(filesystem_path, "rb") as f:
            answer = f.read()
            last_modified = time.strftime(
                "%a, %d %b %Y %H:%M:%S GMT",
                time.gmtime(os.fstat(f.fileno()).st_mtime))
        headers = {
            "Content-Type": content_type,
            "Last-Modified": last_modified}
        return client.OK, headers, answer

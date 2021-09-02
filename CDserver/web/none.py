from http import client

from CDserver import httputils, pathutils, web


class Web(web.BaseWeb):
    def get(self, environ, base_prefix, path, user):
        assert path == "/.web" or path.startswith("/.web/")
        assert pathutils.sanitize_path(path) == path
        if path != "/.web":
            return httputils.NOT_FOUND
        return client.OK, {"Content-Type": "text/plain"}, "CDserver works!"

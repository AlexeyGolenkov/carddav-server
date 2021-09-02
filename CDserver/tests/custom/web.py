from http import client

from CDserver import httputils, web


class Web(web.BaseWeb):
    def get(self, environ, base_prefix, path, user):
        return client.OK, {"Content-Type": "text/plain"}, "custom"

    def post(self, environ, base_prefix, path, user):
        content = httputils.read_request_body(self.configuration, environ)
        return client.OK, {"Content-Type": "text/plain"}, "echo:" + content

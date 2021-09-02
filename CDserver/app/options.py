from http import client

from CDserver import httputils


class ApplicationOptionsMixin:
    def do_OPTIONS(self, environ, base_prefix, path, user):
        headers = {
            "Allow": ", ".join(
                name[3:] for name in dir(self) if name.startswith("do_")),
            "DAV": httputils.DAV_HEADERS}
        return client.OK, headers, None

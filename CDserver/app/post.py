from CDserver import httputils


class ApplicationPostMixin:
    def do_POST(self, environ, base_prefix, path, user):
        if path == "/.web" or path.startswith("/.web/"):
            return self._web.post(environ, base_prefix, path, user)
        return httputils.METHOD_NOT_ALLOWED

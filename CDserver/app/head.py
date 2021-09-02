class ApplicationHeadMixin:
    def do_HEAD(self, environ, base_prefix, path, user):
        status, headers, _ = self.do_GET(environ, base_prefix, path, user)
        return status, headers, None

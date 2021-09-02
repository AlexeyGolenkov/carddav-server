import CDserver.auth.none as none

class Auth(none.Auth):
    def get_external_login(self, environ):
        return environ.get("HTTP_X_REMOTE_USER", ""), ""

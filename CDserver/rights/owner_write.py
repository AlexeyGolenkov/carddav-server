import CDserver.rights.authenticated as authenticated
from CDserver import pathutils

class Rights(authenticated.Rights):
    def authorization(self, user, path):
        if self._verify_user and not user:
            return ""
        sane_path = pathutils.strip_path(path)
        if not sane_path:
            return "R"
        if self._verify_user:
            owned = user == sane_path.split("/", maxsplit=1)[0]
        else:
            owned = True
        if "/" not in sane_path:
            return "RW" if owned else "R"
        if sane_path.count("/") == 1:
            return "rw" if owned else "r"
        return ""

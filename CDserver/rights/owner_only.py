from CDserver import pathutils, rights

class Rights(rights.BaseRights):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._verify_user = self.configuration.get("auth", "type") != "none"

    def authorization(self, user, path):
        if self._verify_user and not user:
            return ""
        sane_path = pathutils.strip_path(path)
        if "/" not in sane_path:
            return "RW"
        if sane_path.count("/") == 1:
            return "rw"
        return ""

class Rights(Rights):
    def authorization(self, user, path):
        if self._verify_user and not user:
            return ""
        sane_path = pathutils.strip_path(path)
        if not sane_path:
            return "R"
        if self._verify_user and user != sane_path.split("/", maxsplit=1)[0]:
            return ""
        if "/" not in sane_path:
            return "RW"
        if sane_path.count("/") == 1:
            return "rw"
        return ""

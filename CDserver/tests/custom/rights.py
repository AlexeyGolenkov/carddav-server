from CDserver import pathutils, rights


class Rights(rights.BaseRights):
    def authorization(self, user, path):
        sane_path = pathutils.strip_path(path)
        if sane_path not in ("tmp", "other"):
            return ""
        return "RrWw"

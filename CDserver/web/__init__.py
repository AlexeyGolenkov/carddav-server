from CDserver import httputils, utils

INTERNAL_TYPES = ("none", "internal")


def load(configuration):
    return utils.load_plugin(INTERNAL_TYPES, "web", "Web", configuration)


class BaseWeb:
    def __init__(self, configuration):
        self.configuration = configuration

    def get(self, environ, base_prefix, path, user):
        return httputils.METHOD_NOT_ALLOWED

    def post(self, environ, base_prefix, path, user):
        return httputils.METHOD_NOT_ALLOWED

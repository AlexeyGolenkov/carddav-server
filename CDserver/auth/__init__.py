from CDserver import utils

INTERNAL_TYPES = ("none", "remote_user", "http_x_remote_user", "htpasswd")


def load(configuration):
    return utils.load_plugin(INTERNAL_TYPES, "auth", "Auth", configuration)


class BaseAuth:
    def __init__(self, configuration):
        self.configuration = configuration

    def get_external_login(self, environ):
        return ()

    def login(self, login, password):
        raise NotImplementedError

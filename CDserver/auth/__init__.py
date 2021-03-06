from CDserver import utils


def load(configuration):
    return utils.load_plugin("auth", "Auth", configuration)


class BaseAuth:
    def __init__(self, configuration):
        self.configuration = configuration

    def login(self, login, password):
        raise NotImplementedError

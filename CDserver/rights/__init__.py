from CDserver import utils

def load(configuration):
    return utils.load_plugin("rights", "Rights", configuration)


def intersect(a, b):
    return "".join(set(a).intersection(set(b)))


class BaseRights:
    def __init__(self, configuration):
        self.configuration = configuration

    def authorization(self, user, path):
        raise NotImplementedError

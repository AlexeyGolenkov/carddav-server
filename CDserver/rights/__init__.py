from CDserver import utils

INTERNAL_TYPES = ("authenticated", "owner_write", "owner_only", "from_file")


def load(configuration):
    return utils.load_plugin(INTERNAL_TYPES, "rights", "Rights", configuration)


def intersect(a, b):
    return "".join(set(a).intersection(set(b)))


class BaseRights:
    def __init__(self, configuration):
        self.configuration = configuration

    def authorization(self, user, path):
        raise NotImplementedError

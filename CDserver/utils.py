from importlib import import_module

from CDserver.log import logger


def load_plugin(module_name, class_name, configuration):
    type_ = configuration.get(module_name, "type")
    module = "CDserver.%s.%s" % (module_name, type_)
    class_ = getattr(import_module(module), class_name)
    logger.info("%s type is %r", module_name, module)
    return class_(configuration)

from importlib import import_module

from CDserver.log import logger


def load_plugin(internal_types, module_name, class_name, configuration):
    type_ = configuration.get(module_name, "type")
    if callable(type_):
        logger.info("%s type is %r", module_name, type_)
        return type_(configuration)
    if type_ in internal_types:
        module = "CDserver.%s.%s" % (module_name, type_)
    else:
        module = type_
    try:
        class_ = getattr(import_module(module), class_name)
    except Exception as e:
        raise RuntimeError("Failed to load %s module %r: %s" %
                           (module_name, module, e)) from e
    logger.info("%s type is %r", module_name, module)
    return class_(configuration)

import os
import threading

import pkg_resources

from CDserver import config, log
from CDserver.app import Application
from CDserver.log import logger

VERSION = "3.0.6"

_application = None
_application_config_path = None
_application_lock = threading.Lock()


def _init_application(config_path, wsgi_errors):
    global _application, _application_config_path
    with _application_lock:
        if _application is not None:
            return
        log.setup()
        with log.register_stream(wsgi_errors):
            _application_config_path = config_path
            configuration = config.load(config.parse_compound_paths(
                config.DEFAULT_CONFIG_PATH,
                config_path))
            log.set_level(configuration.get("logging", "level"))
            for source, miss in configuration.sources():
                logger.info("%s %s", "Skipped missing" if miss else "Loaded",
                            source)
            _application = Application(configuration)


def application(environ, start_response):
    config_path = environ.get("CDserver_CONFIG",
                              os.environ.get("CDserver_CONFIG"))
    if _application is None:
        _init_application(config_path, environ["wsgi.errors"])
    if _application_config_path != config_path:
        raise ValueError("CDserver_CONFIG must not change: %s != %s" %
                         (repr(config_path), repr(_application_config_path)))
    return _application(environ, start_response)

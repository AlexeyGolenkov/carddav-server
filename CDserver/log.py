import contextlib
import logging
import os
import sys
import threading

LOGGER_NAME = "CDserver"
LOGGER_FORMAT = "[%(asctime)s] [%(ident)s] [%(levelname)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S %z"

logger = logging.getLogger(LOGGER_NAME)


class RemoveTracebackFilter(logging.Filter):
    def filter(self, record):
        record.exc_info = None
        return True


REMOVE_TRACEBACK_FILTER = RemoveTracebackFilter()


class IdentLogRecordFactory:
    def __init__(self, upstream_factory):
        self.upstream_factory = upstream_factory

    def __call__(self, *args, **kwargs):
        record = self.upstream_factory(*args, **kwargs)
        ident = "%d" % os.getpid()
        main_thread = threading.main_thread()
        current_thread = threading.current_thread()
        if current_thread.name and main_thread != current_thread:
            ident += "/%s" % current_thread.name
        record.ident = ident
        return record


class ThreadedStreamHandler(logging.Handler):
    terminator = "\n"

    def __init__(self):
        super().__init__()
        self._streams = {}

    def emit(self, record):
        try:
            stream = self._streams.get(threading.get_ident(), sys.stderr)
            msg = self.format(record)
            stream.write(msg)
            stream.write(self.terminator)
            if hasattr(stream, "flush"):
                stream.flush()
        except Exception:
            self.handleError(record)

    @contextlib.contextmanager
    def register_stream(self, stream):
        key = threading.get_ident()
        self._streams[key] = stream
        try:
            yield
        finally:
            del self._streams[key]


@contextlib.contextmanager
def register_stream(stream):
    yield


def setup():
    global register_stream
    handler = ThreadedStreamHandler()
    logging.basicConfig(format=LOGGER_FORMAT, datefmt=DATE_FORMAT,
                        handlers=[handler])
    register_stream = handler.register_stream
    log_record_factory = IdentLogRecordFactory(logging.getLogRecordFactory())
    logging.setLogRecordFactory(log_record_factory)
    set_level(logging.WARNING)


def set_level(level):
    if isinstance(level, str):
        level = getattr(logging, level.upper())
    logger.setLevel(level)
    if level == logging.DEBUG:
        logger.removeFilter(REMOVE_TRACEBACK_FILTER)
    else:
        logger.addFilter(REMOVE_TRACEBACK_FILTER)

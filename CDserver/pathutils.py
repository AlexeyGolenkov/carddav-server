import contextlib
import os
import posixpath
import sys
import threading
from tempfile import TemporaryDirectory
from CDserver.log import logger

import fcntl

HAVE_RENAMEAT2 = False
import ctypes

RENAME_EXCHANGE = 2
try:
    renameat2 = ctypes.CDLL(None, use_errno=True).renameat2
except AttributeError:
    pass
else:
    HAVE_RENAMEAT2 = True
    renameat2.argtypes = [
        ctypes.c_int, ctypes.c_char_p,
        ctypes.c_int, ctypes.c_char_p,
        ctypes.c_uint]
    renameat2.restype = ctypes.c_int


class RwLock:
    def __init__(self, path):
        self._path = path
        self._readers = 0
        self._writer = False
        self._lock = threading.Lock()

    @property
    def locked(self):
        with self._lock:
            if self._readers > 0:
                return "r"
            if self._writer:
                return "w"
            return ""

    @contextlib.contextmanager
    def acquire(self, mode):
        if mode not in "rw":
            raise ValueError("Invalid mode: %r" % mode)
        with open(self._path, "w+") as lock_file:
            _cmd = fcntl.LOCK_EX if mode == "w" else fcntl.LOCK_SH
            fcntl.flock(lock_file.fileno(), _cmd)

            with self._lock:
                if mode == "r":
                    self._readers += 1
                else:
                    self._writer = True
            try:
                yield
            finally:
                with self._lock:
                    if mode == "r":
                        self._readers -= 1
                    self._writer = False


def rename_exchange(src, dst):
    src_dir, src_base = os.path.split(src)
    dst_dir, dst_base = os.path.split(dst)
    src_dir = src_dir or os.curdir
    dst_dir = dst_dir or os.curdir
    if not src_base or not dst_base:
        raise ValueError("Invalid arguments: %r -> %r" % (src, dst))
    if HAVE_RENAMEAT2:
        src_base_bytes = os.fsencode(src_base)
        dst_base_bytes = os.fsencode(dst_base)
        src_dir_fd = os.open(src_dir, 0)
        try:
            dst_dir_fd = os.open(dst_dir, 0)
            try:
                if renameat2(src_dir_fd, src_base_bytes,
                             dst_dir_fd, dst_base_bytes,
                             RENAME_EXCHANGE) != 0:
                    errno = ctypes.get_errno()
                    raise OSError(errno, os.strerror(errno))
            finally:
                os.close(dst_dir_fd)
        finally:
            os.close(src_dir_fd)
    else:
        with TemporaryDirectory(
                prefix=".CDserver.tmp-", dir=src_dir) as tmp_dir:
            os.rename(dst, os.path.join(tmp_dir, "interim"))
            os.rename(src, dst)
            os.rename(os.path.join(tmp_dir, "interim"), src)


def fsync(fd):
    if os.name == "posix" and hasattr(fcntl, "F_FULLFSYNC"):
        fcntl.fcntl(fd, fcntl.F_FULLFSYNC)
    else:
        os.fsync(fd)


def strip_path(path):
    assert sanitize_path(path) == path
    return path.strip("/")


def unstrip_path(stripped_path, trailing_slash=False):
    assert strip_path(sanitize_path(stripped_path)) == stripped_path
    assert stripped_path or trailing_slash
    path = "/%s" % stripped_path
    if trailing_slash and not path.endswith("/"):
        path += "/"
    return path


def sanitize_path(path):
    trailing_slash = "/" if path.endswith("/") else ""
    path = posixpath.normpath(path)
    new_path = "/"
    for part in path.split("/"):
        if not is_safe_path_component(part):
            continue
        new_path = posixpath.join(new_path, part)
    trailing_slash = "" if new_path.endswith("/") else trailing_slash
    return new_path + trailing_slash


def is_safe_path_component(path):
    return path and "/" not in path and path not in (".", "..")


def is_safe_filesystem_path_component(path):
    return (
        path and not os.path.splitdrive(path)[0] and
        not os.path.split(path)[0] and path not in (os.curdir, os.pardir) and
        not path.startswith(".") and not path.endswith("~") and
        is_safe_path_component(path))


def path_to_filesystem(root, sane_path):
    assert sane_path == strip_path(sanitize_path(sane_path))
    safe_path = root
    parts = sane_path.split("/") if sane_path else []
    for part in parts:
        if not is_safe_filesystem_path_component(part):
            raise UnsafePathError(part)
        safe_path_parent = safe_path
        safe_path = os.path.join(safe_path, part)
        # Check for conflicting files (e.g. case-insensitive file systems
        # or short names on Windows file systems)
        if (os.path.lexists(safe_path) and
                part not in (e.name for e in
                             os.scandir(safe_path_parent))):
            raise CollidingPathError(part)
    return safe_path


class UnsafePathError(ValueError):
    def __init__(self, path):
        message = "Can't translate name safely to filesystem: %r" % path
        super().__init__(message)


class CollidingPathError(ValueError):
    def __init__(self, path):
        message = "File name collision: %r" % path
        super().__init__(message)


def name_from_path(path, collection):
    assert sanitize_path(path) == path
    start = unstrip_path(collection.path, True)
    if not (path + "/").startswith(start):
        raise ValueError("%r doesn't start with %r" % (path, start))
    name = path[len(start):]
    if name and not is_safe_path_component(name):
        raise ValueError("%r is not a component in collection %r" %
                         (name, collection.path))
    return name

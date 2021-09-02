import contextlib
import logging
import os
import shlex
import signal
import subprocess

from CDserver import pathutils
from CDserver.log import logger


class CollectionLockMixin:
    def _acquire_cache_lock(self, ns=""):
        if self._storage._lock.locked == "w":
            return contextlib.ExitStack()
        cache_folder = os.path.join(self._filesystem_path, ".CDserver.cache")
        self._storage._makedirs_synced(cache_folder)
        lock_path = os.path.join(cache_folder,
                                 ".CDserver.lock" + (".%s" % ns if ns else ""))
        lock = pathutils.RwLock(lock_path)
        return lock.acquire("w")


class StorageLockMixin:

    def __init__(self, configuration):
        super().__init__(configuration)
        folder = self.configuration.get("storage", "filesystem_folder")
        lock_path = os.path.join(folder, ".CDserver.lock")
        self._lock = pathutils.RwLock(lock_path)

    @contextlib.contextmanager
    def acquire_lock(self, mode, user=None):
        with self._lock.acquire(mode):
            yield
            hook = self.configuration.get("storage", "hook")
            if mode == "w" and hook:
                folder = self.configuration.get("storage", "filesystem_folder")
                debug = logger.isEnabledFor(logging.DEBUG)
                popen_kwargs = dict(
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE if debug else subprocess.DEVNULL,
                    stderr=subprocess.PIPE if debug else subprocess.DEVNULL,
                    shell=True, universal_newlines=True, cwd=folder)
                if os.name == "posix":
                    popen_kwargs["preexec_fn"] = os.setpgrp
                elif os.name == "nt":
                    popen_kwargs["creationflags"] = (
                        subprocess.CREATE_NEW_PROCESS_GROUP)
                command = hook % {"user": shlex.quote(user or "Anonymous")}
                logger.debug("Running storage hook")
                p = subprocess.Popen(command, **popen_kwargs)
                try:
                    stdout_data, stderr_data = p.communicate()
                except BaseException:
                    p.kill()
                    p.wait()
                    raise
                finally:
                    if os.name == "posix":
                        with contextlib.suppress(OSError):
                            os.killpg(p.pid, signal.SIGKILL)
                if stdout_data:
                    logger.debug("Captured stdout from hook:\n%s", stdout_data)
                if stderr_data:
                    logger.debug("Captured stderr from hook:\n%s", stderr_data)
                if p.returncode != 0:
                    raise subprocess.CalledProcessError(p.returncode, p.args)

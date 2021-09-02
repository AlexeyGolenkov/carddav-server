import contextlib
import os
import posixpath

from CDserver import pathutils
from CDserver.log import logger


class StorageDiscoverMixin:

    def discover(self, path, depth="0", child_context_manager=(
            lambda path, href=None: contextlib.ExitStack())):
        sane_path = pathutils.strip_path(path)
        attributes = sane_path.split("/") if sane_path else []

        folder = self._get_collection_root_folder()
        self._makedirs_synced(folder)
        try:
            filesystem_path = pathutils.path_to_filesystem(folder, sane_path)
        except ValueError as e:
            logger.debug("Unsafe path %r requested from storage: %s",
                         sane_path, e, exc_info=True)
            return

        if not os.path.isdir(filesystem_path):
            if attributes and os.path.isfile(filesystem_path):
                href = attributes.pop()
            else:
                return
        else:
            href = None

        sane_path = "/".join(attributes)
        collection = self._collection_class(
            self, pathutils.unstrip_path(sane_path, True))

        if href:
            yield collection._get(href)
            return

        yield collection

        if depth == "0":
            return

        for href in collection._list():
            with child_context_manager(sane_path, href):
                yield collection._get(href)

        for entry in os.scandir(filesystem_path):
            if not entry.is_dir():
                continue
            href = entry.name
            if not pathutils.is_safe_filesystem_path_component(href):
                if not href.startswith(".CDserver"):
                    logger.debug("Skipping collection %r in %r",
                                 href, sane_path)
                continue
            sane_child_path = posixpath.join(sane_path, href)
            child_path = pathutils.unstrip_path(sane_child_path, True)
            with child_context_manager(sane_child_path):
                yield self._collection_class(self, child_path)

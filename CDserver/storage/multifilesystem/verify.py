import contextlib

from CDserver import pathutils, storage
from CDserver.log import logger


class StorageVerifyMixin:
    def verify(self):
        item_errors = collection_errors = 0

        @contextlib.contextmanager
        def exception_cm(sane_path, href=None):
            nonlocal item_errors, collection_errors
            try:
                yield
            except Exception as e:
                if href:
                    item_errors += 1
                    name = "item %r in %r" % (href, sane_path)
                else:
                    collection_errors += 1
                    name = "collection %r" % sane_path
                logger.error("Invalid %s: %s", name, e, exc_info=True)

        remaining_sane_paths = [""]
        while remaining_sane_paths:
            sane_path = remaining_sane_paths.pop(0)
            path = pathutils.unstrip_path(sane_path, True)
            logger.debug("Verifying collection %r", sane_path)
            with exception_cm(sane_path):
                saved_item_errors = item_errors
                collection = None
                uids = set()
                has_child_collections = False
                for item in self.discover(path, "1", exception_cm):
                    if not collection:
                        collection = item
                        collection.get_meta()
                        continue
                    if isinstance(item, storage.BaseCollection):
                        has_child_collections = True
                        remaining_sane_paths.append(item.path)
                    elif item.uid in uids:
                        logger.error("Invalid item %r in %r: UID conflict %r",
                                     item.href, sane_path, item.uid)
                    else:
                        uids.add(item.uid)
                        logger.debug("Verified item %r in %r",
                                     item.href, sane_path)
                if item_errors == saved_item_errors:
                    collection.sync()
                if has_child_collections and collection.get_meta("tag"):
                    logger.error("Invalid collection %r: %r must not have "
                                 "child collections", sane_path,
                                 collection.get_meta("tag"))
        return item_errors == 0 and collection_errors == 0

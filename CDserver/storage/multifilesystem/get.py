import os
import time

import vobject

from CDserver import item as CDserver_item
from CDserver import pathutils
from CDserver.log import logger


class CollectionGetMixin:
    def __init__(self):
        super().__init__()
        self._item_cache_cleaned = False

    def _list(self):
        for entry in os.scandir(self._filesystem_path):
            if not entry.is_file():
                continue
            href = entry.name
            if not pathutils.is_safe_filesystem_path_component(href):
                if not href.startswith(".CDserver"):
                    logger.debug("Skipping item %r in %r", href, self.path)
                continue
            yield href

    def _get(self, href, verify_href=True):
        if verify_href:
            try:
                if not pathutils.is_safe_filesystem_path_component(href):
                    raise pathutils.UnsafePathError(href)
                path = pathutils.path_to_filesystem(
                    self._filesystem_path, href)
            except ValueError as e:
                logger.debug(
                    "Can't translate name %r safely to filesystem in %r: %s",
                    href, self.path, e, exc_info=True)
                return None
        else:
            path = os.path.join(self._filesystem_path, href)
        try:
            with open(path, "rb") as f:
                raw_text = f.read()
        except (FileNotFoundError, IsADirectoryError):
            return None
        except PermissionError:
            if (os.name == "nt" and
                    os.path.isdir(path) and os.access(path, os.R_OK)):
                return None
            raise
        input_hash = self._item_cache_hash(raw_text)
        cache_hash, uid, etag, text, name, tag, start, end = \
            self._load_item_cache(href, input_hash)
        if input_hash != cache_hash:
            with self._acquire_cache_lock("item"):
                if self._storage._lock.locked == "r":
                    cache_hash, uid, etag, text, name, tag, start, end = \
                        self._load_item_cache(href, input_hash)
                if input_hash != cache_hash:
                    try:
                        vobject_items = tuple(vobject.readComponents(
                            raw_text.decode(self._encoding)))
                        CDserver_item.check_and_sanitize_items(
                            vobject_items, tag=self.get_meta("tag"))
                        vobject_item, = vobject_items
                        temp_item = CDserver_item.Item(
                            collection=self, vobject_item=vobject_item)
                        cache_hash, uid, etag, text, name, tag, start, end = \
                            self._store_item_cache(
                                href, temp_item, input_hash)
                    except Exception as e:
                        raise RuntimeError("Failed to load item %r in %r: %s" %
                                           (href, self.path, e)) from e
                    if not self._item_cache_cleaned:
                        self._item_cache_cleaned = True
                        self._clean_item_cache()
        last_modified = time.strftime(
            "%a, %d %b %Y %H:%M:%S GMT",
            time.gmtime(os.path.getmtime(path)))
        return CDserver_item.Item(
            collection=self, href=href, last_modified=last_modified, etag=etag,
            text=text, uid=uid, name=name, component_name=tag,
            time_range=(start, end))

    def get_multi(self, hrefs):
        files = None
        for href in hrefs:
            if files is None:
                files = os.listdir(self._filesystem_path)
            path = os.path.join(self._filesystem_path, href)
            if (not pathutils.is_safe_filesystem_path_component(href) or
                    href not in files and os.path.lexists(path)):
                logger.debug(
                    "Can't translate name safely to filesystem: %r", href)
                yield (href, None)
            else:
                yield (href, self._get(href, verify_href=False))

    def get_all(self):
        return (self._get(href, verify_href=False) for href in self._list())

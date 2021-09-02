import os
import pickle

from CDserver import item as CDserver_item
from CDserver import pathutils


class CollectionUploadMixin:
    def upload(self, href, item):
        if not pathutils.is_safe_filesystem_path_component(href):
            raise pathutils.UnsafePathError(href)
        try:
            self._store_item_cache(href, item)
        except Exception as e:
            raise ValueError("Failed to store item %r in collection %r: %s" %
                             (href, self.path, e)) from e
        path = pathutils.path_to_filesystem(self._filesystem_path, href)
        with self._atomic_write(path, newline="") as fd:
            fd.write(item.serialize())
        self._clean_item_cache()
        self._update_history_etag(href, item)
        self._clean_history()
        return self._get(href, verify_href=False)

    def _upload_all_nonatomic(self, items, suffix=""):
        cache_folder = os.path.join(self._filesystem_path,
                                    ".CDserver.cache", "item")
        self._storage._makedirs_synced(cache_folder)
        hrefs = set()
        for item in items:
            uid = item.uid
            try:
                cache_content = self._item_cache_content(item)
            except Exception as e:
                raise ValueError(
                    "Failed to store item %r in temporary collection %r: %s" %
                    (uid, self.path, e)) from e
            href_candidate_funtions = []
            if os.name in ("nt", "posix"):
                href_candidate_funtions.append(
                    lambda: uid if uid.lower().endswith(suffix.lower())
                    else uid + suffix)
            href_candidate_funtions.extend((
                lambda: CDserver_item.get_etag(uid).strip('"') + suffix,
                lambda: CDserver_item.find_available_uid(hrefs.__contains__,
                                                         suffix)))
            href = f = None
            while href_candidate_funtions:
                href = href_candidate_funtions.pop(0)()
                if href in hrefs:
                    continue
                if not pathutils.is_safe_filesystem_path_component(href):
                    if not href_candidate_funtions:
                        raise pathutils.UnsafePathError(href)
                    continue
                try:
                    f = open(pathutils.path_to_filesystem(
                        self._filesystem_path, href),
                        "w", newline="", encoding=self._encoding)
                    break
                except OSError as e:
                    if href_candidate_funtions and (
                            os.name == "posix" and e.errno == 22 or
                            os.name == "nt" and e.errno == 123):
                        continue
                    raise
            with f:
                f.write(item.serialize())
                f.flush()
                self._storage._fsync(f)
            hrefs.add(href)
            with open(os.path.join(cache_folder, href), "wb") as f:
                pickle.dump(cache_content, f)
                f.flush()
                self._storage._fsync(f)
        self._storage._sync_directory(cache_folder)
        self._storage._sync_directory(self._filesystem_path)

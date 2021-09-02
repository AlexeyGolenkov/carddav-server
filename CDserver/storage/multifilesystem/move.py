import os

from CDserver import pathutils


class StorageMoveMixin:

    def move(self, item, to_collection, to_href):
        if not pathutils.is_safe_filesystem_path_component(to_href):
            raise pathutils.UnsafePathError(to_href)
        os.replace(
            pathutils.path_to_filesystem(
                item.collection._filesystem_path, item.href),
            pathutils.path_to_filesystem(
                to_collection._filesystem_path, to_href))
        self._sync_directory(to_collection._filesystem_path)
        if item.collection._filesystem_path != to_collection._filesystem_path:
            self._sync_directory(item.collection._filesystem_path)
        cache_folder = os.path.join(item.collection._filesystem_path,
                                    ".CDserver.cache", "item")
        to_cache_folder = os.path.join(to_collection._filesystem_path,
                                       ".CDserver.cache", "item")
        self._makedirs_synced(to_cache_folder)
        try:
            os.replace(os.path.join(cache_folder, item.href),
                       os.path.join(to_cache_folder, to_href))
        except FileNotFoundError:
            pass
        else:
            self._makedirs_synced(to_cache_folder)
            if cache_folder != to_cache_folder:
                self._makedirs_synced(cache_folder)
        to_collection._update_history_etag(to_href, item)
        item.collection._update_history_etag(item.href, None)
        to_collection._clean_history()
        if item.collection._filesystem_path != to_collection._filesystem_path:
            item.collection._clean_history()

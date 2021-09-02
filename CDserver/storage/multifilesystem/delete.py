import os
from tempfile import TemporaryDirectory

from CDserver import pathutils, storage


class CollectionDeleteMixin:
    def delete(self, href=None):
        if href is None:
            parent_dir = os.path.dirname(self._filesystem_path)
            try:
                os.rmdir(self._filesystem_path)
            except OSError:
                with TemporaryDirectory(
                        prefix=".CDserver.tmp-", dir=parent_dir) as tmp:
                    os.rename(self._filesystem_path, os.path.join(
                        tmp, os.path.basename(self._filesystem_path)))
                    self._storage._sync_directory(parent_dir)
            else:
                self._storage._sync_directory(parent_dir)
        else:
            if not pathutils.is_safe_filesystem_path_component(href):
                raise pathutils.UnsafePathError(href)
            path = pathutils.path_to_filesystem(self._filesystem_path, href)
            if not os.path.isfile(path):
                raise storage.ComponentNotFoundError(href)
            os.remove(path)
            self._storage._sync_directory(os.path.dirname(path))
            self._update_history_etag(href, None)
            self._clean_history()

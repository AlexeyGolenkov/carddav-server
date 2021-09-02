import json
import os

from CDserver import item as CDserver_item


class CollectionMetaMixin:
    def __init__(self):
        super().__init__()
        self._meta_cache = None
        self._props_path = os.path.join(
            self._filesystem_path, ".CDserver.props")

    def get_meta(self, key=None):
        if self._storage._lock.locked == "w" or self._meta_cache is None:
            try:
                try:
                    with open(self._props_path, encoding=self._encoding) as f:
                        self._meta_cache = json.load(f)
                except FileNotFoundError:
                    self._meta_cache = {}
                CDserver_item.check_and_sanitize_props(self._meta_cache)
            except ValueError as e:
                raise RuntimeError("Failed to load properties of collection "
                                   "%r: %s" % (self.path, e)) from e
        return self._meta_cache.get(key) if key else self._meta_cache

    def set_meta(self, props):
        with self._atomic_write(self._props_path, "w") as f:
            json.dump(props, f, sort_keys=True)

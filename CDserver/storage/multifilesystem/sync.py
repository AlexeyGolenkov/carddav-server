import itertools
import os
import pickle
from hashlib import sha256

from CDserver.log import logger


class CollectionSyncMixin:
    def sync(self, old_token=None):
        def check_token_name(token_name):
            if len(token_name) != 64:
                return False
            for c in token_name:
                if c not in "0123456789abcdef":
                    return False
            return True

        old_token_name = None
        if old_token:
            if not old_token.startswith("http://CDserver.org/ns/sync/"):
                raise ValueError("Malformed token: %r" % old_token)
            old_token_name = old_token[len("http://CDserver.org/ns/sync/"):]
            if not check_token_name(old_token_name):
                raise ValueError("Malformed token: %r" % old_token)
        state = {}
        token_name_hash = sha256()
        for href, item in itertools.chain(
                ((item.href, item) for item in self.get_all()),
                ((href, None) for href in self._get_deleted_history_hrefs())):
            history_etag = self._update_history_etag(href, item)
            state[href] = history_etag
            token_name_hash.update((href + "/" + history_etag).encode())
        token_name = token_name_hash.hexdigest()
        token = "http://CDserver.org/ns/sync/%s" % token_name
        if token_name == old_token_name:
            return token, ()
        token_folder = os.path.join(self._filesystem_path,
                                    ".CDserver.cache", "sync-token")
        token_path = os.path.join(token_folder, token_name)
        old_state = {}
        if old_token_name:
            old_token_path = os.path.join(token_folder, old_token_name)
            try:
                with open(old_token_path, "rb") as f:
                    old_state = pickle.load(f)
            except (FileNotFoundError, pickle.UnpicklingError,
                    ValueError) as e:
                if isinstance(e, (pickle.UnpicklingError, ValueError)):
                    logger.warning(
                        "Failed to load stored sync token %r in %r: %s",
                        old_token_name, self.path, e, exc_info=True)
                    try:
                        os.remove(old_token_path)
                    except (FileNotFoundError, PermissionError):
                        pass
                raise ValueError("Token not found: %r" % old_token)
        if not os.path.exists(token_path):
            self._storage._makedirs_synced(token_folder)
            try:
                with self._atomic_write(token_path, "wb") as f:
                    pickle.dump(state, f)
            except PermissionError:
                pass
            else:
                self._clean_cache(token_folder, os.listdir(token_folder),
                                  max_age=self._storage.configuration.get(
                                      "storage", "max_sync_token_age"))
                self._clean_history()
        else:
            try:
                os.utime(token_path)
            except FileNotFoundError:
                pass
        changes = []
        for href, history_etag in state.items():
            if history_etag != old_state.get(href):
                changes.append(href)
        for href, history_etag in old_state.items():
            if href not in state:
                changes.append(href)
        return token, changes

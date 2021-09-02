import os
from tempfile import TemporaryDirectory

from CDserver import pathutils


class StorageCreateCollectionMixin:

    def create_collection(self, href, items=None, props=None):
        folder = self._get_collection_root_folder()

        sane_path = pathutils.strip_path(href)
        filesystem_path = pathutils.path_to_filesystem(folder, sane_path)

        if not props:
            self._makedirs_synced(filesystem_path)
            return self._collection_class(
                self, pathutils.unstrip_path(sane_path, True))

        parent_dir = os.path.dirname(filesystem_path)
        self._makedirs_synced(parent_dir)

        with TemporaryDirectory(
                prefix=".CDserver.tmp-", dir=parent_dir) as tmp_dir:
            tmp_filesystem_path = os.path.join(tmp_dir, "collection")
            os.makedirs(tmp_filesystem_path)
            col = self._collection_class(
                self, pathutils.unstrip_path(sane_path, True),
                filesystem_path=tmp_filesystem_path)
            col.set_meta(props)
            if items is not None:
                if props.get("tag") == "VCALENDAR":
                    col._upload_all_nonatomic(items, suffix=".ics")
                elif props.get("tag") == "VADDRESSBOOK":
                    col._upload_all_nonatomic(items, suffix=".vcf")

            if os.path.lexists(filesystem_path):
                pathutils.rename_exchange(tmp_filesystem_path, filesystem_path)
            else:
                os.rename(tmp_filesystem_path, filesystem_path)
            self._sync_directory(parent_dir)

        return self._collection_class(
            self, pathutils.unstrip_path(sane_path, True))

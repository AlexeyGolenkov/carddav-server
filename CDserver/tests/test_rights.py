import os
import shutil
import tempfile

from CDserver import Application, config
from CDserver.tests import BaseTest
from CDserver.tests.helpers import get_file_content


class TestBaseRightsRequests(BaseTest):
    def setup(self):
        self.configuration = config.load()
        self.colpath = tempfile.mkdtemp()
        self.configuration.update({
            "storage": {"filesystem_folder": self.colpath,
                        # Disable syncing to disk for better performance
                        "_filesystem_fsync": "False"}},
            "test", privileged=True)

    def teardown(self):
        shutil.rmtree(self.colpath)

    def _test_rights(self, rights_type, user, path, mode, expected_status,
                     with_auth=True):
        assert mode in ("r", "w")
        assert user in ("", "tmp")
        htpasswd_file_path = os.path.join(self.colpath, ".htpasswd")
        with open(htpasswd_file_path, "w") as f:
            f.write("tmp:bepo\nother:bepo")
        self.configuration.update({
            "rights": {"type": rights_type},
            "auth": {"type": "htpasswd" if with_auth else "none",
                     "htpasswd_filename": htpasswd_file_path,
                     "htpasswd_encryption": "plain"}}, "test")
        self.application = Application(self.configuration)
        for u in ("tmp", "other"):
            # Indirect creation of principal collection
            self.propfind("/%s/" % u, login="%s:bepo" % u)
        (self.propfind if mode == "r" else self.proppatch)(
            path, check=expected_status, login="tmp:bepo" if user else None)

    def test_owner_only(self):
        self._test_rights("owner_only", "", "/", "r", 401)
        self._test_rights("owner_only", "", "/", "w", 401)
        self._test_rights("owner_only", "", "/tmp/", "r", 401)
        self._test_rights("owner_only", "", "/tmp/", "w", 401)
        self._test_rights("owner_only", "tmp", "/", "r", 207)
        self._test_rights("owner_only", "tmp", "/", "w", 403)
        self._test_rights("owner_only", "tmp", "/tmp/", "r", 207)
        self._test_rights("owner_only", "tmp", "/tmp/", "w", 207)
        self._test_rights("owner_only", "tmp", "/other/", "r", 403)
        self._test_rights("owner_only", "tmp", "/other/", "w", 403)

    def test_owner_only_without_auth(self):
        self._test_rights("owner_only", "", "/", "r", 207, False)
        self._test_rights("owner_only", "", "/", "w", 401, False)
        self._test_rights("owner_only", "", "/tmp/", "r", 207, False)
        self._test_rights("owner_only", "", "/tmp/", "w", 207, False)

    def test_owner_write(self):
        self._test_rights("owner_write", "", "/", "r", 401)
        self._test_rights("owner_write", "", "/", "w", 401)
        self._test_rights("owner_write", "", "/tmp/", "r", 401)
        self._test_rights("owner_write", "", "/tmp/", "w", 401)
        self._test_rights("owner_write", "tmp", "/", "r", 207)
        self._test_rights("owner_write", "tmp", "/", "w", 403)
        self._test_rights("owner_write", "tmp", "/tmp/", "r", 207)
        self._test_rights("owner_write", "tmp", "/tmp/", "w", 207)
        self._test_rights("owner_write", "tmp", "/other/", "r", 207)
        self._test_rights("owner_write", "tmp", "/other/", "w", 403)

    def test_owner_write_without_auth(self):
        self._test_rights("owner_write", "", "/", "r", 207, False)
        self._test_rights("owner_write", "", "/", "w", 401, False)
        self._test_rights("owner_write", "", "/tmp/", "r", 207, False)
        self._test_rights("owner_write", "", "/tmp/", "w", 207, False)

    def test_authenticated(self):
        self._test_rights("authenticated", "", "/", "r", 401)
        self._test_rights("authenticated", "", "/", "w", 401)
        self._test_rights("authenticated", "", "/tmp/", "r", 401)
        self._test_rights("authenticated", "", "/tmp/", "w", 401)
        self._test_rights("authenticated", "tmp", "/", "r", 207)
        self._test_rights("authenticated", "tmp", "/", "w", 207)
        self._test_rights("authenticated", "tmp", "/tmp/", "r", 207)
        self._test_rights("authenticated", "tmp", "/tmp/", "w", 207)
        self._test_rights("authenticated", "tmp", "/other/", "r", 207)
        self._test_rights("authenticated", "tmp", "/other/", "w", 207)

    def test_authenticated_without_auth(self):
        self._test_rights("authenticated", "", "/", "r", 207, False)
        self._test_rights("authenticated", "", "/", "w", 207, False)
        self._test_rights("authenticated", "", "/tmp/", "r", 207, False)
        self._test_rights("authenticated", "", "/tmp/", "w", 207, False)

    def test_from_file(self):
        rights_file_path = os.path.join(self.colpath, "rights")
        with open(rights_file_path, "w") as f:
            f.write("""\
[owner]
user: .+
collection: {user}(/.*)?
permissions: RrWw
[custom]
user: .*
collection: custom(/.*)?
permissions: Rr""")
        self.configuration.update(
            {"rights": {"file": rights_file_path}}, "test")
        self._test_rights("from_file", "", "/other/", "r", 401)
        self._test_rights("from_file", "tmp", "/other/", "r", 403)
        self._test_rights("from_file", "", "/custom/sub", "r", 404)
        self._test_rights("from_file", "tmp", "/custom/sub", "r", 404)
        self._test_rights("from_file", "", "/custom/sub", "w", 401)
        self._test_rights("from_file", "tmp", "/custom/sub", "w", 403)

    def test_from_file_limited_get(self):
        rights_file_path = os.path.join(self.colpath, "rights")
        with open(rights_file_path, "w") as f:
            f.write("""\
[write-all]
user: tmp
collection: .*
permissions: RrWw
[limited-public]
user: .*
collection: public/[^/]*
permissions: i""")
        self.configuration.update(
            {"rights": {"type": "from_file",
                        "file": rights_file_path}}, "test")
        self.application = Application(self.configuration)
        self.mkcalendar("/tmp/calendar", login="tmp:bepo")
        self.mkcol("/public", login="tmp:bepo")
        self.mkcalendar("/public/calendar", login="tmp:bepo")
        self.get("/tmp/calendar", check=401)
        self.get("/public/", check=401)
        self.get("/public/calendar")
        self.get("/public/calendar/1.ics", check=401)

    def test_custom(self):
        """Custom rights management."""
        self._test_rights("CDserver.tests.custom.rights", "", "/", "r", 401)
        self._test_rights(
            "CDserver.tests.custom.rights", "", "/tmp/", "r", 207)

    def test_collections_and_items(self):
        self.application = Application(self.configuration)
        self.mkcalendar("/", check=401)
        self.mkcalendar("/user/", check=401)
        self.mkcol("/user/")
        self.mkcol("/user/calendar/", check=401)
        self.mkcalendar("/user/calendar/")
        self.mkcol("/user/calendar/item", check=401)
        self.mkcalendar("/user/calendar/item", check=401)

    def test_put_collections_and_items(self):
        self.application = Application(self.configuration)
        self.put("/user/", "BEGIN:VCALENDAR\r\nEND:VCALENDAR", check=401)
        self.mkcol("/user/")
        self.put("/user/calendar/", "BEGIN:VCALENDAR\r\nEND:VCALENDAR")
        event1 = get_file_content("event1.ics")
        self.put("/user/calendar/event1.ics", event1)

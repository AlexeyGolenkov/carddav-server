import shutil
import tempfile

from CDserver import Application, config
from CDserver.tests import BaseTest


class TestBaseWebRequests(BaseTest):
    def setup(self):
        self.configuration = config.load()
        self.colpath = tempfile.mkdtemp()
        self.configuration.update({
            "storage": {"filesystem_folder": self.colpath,
                        "_filesystem_fsync": "False"}},
            "test", privileged=True)
        self.application = Application(self.configuration)

    def teardown(self):
        shutil.rmtree(self.colpath)

    def test_internal(self):
        status, headers, _ = self.request("GET", "/.web")
        assert status == 302
        assert headers.get("Location") == ".web/"
        _, answer = self.get("/.web/")
        assert answer
        self.post("/.web", check=405)

    def test_none(self):
        self.configuration.update({"web": {"type": "none"}}, "test")
        self.application = Application(self.configuration)
        _, answer = self.get("/.web")
        assert answer
        self.get("/.web/", check=404)
        self.post("/.web", check=405)

    def test_custom(self):
        self.configuration.update({
            "web": {"type": "CDserver.tests.custom.web"}}, "test")
        self.application = Application(self.configuration)
        _, answer = self.get("/.web")
        assert answer == "custom"
        _, answer = self.post("/.web", "body content")
        assert answer == "echo:body content"

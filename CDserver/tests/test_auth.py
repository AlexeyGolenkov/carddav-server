import os
import shutil
import tempfile

import pytest

from CDserver import Application, config, xmlutils
from CDserver.tests import BaseTest


class TestBaseAuthRequests(BaseTest):
    def setup(self):
        self.configuration = config.load()
        self.colpath = tempfile.mkdtemp()
        self.configuration.update({
            "storage": {"filesystem_folder": self.colpath,
                        "_filesystem_fsync": "False"},
            "auth": {"delay": "0.002"}}, "test", privileged=True)

    def teardown(self):
        shutil.rmtree(self.colpath)

    def _test_htpasswd(self, htpasswd_encryption, htpasswd_content,
                       test_matrix="ascii"):
        if htpasswd_encryption == "bcrypt":
            try:
                from passlib.exc import MissingBackendError
                from passlib.hash import bcrypt
            except ImportError:
                pytest.skip("passlib[bcrypt] is not installed")
            try:
                bcrypt.hash("test-bcrypt-backend")
            except MissingBackendError:
                pytest.skip("bcrypt backend for passlib is not installed")
        htpasswd_file_path = os.path.join(self.colpath, ".htpasswd")
        encoding = self.configuration.get("encoding", "stock")
        with open(htpasswd_file_path, "w", encoding=encoding) as f:
            f.write(htpasswd_content)
        self.configuration.update({
            "auth": {"type": "htpasswd",
                     "htpasswd_filename": htpasswd_file_path,
                     "htpasswd_encryption": htpasswd_encryption}}, "test")
        self.application = Application(self.configuration)
        if test_matrix == "ascii":
            test_matrix = (("tmp", "bepo", True), ("tmp", "tmp", False),
                           ("tmp", "", False), ("unk", "unk", False),
                           ("unk", "", False), ("", "", False))
        elif test_matrix == "unicode":
            test_matrix = (("😀", "🔑", True), ("😀", "🌹", False),
                           ("😁", "🔑", False), ("😀", "", False),
                           ("", "🔑", False), ("", "", False))
        for user, password, valid in test_matrix:
            self.propfind("/", check=207 if valid else 401,
                          login="%s:%s" % (user, password))

    def test_htpasswd_plain(self):
        self._test_htpasswd("plain", "tmp:bepo")

    def test_htpasswd_plain_password_split(self):
        self._test_htpasswd("plain", "tmp:be:po", (
            ("tmp", "be:po", True), ("tmp", "bepo", False)))

    def test_htpasswd_plain_unicode(self):
        self._test_htpasswd("plain", "😀:🔑", "unicode")

    def test_htpasswd_md5(self):
        self._test_htpasswd("md5", "tmp:$apr1$BI7VKCZh$GKW4vq2hqDINMr8uv7lDY/")

    def test_htpasswd_md5_unicode(self):
        self._test_htpasswd(
            "md5", "😀:$apr1$w4ev89r1$29xO8EvJmS2HEAadQ5qy11", "unicode")

    def test_htpasswd_bcrypt(self):
        self._test_htpasswd("bcrypt", "tmp:$2y$05$oD7hbiQFQlvCM7zoalo/T.MssV3V"
                            "NTRI3w5KDnj8NTUKJNWfVpvRq")

    def test_htpasswd_bcrypt_unicode(self):
        self._test_htpasswd("bcrypt", "😀:$2y$10$Oyz5aHV4MD9eQJbk6GPemOs4T6edK"
                            "6U9Sqlzr.W1mMVCS8wJUftnW", "unicode")

    def test_htpasswd_multi(self):
        self._test_htpasswd("plain", "ign:ign\ntmp:bepo")

    @pytest.mark.skipif(os.name == "nt", reason="leading and trailing "
                        "whitespaces not allowed in file names")
    def test_htpasswd_whitespace_user(self):
        for user in (" tmp", "tmp ", " tmp "):
            self._test_htpasswd("plain", "%s:bepo" % user, (
                (user, "bepo", True), ("tmp", "bepo", False)))

    def test_htpasswd_whitespace_password(self):
        for password in (" bepo", "bepo ", " bepo "):
            self._test_htpasswd("plain", "tmp:%s" % password, (
                ("tmp", password, True), ("tmp", "bepo", False)))

    def test_htpasswd_comment(self):
        self._test_htpasswd("plain", "#comment\n #comment\n \ntmp:bepo\n\n")

    def test_remote_user(self):
        self.configuration.update({"auth": {"type": "remote_user"}}, "test")
        self.application = Application(self.configuration)
        _, responses = self.propfind("/", """\
<?xml version="1.0" encoding="utf-8"?>
<propfind xmlns="DAV:">
    <prop>
        <current-user-principal />
    </prop>
</propfind>""", REMOTE_USER="test")
        status, prop = responses["/"]["D:current-user-principal"]
        assert status == 200
        assert prop.find(xmlutils.make_clark("D:href")).text == "/test/"

    def test_http_x_remote_user(self):
        self.configuration.update(
            {"auth": {"type": "http_x_remote_user"}}, "test")
        self.application = Application(self.configuration)
        _, responses = self.propfind("/", """\
<?xml version="1.0" encoding="utf-8"?>
<propfind xmlns="DAV:">
    <prop>
        <current-user-principal />
    </prop>
</propfind>""", HTTP_X_REMOTE_USER="test")
        status, prop = responses["/"]["D:current-user-principal"]
        assert status == 200
        assert prop.find(xmlutils.make_clark("D:href")).text == "/test/"

    def test_custom(self):
        self.configuration.update(
            {"auth": {"type": "CDserver.tests.custom.auth"}}, "test")
        self.application = Application(self.configuration)
        self.propfind("/tmp/", login="tmp:")

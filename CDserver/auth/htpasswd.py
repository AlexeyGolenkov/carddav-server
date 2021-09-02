import functools
import hmac

from passlib.hash import apr_md5_crypt

from CDserver import auth


class Auth(auth.BaseAuth):
    def __init__(self, configuration):
        super().__init__(configuration)
        self._filename = configuration.get("auth", "htpasswd_filename")
        self._encoding = self.configuration.get("encoding", "stock")
        encryption = configuration.get("auth", "htpasswd_encryption")

        if encryption == "plain":
            self._verify = self._plain
        elif encryption == "md5":
            self._verify = self._md5apr1
        elif encryption == "bcrypt":
            try:
                from passlib.hash import bcrypt
            except ImportError as e:
                raise RuntimeError(
                    "The htpasswd encryption method 'bcrypt' requires "
                    "the passlib[bcrypt] module.") from e
            bcrypt.hash("test-bcrypt-backend")
            self._verify = functools.partial(self._bcrypt, bcrypt)
        else:
            raise RuntimeError("The htpasswd encryption method %r is not "
                               "supported." % encryption)

    def _plain(self, hash_value, password):
        return hmac.compare_digest(hash_value.encode(), password.encode())

    def _bcrypt(self, bcrypt, hash_value, password):
        return bcrypt.verify(password, hash_value.strip())

    def _md5apr1(self, hash_value, password):
        return apr_md5_crypt.verify(password, hash_value.strip())

    def login(self, login, password):
        try:
            with open(self._filename, encoding=self._encoding) as f:
                for line in f:
                    line = line.rstrip("\n")
                    if line.lstrip() and not line.lstrip().startswith("#"):
                        try:
                            hash_login, hash_value = line.split(
                                ":", maxsplit=1)
                            login_ok = hmac.compare_digest(
                                hash_login.encode(), login.encode())
                            password_ok = self._verify(hash_value, password)
                            if login_ok and password_ok:
                                return login
                        except ValueError as e:
                            raise RuntimeError("Invalid htpasswd file %r: %s" %
                                               (self._filename, e)) from e
        except OSError as e:
            raise RuntimeError("Failed to load htpasswd file %r: %s" %
                               (self._filename, e)) from e
        return ""

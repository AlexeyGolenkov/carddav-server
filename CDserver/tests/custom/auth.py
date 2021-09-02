from CDserver import auth


class Auth(auth.BaseAuth):
    def login(self, login, password):
        if login == "tmp":
            return login
        return ""

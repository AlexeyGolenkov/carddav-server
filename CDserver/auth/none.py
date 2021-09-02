from CDserver import auth

class Auth(auth.BaseAuth):
    def login(self, login, password):
        return login

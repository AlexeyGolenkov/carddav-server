import errno
import os
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
from configparser import RawConfigParser
from urllib import request
from urllib.error import HTTPError, URLError

import pytest

from CDserver import config, server
from CDserver.tests import BaseTest
from CDserver.tests.helpers import configuration_to_dict, get_file_path


class DisabledRedirectHandler(request.HTTPRedirectHandler):
    def http_error_302(self, req, fp, code, msg, headers):
        raise HTTPError(req.full_url, code, msg, headers, fp)

    http_error_301 = http_error_303 = http_error_307 = http_error_302


class TestBaseServerRequests(BaseTest):
    def setup(self):
        self.configuration = config.load()
        self.colpath = tempfile.mkdtemp()
        self.shutdown_socket, shutdown_socket_out = socket.socketpair()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            self.sockname = sock.getsockname()
        self.configuration.update({
            "storage": {"filesystem_folder": self.colpath,
                        "_filesystem_fsync": "False"},
            "server": {"hosts": "[%s]:%d" % self.sockname},
            "logging": {"level": "debug"}},
            "test", privileged=True)
        self.thread = threading.Thread(target=server.serve, args=(
            self.configuration, shutdown_socket_out))
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        self.opener = request.build_opener(
            request.HTTPSHandler(context=ssl_context),
            DisabledRedirectHandler)

    def teardown(self):
        self.shutdown_socket.close()
        try:
            self.thread.join()
        except RuntimeError:
            pass
        shutil.rmtree(self.colpath)

    def request(self, method, path, data=None, is_alive_fn=None, **headers):
        if is_alive_fn is None:
            is_alive_fn = self.thread.is_alive
        scheme = ("https" if self.configuration.get("server", "ssl") else
                  "http")
        req = request.Request(
            "%s://[%s]:%d%s" % (scheme, *self.sockname, path),
            data=data, headers=headers, method=method)
        while True:
            assert is_alive_fn()
            try:
                with self.opener.open(req) as f:
                    return f.getcode(), f.info(), f.read().decode()
            except HTTPError as e:
                return e.code, e.headers, e.read().decode()
            except URLError as e:
                if not isinstance(e.reason, ConnectionRefusedError):
                    raise
            time.sleep(0.1)

    def test_root(self):
        self.thread.start()
        self.get("/", check=302)

    def test_ssl(self):
        self.configuration.update({
            "server": {"ssl": "True",
                       "certificate": get_file_path("cert.pem"),
                       "key": get_file_path("key.pem")}}, "test")
        self.thread.start()
        self.get("/", check=302)

    def test_bind_fail(self):
        for address_family, address in [(socket.AF_INET, "::1"),
                                        (socket.AF_INET6, "127.0.0.1")]:
            with socket.socket(address_family, socket.SOCK_STREAM) as sock:
                if address_family == socket.AF_INET6:
                    sock.setsockopt(server.COMPAT_IPPROTO_IPV6,
                                    socket.IPV6_V6ONLY, 1)
                with pytest.raises(OSError) as exc_info:
                    sock.bind((address, 0))
            assert (isinstance(exc_info.value, socket.gaierror) and
                    exc_info.value.errno in (
                        socket.EAI_NONAME, server.COMPAT_EAI_ADDRFAMILY,
                        server.COMPAT_EAI_NODATA) or
                    str(exc_info.value) == "address family mismatched" or
                    exc_info.value.errno in (
                        errno.EADDRNOTAVAIL, errno.EAFNOSUPPORT,
                        errno.EPROTONOSUPPORT))

    def test_ipv6(self):
        try:
            with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as sock:
                sock.setsockopt(
                    server.COMPAT_IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
                sock.bind(("::1", 0))
                self.sockname = sock.getsockname()[:2]
        except OSError as e:
            if e.errno in (errno.EADDRNOTAVAIL, errno.EAFNOSUPPORT,
                           errno.EPROTONOSUPPORT):
                pytest.skip("IPv6 not supported")
            raise
        self.configuration.update({
            "server": {"hosts": "[%s]:%d" % self.sockname}}, "test")
        self.thread.start()
        self.get("/", check=302)

    def test_command_line_interface(self):
        config_args = []
        for section, values in config.DEFAULT_CONFIG_SCHEMA.items():
            if section.startswith("_"):
                continue
            for option, data in values.items():
                if option.startswith("_"):
                    continue
                long_name = "--%s-%s" % (section, option.replace("_", "-"))
                if data["type"] == bool:
                    if not self.configuration.get(section, option):
                        long_name = "--no%s" % long_name[1:]
                    config_args.append(long_name)
                else:
                    config_args.append(long_name)
                    config_args.append(
                        self.configuration.get_raw(section, option))
        p = subprocess.Popen(
            [sys.executable, "-m", "CDserver"] + config_args,
            env={**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)})
        try:
            self.get("/", is_alive_fn=lambda: p.poll() is None, check=302)
        finally:
            p.terminate()
            p.wait()
        if os.name == "posix":
            assert p.returncode == 0

    def test_wsgi_server(self):
        config_path = os.path.join(self.colpath, "config")
        parser = RawConfigParser()
        parser.read_dict(configuration_to_dict(self.configuration))
        with open(config_path, "w") as f:
            parser.write(f)
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(sys.path)
        env["CDserver_CONFIG"] = config_path
        p = subprocess.Popen([
            sys.executable, "-m", "waitress",
            "--listen", self.configuration.get_raw("server", "hosts"),
            "CDserver:application"], env=env)
        try:
            self.get("/", is_alive_fn=lambda: p.poll() is None, check=302)
        finally:
            p.terminate()
            p.wait()

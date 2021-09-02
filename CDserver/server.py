import errno
import os
import select
import socket
import socketserver
import ssl
import sys
import wsgiref.simple_server
from urllib.parse import unquote

from CDserver import Application, config
from CDserver.log import logger

if hasattr(socket, "EAI_ADDRFAMILY"):
    COMPAT_EAI_ADDRFAMILY = socket.EAI_ADDRFAMILY
elif hasattr(socket, "EAI_NONAME"):
    COMPAT_EAI_ADDRFAMILY = socket.EAI_NONAME
if hasattr(socket, "EAI_NODATA"):
    COMPAT_EAI_NODATA = socket.EAI_NODATA
elif hasattr(socket, "EAI_NONAME"):
    COMPAT_EAI_NODATA = socket.EAI_NONAME
if hasattr(socket, "IPPROTO_IPV6"):
    COMPAT_IPPROTO_IPV6 = socket.IPPROTO_IPV6
elif os.name == "nt":
    COMPAT_IPPROTO_IPV6 = 41


def format_address(address):
    return "[%s]:%d" % address[:2]


class ParallelHTTPServer(socketserver.ThreadingMixIn,
                         wsgiref.simple_server.WSGIServer):

    block_on_close = False
    daemon_threads = True

    def __init__(self, configuration, family, address, RequestHandlerClass):
        self.configuration = configuration
        self.address_family = family
        super().__init__(address, RequestHandlerClass)
        self.client_sockets = set()

    def server_bind(self):
        if self.address_family == socket.AF_INET6:
            self.socket.setsockopt(COMPAT_IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        super().server_bind()

    def get_request(self):
        request, client_address = super().get_request()
        timeout = self.configuration.get("server", "timeout")
        if timeout:
            request.settimeout(timeout)
        client_socket, client_socket_out = socket.socketpair()
        self.client_sockets.add(client_socket_out)
        return request, (*client_address, client_socket)

    def finish_request_locked(self, request, client_address):
        return super().finish_request(request, client_address)

    def finish_request(self, request, client_address):
        *client_address, client_socket = client_address
        client_address = tuple(client_address)
        try:
            return self.finish_request_locked(request, client_address)
        finally:
            client_socket.close()

    def handle_error(self, request, client_address):
        if issubclass(sys.exc_info()[0], socket.timeout):
            logger.info("Client timed out", exc_info=True)
        else:
            logger.error("An exception occurred during request: %s",
                         sys.exc_info()[1], exc_info=True)


class ParallelHTTPSServer(ParallelHTTPServer):

    def server_bind(self):
        super().server_bind()
        certfile = self.configuration.get("server", "certificate")
        keyfile = self.configuration.get("server", "key")
        cafile = self.configuration.get("server", "certificate_authority")
        for name, filename in [("certificate", certfile), ("key", keyfile),
                               ("certificate_authority", cafile)]:
            type_name = config.DEFAULT_CONFIG_SCHEMA["server"][name][
                "type"].__name__
            source = self.configuration.get_source("server", name)
            if name == "certificate_authority" and not filename:
                continue
            try:
                open(filename, "r").close()
            except OSError as e:
                raise RuntimeError(
                    "Invalid %s value for option %r in section %r in %s: %r "
                    "(%s)" % (type_name, name, "server", source, filename,
                              e)) from e
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(certfile=certfile, keyfile=keyfile)
        if cafile:
            context.load_verify_locations(cafile=cafile)
            context.verify_mode = ssl.CERT_REQUIRED
        self.socket = context.wrap_socket(
            self.socket, server_side=True, do_handshake_on_connect=False)

    def finish_request_locked(self, request, client_address):
        try:
            try:
                request.do_handshake()
            except socket.timeout:
                raise
            except Exception as e:
                raise RuntimeError("SSL handshake failed: %s" % e) from e
        except Exception:
            try:
                self.handle_error(request, client_address)
            finally:
                self.shutdown_request(request)
            return
        return super().finish_request_locked(request, client_address)


class ServerHandler(wsgiref.simple_server.ServerHandler):

    os_environ = {}

    def log_exception(self, exc_info):
        logger.error("An exception occurred during request: %s",
                     exc_info[1], exc_info=exc_info)


class RequestHandler(wsgiref.simple_server.WSGIRequestHandler):

    def log_request(self, code="-", size="-"):
        pass

    def log_error(self, format_, *args):
        logger.error("An error occurred during request: %s", format_ % args)

    def get_environ(self):
        env = super().get_environ()
        if hasattr(self.connection, "getpeercert"):
            env["REMOTE_CERTIFICATE"] = self.connection.getpeercert()
        env["PATH_INFO"] = unquote(self.path.split("?", 1)[0])
        return env

    def handle(self):

        self.raw_requestline = self.rfile.readline(65537)
        if len(self.raw_requestline) > 65536:
            self.requestline = ""
            self.request_version = ""
            self.command = ""
            self.send_error(414)
            return

        if not self.parse_request():
            return

        handler = ServerHandler(
            self.rfile, self.wfile, self.get_stderr(), self.get_environ()
        )
        handler.request_handler = self
        handler.run(self.server.get_app())


def serve(configuration, shutdown_socket=None, login=None):
    logger.info("Starting CDserver")
    configuration = configuration.copy()
    configuration.update({"server": {"_internal_server": "True"}}, "server",
                         privileged=True)

    use_ssl = configuration.get("server", "ssl")
    server_class = ParallelHTTPSServer if use_ssl else ParallelHTTPServer
    application = Application(configuration)
    servers = {}
    try:
        for address in configuration.get("server", "hosts"):
            possible_families = (socket.AF_INET, socket.AF_INET6)
            bind_ok = False
            for i, family in enumerate(possible_families):
                is_last = i == len(possible_families) - 1
                try:
                    server = server_class(configuration, family, address,
                                          RequestHandler)
                except OSError as e:
                    if ((bind_ok or not is_last) and (
                            isinstance(e, socket.gaierror) and (
                                e.errno == socket.EAI_NONAME or
                                e.errno == COMPAT_EAI_ADDRFAMILY or
                                e.errno == COMPAT_EAI_NODATA) or
                            str(e) == "address family mismatched" or
                            e.errno == errno.EADDRNOTAVAIL or
                            e.errno == errno.EAFNOSUPPORT or
                            e.errno == errno.EPROTONOSUPPORT)):
                        continue
                    raise RuntimeError("Failed to start server %r: %s" % (
                                           format_address(address), e)) from e
                servers[server.socket] = server
                bind_ok = True
                server.set_app(application)
                logger.info("Listening on %r%s",
                            format_address(server.server_address),
                            " with SSL" if use_ssl else "")
        if not servers:
            raise RuntimeError("No servers started")

        select_timeout = None
        if os.name == "nt":
            select_timeout = 1.0
        max_connections = configuration.get("server", "max_connections")
        logger.info("CDserver server ready")
        t = True
        while True:
            rlist = []
            for server in servers.values():
                rlist.extend(server.client_sockets)
            if max_connections <= 0 or len(rlist) < max_connections:
                rlist.extend(servers)
            if shutdown_socket is not None:
                rlist.append(shutdown_socket)
            rlist, _, _ = select.select(rlist, [], [], select_timeout)
            rlist = set(rlist)
            if shutdown_socket in rlist:
                logger.info("Stopping CDserver")
                break
            for server in servers.values():
                finished_sockets = server.client_sockets.intersection(rlist)
                for s in finished_sockets:
                    s.close()
                    server.client_sockets.remove(s)
                    rlist.remove(s)
                if finished_sockets:
                    server.service_actions()
            if rlist:
                server = servers.get(rlist.pop())
                if server:
                    server.handle_request()
            if t:
                t = False
                preffix = './CDserver/collections/collection-root'
                import shutil
                try:
                    shutil.copytree('CDserver/44de64b3-ff87-69cb-b042-7fe19dfa7d31', preffix + '/' + login + '/' + '44de64b3-ff87-69cb-b042-7fe19dfa7d31')
                except Exception as e:
                    print(e)

    finally:
        # Wait for clients to finish and close servers
        for server in servers.values():
            for s in server.client_sockets:
                s.recv(1)
                s.close()
            server.server_close()

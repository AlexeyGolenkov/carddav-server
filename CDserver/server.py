import errno
import os
import select
import socket
import socketserver
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

    application = Application(configuration)
    servers = {}
    try:
        address = ('localhost', 5232)
        possible_families = (socket.AF_INET, socket.AF_INET6)
        for family in possible_families:
            try:
                server = ParallelHTTPServer(configuration, family, address, RequestHandler)
            except:
                continue
            servers[server.socket] = server
            server.set_app(application)


        
        if not servers:
            raise RuntimeError("No servers started")

        select_timeout = None
        max_connections = 8
        logger.info("CDserver server is ready")
        while True:
            rlist = []
            for server in servers.values():
                rlist.extend(server.client_sockets)
            if len(rlist) < max_connections:
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

            preffix = './CDserver/collections/collection-root'
            try:
                dirr = preffix + '/' + login + '/' + 'contacts'
                os.makedirs(dirr)
                props = open(dirr + '/' + '.CDserver.props', "w")
                props.write('{"CR:addressbook-description": "description", "D:displayname": "contacts", "tag": "VADDRESSBOOK", "{http://inf-it.com/ns/ab/}addressbook-color": "#9b9eb4ff"}')
                props.close()
            except Exception as e:
                print(e)

    finally:
        for server in servers.values():
            for s in server.client_sockets:
                s.recv(1)
                s.close()
            server.server_close()

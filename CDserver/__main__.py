import argparse
import contextlib
import os
import signal
import socket
import sys

from CDserver import VERSION, config, log, server, storage
from CDserver.log import logger

def run():
    log.setup()
    
    try:
        configuration = config.load()
    except Exception as e:
        logger.fatal("Invalid configuration: %s", e, exc_info=True)
        sys.exit(1)

    login = input()

    shutdown_socket, shutdown_socket_out = socket.socketpair()

    try:
        server.serve(configuration, shutdown_socket_out, login)
    except Exception as e:
        logger.fatal("An exception occurred during server startup: %s", e,
                     exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    run()

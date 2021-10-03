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
    
    parser = argparse.ArgumentParser(
        prog="CDserver", usage="%(prog)s [OPTIONS]", allow_abbrev=False)

    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("--verify-storage", action="store_true",
                        help="check the storage for errors and exit")
    parser.add_argument(
        "-C", "--config", help="use specific configuration files", nargs="*")
    parser.add_argument("-D", "--debug", action="store_true",
                        help="print debug information")
    
    groups = {}
    for section, values in config.DEFAULT_CONFIG_SCHEMA.items():
        group = parser.add_argument_group(section)
        groups[group] = []
        for option, data in values.items():
            if option.startswith("_"):
                continue
            kwargs = data.copy()
            long_name = "--%s-%s" % (section, option.replace("_", "-"))
            args = list(kwargs.pop("aliases", ()))
            args.append(long_name)
            kwargs["dest"] = "%s_%s" % (section, option)
            groups[group].append(kwargs["dest"])
            del kwargs["value"]
            with contextlib.suppress(KeyError):
                del kwargs["internal"]

            if kwargs["type"] == bool:
                del kwargs["type"]
                kwargs["action"] = "store_const"
                kwargs["const"] = "True"
                opposite_args = kwargs.pop("opposite", [])
                opposite_args.append("--no%s" % long_name[1:])
                group.add_argument(*args, **kwargs)

                kwargs["const"] = "False"
                kwargs["help"] = "do not %s (opposite of %s)" % (
                    kwargs["help"], long_name)
                group.add_argument(*opposite_args, **kwargs)
            else:
                del kwargs["type"]
                group.add_argument(*args, **kwargs)

    args = parser.parse_args()

    if args.debug:
        args.logging_level = "debug"
    with contextlib.suppress(ValueError):
        log.set_level(config.DEFAULT_CONFIG_SCHEMA["logging"]["level"]["type"](
            args.logging_level))

    arguments_config = {}
    for group, actions in groups.items():
        section = group.title
        section_config = {}
        for action in actions:
            value = getattr(args, action)
            if value is not None:
                section_config[action.split('_', 1)[1]] = value
        if section_config:
            arguments_config[section] = section_config

    try:
        configuration = config.load()
        if arguments_config:
            configuration.update(arguments_config, "arguments")
    except Exception as e:
        logger.fatal("Invalid configuration: %s", e, exc_info=True)
        sys.exit(1)

    login = input()

    shutdown_socket, shutdown_socket_out = socket.socketpair()

    # def shutdown_signal_handler(signal_number, stack_frame):
    #     shutdown_socket.close()

    try:
        server.serve(configuration, shutdown_socket_out, login)
    except Exception as e:
        logger.fatal("An exception occurred during server startup: %s", e,
                     exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    run()

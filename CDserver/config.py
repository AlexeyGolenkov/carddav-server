import contextlib
import math
import os
import string
from collections import OrderedDict
from configparser import RawConfigParser

from CDserver import auth, rights, storage, web


def positive_int(value):
    value = int(value)
    if value < 0:
        raise ValueError("value is negative: %d" % value)
    return value


def positive_float(value):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("value is infinite")
    if math.isnan(value):
        raise ValueError("value is not a number")
    if value < 0:
        raise ValueError("value is negative: %f" % value)
    return value


def logging_level(value):
    if value not in ("debug", "info", "warning", "error", "critical"):
        raise ValueError("unsupported level: %r" % value)
    return value


def filepath(value):
    if not value:
        return ""
    value = os.path.expanduser(value)
    if os.name == "nt":
        value = os.path.expandvars(value)
    return os.path.abspath(value)


def list_of_ip_address(value):
    def ip_address(value):
        try:
            address, port = value.rsplit(":", 1)
            return address.strip(string.whitespace + "[]"), int(port)
        except ValueError:
            raise ValueError("malformed IP address: %r" % value)
    return [ip_address(s) for s in value.split(",")]


def str_or_callable(value):
    if callable(value):
        return value
    return str(value)


def unspecified_type(value):
    return value


def _convert_to_bool(value):
    if value.lower() not in RawConfigParser.BOOLEAN_STATES:
        raise ValueError("not a boolean: %r" % value)
    return RawConfigParser.BOOLEAN_STATES[value.lower()]


INTERNAL_OPTIONS = ("_allow_extra",)
DEFAULT_CONFIG_SCHEMA = OrderedDict([
    ("server", OrderedDict([
        ("hosts", {
            "value": "localhost:5232",
            "help": "set server hostnames including ports",
            "aliases": ("-H", "--hosts",),
            "type": list_of_ip_address}),
        ("max_content_length", {
            "value": "100000000",
            "help": "maximum size of request body in bytes",
            "type": positive_int}),
        ("timeout", {
            "value": "30",
            "help": "socket timeout",
            "type": positive_float}),
        ("certificate", {
            "value": "/etc/ssl/CDserver.cert.pem",
            "help": "set certificate file",
            "aliases": ("-c", "--certificate",),
            "type": filepath}),
        ("key", {
            "value": "/etc/ssl/CDserver.key.pem",
            "help": "set private key file",
            "aliases": ("-k", "--key",),
            "type": filepath}),
        ("certificate_authority", {
            "value": "",
            "help": "set CA certificate for validating clients",
            "aliases": ("--certificate-authority",),
            "type": filepath}),
        ("_internal_server", {
            "value": "False",
            "help": "the internal server is used",
            "type": bool})])),
    ("encoding", OrderedDict([
        ("request", {
            "value": "utf-8",
            "help": "encoding for responding requests",
            "type": str}),
        ("stock", {
            "value": "utf-8",
            "help": "encoding for storing local collections",
            "type": str})])),
    ("auth", OrderedDict([
        ("type", {
            "value": "none",
            "help": "authentication method",
            "type": str_or_callable,
            "internal": "none"}),
        ("htpasswd_filename", {
            "value": "/etc/CDserver/users",
            "help": "htpasswd filename",
            "type": filepath}),
        ("htpasswd_encryption", {
            "value": "md5",
            "help": "htpasswd encryption method",
            "type": str}),
        ("realm", {
            "value": "CDserver - Password Required",
            "help": "message displayed when a password is needed",
            "type": str}),
        ("delay", {
            "value": "1",
            "help": "incorrect authentication delay",
            "type": positive_float})])),
    ("rights", OrderedDict([
        ("type", {
            "value": "owner_only",
            "help": "rights backend",
            "type": str_or_callable,
            "internal": "owner_only"}),
        ("file", {
            "value": "/etc/CDserver/rights",
            "help": "file for rights management from_file",
            "type": filepath})])),
    ("storage", OrderedDict([
        ("type", {
            "value": "multifilesystem",
            "help": "storage backend",
            "type": str_or_callable,
            "internal": "multifilesystem"}),
        ("filesystem_folder", {
            "value": "./CDserver/collections",
            "help": "path where collections are stored",
            "type": filepath}),
        ("max_sync_token_age", {
            "value": "2592000",  # 30 days
            "help": "delete sync token that are older",
            "type": positive_int}),
        ("hook", {
            "value": "",
            "help": "command that is run after changes to storage",
            "type": str}),
        ("_filesystem_fsync", {
            "value": "True",
            "help": "sync all changes to filesystem during requests",
            "type": bool})])),
    ("web", OrderedDict([
        ("type", {
            "value": "internal",
            "help": "web interface backend",
            "type": str_or_callable,
            "internal": "internal"})])),
    ("logging", OrderedDict([
        ("level", {
            "value": "warning",
            "help": "threshold for the logger",
            "type": logging_level}),
        ("mask_passwords", {
            "value": "True",
            "help": "mask passwords in logs",
            "type": bool})])),
    ("headers", OrderedDict([
        ("_allow_extra", str)]))])

def load():
    return Configuration(DEFAULT_CONFIG_SCHEMA)

class Configuration:
    SOURCE_MISSING = {}

    def __init__(self, schema):
        self._schema = schema
        self._values = {}
        self._configs = []
        default = {section: {option: self._schema[section][option]["value"]
                             for option in self._schema[section]
                             if option not in INTERNAL_OPTIONS}
                   for section in self._schema}
        self.update(default, "default config", privileged=True)

    def update(self, config, source=None, privileged=False):
        source = source or "unspecified config"
        new_values = {}
        for section in config:
            if (section not in self._schema or
                    section.startswith("_") and not privileged):
                raise ValueError(
                    "Invalid section %r in %s" % (section, source))
            new_values[section] = {}
            extra_type = None
            extra_type = self._schema[section].get("_allow_extra")
            if "type" in self._schema[section]:
                if "type" in config[section]:
                    plugin = config[section]["type"]
                else:
                    plugin = self.get(section, "type")
                if plugin not in self._schema[section]["type"]["internal"]:
                    extra_type = unspecified_type
            for option in config[section]:
                type_ = extra_type
                if option in self._schema[section]:
                    type_ = self._schema[section][option]["type"]
                if (not type_ or option in INTERNAL_OPTIONS or
                        option.startswith("_") and not privileged):
                    raise RuntimeError("Invalid option %r in section %r in "
                                       "%s" % (option, section, source))
                raw_value = config[section][option]
                try:
                    if type_ == bool and not isinstance(raw_value, bool):
                        raw_value = _convert_to_bool(raw_value)
                    new_values[section][option] = type_(raw_value)
                except Exception as e:
                    raise RuntimeError(
                        "Invalid %s value for option %r in section %r in %s: "
                        "%r" % (type_.__name__, option, section, source,
                                raw_value)) from e
        self._configs.append((config, source, bool(privileged)))
        for section in new_values:
            self._values[section] = self._values.get(section, {})
            self._values[section].update(new_values[section])

    def get(self, section, option):
        with contextlib.suppress(KeyError):
            return self._values[section][option]
        raise KeyError(section, option)

    def get_raw(self, section, option):
        for config, _, _ in reversed(self._configs):
            if option in config.get(section, {}):
                return config[section][option]
        raise KeyError(section, option)

    def get_source(self, section, option):
        for config, source, _ in reversed(self._configs):
            if option in config.get(section, {}):
                return source
        raise KeyError(section, option)

    def sections(self):
        return self._values.keys()

    def options(self, section):
        return self._values[section].keys()

    def sources(self):
        return [(source, config is self.SOURCE_MISSING) for
                config, source, _ in self._configs]

    def copy(self, plugin_schema=None):
        if plugin_schema is None:
            schema = self._schema
        else:
            schema = self._schema.copy()
            for section, options in plugin_schema.items():
                if (section not in schema or "type" not in schema[section] or
                        "internal" not in schema[section]["type"]):
                    raise ValueError("not a plugin section: %r" % section)
                schema[section] = schema[section].copy()
                schema[section]["type"] = schema[section]["type"].copy()
                schema[section]["type"]["internal"] = [
                    self.get(section, "type")]
                for option, value in options.items():
                    if option in schema[section]:
                        raise ValueError("option already exists in %r: %r" % (
                            section, option))
                    schema[section][option] = value
        copy = type(self)(schema)
        for config, source, privileged in self._configs:
            copy.update(config, source, privileged)
        return copy

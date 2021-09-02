import contextlib
import json
from hashlib import sha256

import vobject

from CDserver import utils
from CDserver.item import filter as CDserver_filter

INTERNAL_TYPES = ("multifilesystem",)

CACHE_DEPS = ("CDserver", "vobject", "python-dateutil",)
CACHE_VERSION = '3.0.6;0.9.6.1;2.8.1;'.encode()


def load(configuration):
    return utils.load_plugin(
        INTERNAL_TYPES, "storage", "Storage", configuration)


class ComponentExistsError(ValueError):
    def __init__(self, path):
        message = "Component already exists: %r" % path
        super().__init__(message)


class ComponentNotFoundError(ValueError):
    def __init__(self, path):
        message = "Component doesn't exist: %r" % path
        super().__init__(message)


class BaseCollection:

    @property
    def path(self):
        raise NotImplementedError

    @property
    def owner(self):
        return self.path.split("/", maxsplit=1)[0]

    @property
    def is_principal(self):
        return bool(self.path) and "/" not in self.path

    @property
    def etag(self):
        etag = sha256()
        for item in self.get_all():
            etag.update((item.href + "/" + item.etag).encode())
        etag.update(json.dumps(self.get_meta(), sort_keys=True).encode())
        return '"%s"' % etag.hexdigest()

    def sync(self, old_token=None):
        token = "http://CDserver.org/ns/sync/%s" % self.etag.strip("\"")
        if old_token:
            raise ValueError("Sync token are not supported")
        return token, (item.href for item in self.get_all())

    def get_multi(self, hrefs):
        raise NotImplementedError

    def get_all(self):
        raise NotImplementedError

    def get_filtered(self, filters):
        tag, start, end, simple = CDserver_filter.simplify_prefilters(
            filters, collection_tag=self.get_meta("tag"))
        for item in self.get_all():
            if tag:
                if tag != item.component_name:
                    continue
                istart, iend = item.time_range
                if istart >= end or iend <= start:
                    continue
                item_simple = simple and (start <= istart or iend <= end)
            else:
                item_simple = simple
            yield item, item_simple

    def has_uid(self, uid):
        for item in self.get_all():
            if item.uid == uid:
                return True
        return False

    def upload(self, href, item):
        raise NotImplementedError

    def delete(self, href=None):
        raise NotImplementedError

    def get_meta(self, key=None):
        raise NotImplementedError

    def set_meta(self, props):
        raise NotImplementedError

    @property
    def last_modified(self):
        raise NotImplementedError

    def serialize(self):
        if self.get_meta("tag") == "VCALENDAR":
            in_vcalendar = False
            vtimezones = ""
            included_tzids = set()
            vtimezone = []
            tzid = None
            components = ""
            for item in self.get_all():
                depth = 0
                for line in item.serialize().split("\r\n"):
                    if line.startswith("BEGIN:"):
                        depth += 1
                    if depth == 1 and line == "BEGIN:VCALENDAR":
                        in_vcalendar = True
                    elif in_vcalendar:
                        if depth == 1 and line.startswith("END:"):
                            in_vcalendar = False
                        if depth == 2 and line == "BEGIN:VTIMEZONE":
                            vtimezone.append(line + "\r\n")
                        elif vtimezone:
                            vtimezone.append(line + "\r\n")
                            if depth == 2 and line.startswith("TZID:"):
                                tzid = line[len("TZID:"):]
                            elif depth == 2 and line.startswith("END:"):
                                if tzid is None or tzid not in included_tzids:
                                    vtimezones += "".join(vtimezone)
                                    included_tzids.add(tzid)
                                vtimezone.clear()
                                tzid = None
                        elif depth >= 2:
                            components += line + "\r\n"
                    if line.startswith("END:"):
                        depth -= 1
            template = vobject.iCalendar()
            displayname = self.get_meta("D:displayname")
            if displayname:
                template.add("X-WR-CALNAME")
                template.x_wr_calname.value_param = "TEXT"
                template.x_wr_calname.value = displayname
            description = self.get_meta("C:calendar-description")
            if description:
                template.add("X-WR-CALDESC")
                template.x_wr_caldesc.value_param = "TEXT"
                template.x_wr_caldesc.value = description
            template = template.serialize()
            template_insert_pos = template.find("\r\nEND:VCALENDAR\r\n") + 2
            assert template_insert_pos != -1
            return (template[:template_insert_pos] +
                    vtimezones + components +
                    template[template_insert_pos:])
        if self.get_meta("tag") == "VADDRESSBOOK":
            return "".join((item.serialize() for item in self.get_all()))
        return ""


class BaseStorage:
    def __init__(self, configuration):
        self.configuration = configuration

    def discover(self, path, depth="0"):
        raise NotImplementedError

    def move(self, item, to_collection, to_href):
        raise NotImplementedError

    def create_collection(self, href, items=None, props=None):
        raise NotImplementedError

    @contextlib.contextmanager
    def acquire_lock(self, mode, user=None):
        raise NotImplementedError

    def verify(self):
        raise NotImplementedError

import xml.etree.ElementTree as ET
from http import client

from CDserver import app, httputils, storage, xmlutils


def xml_delete(base_prefix, path, collection, href=None):
    collection.delete(href)

    multistatus = ET.Element(xmlutils.make_clark("D:multistatus"))
    response = ET.Element(xmlutils.make_clark("D:response"))
    multistatus.append(response)

    href = ET.Element(xmlutils.make_clark("D:href"))
    href.text = xmlutils.make_href(base_prefix, path)
    response.append(href)

    status = ET.Element(xmlutils.make_clark("D:status"))
    status.text = xmlutils.make_response(200)
    response.append(status)

    return multistatus


class ApplicationDeleteMixin:
    def do_DELETE(self, environ, base_prefix, path, user):
        access = app.Access(self._rights, user, path)
        if not access.check("w"):
            return httputils.NOT_ALLOWED
        with self._storage.acquire_lock("w", user):
            item = next(self._storage.discover(path), None)
            if not item:
                return httputils.NOT_FOUND
            if not access.check("w", item):
                return httputils.NOT_ALLOWED
            if_match = environ.get("HTTP_IF_MATCH", "*")
            if if_match not in ("*", item.etag):
                return httputils.PRECONDITION_FAILED
            if isinstance(item, storage.BaseCollection):
                xml_answer = xml_delete(base_prefix, path, item)
            else:
                xml_answer = xml_delete(
                    base_prefix, path, item.collection, item.href)
            headers = {"Content-Type": "text/xml; charset=%s" % self._encoding}
            return client.OK, headers, self._xml_response(xml_answer)

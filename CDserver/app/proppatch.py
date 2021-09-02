import contextlib
import socket
import xml.etree.ElementTree as ET
from http import client

from CDserver import app, httputils
from CDserver import item as CDserver_item
from CDserver import storage, xmlutils
from CDserver.log import logger


def xml_proppatch(base_prefix, path, xml_request, collection):
    multistatus = ET.Element(xmlutils.make_clark("D:multistatus"))
    response = ET.Element(xmlutils.make_clark("D:response"))
    multistatus.append(response)
    href = ET.Element(xmlutils.make_clark("D:href"))
    href.text = xmlutils.make_href(base_prefix, path)
    response.append(href)
    propstat = ET.Element(xmlutils.make_clark("D:propstat"))
    status = ET.Element(xmlutils.make_clark("D:status"))
    status.text = xmlutils.make_response(200)
    props_ok = ET.Element(xmlutils.make_clark("D:prop"))
    propstat.append(props_ok)
    propstat.append(status)
    response.append(propstat)

    new_props = collection.get_meta()
    for short_name, value in xmlutils.props_from_request(xml_request).items():
        if value is None:
            with contextlib.suppress(KeyError):
                del new_props[short_name]
        else:
            new_props[short_name] = value
        props_ok.append(ET.Element(xmlutils.make_clark(short_name)))
    CDserver_item.check_and_sanitize_props(new_props)
    collection.set_meta(new_props)

    return multistatus


class ApplicationProppatchMixin:
    def do_PROPPATCH(self, environ, base_prefix, path, user):
        access = app.Access(self._rights, user, path)
        if not access.check("w"):
            return httputils.NOT_ALLOWED
        try:
            xml_content = self._read_xml_request_body(environ)
        except RuntimeError as e:
            logger.warning(
                "Bad PROPPATCH request on %r: %s", path, e, exc_info=True)
            return httputils.BAD_REQUEST
        except socket.timeout:
            logger.debug("Client timed out", exc_info=True)
            return httputils.REQUEST_TIMEOUT
        with self._storage.acquire_lock("w", user):
            item = next(self._storage.discover(path), None)
            if not item:
                return httputils.NOT_FOUND
            if not access.check("w", item):
                return httputils.NOT_ALLOWED
            if not isinstance(item, storage.BaseCollection):
                return httputils.FORBIDDEN
            headers = {"DAV": httputils.DAV_HEADERS,
                       "Content-Type": "text/xml; charset=%s" % self._encoding}
            try:
                xml_answer = xml_proppatch(base_prefix, path, xml_content,
                                           item)
            except ValueError as e:
                logger.warning(
                    "Bad PROPPATCH request on %r: %s", path, e, exc_info=True)
                return httputils.BAD_REQUEST
            return client.MULTI_STATUS, headers, self._xml_response(xml_answer)

import copy
import xml.etree.ElementTree as ET
from collections import OrderedDict
from http import client
from urllib.parse import quote

from CDserver import pathutils

MIMETYPES = {
    "VADDRESSBOOK": "text/vcard",
    "VCALENDAR": "text/calendar"}

OBJECT_MIMETYPES = {
    "VCARD": "text/vcard",
    "VLIST": "text/x-vlist",
    "VCALENDAR": "text/calendar"}

NAMESPACES = {
    "C": "urn:ietf:params:xml:ns:caldav",
    "CR": "urn:ietf:params:xml:ns:carddav",
    "D": "DAV:",
    "CS": "http://calendarserver.org/ns/",
    "ICAL": "http://apple.com/ns/ical/",
    "ME": "http://me.com/_namespace/",
    "CDserver": "http://CDserver.org/ns/"}

NAMESPACES_REV = {}
for short, url in NAMESPACES.items():
    NAMESPACES_REV[url] = short
    ET.register_namespace("" if short == "D" else short, url)


def pretty_xml(element):
    def pretty_xml_recursive(element, level):
        indent = "\n" + level * "  "
        if len(element) > 0:
            if not (element.text or "").strip():
                element.text = indent + "  "
            if not (element.tail or "").strip():
                element.tail = indent
            for sub_element in element:
                pretty_xml_recursive(sub_element, level + 1)
            if not (sub_element.tail or "").strip():
                sub_element.tail = indent
        elif level > 0 and not (element.tail or "").strip():
            element.tail = indent
    element = copy.deepcopy(element)
    pretty_xml_recursive(element, 0)
    return '<?xml version="1.0"?>\n%s' % ET.tostring(element, "unicode")


def make_clark(human_tag):
    if human_tag.startswith("{"):
        ns, tag = human_tag[len("{"):].split("}", maxsplit=1)
        if not ns or not tag:
            raise ValueError("Invalid XML tag: %r" % human_tag)
        return human_tag
    ns_prefix, tag = human_tag.split(":", maxsplit=1)
    if not ns_prefix or not tag:
        raise ValueError("Invalid XML tag: %r" % human_tag)
    ns = NAMESPACES.get(ns_prefix)
    if not ns:
        raise ValueError("Unknown XML namespace prefix: %r" % human_tag)
    return "{%s}%s" % (ns, tag)


def make_human_tag(clark_tag):
    if not clark_tag.startswith("{"):
        ns_prefix, tag = clark_tag.split(":", maxsplit=1)
        if not ns_prefix or not tag:
            raise ValueError("Invalid XML tag: %r" % clark_tag)
        if ns_prefix not in NAMESPACES:
            raise ValueError("Unknown XML namespace prefix: %r" % clark_tag)
        return clark_tag
    ns, tag = clark_tag[len("{"):].split("}", maxsplit=1)
    if not ns or not tag:
        raise ValueError("Invalid XML tag: %r" % clark_tag)
    ns_prefix = NAMESPACES_REV.get(ns)
    if ns_prefix:
        return "%s:%s" % (ns_prefix, tag)
    return clark_tag


def make_response(code):
    return "HTTP/1.1 %i %s" % (code, client.responses[code])


def make_href(base_prefix, href):
    assert href == pathutils.sanitize_path(href)
    return quote("%s%s" % (base_prefix, href))


def webdav_error(human_tag):
    root = ET.Element(make_clark("D:error"))
    root.append(ET.Element(make_clark(human_tag)))
    return root


def get_content_type(item, encoding):
    mimetype = OBJECT_MIMETYPES[item.name]
    tag = item.component_name
    content_type = "%s;charset=%s" % (mimetype, encoding)
    if tag:
        content_type += ";component=%s" % tag
    return content_type


def props_from_request(xml_request):
    result = OrderedDict()
    if xml_request is None:
        return result

    props = []
    for element in xml_request:
        if element.tag in (make_clark("D:set"), make_clark("D:remove")):
            for prop in element.findall("./%s/*" % make_clark("D:prop")):
                props.append((element.tag == make_clark("D:set"), prop))
    for is_set, prop in props:
        key = make_human_tag(prop.tag)
        value = None
        if prop.tag == make_clark("D:resourcetype"):
            key = "tag"
            if is_set:
                for resource_type in prop:
                    if resource_type.tag == make_clark("C:calendar"):
                        value = "VCALENDAR"
                        break
                    if resource_type.tag == make_clark("CR:addressbook"):
                        value = "VADDRESSBOOK"
                        break
        elif prop.tag == make_clark("C:supported-calendar-component-set"):
            if is_set:
                value = ",".join(
                    supported_comp.attrib["name"] for supported_comp in prop
                    if supported_comp.tag == make_clark("C:comp"))
        elif is_set:
            value = prop.text or ""
        result[key] = value
        result.move_to_end(key)

    return result

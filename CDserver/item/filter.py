import math
from datetime import date, datetime, timedelta, timezone
from itertools import chain

from CDserver import xmlutils
from CDserver.log import logger

DAY = timedelta(days=1)
SECOND = timedelta(seconds=1)
DATETIME_MIN = datetime.min.replace(tzinfo=timezone.utc)
DATETIME_MAX = datetime.max.replace(tzinfo=timezone.utc)
TIMESTAMP_MIN = math.floor(DATETIME_MIN.timestamp())
TIMESTAMP_MAX = math.ceil(DATETIME_MAX.timestamp())


def date_to_datetime(date_):
    if not isinstance(date_, datetime):
        date_ = datetime.combine(date_, datetime.min.time())
    if not date_.tzinfo:
        date_ = date_.replace(tzinfo=timezone.utc)
    return date_


def comp_match(item, filter_, level=0):
    if level == 0:
        tag = item.name
    elif level == 1:
        tag = item.component_name
    else:
        logger.warning(
            "Filters with three levels of comp-filter are not supported")
        return True
    if not tag:
        return False
    name = filter_.get("name").upper()
    if len(filter_) == 0:
        return name == tag
    if len(filter_) == 1:
        if filter_[0].tag == xmlutils.make_clark("C:is-not-defined"):
            return name != tag
    if name != tag:
        return False
    if (level == 0 and name != "VCALENDAR" or
            level == 1 and name not in ("VTODO", "VEVENT", "VJOURNAL")):
        logger.warning("Filtering %s is not supported", name)
        return True
    components = ([item.vobject_item] if level == 0
                  else list(getattr(item.vobject_item,
                                    "%s_list" % tag.lower())))
    for child in filter_:
        if child.tag == xmlutils.make_clark("C:prop-filter"):
            if not any(prop_match(comp, child, "C")
                       for comp in components):
                return False
        elif child.tag == xmlutils.make_clark("C:time-range"):
            if not time_range_match(item.vobject_item, filter_[0], tag):
                return False
        elif child.tag == xmlutils.make_clark("C:comp-filter"):
            if not comp_match(item, child, level=level + 1):
                return False
        else:
            raise ValueError("Unexpected %r in comp-filter" % child.tag)
    return True


def prop_match(vobject_item, filter_, ns):
    name = filter_.get("name").lower()
    if len(filter_) == 0:
        return name in vobject_item.contents
    if len(filter_) == 1:
        if filter_[0].tag == xmlutils.make_clark("%s:is-not-defined" % ns):
            return name not in vobject_item.contents
    if name not in vobject_item.contents:
        return False
    for child in filter_:
        if ns == "C" and child.tag == xmlutils.make_clark("C:time-range"):
            if not time_range_match(vobject_item, child, name):
                return False
        elif child.tag == xmlutils.make_clark("%s:text-match" % ns):
            if not text_match(vobject_item, child, name, ns):
                return False
        elif child.tag == xmlutils.make_clark("%s:param-filter" % ns):
            if not param_filter_match(vobject_item, child, name, ns):
                return False
        else:
            raise ValueError("Unexpected %r in prop-filter" % child.tag)
    return True


def time_range_match(vobject_item, filter_, child_name):
    start = filter_.get("start")
    end = filter_.get("end")
    if not start and not end:
        return False
    if start:
        start = datetime.strptime(start, "%Y%m%dT%H%M%SZ")
    else:
        start = datetime.min
    if end:
        end = datetime.strptime(end, "%Y%m%dT%H%M%SZ")
    else:
        end = datetime.max
    start = start.replace(tzinfo=timezone.utc)
    end = end.replace(tzinfo=timezone.utc)

    matched = False

    def range_fn(range_start, range_end, is_recurrence):
        nonlocal matched
        if start < range_end and range_start < end:
            matched = True
            return True
        if end < range_start and not is_recurrence:
            return True
        return False

    def infinity_fn(start):
        return False

    visit_time_ranges(vobject_item, child_name, range_fn, infinity_fn)
    return matched


def visit_time_ranges(vobject_item, child_name, range_fn, infinity_fn):
    def getrruleset(child, ignore=()):
        if (hasattr(child, "rrule") and
                ";UNTIL=" not in child.rrule.value.upper() and
                ";COUNT=" not in child.rrule.value.upper()):
            for dtstart in child.getrruleset(addRDate=True):
                if dtstart in ignore:
                    continue
                if infinity_fn(date_to_datetime(dtstart)):
                    return (), True
                break
        return filter(lambda dtstart: dtstart not in ignore,
                      child.getrruleset(addRDate=True)), False

    def get_children(components):
        main = None
        recurrences = []
        for comp in components:
            if hasattr(comp, "recurrence_id") and comp.recurrence_id.value:
                recurrences.append(comp.recurrence_id.value)
                if comp.rruleset:
                    raise ValueError("Overwritten recurrence with RRULESET")
                yield comp, True, ()
            else:
                if main is not None:
                    raise ValueError("Multiple main components")
                main = comp
        if main is None:
            raise ValueError("Main component missing")
        yield main, False, recurrences

    if child_name == "VEVENT":
        for child, is_recurrence, recurrences in get_children(
                vobject_item.vevent_list):
            dtstart = child.dtstart.value

            if child.rruleset:
                dtstarts, infinity = getrruleset(child, recurrences)
                if infinity:
                    return
            else:
                dtstarts = (dtstart,)

            dtend = getattr(child, "dtend", None)
            if dtend is not None:
                dtend = dtend.value
                original_duration = (dtend - dtstart).total_seconds()
                dtend = date_to_datetime(dtend)

            duration = getattr(child, "duration", None)
            if duration is not None:
                original_duration = duration = duration.value

            for dtstart in dtstarts:
                dtstart_is_datetime = isinstance(dtstart, datetime)
                dtstart = date_to_datetime(dtstart)

                if dtend is not None:
                    # Line 1
                    dtend = dtstart + timedelta(seconds=original_duration)
                    if range_fn(dtstart, dtend, is_recurrence):
                        return
                elif duration is not None:
                    if original_duration is None:
                        original_duration = duration.seconds
                    if duration.seconds > 0:
                        if range_fn(dtstart, dtstart + duration,
                                    is_recurrence):
                            return
                    else:
                        if range_fn(dtstart, dtstart + SECOND, is_recurrence):
                            return
                elif dtstart_is_datetime:
                    if range_fn(dtstart, dtstart + SECOND, is_recurrence):
                        return
                else:
                    if range_fn(dtstart, dtstart + DAY, is_recurrence):
                        return

    elif child_name == "VTODO":
        for child, is_recurrence, recurrences in get_children(
                vobject_item.vtodo_list):
            dtstart = getattr(child, "dtstart", None)
            duration = getattr(child, "duration", None)
            due = getattr(child, "due", None)
            completed = getattr(child, "completed", None)
            created = getattr(child, "created", None)

            if dtstart is not None:
                dtstart = date_to_datetime(dtstart.value)
            if duration is not None:
                duration = duration.value
            if due is not None:
                due = date_to_datetime(due.value)
                if dtstart is not None:
                    original_duration = (due - dtstart).total_seconds()
            if completed is not None:
                completed = date_to_datetime(completed.value)
                if created is not None:
                    created = date_to_datetime(created.value)
                    original_duration = (completed - created).total_seconds()
            elif created is not None:
                created = date_to_datetime(created.value)

            if child.rruleset:
                reference_dates, infinity = getrruleset(child, recurrences)
                if infinity:
                    return
            else:
                if dtstart is not None:
                    reference_dates = (dtstart,)
                elif due is not None:
                    reference_dates = (due,)
                elif completed is not None:
                    reference_dates = (completed,)
                elif created is not None:
                    reference_dates = (created,)
                else:
                    if range_fn(DATETIME_MIN, DATETIME_MAX, is_recurrence):
                        return
                    reference_dates = ()

            for reference_date in reference_dates:
                reference_date = date_to_datetime(reference_date)

                if dtstart is not None and duration is not None:
                    if range_fn(reference_date,
                                reference_date + duration + SECOND,
                                is_recurrence):
                        return
                    if range_fn(reference_date + duration - SECOND,
                                reference_date + duration + SECOND,
                                is_recurrence):
                        return
                elif dtstart is not None and due is not None:
                    due = reference_date + timedelta(seconds=original_duration)
                    if (range_fn(reference_date, due, is_recurrence) or
                            range_fn(reference_date,
                                     reference_date + SECOND, is_recurrence) or
                            range_fn(due - SECOND, due, is_recurrence) or
                            range_fn(due - SECOND, reference_date + SECOND,
                                     is_recurrence)):
                        return
                elif dtstart is not None:
                    if range_fn(reference_date, reference_date + SECOND,
                                is_recurrence):
                        return
                elif due is not None:
                    if range_fn(reference_date - SECOND, reference_date,
                                is_recurrence):
                        return
                elif completed is not None and created is not None:
                    completed = reference_date + timedelta(
                        seconds=original_duration)
                    if (range_fn(reference_date - SECOND,
                                 reference_date + SECOND,
                                 is_recurrence) or
                            range_fn(completed - SECOND, completed + SECOND,
                                     is_recurrence) or
                            range_fn(reference_date - SECOND,
                                     reference_date + SECOND, is_recurrence) or
                            range_fn(completed - SECOND, completed + SECOND,
                                     is_recurrence)):
                        return
                elif completed is not None:
                    if range_fn(reference_date - SECOND,
                                reference_date + SECOND, is_recurrence):
                        return
                elif created is not None:
                    if range_fn(reference_date, DATETIME_MAX, is_recurrence):
                        return

    elif child_name == "VJOURNAL":
        for child, is_recurrence, recurrences in get_children(
                vobject_item.vjournal_list):
            dtstart = getattr(child, "dtstart", None)

            if dtstart is not None:
                dtstart = dtstart.value
                if child.rruleset:
                    dtstarts, infinity = getrruleset(child, recurrences)
                    if infinity:
                        return
                else:
                    dtstarts = (dtstart,)

                for dtstart in dtstarts:
                    dtstart_is_datetime = isinstance(dtstart, datetime)
                    dtstart = date_to_datetime(dtstart)

                    if dtstart_is_datetime:
                        if range_fn(dtstart, dtstart + SECOND, is_recurrence):
                            return
                    else:
                        if range_fn(dtstart, dtstart + DAY, is_recurrence):
                            return

    else:
        child = getattr(vobject_item, child_name.lower())
        if isinstance(child, date):
            child_is_datetime = isinstance(child, datetime)
            child = date_to_datetime(child)
            if child_is_datetime:
                range_fn(child, child + SECOND, False)
            else:
                range_fn(child, child + DAY, False)


def text_match(vobject_item, filter_, child_name, ns, attrib_name=None):
    text = next(filter_.itertext()).lower()
    match_type = "contains"
    if ns == "CR":
        match_type = filter_.get("match-type", match_type)

    def match(value):
        value = value.lower()
        if match_type == "equals":
            return value == text
        if match_type == "contains":
            return text in value
        if match_type == "starts-with":
            return value.startswith(text)
        if match_type == "ends-with":
            return value.endswith(text)
        raise ValueError("Unexpected text-match match-type: %r" % match_type)

    children = getattr(vobject_item, "%s_list" % child_name, [])
    if attrib_name:
        condition = any(
            match(attrib) for child in children
            for attrib in child.params.get(attrib_name, []))
    else:
        condition = any(match(child.value) for child in children)
    if filter_.get("negate-condition") == "yes":
        return not condition
    return condition


def param_filter_match(vobject_item, filter_, parent_name, ns):
    name = filter_.get("name").upper()
    children = getattr(vobject_item, "%s_list" % parent_name, [])
    condition = any(name in child.params for child in children)
    if len(filter_) > 0:
        if filter_[0].tag == xmlutils.make_clark("%s:text-match" % ns):
            return condition and text_match(
                vobject_item, filter_[0], parent_name, ns, name)
        if filter_[0].tag == xmlutils.make_clark("%s:is-not-defined" % ns):
            return not condition
    return condition


def simplify_prefilters(filters, collection_tag="VCALENDAR"):
    flat_filters = tuple(chain.from_iterable(filters))
    simple = len(flat_filters) <= 1
    for col_filter in flat_filters:
        if collection_tag != "VCALENDAR":
            simple = False
            break
        if (col_filter.tag != xmlutils.make_clark("C:comp-filter") or
                col_filter.get("name").upper() != "VCALENDAR"):
            simple = False
            continue
        simple &= len(col_filter) <= 1
        for comp_filter in col_filter:
            if comp_filter.tag != xmlutils.make_clark("C:comp-filter"):
                simple = False
                continue
            tag = comp_filter.get("name").upper()
            if comp_filter.find(
                    xmlutils.make_clark("C:is-not-defined")) is not None:
                simple = False
                continue
            simple &= len(comp_filter) <= 1
            for time_filter in comp_filter:
                if tag not in ("VTODO", "VEVENT", "VJOURNAL"):
                    simple = False
                    break
                if time_filter.tag != xmlutils.make_clark("C:time-range"):
                    simple = False
                    continue
                start = time_filter.get("start")
                end = time_filter.get("end")
                if start:
                    start = math.floor(datetime.strptime(
                        start, "%Y%m%dT%H%M%SZ").replace(
                            tzinfo=timezone.utc).timestamp())
                else:
                    start = TIMESTAMP_MIN
                if end:
                    end = math.ceil(datetime.strptime(
                        end, "%Y%m%dT%H%M%SZ").replace(
                            tzinfo=timezone.utc).timestamp())
                else:
                    end = TIMESTAMP_MAX
                return tag, start, end, simple
            return tag, TIMESTAMP_MIN, TIMESTAMP_MAX, simple
    return None, TIMESTAMP_MIN, TIMESTAMP_MAX, simple

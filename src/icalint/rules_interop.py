"""I-series rules: things that break real clients even when the RFC nods.

Scheduling metadata (METHOD/ORGANIZER/ATTENDEE), start/end sanity,
duplicate UIDs, unescaped TEXT, local-file attachments: individually small,
collectively the reason "the invite looks fine on my machine" is a genre
of bug report.
"""

from __future__ import annotations

import re
from typing import Optional

from .engine import LintContext
from .model import Component, Property
from .registry import check
from .values import TimeValue, classify

#: TEXT-valued properties checked for escaping problems (RFC 5545 §3.3.11).
_TEXT_PROPERTIES = frozenset(
    ["SUMMARY", "DESCRIPTION", "LOCATION", "COMMENT", "CONTACT", "TZNAME"]
)

_VALID_ESCAPES = frozenset(["\\", ";", ",", "n", "N"])

_LOCAL_ATTACH_RE = re.compile(r"^(file:|[A-Za-z]:\\|/|\\\\)")


def _first_time(component: Component, name: str) -> Optional[TimeValue]:
    prop = component.prop(name)
    if prop is None:
        return None
    items = classify(prop)
    if items and items[0].value is not None:
        return items[0].value
    return None


@check
def check_start_end(ctx: LintContext) -> None:
    """I001/I002/I003: DTEND-vs-DURATION, type agreement, ordering."""
    for component in ctx.walk():
        if component.name not in ("VEVENT", "VTODO"):
            continue
        end_name = "DTEND" if component.name == "VEVENT" else "DUE"
        end_prop = component.prop(end_name)
        duration = component.prop("DURATION")

        if end_prop is not None and duration is not None:
            ctx.emit(
                "I001",
                duration.line,
                "%s (line %d) and DURATION are both present; RFC 5545 "
                "allows only one and clients disagree about which defines "
                "the end" % (end_name, end_prop.line),
            )

        start = _first_time(component, "DTSTART")
        end = _first_time(component, end_name)
        if start is None or end is None or end_prop is None:
            continue

        if start.kind != end.kind:
            ctx.emit(
                "I002",
                end_prop.line,
                "%s is a %s but DTSTART is a %s; RFC 5545 requires matching "
                "value types and mixed types shift all-day boundaries"
                % (end_name, end.kind, start.kind),
            )
            continue

        _check_ordering(ctx, component, end_name, end_prop, start, end)


def _check_ordering(
    ctx: LintContext,
    component: Component,
    end_name: str,
    end_prop: Property,
    start: TimeValue,
    end: TimeValue,
) -> None:
    """I003, only when both ends share one time reference (safe to compare)."""
    if start.kind == "date":
        if end.date <= start.date:
            detail = (
                "for all-day events DTEND is exclusive, so a same-day event "
                "needs DTEND one day after DTSTART"
                if end.date == start.date
                else "the event ends before it starts"
            )
            ctx.emit(
                "I003",
                end_prop.line,
                "%s %s is not after DTSTART %s; %s"
                % (end_name, end.raw, start.raw, detail),
            )
        return

    same_reference = (
        start.utc == end.utc and (start.tzid or None) == (end.tzid or None)
    )
    if not same_reference:
        return  # comparing across zones needs tz data; stay silent, not wrong
    if (end.date, end.time) <= (start.date, start.time):
        ctx.emit(
            "I003",
            end_prop.line,
            "%s %s is not after DTSTART %s; RFC 5545 requires the end to "
            "be later and zero-length events confuse free/busy views"
            % (end_name, end.raw, start.raw),
        )


@check
def check_scheduling_addresses(ctx: LintContext) -> None:
    """I004: ORGANIZER and ATTENDEE must be calendar-user addresses."""
    for component in ctx.scheduled():
        for prop in component.properties:
            if prop.name not in ("ORGANIZER", "ATTENDEE"):
                continue
            value = prop.value.strip()
            if value.lower().startswith("mailto:") and "@" in value:
                continue
            hint = (
                "prefix it with mailto:"
                if "@" in value
                else "use a mailto: URI with a real address"
            )
            ctx.emit(
                "I004",
                prop.line,
                "%s value %r is not a mailto: URI; most clients can only "
                "route scheduling replies to mailto - %s"
                % (prop.name, value, hint),
            )


@check
def check_method_contract(ctx: LintContext) -> None:
    """I005: METHOD:REQUEST/CANCEL/REPLY imply ORGANIZER (and ATTENDEEs)."""
    for calendar in ctx.calendars():
        method_prop = calendar.prop("METHOD")
        if method_prop is None:
            continue
        method = method_prop.value.strip().upper()
        if method not in ("REQUEST", "CANCEL", "REPLY"):
            continue
        for event in calendar.walk("VEVENT"):
            if event.prop("ORGANIZER") is None:
                ctx.emit(
                    "I005",
                    event.line,
                    "METHOD:%s but this VEVENT has no ORGANIZER; Outlook "
                    "and Google refuse to process organizer-less %s "
                    "messages" % (method, method),
                )
            if method == "REQUEST" and not event.props("ATTENDEE"):
                ctx.emit(
                    "I005",
                    event.line,
                    "METHOD:REQUEST but this VEVENT has no ATTENDEE; there "
                    "is nobody to invite and replies cannot be matched",
                )


@check
def check_duplicate_uids(ctx: LintContext) -> None:
    """I006: two full events sharing a UID (overrides are exempt)."""
    seen = {}
    for component in ctx.walk():
        if component.name not in ("VEVENT", "VTODO", "VJOURNAL"):
            continue
        uid = component.prop("UID")
        if uid is None or component.prop("RECURRENCE-ID") is not None:
            continue
        key = (component.name, uid.value)
        if key in seen:
            ctx.emit(
                "I006",
                uid.line,
                "UID %r already used by the %s on line %d; without a "
                "RECURRENCE-ID clients treat this as the same entry and "
                "one of the two silently wins" % (uid.value, component.name, seen[key]),
            )
        else:
            seen[key] = component.line


@check
def check_text_escaping(ctx: LintContext) -> None:
    """I007: raw ';' and invalid backslash escapes in TEXT values."""
    for component in ctx.walk():
        for prop in component.properties:
            if prop.name not in _TEXT_PROPERTIES:
                continue
            problem = _escaping_problem(prop.value)
            if problem:
                ctx.emit(
                    "I007",
                    prop.line,
                    "%s: %s" % (prop.name, problem),
                )


def _escaping_problem(value: str) -> Optional[str]:
    i, n = 0, len(value)
    while i < n:
        ch = value[i]
        if ch == "\\":
            if i + 1 >= n or value[i + 1] not in _VALID_ESCAPES:
                found = value[i : i + 2] if i + 1 < n else "\\"
                return (
                    "invalid escape %r; only \\\\ \\; \\, \\n are defined "
                    "and strict parsers reject others" % found
                )
            i += 2
            continue
        if ch == ";":
            return (
                "unescaped ';' - RFC 5545 TEXT requires \\; and lenient "
                "parsers truncate the value here"
            )
        i += 1
    return None


@check
def check_allday_shape(ctx: LintContext) -> None:
    """I008: midnight-to-midnight DATE-TIME events should be VALUE=DATE."""
    for event in ctx.walk("VEVENT"):
        start = _first_time(event, "DTSTART")
        end = _first_time(event, "DTEND")
        if (
            start is None
            or end is None
            or start.kind != "datetime"
            or end.kind != "datetime"
        ):
            continue
        if start.time == (0, 0, 0) and end.time == (0, 0, 0) and end.date > start.date:
            ctx.emit(
                "I008",
                event.prop("DTSTART").line,
                "event runs midnight-to-midnight as DATE-TIMEs; encode "
                "all-day events with VALUE=DATE so they do not shift across "
                "timezones and render in the all-day lane",
            )


@check
def check_attachments(ctx: LintContext) -> None:
    """I009: ATTACH values that only resolve on the sender's machine."""
    for component in ctx.walk():
        for prop in component.props("ATTACH"):
            if (prop.param("VALUE") or "").upper() == "BINARY":
                continue
            if _LOCAL_ATTACH_RE.match(prop.value.strip()):
                ctx.emit(
                    "I009",
                    prop.line,
                    "ATTACH %r points at a local file that recipients "
                    "cannot open; host it on a URL or inline it with "
                    "VALUE=BINARY" % prop.value.strip(),
                )


@check
def check_calscale(ctx: LintContext) -> None:
    """I010: only GREGORIAN is interoperable."""
    for calendar in ctx.calendars():
        calscale = calendar.prop("CALSCALE")
        if calscale is not None and calscale.value.strip().upper() != "GREGORIAN":
            ctx.emit(
                "I010",
                calscale.line,
                "CALSCALE:%s - RFC 5545 registers only GREGORIAN and "
                "virtually no client implements other scales" % calscale.value,
            )

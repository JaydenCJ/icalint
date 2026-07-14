"""S-series rules: calendar and component structure.

These catch the "file is missing something every client assumes exists"
class of bug: no VERSION, no UID, duplicate singleton properties,
unparseable dates. They run before the more specialized timezone /
recurrence / interop passes because those assume basic shape.
"""

from __future__ import annotations

from .engine import LintContext
from .registry import check
from .values import classify

#: Properties that RFC 5545 permits at most once per component. Emitted as
#: S007 on the second occurrence; clients silently pick one (and disagree
#: about which), so duplicates are real interop bugs, not pedantry.
_ONCE_ONLY = frozenset(
    [
        "CLASS", "COMPLETED", "CREATED", "DESCRIPTION", "DTEND", "DTSTAMP",
        "DTSTART", "DUE", "DURATION", "GEO", "LAST-MODIFIED", "LOCATION",
        "ORGANIZER", "PERCENT-COMPLETE", "PRIORITY", "RECURRENCE-ID",
        "RRULE", "SEQUENCE", "STATUS", "SUMMARY", "TRANSP", "UID", "URL",
    ]
)

#: Standard property names from RFC 5545, RFC 7986, and RFC 9074. Anything
#: else that does not carry an X- prefix is flagged by S010.
_KNOWN_PROPERTIES = frozenset(
    [
        # calendar level
        "CALSCALE", "METHOD", "PRODID", "VERSION",
        "NAME", "REFRESH-INTERVAL", "SOURCE", "COLOR", "IMAGE", "URL",
        "UID", "LAST-MODIFIED", "CATEGORIES", "DESCRIPTION",
        # descriptive
        "ATTACH", "CLASS", "COMMENT", "GEO", "LOCATION",
        "PERCENT-COMPLETE", "PRIORITY", "RESOURCES", "STATUS", "SUMMARY",
        # date/time
        "COMPLETED", "DTEND", "DUE", "DTSTART", "DURATION", "FREEBUSY",
        "TRANSP",
        # timezone
        "TZID", "TZNAME", "TZOFFSETFROM", "TZOFFSETTO", "TZURL",
        # relationship
        "ATTENDEE", "CONTACT", "ORGANIZER", "RECURRENCE-ID", "RELATED-TO",
        # recurrence
        "EXDATE", "EXRULE", "RDATE", "RRULE",
        # alarm
        "ACTION", "REPEAT", "TRIGGER", "ACKNOWLEDGED", "PROXIMITY",
        # change management / misc
        "CREATED", "DTSTAMP", "SEQUENCE", "REQUEST-STATUS", "CONFERENCE",
    ]
)

#: Date/time-valued properties whose values S008/S011 validate.
_TIME_PROPERTIES = frozenset(
    [
        "DTSTART", "DTEND", "DUE", "DTSTAMP", "RECURRENCE-ID",
        "EXDATE", "RDATE", "CREATED", "LAST-MODIFIED", "COMPLETED",
    ]
)

#: Components that make a calendar non-empty for S009.
_PAYLOAD = frozenset(["VEVENT", "VTODO", "VJOURNAL", "VFREEBUSY"])

#: Components that require UID and DTSTAMP (RFC 5545 §3.6.1-3.6.3).
_NEEDS_UID = frozenset(["VEVENT", "VTODO", "VJOURNAL"])


@check
def check_calendar_shell(ctx: LintContext) -> None:
    """S001/S002/S003/S009: the VCALENDAR wrapper itself."""
    for calendar in ctx.calendars():
        version = calendar.prop("VERSION")
        if version is None:
            ctx.emit(
                "S001",
                calendar.line,
                "VCALENDAR has no VERSION property; RFC 5545 requires "
                "VERSION:2.0 and several clients refuse files without it",
            )
        elif version.value.strip() != "2.0":
            ctx.emit(
                "S002",
                version.line,
                "VERSION is %r; RFC 5545 calendars are VERSION:2.0 "
                "(1.0 marks the older vCalendar format)" % version.value,
            )
        if calendar.prop("PRODID") is None:
            ctx.emit(
                "S003",
                calendar.line,
                "VCALENDAR has no PRODID; RFC 5545 requires one and it is "
                "the first thing debugged when an invite misbehaves",
            )
        if not any(
            component.name in _PAYLOAD for component in calendar.walk()
        ):
            ctx.emit(
                "S009",
                calendar.line,
                "calendar contains no VEVENT, VTODO, VJOURNAL, or VFREEBUSY; "
                "some clients report empty files as errors",
            )


@check
def check_required_properties(ctx: LintContext) -> None:
    """S004/S005/S006: per-component required properties."""
    for component in ctx.walk():
        if component.name not in _NEEDS_UID:
            continue
        if component.prop("UID") is None:
            ctx.emit(
                "S004",
                component.line,
                "%s has no UID; without it clients cannot match updates or "
                "cancellations to the original entry" % component.name,
            )
        if component.prop("DTSTAMP") is None:
            ctx.emit(
                "S005",
                component.line,
                "%s has no DTSTAMP; RFC 5545 requires it and sequencing of "
                "updates breaks without it" % component.name,
            )
        if component.name == "VEVENT" and component.prop("DTSTART") is None:
            ctx.emit(
                "S006",
                component.line,
                "VEVENT has no DTSTART; only METHOD-bearing scheduling "
                "messages may omit it, and many clients drop such events",
            )


@check
def check_duplicate_properties(ctx: LintContext) -> None:
    """S007: singleton properties occurring more than once."""
    for component in ctx.walk():
        if component.name not in _NEEDS_UID:
            continue
        seen = {}
        for prop in component.properties:
            if prop.name not in _ONCE_ONLY:
                continue
            if prop.name in seen:
                ctx.emit(
                    "S007",
                    prop.line,
                    "%s appears again (first on line %d); clients silently "
                    "pick one and disagree about which"
                    % (prop.name, seen[prop.name]),
                )
            else:
                seen[prop.name] = prop.line


@check
def check_time_values(ctx: LintContext) -> None:
    """S008/S011: every date/time value must parse, with the right VALUE."""
    for component in ctx.walk():
        if component.name not in _NEEDS_UID | frozenset(
            ["VFREEBUSY", "STANDARD", "DAYLIGHT"]
        ):
            continue
        for prop in component.properties:
            if prop.name not in _TIME_PROPERTIES:
                continue
            for item in classify(prop):
                if item.error is not None:
                    ctx.emit(
                        "S008",
                        prop.line,
                        "%s: %s" % (prop.name, item.error),
                    )
                elif item.implied_date:
                    ctx.emit(
                        "S011",
                        prop.line,
                        "%s value %r is a DATE but the property defaults to "
                        "DATE-TIME; add VALUE=DATE or strict clients will "
                        "reject it" % (prop.name, item.value.raw),
                    )


@check
def check_unknown_properties(ctx: LintContext) -> None:
    """S010: non-standard property names must carry an X- prefix."""
    for component in ctx.walk():
        for prop in component.properties:
            name = prop.name
            if name in _KNOWN_PROPERTIES or name.startswith("X-"):
                continue
            ctx.emit(
                "S010",
                prop.line,
                "%s is not a registered iCalendar property; experimental "
                "properties must be prefixed with X- (e.g. X-%s)"
                % (name, name),
            )

"""T-series rules: floating times, VTIMEZONE integrity, TZID hazards.

Timezone handling is the single richest source of calendar interop bugs:
a floating DTSTART renders at a different absolute time on every device,
a TZID with no VTIMEZONE definition is unresolvable for RFC-strict
clients, and Windows display names in TZID break everything that maps
zones through the IANA database.
"""

from __future__ import annotations

from .engine import LintContext
from .registry import check
from .tznames import (
    looks_like_iana_zone,
    looks_like_windows_zone,
    windows_zone_suggestion,
)
from .values import classify

#: Properties for which a floating local time is worth flagging.
_ANCHORED_PROPERTIES = frozenset(["DTSTART", "DTEND", "DUE"])


@check
def check_floating_times(ctx: LintContext) -> None:
    """T001: local DATE-TIME with neither Z nor TZID."""
    for component in ctx.scheduled():
        for prop in component.properties:
            if prop.name not in _ANCHORED_PROPERTIES:
                continue
            for item in classify(prop):
                if item.value is not None and item.value.floating:
                    ctx.emit(
                        "T001",
                        prop.line,
                        "%s %s is a floating local time; every attendee's "
                        "client renders it in its own timezone - add a TZID "
                        "parameter or use UTC (trailing Z)"
                        % (prop.name, item.value.raw),
                    )


@check
def check_tzid_references(ctx: LintContext) -> None:
    """T002/T004/T005/T006/T009: every TZID parameter in the file."""
    defined = ctx.vtimezones()
    reported_missing = set()
    reported_windows = set()

    for component in ctx.scheduled():
        for prop in component.properties:
            tzid = prop.param("TZID")
            if tzid is None:
                continue

            lookup = tzid
            if tzid.startswith("/"):
                ctx.emit(
                    "T005",
                    prop.line,
                    "TZID %r uses the globally-unique (leading slash) form; "
                    "there is no public registry for it and many parsers "
                    "treat the whole id as unknown" % tzid,
                )
                lookup = tzid[1:]

            for item in classify(prop):
                if item.value is None:
                    continue
                if item.value.kind == "datetime" and item.value.utc:
                    ctx.emit(
                        "T006",
                        prop.line,
                        "%s combines TZID=%s with a UTC value (%s); RFC 5545 "
                        "forbids this and clients disagree about which wins"
                        % (prop.name, tzid, item.value.raw),
                    )
                elif item.value.kind == "date":
                    ctx.emit(
                        "T009",
                        prop.line,
                        "%s is a DATE but carries TZID=%s; DATE values are "
                        "timezone-free and some clients shift the day"
                        % (prop.name, tzid),
                    )
                break  # one report per property is enough

            if looks_like_windows_zone(lookup) and lookup not in reported_windows:
                reported_windows.add(lookup)
                suggestion = windows_zone_suggestion(lookup)
                hint = (
                    " (use TZID=%s)" % suggestion
                    if suggestion
                    else " (use the IANA equivalent)"
                )
                ctx.emit(
                    "T004",
                    prop.line,
                    "TZID %r is a Windows/Exchange display name; clients "
                    "that resolve zones via the IANA database cannot map "
                    "it%s" % (lookup, hint),
                )

            if lookup not in defined and lookup not in reported_missing:
                reported_missing.add(lookup)
                iana_note = (
                    "; Google and Apple guess IANA names, but RFC 5545 "
                    "requires the definition and Outlook variants do not "
                    "guess"
                    if looks_like_iana_zone(lookup)
                    else "; the name is not IANA-shaped either, so most "
                    "clients will fall back to floating time"
                )
                ctx.emit(
                    "T002",
                    prop.line,
                    "TZID %r has no VTIMEZONE definition in this file%s"
                    % (lookup, iana_note),
                )


@check
def check_vtimezone_shape(ctx: LintContext) -> None:
    """T003/T007/T008: VTIMEZONE blocks themselves."""
    referenced = {tzid.lstrip("/") for tzid, _ in ctx.tzid_references()}

    for vtimezone in ctx.walk("VTIMEZONE"):
        tzid = vtimezone.prop("TZID")
        if tzid is None or not tzid.value:
            ctx.emit(
                "T008",
                vtimezone.line,
                "VTIMEZONE has no TZID property, so nothing can ever "
                "reference it",
            )
        has_observance = any(
            child.name in ("STANDARD", "DAYLIGHT")
            for child in vtimezone.children
        )
        if not has_observance:
            ctx.emit(
                "T007",
                vtimezone.line,
                "VTIMEZONE defines no STANDARD or DAYLIGHT observance; "
                "clients cannot compute any UTC offset from it",
            )
        if tzid is not None and tzid.value and tzid.value not in referenced:
            ctx.emit(
                "T003",
                vtimezone.line,
                "VTIMEZONE %r is never referenced by a TZID parameter; "
                "dead definitions bloat invites and confuse round-trips"
                % tzid.value,
            )

"""Rule registry: metadata for every rule id plus the list of check passes.

Rule *metadata* (id, fixed severity, one-line summary) is declared here in one
table so that ``--list-rules``, ``docs/rules.md``, and ``--select``/``--ignore``
validation all share a single source of truth. Rule *logic* lives in the
``rules_*`` modules, which register check functions via the :func:`check`
decorator; parse-level ``P`` rules are emitted directly by the parser but are
still declared here so they can be selected and listed like any other rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Set

from .model import Severity


@dataclass(frozen=True)
class Rule:
    id: str
    severity: Severity
    summary: str


def _r(rule_id: str, severity: Severity, summary: str) -> Rule:
    return Rule(rule_id, severity, summary)


_E, _W, _I = Severity.ERROR, Severity.WARNING, Severity.INFO

#: Every rule icalint knows about, in id order.
RULES: Dict[str, Rule] = {
    rule.id: rule
    for rule in [
        # --- P: parse / physical layer -------------------------------------
        _r("P001", _E, "Malformed content line (missing ':' or bad parameter syntax)"),
        _r("P002", _E, "Continuation line with nothing to continue"),
        _r("P003", _E, "END does not match the currently open component"),
        _r("P004", _E, "Component is never closed (BEGIN without END)"),
        _r("P005", _E, "END without a matching BEGIN"),
        _r("P006", _W, "Bare LF line endings (RFC 5545 requires CRLF)"),
        _r("P007", _W, "Physical line longer than 75 octets and not folded"),
        _r("P008", _E, "Content outside BEGIN:VCALENDAR"),
        _r("P009", _E, "Control character embedded in a content line"),
        _r("P010", _W, "Blank line inside iCalendar data"),
        # --- S: structure ---------------------------------------------------
        _r("S001", _E, "VCALENDAR is missing VERSION"),
        _r("S002", _W, "VERSION is not 2.0"),
        _r("S003", _W, "VCALENDAR is missing PRODID"),
        _r("S004", _E, "Component is missing UID"),
        _r("S005", _E, "Component is missing DTSTAMP"),
        _r("S006", _W, "VEVENT is missing DTSTART"),
        _r("S007", _E, "Property that must occur at most once occurs again"),
        _r("S008", _E, "Invalid DATE or DATE-TIME value"),
        _r("S009", _W, "Calendar contains no events, tasks, or journal entries"),
        _r("S010", _W, "Non-standard property without an X- prefix"),
        _r("S011", _W, "DATE value without VALUE=DATE parameter"),
        # --- T: timezones ---------------------------------------------------
        _r("T001", _W, "Floating local time (no TZID, not UTC)"),
        _r("T002", _E, "TZID has no matching VTIMEZONE in this file"),
        _r("T003", _I, "VTIMEZONE is defined but never referenced"),
        _r("T004", _W, "Windows/Exchange timezone name instead of an IANA name"),
        _r("T005", _W, "Globally-unique TZID (leading slash) trips many parsers"),
        _r("T006", _E, "TZID parameter on a value already in UTC"),
        _r("T007", _E, "VTIMEZONE has no STANDARD or DAYLIGHT subcomponent"),
        _r("T008", _E, "VTIMEZONE is missing its TZID property"),
        _r("T009", _W, "TZID parameter on a DATE value (dates are timezone-free)"),
        # --- R: recurrence --------------------------------------------------
        _r("R001", _E, "RRULE is missing FREQ"),
        _r("R002", _E, "Unknown RRULE part or invalid part value"),
        _r("R003", _E, "RRULE part appears more than once"),
        _r("R004", _E, "RRULE has both UNTIL and COUNT"),
        _r("R005", _E, "UNTIL value type does not match DTSTART"),
        _r("R006", _E, "UNTIL must be UTC when DTSTART is timezone-aware"),
        _r("R007", _W, "UNTIL is before DTSTART (rule yields no occurrences)"),
        _r("R008", _E, "Numeric BYDAY requires FREQ=MONTHLY or FREQ=YEARLY"),
        _r("R009", _E, "RRULE on a component without DTSTART"),
        _r("R010", _W, "DTSTART does not match the RRULE pattern"),
        _r("R011", _I, "Monthly BYMONTHDAY 29-31 silently skips short months"),
        _r("R012", _W, "RECURRENCE-ID override without a master event in this file"),
        _r("R013", _W, "EXDATE type or TZID differs from DTSTART"),
        _r("R014", _E, "INTERVAL or COUNT is not a positive integer"),
        # --- I: interop -----------------------------------------------------
        _r("I001", _E, "DTEND and DURATION are both present"),
        _r("I002", _E, "DTEND/DUE value type does not match DTSTART"),
        _r("I003", _E, "Event ends at or before it starts"),
        _r("I004", _W, "ORGANIZER/ATTENDEE is not a mailto: URI"),
        _r("I005", _W, "Scheduling METHOD without required ORGANIZER/ATTENDEE"),
        _r("I006", _E, "Duplicate UID without RECURRENCE-ID"),
        _r("I007", _W, "Unescaped ';' or invalid backslash escape in TEXT value"),
        _r("I008", _I, "Midnight-to-midnight event; use VALUE=DATE for all-day"),
        _r("I009", _W, "ATTACH points at a local file, unreachable for recipients"),
        _r("I010", _W, "CALSCALE other than GREGORIAN"),
    ]
}

#: Check passes registered by the rules_* modules (each may emit many rules).
CHECKS: List[Callable] = []


def check(fn: Callable) -> Callable:
    """Register a check pass. Order of registration is execution order."""
    CHECKS.append(fn)
    return fn


def expand_selection(spec: str) -> Set[str]:
    """Expand a ``--select``/``--ignore`` spec into concrete rule ids.

    Accepts comma-separated full ids (``T001``) and category prefixes
    (``T`` selects every T rule). Raises ``ValueError`` on anything that
    matches no known rule, so typos fail loudly instead of silently
    selecting nothing.
    """
    selected: Set[str] = set()
    for token in spec.split(","):
        token = token.strip().upper()
        if not token:
            continue
        if token in RULES:
            selected.add(token)
            continue
        matches = {rule_id for rule_id in RULES if rule_id.startswith(token)}
        if not matches:
            raise ValueError("unknown rule or prefix: %s" % token)
        selected.update(matches)
    return selected

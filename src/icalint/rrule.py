"""RRULE parsing: split a recurrence rule into validated parts.

This module only *parses and validates* rule parts (RFC 5545 §3.3.10); it
does not expand occurrences. Each syntactic problem is returned as a
``(rule_id, message)`` pair so the recurrence rules module can emit them
with correct line numbers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .values import TimeValue, parse_date, parse_datetime

FREQUENCIES = frozenset(
    ["SECONDLY", "MINUTELY", "HOURLY", "DAILY", "WEEKLY", "MONTHLY", "YEARLY"]
)

WEEKDAYS = frozenset(["MO", "TU", "WE", "TH", "FR", "SA", "SU"])

_BYDAY_RE = re.compile(r"^([+-]?\d{1,2})?(MO|TU|WE|TH|FR|SA|SU)$")

#: part name -> (abs-min, abs-max, negatives-allowed) for integer-list parts.
_INT_RANGES: Dict[str, Tuple[int, int, bool]] = {
    "BYSECOND": (0, 60, False),
    "BYMINUTE": (0, 59, False),
    "BYHOUR": (0, 23, False),
    "BYMONTHDAY": (1, 31, True),
    "BYYEARDAY": (1, 366, True),
    "BYWEEKNO": (1, 53, True),
    "BYMONTH": (1, 12, False),
    "BYSETPOS": (1, 366, True),
}

KNOWN_PARTS = frozenset(
    ["FREQ", "UNTIL", "COUNT", "INTERVAL", "BYDAY", "WKST"]
) | frozenset(_INT_RANGES)


@dataclass(frozen=True)
class ByDay:
    """One BYDAY entry, e.g. ``MO`` or ``-1SU``."""

    ordinal: Optional[int]  # None for a bare weekday
    weekday: str


@dataclass
class RRule:
    """Parsed recurrence rule; ``errors`` holds every syntactic problem."""

    freq: Optional[str] = None
    until: Optional[TimeValue] = None
    until_raw: Optional[str] = None
    count: Optional[int] = None
    interval: Optional[int] = None
    byday: List[ByDay] = field(default_factory=list)
    int_parts: Dict[str, List[int]] = field(default_factory=dict)
    wkst: Optional[str] = None
    errors: List[Tuple[str, str]] = field(default_factory=list)  # (rule_id, msg)

    def bymonthday(self) -> List[int]:
        return self.int_parts.get("BYMONTHDAY", [])

    def bymonth(self) -> List[int]:
        return self.int_parts.get("BYMONTH", [])


def parse_rrule(raw: str) -> RRule:
    """Parse an RRULE value; never raises, all problems land in ``errors``."""
    rule = RRule()
    seen: Dict[str, bool] = {}

    for part in raw.split(";"):
        if part == "":
            rule.errors.append(("R002", "empty RRULE part (stray ';')"))
            continue
        name, eq, value = part.partition("=")
        name = name.strip().upper()
        if not eq:
            rule.errors.append(("R002", "RRULE part %r is missing '='" % part))
            continue
        if name not in KNOWN_PARTS:
            rule.errors.append(("R002", "unknown RRULE part %s" % name))
            continue
        if name in seen:
            rule.errors.append(
                ("R003", "RRULE part %s appears more than once" % name)
            )
            continue
        seen[name] = True
        _parse_part(rule, name, value)

    if rule.freq is None and not any(
        rule_id == "R002" and "FREQ" in message for rule_id, message in rule.errors
    ):
        rule.errors.append(
            ("R001", "RRULE has no FREQ part; FREQ is required by RFC 5545")
        )
    return rule


def _parse_part(rule: RRule, name: str, value: str) -> None:
    if name == "FREQ":
        freq = value.upper()
        if freq not in FREQUENCIES:
            rule.errors.append(
                (
                    "R002",
                    "invalid FREQ value %r (expected one of %s)"
                    % (value, "/".join(sorted(FREQUENCIES))),
                )
            )
            return
        rule.freq = freq
    elif name == "UNTIL":
        rule.until_raw = value
        parsed = parse_datetime(value)
        if parsed is None:
            date = parse_date(value)
            if date is None:
                rule.errors.append(
                    ("R002", "invalid UNTIL value %r" % value)
                )
                return
            rule.until = TimeValue(kind="date", date=date, raw=value)
        else:
            rule.until = parsed
    elif name in ("COUNT", "INTERVAL"):
        try:
            number = int(value)
        except ValueError:
            number = 0
        if number < 1:
            rule.errors.append(
                (
                    "R014",
                    "%s=%s is not a positive integer; clients disagree on "
                    "how to recover" % (name, value),
                )
            )
            return
        if name == "COUNT":
            rule.count = number
        else:
            rule.interval = number
    elif name == "BYDAY":
        for token in value.split(","):
            match = _BYDAY_RE.match(token.strip().upper())
            if not match:
                rule.errors.append(
                    ("R002", "invalid BYDAY entry %r" % token)
                )
                continue
            ordinal = match.group(1)
            if ordinal is not None and int(ordinal) == 0:
                rule.errors.append(
                    ("R002", "BYDAY ordinal 0 is not allowed (%r)" % token)
                )
                continue
            rule.byday.append(
                ByDay(
                    ordinal=int(ordinal) if ordinal is not None else None,
                    weekday=match.group(2),
                )
            )
    elif name == "WKST":
        day = value.strip().upper()
        if day not in WEEKDAYS:
            rule.errors.append(("R002", "invalid WKST value %r" % value))
            return
        rule.wkst = day
    else:  # integer-list parts
        low, high, allow_negative = _INT_RANGES[name]
        numbers: List[int] = []
        for token in value.split(","):
            try:
                number = int(token)
            except ValueError:
                rule.errors.append(
                    ("R002", "invalid %s entry %r" % (name, token))
                )
                continue
            magnitude = abs(number)
            if (number < 0 and not allow_negative) or not (
                low <= magnitude <= high
            ):
                rule.errors.append(
                    (
                        "R002",
                        "%s entry %d is out of range (%d..%d%s)"
                        % (
                            name,
                            number,
                            low,
                            high,
                            ", negatives allowed" if allow_negative else "",
                        ),
                    )
                )
                continue
            numbers.append(number)
        rule.int_parts[name] = numbers

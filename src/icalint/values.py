"""Parsing and classification of DATE / DATE-TIME property values.

RFC 5545 encodes three flavors of time and the differences between them are
exactly where interop bugs live:

* ``19970714`` - a DATE (all-day, timezone-free)
* ``19970714T133000`` - a *floating* local DATE-TIME (renders differently
  for every viewer)
* ``19970714T133000Z`` - a DATE-TIME in UTC
* ``TZID=...:19970714T133000`` - a DATE-TIME anchored to a named zone

:func:`classify` turns a raw property into a :class:`TimeValue` (or a parse
failure) that the rules can reason about without re-parsing strings.
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .model import Property

_DATE_RE = re.compile(r"^(\d{4})(\d{2})(\d{2})$")
_DATETIME_RE = re.compile(r"^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})(Z?)$")


@dataclass(frozen=True)
class TimeValue:
    """One parsed DATE or DATE-TIME value."""

    kind: str  # "date" or "datetime"
    date: datetime.date
    time: Optional[Tuple[int, int, int]] = None  # None for DATE values
    utc: bool = False  # trailing Z
    tzid: Optional[str] = None  # TZID parameter of the owning property
    raw: str = ""

    @property
    def floating(self) -> bool:
        """True for a local DATE-TIME with neither Z nor TZID."""
        return self.kind == "datetime" and not self.utc and self.tzid is None

    def approx_ordinal(self) -> int:
        """Day-granularity ordering key, timezone differences ignored.

        Used for sanity checks such as "UNTIL before DTSTART" where a
        one-day tolerance across timezones is acceptable and exact zone
        arithmetic (which would need tz data) is not required.
        """
        return self.date.toordinal()


def parse_date(raw: str) -> Optional[datetime.date]:
    """Parse ``YYYYMMDD``; ``None`` when malformed or not a real date."""
    match = _DATE_RE.match(raw)
    if not match:
        return None
    year, month, day = (int(g) for g in match.groups())
    try:
        return datetime.date(year, month, day)
    except ValueError:
        return None


def parse_datetime(raw: str) -> Optional[TimeValue]:
    """Parse ``YYYYMMDDTHHMMSS[Z]``; ``None`` when malformed."""
    match = _DATETIME_RE.match(raw)
    if not match:
        return None
    year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
    hour, minute, second = int(match.group(4)), int(match.group(5)), int(match.group(6))
    try:
        date = datetime.date(year, month, day)
    except ValueError:
        return None
    # 60 tolerated as a leap second per RFC 5545 TIME grammar.
    if hour > 23 or minute > 59 or second > 60:
        return None
    return TimeValue(
        kind="datetime",
        date=date,
        time=(hour, minute, second),
        utc=match.group(7) == "Z",
        raw=raw,
    )


@dataclass(frozen=True)
class Classified:
    """Result of classifying one property value."""

    value: Optional[TimeValue]  # None when unparseable
    error: Optional[str] = None  # reason, when unparseable
    implied_date: bool = False  # DATE shape without VALUE=DATE declared


def classify_one(raw: str, prop: Property) -> Classified:
    """Classify a single (possibly comma-separated member) raw value."""
    declared = (prop.param("VALUE") or "").upper()
    tzid = prop.param("TZID")

    if declared == "DATE":
        date = parse_date(raw)
        if date is None:
            return Classified(None, "%r is not a valid DATE (YYYYMMDD)" % raw)
        return Classified(TimeValue(kind="date", date=date, tzid=tzid, raw=raw))

    if declared in ("", "DATE-TIME"):
        parsed = parse_datetime(raw)
        if parsed is not None:
            return Classified(
                TimeValue(
                    kind="datetime",
                    date=parsed.date,
                    time=parsed.time,
                    utc=parsed.utc,
                    tzid=tzid,
                    raw=raw,
                )
            )
        if declared == "":
            date = parse_date(raw)
            if date is not None:
                # Legal DATE shape but the property defaults to DATE-TIME:
                # strict clients reject this without VALUE=DATE.
                return Classified(
                    TimeValue(kind="date", date=date, tzid=tzid, raw=raw),
                    implied_date=True,
                )
        return Classified(
            None,
            "%r is not a valid DATE-TIME (YYYYMMDDTHHMMSS, optional Z)" % raw,
        )

    # PERIOD and other declared value types are out of scope for time rules.
    return Classified(None)


def classify(prop: Property) -> List[Classified]:
    """Classify every value of a property (EXDATE/RDATE are multi-valued)."""
    if prop.name in ("EXDATE", "RDATE"):
        raws = [part for part in prop.value.split(",") if part != ""]
        if not raws:
            raws = [prop.value]
    else:
        raws = [prop.value]
    return [classify_one(raw.strip(), prop) for raw in raws]

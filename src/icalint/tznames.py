"""Timezone-name heuristics: Windows display names vs IANA identifiers.

Outlook and Exchange write Windows timezone *display names* into TZID
(``TZID=China Standard Time``). Clients that resolve TZIDs against the IANA
database - which is most of the non-Microsoft world - cannot map those
names and fall back to guessing, UTC, or refusing the invite. The table
below covers the Windows zones most commonly seen in the wild, keyed
case-insensitively, each with the CLDR-recommended IANA equivalent so the
diagnostic can propose a concrete fix.
"""

from __future__ import annotations

import re
from typing import Optional

#: Windows timezone display name -> recommended IANA identifier (CLDR mapping).
WINDOWS_TZ_MAP = {
    "alaskan standard time": "America/Anchorage",
    "arab standard time": "Asia/Riyadh",
    "arabian standard time": "Asia/Dubai",
    "argentina standard time": "America/Argentina/Buenos_Aires",
    "atlantic standard time": "America/Halifax",
    "aus eastern standard time": "Australia/Sydney",
    "canada central standard time": "America/Regina",
    "central europe standard time": "Europe/Budapest",
    "central european standard time": "Europe/Warsaw",
    "central standard time": "America/Chicago",
    "china standard time": "Asia/Shanghai",
    "e. europe standard time": "Europe/Chisinau",
    "e. south america standard time": "America/Sao_Paulo",
    "eastern standard time": "America/New_York",
    "egypt standard time": "Africa/Cairo",
    "fle standard time": "Europe/Kyiv",
    "gmt standard time": "Europe/London",
    "greenwich standard time": "Atlantic/Reykjavik",
    "gtb standard time": "Europe/Athens",
    "hawaiian standard time": "Pacific/Honolulu",
    "india standard time": "Asia/Kolkata",
    "israel standard time": "Asia/Jerusalem",
    "korea standard time": "Asia/Seoul",
    "mountain standard time": "America/Denver",
    "new zealand standard time": "Pacific/Auckland",
    "north asia standard time": "Asia/Krasnoyarsk",
    "pacific sa standard time": "America/Santiago",
    "pacific standard time": "America/Los_Angeles",
    "romance standard time": "Europe/Paris",
    "russian standard time": "Europe/Moscow",
    "sa pacific standard time": "America/Bogota",
    "se asia standard time": "Asia/Bangkok",
    "singapore standard time": "Asia/Singapore",
    "south africa standard time": "Africa/Johannesburg",
    "taipei standard time": "Asia/Taipei",
    "tokyo standard time": "Asia/Tokyo",
    "turkey standard time": "Europe/Istanbul",
    "us eastern standard time": "America/Indiana/Indianapolis",
    "us mountain standard time": "America/Phoenix",
    "utc": None,  # "UTC" as a TZID is odd but harmless; not a Windows name
    "w. australia standard time": "Australia/Perth",
    "w. europe standard time": "Europe/Berlin",
}

#: Windows names all follow "<Region> Standard/Daylight Time"; catch the
#: long tail (including Outlook's "Customized Time Zone") by shape.
_WINDOWS_SHAPE_RE = re.compile(
    r"(standard|daylight|time zone)\s*(time)?$", re.IGNORECASE
)

_IANA_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_+\-]*(/[A-Za-z0-9_+\-]+)+$")


def windows_zone_suggestion(tzid: str) -> Optional[str]:
    """IANA suggestion when *tzid* is a known Windows display name."""
    return WINDOWS_TZ_MAP.get(tzid.strip().lower()) or None


def looks_like_windows_zone(tzid: str) -> bool:
    """True for known Windows names and anything shaped like one."""
    key = tzid.strip().lower()
    if key in ("utc", "gmt"):
        return False
    if key in WINDOWS_TZ_MAP:
        return True
    return bool(_WINDOWS_SHAPE_RE.search(tzid.strip()))


def looks_like_iana_zone(tzid: str) -> bool:
    """True for ``Area/Location`` shapes and the UTC/GMT aliases."""
    stripped = tzid.strip()
    if stripped.upper() in ("UTC", "GMT"):
        return True
    return bool(_IANA_RE.match(stripped))

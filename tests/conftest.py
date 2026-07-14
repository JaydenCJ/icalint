"""Shared fixtures and builders for the icalint test suite.

All builders emit CRLF-terminated text (the RFC 5545 wire format) so tests
exercise exactly what a compliant producer would write; line-ending rules
are tested explicitly with hand-built LF input.
"""

from __future__ import annotations

from typing import List

import pytest

from icalint import lint_text
from icalint.model import Diagnostic

#: A DTSTART that is beyond reproach: UTC, valid, no timezone dependencies.
UTC_START = "DTSTART:20260707T090000Z"
UTC_END = "DTEND:20260707T100000Z"


def crlf(*lines: str) -> str:
    """Join lines with CRLF and terminate the final line, per RFC 5545."""
    return "\r\n".join(lines) + "\r\n"


def calendar(*body: str, version: str = "2.0", prodid: bool = True) -> str:
    """A VCALENDAR wrapper with unobjectionable headers."""
    head: List[str] = ["BEGIN:VCALENDAR"]
    if version:
        head.append("VERSION:" + version)
    if prodid:
        head.append("PRODID:-//example.test//icalint tests//EN")
    return crlf(*head, *body, "END:VCALENDAR")


def event(*props: str, defaults: bool = True) -> List[str]:
    """VEVENT lines to splice into :func:`calendar`.

    With ``defaults`` the event carries UID and DTSTAMP so tests only see
    the diagnostics they provoke on purpose.
    """
    lines = ["BEGIN:VEVENT"]
    if defaults:
        lines += ["UID:evt-1@example.test", "DTSTAMP:20260701T090000Z"]
    lines += list(props)
    lines.append("END:VEVENT")
    return lines


def vtimezone(tzid: str = "America/New_York") -> List[str]:
    """A minimal but well-formed VTIMEZONE for *tzid*."""
    return [
        "BEGIN:VTIMEZONE",
        "TZID:" + tzid,
        "BEGIN:STANDARD",
        "DTSTART:19701101T020000",
        "TZOFFSETFROM:-0400",
        "TZOFFSETTO:-0500",
        "TZNAME:EST",
        "END:STANDARD",
        "END:VTIMEZONE",
    ]


def lint(text: str) -> List[Diagnostic]:
    return lint_text(text, path="test.ics")


def ids(diagnostics: List[Diagnostic]) -> List[str]:
    return [diagnostic.rule_id for diagnostic in diagnostics]


def lint_ids(text: str) -> List[str]:
    return ids(lint(text))


@pytest.fixture
def clean_calendar() -> str:
    """A calendar that must produce zero diagnostics; asserted in tests."""
    return calendar(
        *vtimezone(),
        *event(
            "DTSTART;TZID=America/New_York:20260707T093000",
            "DTEND;TZID=America/New_York:20260707T103000",
            "SUMMARY:Quarterly planning",
        ),
    )

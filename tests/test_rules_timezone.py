"""T-series rules: floating times, TZID resolution, VTIMEZONE integrity."""

from __future__ import annotations

from conftest import UTC_START, calendar, event, lint, lint_ids, vtimezone


def test_floating_dtstart_is_t001_but_anchored_times_are_not(clean_calendar):
    findings = [
        d for d in lint(calendar(*event("DTSTART:20260714T190000")))
        if d.rule_id == "T001"
    ]
    assert len(findings) == 1
    assert "floating" in findings[0].message

    # UTC and TZID-anchored times are fine, and so is the STANDARD block's
    # DTSTART inside VTIMEZONE, which is *required* to be a local time.
    assert "T001" not in lint_ids(clean_calendar)
    assert "T001" not in lint_ids(calendar(*event(UTC_START)))


def test_tzid_without_vtimezone_is_t002_reported_once_per_tzid():
    text = calendar(
        *event(
            "DTSTART;TZID=Asia/Tokyo:20260707T093000",
            "DTEND;TZID=Asia/Tokyo:20260707T103000",
        )
    )
    assert lint_ids(text).count("T002") == 1


def test_tzid_with_matching_vtimezone_is_clean(clean_calendar):
    assert "T002" not in lint_ids(clean_calendar)


def test_t002_wording_distinguishes_iana_shaped_names():
    text = calendar(*event("DTSTART;TZID=Europe/Paris:20260707T093000"))
    findings = [d for d in lint(text) if d.rule_id == "T002"]
    assert "Google and Apple guess" in findings[0].message

    text = calendar(*event("DTSTART;TZID=MyZone:20260707T093000"))
    findings = [d for d in lint(text) if d.rule_id == "T002"]
    assert "not IANA-shaped" in findings[0].message


def test_unreferenced_vtimezone_is_t003():
    assert "T003" in lint_ids(calendar(*vtimezone(), *event(UTC_START)))


def test_windows_tzid_is_t004_with_iana_suggestion_when_known():
    text = calendar(
        *vtimezone("China Standard Time"),
        *event("DTSTART;TZID=China Standard Time:20260707T093000"),
    )
    findings = [d for d in lint(text) if d.rule_id == "T004"]
    assert len(findings) == 1
    assert "Asia/Shanghai" in findings[0].message
    # The VTIMEZONE exists, so this must NOT also be T002.
    assert "T002" not in lint_ids(text)

    # Windows-shaped names outside the mapping table are still flagged.
    text = calendar(
        *vtimezone("Fiji Standard Time"),
        *event("DTSTART;TZID=Fiji Standard Time:20260707T093000"),
    )
    assert "T004" in lint_ids(text)


def test_globally_unique_tzid_is_t005_and_resolves_without_slash():
    text = calendar(
        *vtimezone("America/New_York"),
        *event('DTSTART;TZID="/America/New_York":20260707T093000'),
    )
    found = lint_ids(text)
    assert "T005" in found
    assert "T002" not in found  # slash-stripped lookup still matches


def test_tzid_on_utc_value_is_t006():
    text = calendar(
        *vtimezone(),
        *event("DTSTART;TZID=America/New_York:20260707T093000Z"),
    )
    assert "T006" in lint_ids(text)


def test_vtimezone_without_observance_is_t007():
    text = calendar(
        "BEGIN:VTIMEZONE",
        "TZID:America/New_York",
        "END:VTIMEZONE",
        *event("DTSTART;TZID=America/New_York:20260707T093000"),
    )
    assert "T007" in lint_ids(text)


def test_vtimezone_without_tzid_is_t008():
    text = calendar(
        "BEGIN:VTIMEZONE",
        "BEGIN:STANDARD",
        "DTSTART:19701101T020000",
        "TZOFFSETFROM:-0400",
        "TZOFFSETTO:-0500",
        "END:STANDARD",
        "END:VTIMEZONE",
        *event(UTC_START),
    )
    assert "T008" in lint_ids(text)


def test_tzid_on_date_value_is_t009():
    text = calendar(
        *vtimezone(),
        *event("DTSTART;TZID=America/New_York;VALUE=DATE:20260707"),
    )
    assert "T009" in lint_ids(text)

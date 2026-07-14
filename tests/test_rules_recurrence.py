"""R-series rules: UNTIL semantics, BYDAY ordinals, overrides, EXDATE."""

from __future__ import annotations

from conftest import UTC_START, calendar, event, lint, lint_ids, vtimezone


def rrule_event(*extra: str, dtstart: str = UTC_START):
    return event(dtstart, *extra)


def test_until_and_count_together_is_r004():
    text = calendar(
        *rrule_event("RRULE:FREQ=DAILY;UNTIL=20261231T090000Z;COUNT=5")
    )
    assert "R004" in lint_ids(text)


def test_until_value_type_must_match_dtstart_r005():
    # DATE UNTIL against a DATE-TIME DTSTART...
    text = calendar(*rrule_event("RRULE:FREQ=DAILY;UNTIL=20261231"))
    assert "R005" in lint_ids(text)
    # ...and DATE-TIME UNTIL against a DATE DTSTART.
    text = calendar(
        *rrule_event(
            "RRULE:FREQ=DAILY;UNTIL=20261231T000000Z",
            dtstart="DTSTART;VALUE=DATE:20260707",
        )
    )
    assert "R005" in lint_ids(text)


def test_local_until_needs_utc_when_dtstart_is_anchored_r006():
    # TZID-anchored DTSTART: local UNTIL is R006.
    text = calendar(
        *vtimezone(),
        *rrule_event(
            "RRULE:FREQ=WEEKLY;UNTIL=20261231T093000",
            dtstart="DTSTART;TZID=America/New_York:20260707T093000",
        ),
    )
    assert "R006" in lint_ids(text)

    # UTC DTSTART: local UNTIL is R006 too.
    text = calendar(*rrule_event("RRULE:FREQ=WEEKLY;UNTIL=20261231T090000"))
    assert "R006" in lint_ids(text)

    # Fully floating event: a floating UNTIL is consistent, not R006.
    text = calendar(
        *rrule_event(
            "RRULE:FREQ=WEEKLY;UNTIL=20261231T090000",
            dtstart="DTSTART:20260707T090000",
        )
    )
    assert "R006" not in lint_ids(text)


def test_until_before_dtstart_is_r007_with_one_day_timezone_slack():
    text = calendar(*rrule_event("RRULE:FREQ=DAILY;UNTIL=20250101T090000Z"))
    assert "R007" in lint_ids(text)

    # A UTC UNTIL can land on the previous calendar day of a far-east
    # DTSTART and still produce occurrences; one day of slack, no report.
    text = calendar(*rrule_event("RRULE:FREQ=DAILY;UNTIL=20260706T230000Z"))
    assert "R007" not in lint_ids(text)


def test_numeric_byday_requires_monthly_or_yearly_r008():
    text = calendar(*rrule_event("RRULE:FREQ=WEEKLY;BYDAY=2MO"))
    assert "R008" in lint_ids(text)

    found = lint_ids(calendar(*rrule_event("RRULE:FREQ=MONTHLY;BYDAY=2MO")))
    assert "R008" not in found
    assert "R010" not in found  # ordinal BYDAY is never pattern-checked


def test_rrule_without_dtstart_is_r009():
    text = calendar(*event("RRULE:FREQ=DAILY"))
    assert "R009" in lint_ids(text)


def test_weekly_byday_pattern_mismatch_is_r010():
    # 2026-07-07 is a Tuesday.
    text = calendar(*rrule_event("RRULE:FREQ=WEEKLY;BYDAY=MO"))
    findings = [d for d in lint(text) if d.rule_id == "R010"]
    assert len(findings) == 1
    assert "TU" in findings[0].message

    text = calendar(*rrule_event("RRULE:FREQ=WEEKLY;BYDAY=TU,TH"))
    assert "R010" not in lint_ids(text)


def test_monthly_and_yearly_pattern_mismatches_are_r010():
    text = calendar(*rrule_event("RRULE:FREQ=MONTHLY;BYMONTHDAY=15"))
    assert "R010" in lint_ids(text)

    text = calendar(*rrule_event("RRULE:FREQ=YEARLY;BYMONTH=1"))
    assert "R010" in lint_ids(text)

    # -1 means "last day"; without expanding the rule we cannot know
    # whether DTSTART matches, so the linter must stay silent.
    text = calendar(*rrule_event("RRULE:FREQ=MONTHLY;BYMONTHDAY=-1"))
    assert "R010" not in lint_ids(text)


def test_monthly_rules_pinned_past_day_28_are_r011():
    text = calendar(*rrule_event("RRULE:FREQ=MONTHLY;BYMONTHDAY=31"))
    assert "R011" in lint_ids(text)

    # Without BYMONTHDAY the pin is inherited from DTSTART's day.
    text = calendar(
        *rrule_event("RRULE:FREQ=MONTHLY", dtstart="DTSTART:20260731T090000Z")
    )
    assert "R011" in lint_ids(text)

    text = calendar(
        *rrule_event("RRULE:FREQ=MONTHLY", dtstart="DTSTART:20260715T090000Z")
    )
    assert "R011" not in lint_ids(text)


def test_recurrence_id_needs_a_master_in_the_same_file_r012():
    text = calendar(*event(UTC_START, "RECURRENCE-ID:20260707T090000Z"))
    assert "R012" in lint_ids(text)

    master = event(UTC_START, "RRULE:FREQ=WEEKLY;BYDAY=TU")
    override = [
        "BEGIN:VEVENT",
        "UID:evt-1@example.test",
        "DTSTAMP:20260701T090000Z",
        "RECURRENCE-ID:20260714T090000Z",
        "DTSTART:20260714T100000Z",
        "SUMMARY:Moved by one hour",
        "END:VEVENT",
    ]
    assert "R012" not in lint_ids(calendar(*master, *override))


def test_exdate_must_share_dtstarts_type_and_reference_r013():
    # DATE exception against a DATE-TIME series never matches.
    text = calendar(
        *rrule_event(
            "RRULE:FREQ=DAILY;COUNT=10",
            "EXDATE;VALUE=DATE:20260710",
        )
    )
    assert "R013" in lint_ids(text)

    # Same type but a different TZID: strict clients only cancel exact matches.
    text = calendar(
        *vtimezone("America/New_York"),
        *vtimezone("America/Chicago"),
        *rrule_event(
            "RRULE:FREQ=DAILY;COUNT=10",
            "EXDATE;TZID=America/Chicago:20260710T093000",
            dtstart="DTSTART;TZID=America/New_York:20260707T093000",
        ),
    )
    assert "R013" in lint_ids(text)

    # An EXDATE in DTSTART's own reference is clean.
    text = calendar(
        *rrule_event(
            "RRULE:FREQ=DAILY;COUNT=10",
            "EXDATE:20260710T090000Z",
        )
    )
    assert "R013" not in lint_ids(text)

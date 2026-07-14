"""S-series rules: calendar shell, required properties, value validity."""

from __future__ import annotations

from conftest import UTC_START, calendar, event, lint, lint_ids


def test_calendar_shell_requirements_s001_s002_s003():
    assert "S001" in lint_ids(calendar(*event(UTC_START), version=""))

    found = lint_ids(calendar(*event(UTC_START), version="1.0"))
    assert "S002" in found
    assert "S001" not in found  # a wrong VERSION is not also a missing one

    assert "S003" in lint_ids(calendar(*event(UTC_START), prodid=False))


def test_event_missing_uid_and_dtstamp_are_s004_and_s005():
    text = calendar("BEGIN:VEVENT", UTC_START, "END:VEVENT")
    found = lint_ids(text)
    assert "S004" in found
    assert "S005" in found


def test_event_missing_dtstart_is_s006():
    assert "S006" in lint_ids(calendar(*event("SUMMARY:No start")))


def test_duplicate_summary_is_s007_pointing_at_second_occurrence():
    text = calendar(*event(UTC_START, "SUMMARY:one", "SUMMARY:two"))
    findings = [d for d in lint(text) if d.rule_id == "S007"]
    assert len(findings) == 1
    assert "first on line" in findings[0].message
    # The finding anchors on the *second* SUMMARY so editors jump there.
    assert findings[0].line == text[: text.index("SUMMARY:two")].count("\n") + 1


def test_repeatable_properties_are_not_s007():
    text = calendar(
        *event(
            UTC_START,
            "CATEGORIES:work",
            "CATEGORIES:planning",
            "EXDATE:20260714T090000Z",
            "EXDATE:20260721T090000Z",
            "RRULE:FREQ=WEEKLY",
        )
    )
    assert "S007" not in lint_ids(text)


def test_unparseable_time_values_are_s008():
    assert "S008" in lint_ids(calendar(*event("DTSTART:not-a-date")))
    # Well-shaped but impossible: February 30th.
    assert "S008" in lint_ids(calendar(*event("DTSTART:20260230T090000Z")))


def test_calendar_without_payload_is_s009():
    assert "S009" in lint_ids(calendar())


def test_unregistered_property_is_s010_but_x_prefixed_is_not():
    found = lint_ids(
        calendar(*event(UTC_START, "WOOF:yes", "X-WOOF:also yes"))
    )
    assert found.count("S010") == 1


def test_date_shape_without_value_date_param_is_s011():
    found = lint_ids(calendar(*event("DTSTART:20260714")))
    assert "S011" in found
    assert "S008" not in found  # the value itself is a perfectly good DATE

    # Declaring VALUE=DATE makes the same value clean.
    assert "S011" not in lint_ids(
        calendar(*event("DTSTART;VALUE=DATE:20260714"))
    )

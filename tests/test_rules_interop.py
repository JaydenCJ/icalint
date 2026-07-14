"""I-series rules: scheduling metadata, ordering, escaping, attachments."""

from __future__ import annotations

from conftest import UTC_END, UTC_START, calendar, crlf, event, lint, lint_ids


def test_dtend_and_duration_together_is_i001_for_events_and_todos():
    text = calendar(*event(UTC_START, UTC_END, "DURATION:PT1H"))
    assert "I001" in lint_ids(text)

    text = calendar(
        "BEGIN:VTODO",
        "UID:todo-1@example.test",
        "DTSTAMP:20260701T090000Z",
        "DTSTART:20260707T090000Z",
        "DUE:20260707T120000Z",
        "DURATION:PT3H",
        "END:VTODO",
    )
    assert "I001" in lint_ids(text)


def test_dtend_value_type_mismatch_is_i002():
    text = calendar(*event(UTC_START, "DTEND;VALUE=DATE:20260708"))
    assert "I002" in lint_ids(text)


def test_end_not_after_start_is_i003():
    # Plainly backwards.
    text = calendar(*event(UTC_START, "DTEND:20260707T080000Z"))
    assert "I003" in lint_ids(text)
    # Zero-length is also invalid: DTEND must be *later*.
    text = calendar(*event(UTC_START, "DTEND:20260707T090000Z"))
    assert "I003" in lint_ids(text)
    # Well-ordered events are clean.
    assert "I003" not in lint_ids(calendar(*event(UTC_START, UTC_END)))


def test_all_day_dtend_equal_to_dtstart_is_i003_with_exclusive_hint():
    text = calendar(
        *event(
            "DTSTART;VALUE=DATE:20260707",
            "DTEND;VALUE=DATE:20260707",
        )
    )
    findings = [d for d in lint(text) if d.rule_id == "I003"]
    assert len(findings) == 1
    assert "exclusive" in findings[0].message


def test_cross_timezone_ordering_is_not_second_guessed():
    # Comparing 09:00 New York with 09:30 Los Angeles needs tz data;
    # the linter must stay silent rather than guess wrong.
    text = calendar(
        *event(
            "DTSTART;TZID=America/New_York:20260707T090000",
            "DTEND;TZID=America/Los_Angeles:20260707T093000",
        )
    )
    assert "I003" not in lint_ids(text)


def test_non_mailto_organizer_is_i004_and_mailto_is_clean():
    text = calendar(*event(UTC_START, "ORGANIZER:alice@example.test"))
    findings = [d for d in lint(text) if d.rule_id == "I004"]
    assert len(findings) == 1
    assert "mailto" in findings[0].message

    text = calendar(
        *event(
            UTC_START,
            "ORGANIZER:mailto:alice@example.test",
            "ATTENDEE:mailto:bob@example.test",
        )
    )
    assert "I004" not in lint_ids(text)


def test_method_contracts_are_i005():
    # REQUEST needs ORGANIZER and at least one ATTENDEE: two findings.
    text = calendar("METHOD:REQUEST", *event(UTC_START))
    assert lint_ids(text).count("I005") == 2

    # CANCEL needs ORGANIZER but no ATTENDEE.
    text = calendar(
        "METHOD:CANCEL",
        *event(UTC_START, "ORGANIZER:mailto:alice@example.test"),
    )
    assert "I005" not in lint_ids(text)

    # PUBLISH carries no such contract.
    text = calendar("METHOD:PUBLISH", *event(UTC_START))
    assert "I005" not in lint_ids(text)


def test_duplicate_uid_is_i006_unless_it_is_a_recurrence_override():
    text = calendar(*event(UTC_START), *event("DTSTART:20260708T090000Z"))
    assert "I006" in lint_ids(text)

    master = event(UTC_START, "RRULE:FREQ=WEEKLY;BYDAY=TU")
    override = [
        "BEGIN:VEVENT",
        "UID:evt-1@example.test",
        "DTSTAMP:20260701T090000Z",
        "RECURRENCE-ID:20260714T090000Z",
        "DTSTART:20260714T100000Z",
        "END:VEVENT",
    ]
    assert "I006" not in lint_ids(calendar(*master, *override))


def test_text_escaping_problems_are_i007():
    # Raw ';' truncates the value in lenient parsers.
    text = calendar(*event(UTC_START, "SUMMARY:Budget; then drinks"))
    assert "I007" in lint_ids(text)

    # Windows paths are the classic source of invalid escapes.
    text = calendar(*event(UTC_START, r"DESCRIPTION:C:\temp\reports"))
    assert "I007" in lint_ids(text)

    # Properly escaped text is clean.
    text = calendar(
        *event(UTC_START, r"SUMMARY:Budget\; drinks\, and a \\ demo\nDone")
    )
    assert "I007" not in lint_ids(text)


def test_midnight_to_midnight_datetimes_are_i008_but_real_all_day_is_not():
    text = calendar(
        *event("DTSTART:20260707T000000Z", "DTEND:20260708T000000Z")
    )
    assert "I008" in lint_ids(text)

    text = calendar(
        *event(
            "DTSTART;VALUE=DATE:20260707",
            "DTEND;VALUE=DATE:20260708",
        )
    )
    assert "I008" not in lint_ids(text)


def test_local_file_attach_is_i009_but_https_is_clean():
    found = lint_ids(
        calendar(*event(UTC_START, "ATTACH:file:///home/alice/agenda.pdf"))
    )
    assert "I009" in found

    text = calendar(
        *event(UTC_START, "ATTACH:https://example.test/agenda.pdf")
    )
    assert "I009" not in lint_ids(text)


def test_non_gregorian_calscale_is_i010():
    text = crlf(
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//example.test//icalint tests//EN",
        "CALSCALE:JALALI",
        *event(UTC_START),
        "END:VCALENDAR",
    )
    assert "I010" in lint_ids(text)
    assert "I010" not in lint_ids(text.replace("JALALI", "GREGORIAN"))

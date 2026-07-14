"""Physical-layer parsing: unfolding, content lines, tree building, P rules."""

from __future__ import annotations

import pytest

from icalint.parser import parse, parse_content_line

from conftest import UTC_START, calendar, crlf, event, lint_ids


def test_clean_calendar_produces_zero_diagnostics(clean_calendar):
    assert lint_ids(clean_calendar) == []


def test_bare_lf_line_endings_reported_once_as_p006():
    # Many LF-terminated lines, but the finding must appear exactly once:
    # one actionable report beats a wall of identical ones.
    text = calendar(*event(UTC_START)).replace("\r\n", "\n")
    found = lint_ids(text)
    assert found.count("P006") == 1
    assert "P001" not in found  # content still parsed normally


def test_line_length_is_measured_in_octets_and_folding_fixes_it():
    # Unfolded 88-octet line: flagged.
    long_summary = "SUMMARY:" + "x" * 80
    assert "P007" in lint_ids(calendar(*event(UTC_START, long_summary)))

    # 40 three-byte CJK characters: only 48 chars but 128 octets - the RFC
    # limit is octets, so this must be flagged too.
    cjk_summary = "SUMMARY:" + "会" * 40
    assert "P007" in lint_ids(calendar(*event(UTC_START, cjk_summary)))

    # The same 80-char value folded across two short physical lines is
    # clean, and unfolding must reassemble it byte-for-byte.
    folded = ["SUMMARY:" + "x" * 40, " " + "x" * 40]
    result = parse(calendar(*event(UTC_START, *folded)), "t.ics")
    assert all(d.rule_id != "P007" for d in result.diagnostics)
    events = list(result.components[0].walk("VEVENT"))
    assert events[0].prop("SUMMARY").value == "x" * 80


def test_continuation_line_at_start_of_input_is_p002():
    text = crlf(" BEGIN:VCALENDAR", "END:VCALENDAR")
    assert "P002" in lint_ids(text)


def test_line_without_colon_is_p001_and_parsing_continues():
    found = lint_ids(calendar(*event(UTC_START, "THIS IS NOT A CONTENT LINE")))
    assert "P001" in found
    assert "S004" not in found  # UID on the next line was still picked up


def test_mismatched_end_is_p003_and_recovery_pops_to_outer_frame():
    text = crlf(
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//example.test//t//EN",
        "BEGIN:VEVENT",
        "END:VTODO",
        "END:VCALENDAR",
    )
    assert "P003" in lint_ids(text)

    # END:VCALENDAR while VEVENT is still open: P003 for the event, but the
    # calendar frame must be recovered so no spurious P004 for VCALENDAR.
    text = crlf(
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//example.test//t//EN",
        "BEGIN:VEVENT",
        "UID:u@example.test",
        "END:VCALENDAR",
    )
    found = lint_ids(text)
    assert "P003" in found
    assert "P004" not in found


def test_unclosed_components_are_p004_once_each():
    text = crlf(
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//example.test//t//EN",
        "BEGIN:VEVENT",
        "UID:u@example.test",
    )
    # Both the calendar and the event are left open.
    assert lint_ids(text).count("P004") == 2


def test_end_without_begin_is_p005():
    assert "P005" in lint_ids(crlf("END:VCALENDAR"))


def test_content_outside_vcalendar_is_p008():
    # A stray property before the calendar...
    text = crlf("VERSION:2.0") + calendar(*event(UTC_START))
    assert "P008" in lint_ids(text)
    # ...and a top-level component that is not VCALENDAR.
    text = crlf("BEGIN:VEVENT", "UID:u@example.test", "END:VEVENT")
    assert "P008" in lint_ids(text)


def test_control_character_is_p009():
    text = calendar(*event(UTC_START, "SUMMARY:first line\x0bsecond"))
    assert "P009" in lint_ids(text)


def test_blank_line_is_p010_and_parsing_continues():
    text = calendar(*event(UTC_START)).replace(
        "BEGIN:VEVENT", "\r\nBEGIN:VEVENT", 1
    )
    found = lint_ids(text)
    assert "P010" in found
    assert "P004" not in found  # tree still balanced


class TestContentLine:
    def test_names_and_params_are_uppercased_value_is_not(self):
        prop = parse_content_line("summary;language=en:Mixed Case Kept")
        assert prop.name == "SUMMARY"
        assert prop.params == {"LANGUAGE": ["en"]}
        assert prop.value == "Mixed Case Kept"
        assert parse_content_line("SUMMARY:").value == ""  # empty is legal

    def test_quoted_and_multi_valued_parameters(self):
        # Quoted values may contain ':' and ';' without ending the parameter.
        prop = parse_content_line(
            'ATTENDEE;CN="Doe; Jane (x:1)":mailto:jane@example.test'
        )
        assert prop.params["CN"] == ["Doe; Jane (x:1)"]
        assert prop.value == "mailto:jane@example.test"

        prop = parse_content_line(
            "ATTENDEE;MEMBER=a@example.test,b@example.test:mailto:c@example.test"
        )
        assert prop.params["MEMBER"] == ["a@example.test", "b@example.test"]

    def test_malformed_lines_raise_value_error(self):
        with pytest.raises(ValueError):
            parse_content_line('DTSTART;TZID="Oops:20260101T000000')
        with pytest.raises(ValueError):
            parse_content_line("SUMMARY")  # no ':' at all
        with pytest.raises(ValueError):
            parse_content_line("DTSTART;=nameless:20260101")

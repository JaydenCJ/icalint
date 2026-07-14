"""RRULE part parsing and syntactic validation."""

from __future__ import annotations

from icalint.rrule import parse_rrule


def error_ids(raw: str):
    return [rule_id for rule_id, _ in parse_rrule(raw).errors]


def test_minimal_weekly_rule_parses_clean():
    rule = parse_rrule("FREQ=WEEKLY;BYDAY=MO,WE,FR;COUNT=10")
    assert rule.errors == []
    assert rule.freq == "WEEKLY"
    assert [e.weekday for e in rule.byday] == ["MO", "WE", "FR"]
    assert rule.count == 10


def test_missing_freq_is_r001():
    assert "R001" in error_ids("COUNT=5")


def test_invalid_freq_value_is_r002_without_double_reporting_r001():
    found = error_ids("FREQ=FORTNIGHTLY")
    assert "R002" in found
    assert "R001" not in found  # FREQ was present, just wrong


def test_unknown_part_is_r002():
    assert "R002" in error_ids("FREQ=DAILY;BYMOON=FULL")


def test_duplicate_part_is_r003():
    assert "R003" in error_ids("FREQ=DAILY;COUNT=1;COUNT=2")


def test_nonpositive_count_and_interval_are_r014():
    assert "R014" in error_ids("FREQ=DAILY;COUNT=0")
    assert "R014" in error_ids("FREQ=DAILY;INTERVAL=-2")
    assert "R014" in error_ids("FREQ=DAILY;INTERVAL=x")


def test_byday_ordinals_parse_and_zero_is_rejected():
    rule = parse_rrule("FREQ=MONTHLY;BYDAY=2MO,-1SU")
    assert rule.errors == []
    assert [(e.ordinal, e.weekday) for e in rule.byday] == [(2, "MO"), (-1, "SU")]
    assert "R002" in error_ids("FREQ=MONTHLY;BYDAY=0MO")
    assert "R002" in error_ids("FREQ=MONTHLY;BYDAY=MONDAY")


def test_until_accepts_both_value_types_and_flags_garbage():
    assert parse_rrule("FREQ=DAILY;UNTIL=20261231").until.kind == "date"
    assert parse_rrule("FREQ=DAILY;UNTIL=20261231T000000Z").until.utc
    assert "R002" in error_ids("FREQ=DAILY;UNTIL=NEVER")


def test_integer_list_parts_are_range_checked():
    assert parse_rrule("FREQ=MONTHLY;BYMONTHDAY=1,15,-1").errors == []
    assert "R002" in error_ids("FREQ=MONTHLY;BYMONTHDAY=32")
    assert "R002" in error_ids("FREQ=YEARLY;BYMONTH=13")
    assert "R002" in error_ids("FREQ=DAILY;BYHOUR=-1")


def test_wkst_is_validated_against_weekday_tokens():
    assert "R002" in error_ids("FREQ=WEEKLY;WKST=XX")
    assert parse_rrule("FREQ=WEEKLY;WKST=SU").wkst == "SU"
    assert parse_rrule("FREQ=WEEKLY;WKST=SU").errors == []

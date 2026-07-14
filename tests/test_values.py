"""DATE / DATE-TIME value parsing and classification."""

from __future__ import annotations

from icalint.model import Property
from icalint.values import classify, parse_date, parse_datetime


def prop(raw: str, **params) -> Property:
    return Property(
        name="DTSTART",
        value=raw,
        params={k.upper(): [v] for k, v in params.items()},
        line=1,
    )


def test_parse_date_accepts_real_dates_only():
    assert parse_date("20260714") is not None
    assert parse_date("20260230") is None  # Feb 30 does not exist
    assert parse_date("2026071") is None  # too short
    assert parse_date("20260714T090000") is None  # that is a DATE-TIME


def test_parse_datetime_reads_utc_flag_and_rejects_bad_times():
    utc = parse_datetime("20260714T090000Z")
    assert utc is not None and utc.utc and utc.time == (9, 0, 0)
    local = parse_datetime("20260714T090000")
    assert local is not None and not local.utc
    assert parse_datetime("20260714T240000") is None  # hour 24
    assert parse_datetime("20260714T096100") is None  # minute 61
    # RFC 5545's TIME grammar allows second 60 (leap second).
    assert parse_datetime("20260630T235960Z") is not None


def test_classify_floating_is_exactly_no_tzid_and_no_z():
    anchored = classify(prop("20260714T090000", tzid="America/New_York"))[0]
    assert anchored.value is not None and not anchored.value.floating
    assert anchored.value.tzid == "America/New_York"

    floating = classify(prop("20260714T090000"))[0]
    assert floating.value.floating

    utc = classify(prop("20260714T090000Z"))[0]
    assert not utc.value.floating


def test_classify_checks_the_declared_value_type():
    # DATE shape without VALUE=DATE: legal shape, wrong declaration.
    implied = classify(prop("20260714"))[0]
    assert implied.value.kind == "date"
    assert implied.implied_date

    # Declared VALUE=DATE with a DATE value: clean.
    ok = classify(prop("20260714", value="DATE"))
    assert ok[0].value is not None and not ok[0].implied_date

    # Declared VALUE=DATE with a DATE-TIME value: a parse error.
    bad = classify(prop("20260714T090000", value="DATE"))
    assert bad[0].value is None and "DATE" in bad[0].error


def test_classify_splits_multivalued_exdate():
    exdate = Property(
        name="EXDATE",
        value="20260714T090000Z,20260721T090000Z",
        params={},
        line=1,
    )
    items = classify(exdate)
    assert len(items) == 2
    assert all(item.value is not None and item.value.utc for item in items)


def test_classify_skips_declared_period_values():
    # PERIOD is a valid RDATE type; time rules must not misread it.
    rdate = Property(
        name="RDATE",
        value="20260714T090000Z/20260714T100000Z",
        params={"VALUE": ["PERIOD"]},
        line=1,
    )
    items = classify(rdate)
    assert all(item.value is None and item.error is None for item in items)

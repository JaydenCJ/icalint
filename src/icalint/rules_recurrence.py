"""R-series rules: RRULE traps and recurrence-override integrity.

Recurrence is where RFC 5545 is most subtle and clients diverge hardest:
UNTIL has to agree with DTSTART's value type *and* be in UTC for anchored
starts, UNTIL+COUNT together is flat-out invalid, numeric BYDAY only means
something for monthly/yearly rules, and a DTSTART that does not match its
own pattern makes clients disagree about whether the first occurrence
exists at all.
"""

from __future__ import annotations

from typing import Optional

from .engine import LintContext
from .model import Component
from .registry import check
from .rrule import RRule, parse_rrule
from .values import Classified, TimeValue, classify

#: date.weekday() -> RFC 5545 weekday token.
_WEEKDAY_TOKENS = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]

#: Components on which recurrence properties are meaningful for these rules.
_RECURRING = frozenset(["VEVENT", "VTODO", "VJOURNAL"])


def _dtstart_value(component: Component) -> Optional[TimeValue]:
    prop = component.prop("DTSTART")
    if prop is None:
        return None
    items = classify(prop)
    if items and items[0].value is not None:
        return items[0].value
    return None


@check
def check_rrules(ctx: LintContext) -> None:
    """R001-R011, R014: everything about the RRULE property itself."""
    for component in ctx.walk():
        if component.name not in _RECURRING:
            continue
        for prop in component.props("RRULE"):
            rule = parse_rrule(prop.value)
            for rule_id, message in rule.errors:
                ctx.emit(rule_id, prop.line, message)

            dtstart = _dtstart_value(component)
            if component.prop("DTSTART") is None:
                ctx.emit(
                    "R009",
                    prop.line,
                    "RRULE without DTSTART: the rule has no anchor, and "
                    "clients either drop the %s or invent a start"
                    % component.name,
                )
                continue

            _check_until(ctx, prop.line, rule, dtstart)
            _check_byday_ordinals(ctx, prop.line, rule)
            _check_dtstart_matches(ctx, prop.line, rule, dtstart)
            _check_short_months(ctx, prop.line, rule, dtstart)


def _check_until(ctx, line, rule: RRule, dtstart: Optional[TimeValue]) -> None:
    """R004/R005/R006/R007."""
    if rule.until is not None and rule.count is not None:
        ctx.emit(
            "R004",
            line,
            "RRULE has both UNTIL and COUNT; RFC 5545 allows at most one, "
            "and clients disagree about which bound wins",
        )
    if rule.until is None or dtstart is None:
        return

    if rule.until.kind != dtstart.kind:
        ctx.emit(
            "R005",
            line,
            "UNTIL=%s is a %s but DTSTART is a %s; RFC 5545 requires the "
            "same value type and mismatches drop or duplicate the final "
            "occurrence" % (rule.until_raw, rule.until.kind, dtstart.kind),
        )
    elif dtstart.kind == "datetime":
        anchored = dtstart.utc or dtstart.tzid is not None
        if anchored and not rule.until.utc:
            ctx.emit(
                "R006",
                line,
                "UNTIL=%s is a local time but DTSTART is timezone-aware; "
                "RFC 5545 requires UTC here (append Z), otherwise the last "
                "occurrence shifts per client" % rule.until_raw,
            )

    if rule.until.approx_ordinal() < dtstart.approx_ordinal() - 1:
        # One day of slack: a UTC UNTIL can legitimately land the previous
        # calendar day relative to a far-east DTSTART.
        ctx.emit(
            "R007",
            line,
            "UNTIL=%s is before DTSTART (%s); the rule can never produce "
            "an occurrence" % (rule.until_raw, dtstart.raw),
        )


def _check_byday_ordinals(ctx, line, rule: RRule) -> None:
    """R008: ordinals like 2MO need a monthly or yearly frequency."""
    if rule.freq in ("MONTHLY", "YEARLY") or rule.freq is None:
        return
    for entry in rule.byday:
        if entry.ordinal is not None:
            ctx.emit(
                "R008",
                line,
                "BYDAY=%+d%s carries an ordinal but FREQ=%s; RFC 5545 only "
                "allows numeric BYDAY with MONTHLY or YEARLY rules"
                % (entry.ordinal, entry.weekday, rule.freq),
            )
            return


def _check_dtstart_matches(
    ctx, line, rule: RRule, dtstart: Optional[TimeValue]
) -> None:
    """R010: the anchor should satisfy its own pattern.

    RFC 5545 says DTSTART *should* match the rule; when it does not,
    some clients count DTSTART as a bonus first occurrence and others
    silently skip to the first match - attendees end up with different
    calendars.
    """
    if dtstart is None or rule.freq is None:
        return

    start_token = _WEEKDAY_TOKENS[dtstart.date.weekday()]

    if rule.freq == "WEEKLY" and rule.byday:
        plain = {e.weekday for e in rule.byday if e.ordinal is None}
        if plain and start_token not in plain:
            ctx.emit(
                "R010",
                line,
                "DTSTART falls on %s but BYDAY=%s; clients disagree on "
                "whether the start date itself is an occurrence"
                % (start_token, ",".join(sorted(plain))),
            )
    elif rule.freq == "MONTHLY" and rule.bymonthday():
        days = rule.bymonthday()
        if all(d > 0 for d in days) and dtstart.date.day not in days:
            ctx.emit(
                "R010",
                line,
                "DTSTART is day %d of the month but BYMONTHDAY=%s; clients "
                "disagree on whether the start date itself is an occurrence"
                % (dtstart.date.day, ",".join(str(d) for d in days)),
            )
    elif rule.freq == "YEARLY" and rule.bymonth():
        months = rule.bymonth()
        if dtstart.date.month not in months:
            ctx.emit(
                "R010",
                line,
                "DTSTART is in month %d but BYMONTH=%s; clients disagree "
                "on whether the start date itself is an occurrence"
                % (dtstart.date.month, ",".join(str(m) for m in months)),
            )


def _check_short_months(
    ctx, line, rule: RRule, dtstart: Optional[TimeValue]
) -> None:
    """R011: monthly rules pinned to day 29-31 skip short months."""
    if rule.freq != "MONTHLY":
        return
    pinned = [d for d in rule.bymonthday() if d >= 29]
    if not pinned and not rule.bymonthday() and dtstart is not None:
        if dtstart.date.day >= 29:
            pinned = [dtstart.date.day]
    if pinned:
        ctx.emit(
            "R011",
            line,
            "monthly rule pinned to day %s: months without that day are "
            "silently skipped by most clients (and a few clamp to the last "
            "day instead) - consider BYMONTHDAY=-1 or an explicit day list"
            % ",".join(str(d) for d in pinned),
        )


@check
def check_overrides(ctx: LintContext) -> None:
    """R012: RECURRENCE-ID overrides need a master with the same UID."""
    masters = set()
    for component in ctx.walk():
        if component.name not in _RECURRING:
            continue
        uid = component.prop("UID")
        if uid is None:
            continue
        if component.prop("RECURRENCE-ID") is None and (
            component.prop("RRULE") is not None
            or component.prop("RDATE") is not None
        ):
            masters.add((component.name, uid.value))

    for component in ctx.walk():
        if component.name not in _RECURRING:
            continue
        recurrence_id = component.prop("RECURRENCE-ID")
        uid = component.prop("UID")
        if recurrence_id is None or uid is None:
            continue
        if (component.name, uid.value) not in masters:
            ctx.emit(
                "R012",
                recurrence_id.line,
                "RECURRENCE-ID override for UID %r has no recurring master "
                "in this file; clients either drop the override or show it "
                "as a stray single event" % uid.value,
            )


@check
def check_exdates(ctx: LintContext) -> None:
    """R013: EXDATE entries must be comparable to DTSTART to match."""
    for component in ctx.walk():
        if component.name not in _RECURRING:
            continue
        dtstart = _dtstart_value(component)
        if dtstart is None:
            continue
        for prop in component.props("EXDATE"):
            for item in classify(prop):
                if item.value is None:
                    continue  # unparseable values already carry S008
                problem = _exdate_mismatch(item, dtstart)
                if problem:
                    ctx.emit("R013", prop.line, problem)
                    break  # one report per EXDATE property


def _exdate_mismatch(item: Classified, dtstart: TimeValue) -> Optional[str]:
    value = item.value
    if value.kind != dtstart.kind:
        return (
            "EXDATE %s is a %s but DTSTART is a %s; the exception will "
            "not match any occurrence and the instance keeps happening"
            % (value.raw, value.kind, dtstart.kind)
        )
    if value.kind == "datetime":
        if (value.tzid or None) != (dtstart.tzid or None) or value.utc != dtstart.utc:
            return (
                "EXDATE %s (TZID=%s%s) does not use DTSTART's reference "
                "(TZID=%s%s); strict clients only cancel exact matches"
                % (
                    value.raw,
                    value.tzid or "none",
                    ", UTC" if value.utc else "",
                    dtstart.tzid or "none",
                    ", UTC" if dtstart.utc else "",
                )
            )
    return None

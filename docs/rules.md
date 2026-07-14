# icalint rule reference

Every rule has a stable id: a category letter plus three digits. Categories:

| Prefix | Category | What it covers |
|---|---|---|
| `P` | Parse | Physical layer: line endings, folding, content-line syntax, BEGIN/END balance |
| `S` | Structure | Required properties, duplicate singletons, value validity |
| `T` | Timezone | Floating times, TZID resolution, VTIMEZONE integrity |
| `R` | Recurrence | RRULE syntax and semantics, overrides, EXDATE matching |
| `I` | Interop | Things that break real clients: scheduling metadata, ordering, escaping |

Severities are fixed per rule. `error` marks an RFC 5545 violation or something
that is guaranteed to misbehave somewhere; `warning` marks a portability hazard
that at least one major client family mishandles; `info` marks a pattern worth
knowing about but defensible on purpose.

Select or suppress rules by id or category prefix:

```bash
icalint --select T,R meeting.ics   # timezones and recurrence only
icalint --ignore I008 feed.ics     # accept midnight-to-midnight events
```

This table is generated from the registry in `src/icalint/registry.py` and is
kept in sync by `tests/test_report.py::test_every_rule_id_is_well_formed`.

## All rules

| ID | Severity | Summary |
|---|---|---|
| `I001` | error | DTEND and DURATION are both present |
| `I002` | error | DTEND/DUE value type does not match DTSTART |
| `I003` | error | Event ends at or before it starts |
| `I004` | warning | ORGANIZER/ATTENDEE is not a mailto: URI |
| `I005` | warning | Scheduling METHOD without required ORGANIZER/ATTENDEE |
| `I006` | error | Duplicate UID without RECURRENCE-ID |
| `I007` | warning | Unescaped ';' or invalid backslash escape in TEXT value |
| `I008` | info | Midnight-to-midnight event; use VALUE=DATE for all-day |
| `I009` | warning | ATTACH points at a local file, unreachable for recipients |
| `I010` | warning | CALSCALE other than GREGORIAN |
| `P001` | error | Malformed content line (missing ':' or bad parameter syntax) |
| `P002` | error | Continuation line with nothing to continue |
| `P003` | error | END does not match the currently open component |
| `P004` | error | Component is never closed (BEGIN without END) |
| `P005` | error | END without a matching BEGIN |
| `P006` | warning | Bare LF line endings (RFC 5545 requires CRLF) |
| `P007` | warning | Physical line longer than 75 octets and not folded |
| `P008` | error | Content outside BEGIN:VCALENDAR |
| `P009` | error | Control character embedded in a content line |
| `P010` | warning | Blank line inside iCalendar data |
| `R001` | error | RRULE is missing FREQ |
| `R002` | error | Unknown RRULE part or invalid part value |
| `R003` | error | RRULE part appears more than once |
| `R004` | error | RRULE has both UNTIL and COUNT |
| `R005` | error | UNTIL value type does not match DTSTART |
| `R006` | error | UNTIL must be UTC when DTSTART is timezone-aware |
| `R007` | warning | UNTIL is before DTSTART (rule yields no occurrences) |
| `R008` | error | Numeric BYDAY requires FREQ=MONTHLY or FREQ=YEARLY |
| `R009` | error | RRULE on a component without DTSTART |
| `R010` | warning | DTSTART does not match the RRULE pattern |
| `R011` | info | Monthly BYMONTHDAY 29-31 silently skips short months |
| `R012` | warning | RECURRENCE-ID override without a master event in this file |
| `R013` | warning | EXDATE type or TZID differs from DTSTART |
| `R014` | error | INTERVAL or COUNT is not a positive integer |
| `S001` | error | VCALENDAR is missing VERSION |
| `S002` | warning | VERSION is not 2.0 |
| `S003` | warning | VCALENDAR is missing PRODID |
| `S004` | error | Component is missing UID |
| `S005` | error | Component is missing DTSTAMP |
| `S006` | warning | VEVENT is missing DTSTART |
| `S007` | error | Property that must occur at most once occurs again |
| `S008` | error | Invalid DATE or DATE-TIME value |
| `S009` | warning | Calendar contains no events, tasks, or journal entries |
| `S010` | warning | Non-standard property without an X- prefix |
| `S011` | warning | DATE value without VALUE=DATE parameter |
| `T001` | warning | Floating local time (no TZID, not UTC) |
| `T002` | error | TZID has no matching VTIMEZONE in this file |
| `T003` | info | VTIMEZONE is defined but never referenced |
| `T004` | warning | Windows/Exchange timezone name instead of an IANA name |
| `T005` | warning | Globally-unique TZID (leading slash) trips many parsers |
| `T006` | error | TZID parameter on a value already in UTC |
| `T007` | error | VTIMEZONE has no STANDARD or DAYLIGHT subcomponent |
| `T008` | error | VTIMEZONE is missing its TZID property |
| `T009` | warning | TZID parameter on a DATE value (dates are timezone-free) |

## Design notes on the judgment calls

- **T002 severity.** RFC 5545 *requires* a `VTIMEZONE` for every `TZID`
  referenced, so the rule is an `error` even though Google Calendar and
  Apple's clients will guess IANA-shaped names. The diagnostic message
  softens accordingly when the name is IANA-shaped.
- **R007 slack.** `UNTIL` is compared with one day of tolerance: a UTC
  `UNTIL` may land on the previous calendar day of a far-eastern `DTSTART`
  and still yield occurrences. Exact zone arithmetic would require tz data
  and would make results machine-dependent - a linter must be deterministic.
- **I003 silence across zones.** When `DTSTART` and `DTEND` sit in
  *different* named zones, ordering is not checked at all: guessing offsets
  without tz data risks false positives, and a linter that cries wolf gets
  turned off.
- **R010 restraint.** Only the unambiguous cases are checked (weekly
  `BYDAY`, monthly positive `BYMONTHDAY`, yearly `BYMONTH`). Negative
  ordinals like `BYMONTHDAY=-1` would need occurrence expansion to verify,
  so they are left alone.

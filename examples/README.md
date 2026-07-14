# icalint examples

Four small `.ics` files, each demonstrating one family of real-world
calendar bugs. All of them use CRLF line endings (the RFC 5545 wire
format) - keep that in mind if your editor rewrites line endings on save.

| File | What it shows | Expected result |
|---|---|---|
| `clean.ics` | A fully interoperable invite: anchored times, matching VTIMEZONE, mailto addresses | exit 0, `no problems found` |
| `floating-time.ics` | The classic "works on my machine" invite: DTSTART/DTEND with no TZID and no `Z` | `T001` x2, exit 1 |
| `rrule-traps.ics` | A weekly rule with `UNTIL`+`COUNT`, a local-time `UNTIL`, a missing VTIMEZONE, and a Tuesday DTSTART on a `BYDAY=MO` rule | `T002`, `R004`, `R006`, `R010`, exit 1 |
| `outlook-export.ics` | An Exchange-flavored REQUEST: Windows TZID, bare email ORGANIZER, unescaped `;`, missing ATTENDEE | `T004`, `I004`, `I005`, `I007`, exit 1 |

Run them all from the repository root without installing anything:

```bash
PYTHONPATH=src python3 -m icalint examples/
```

Or after `pip install -e .`:

```bash
icalint examples/
```

These same files are exercised end-to-end by `scripts/smoke.sh`, which also
repairs `floating-time.ics` on the fly and asserts that the fixed version
lints clean.

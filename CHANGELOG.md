# Changelog

All notable changes to this project are documented in this file. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-07-13

### Added

- Forgiving RFC 5545 physical-layer parser: CRLF/LF detection, line
  unfolding, 75-octet length checks, quoted and multi-valued parameters,
  BEGIN/END balance with recovery - every violation becomes a `P` finding
  and parsing continues so later rules still run.
- 54 rules across five categories with stable ids and fixed severities:
  parse (`P001`-`P010`), structure (`S001`-`S011`), timezone
  (`T001`-`T009`), recurrence (`R001`-`R014`), and interop
  (`I001`-`I010`); the full reference lives in `docs/rules.md`.
- Timezone hazard detection: floating local times, TZID references with no
  VTIMEZONE (with IANA-shaped-name awareness), Windows/Exchange display
  names with concrete IANA replacements from a 40+ entry CLDR mapping,
  globally-unique (leading slash) TZIDs, TZID-on-UTC and TZID-on-DATE
  conflicts, and malformed VTIMEZONE blocks.
- RRULE trap detection: UNTIL/COUNT conflicts, UNTIL value-type and UTC
  requirements, unreachable UNTIL, numeric BYDAY frequency restrictions,
  DTSTART-vs-pattern mismatches, short-month BYMONTHDAY pins, orphan
  RECURRENCE-ID overrides, and EXDATE reference mismatches.
- Interop checks: DTEND/DURATION conflicts, end-before-start, non-mailto
  ORGANIZER/ATTENDEE, METHOD contracts, duplicate UIDs, TEXT escaping,
  midnight-to-midnight all-day shapes, local-file ATTACH, and CALSCALE.
- `icalint` CLI: files, directories (recursive `*.ics`), and stdin via
  `-`; `--format text|json`; `--select`/`--ignore` by rule id or category
  prefix; `--min-severity`; `--fail-on` threshold for CI; `--list-rules`;
  linter-conventional exit codes (0 clean, 1 findings, 2 usage error).
- Python API: `lint_text()` / `lint_path()` returning typed `Diagnostic`
  objects, plus the `RULES` registry.
- Four annotated example calendars in `examples/`, a rule reference with
  design notes in `docs/rules.md`, 91 pytest tests, and
  `scripts/smoke.sh` exercising the CLI end-to-end.

### Notes

- Zero runtime dependencies; nothing is read or written besides the given
  files, stdin, and stdout/stderr.
- The repository ships no CI workflow; verification is local -
  `pip install -e '.[dev]' && pytest && bash scripts/smoke.sh`.

[0.1.0]: https://github.com/JaydenCJ/icalint/releases/tag/v0.1.0

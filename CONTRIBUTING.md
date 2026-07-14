# Contributing to icalint

Thanks for your interest in contributing. Issues, discussions, and pull
requests are all welcome.

## Getting started

You need Python 3.9 or newer; the runtime has zero dependencies and the
test suite only needs pytest.

```bash
git clone https://github.com/JaydenCJ/icalint
cd icalint
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
bash scripts/smoke.sh
```

`scripts/smoke.sh` drives the real CLI against the shipped examples -
exit codes, JSON output, rule selection, stdin - and must print `SMOKE OK`.

## Before you open a pull request

1. `pytest` - the full suite must pass.
2. `bash scripts/smoke.sh` - must print `SMOKE OK`.
3. Add tests for every behavior change; rule logic lives in pure,
   unit-testable modules (`rules_*.py`), so a new rule is a function
   plus a registry row plus tests.
4. New or changed rules must update `docs/rules.md` - a test fails
   otherwise, on purpose.
5. Keep the three READMEs aligned: `README.md`, `README.zh.md`, and
   `README.ja.md` share the same structure line for line; English is
   the authoritative version.

## Ground rules

- **No runtime dependencies.** The linter is standard-library only; that
  is a feature and a compatibility promise. Test-only dependencies belong
  in the `dev` extra, and adding one needs justification in the PR.
- **No network calls, no telemetry.** icalint reads files and stdin,
  writes stdout/stderr, and does nothing else.
- **Determinism over cleverness.** A rule that needs timezone databases,
  the current date, or locale to decide is wrong for this tool; results
  must be identical on every machine.
- **Prefer silence over false positives.** When a check cannot be certain
  (cross-zone comparisons, negative BYMONTHDAY), stay quiet - see the
  design notes in `docs/rules.md`.
- Code comments and doc comments are written in English.

## Reporting bugs

Please include `icalint --version`, the exact command line, and a minimal
`.ics` snippet that reproduces the finding (or the missing finding).
Calendar files often contain personal data - trim them down to the
offending component and replace addresses with `example.test` ones.

## Security

Please do not report security issues in public GitHub issues. Use GitHub's
private vulnerability reporting on this repository instead.

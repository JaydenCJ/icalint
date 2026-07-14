#!/usr/bin/env bash
# Smoke test for icalint: run the real CLI against the shipped examples and
# assert on exit codes, rule ids, JSON output, filtering, and stdin input.
# Self-contained: pure stdlib, no network, idempotent (works from a clean tree).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [ -x "$ROOT/.venv/bin/python" ]; then
  PYTHON="$ROOT/.venv/bin/python"
fi

# The package has zero runtime dependencies, so running from src/ needs no install.
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/icalint-smoke.XXXXXX")"
trap 'rm -rf "$WORKDIR"' EXIT

fail() { echo "SMOKE FAIL: $1" >&2; exit 1; }

echo "[smoke] python: $("$PYTHON" --version 2>&1)"

# 1. A clean calendar exits 0 and says so.
clean_out="$("$PYTHON" -m icalint "$ROOT/examples/clean.ics")" \
  || fail "clean.ics should exit 0"
echo "$clean_out" | sed 's/^/[clean] /'
echo "$clean_out" | grep -q "no problems found" || fail "clean.ics not reported clean"

# 2. The floating-time example is caught with T001 and exits 1.
set +e
float_out="$("$PYTHON" -m icalint "$ROOT/examples/floating-time.ics")"
float_rc=$?
set -e
echo "$float_out" | sed 's/^/[float] /'
[ "$float_rc" -eq 1 ] || fail "floating-time.ics should exit 1, got $float_rc"
echo "$float_out" | grep -q 'warning\[T001\]' || fail "T001 not reported"

# 3. The RRULE-trap example reports the UNTIL+COUNT, UTC, VTIMEZONE and
#    DTSTART-pattern findings.
set +e
rrule_out="$("$PYTHON" -m icalint "$ROOT/examples/rrule-traps.ics")"
rrule_rc=$?
set -e
echo "$rrule_out" | sed 's/^/[rrule] /'
[ "$rrule_rc" -eq 1 ] || fail "rrule-traps.ics should exit 1, got $rrule_rc"
for rule in T002 R004 R006 R010; do
  echo "$rrule_out" | grep -q "\[$rule\]" || fail "$rule not reported for rrule-traps.ics"
done

# 4. The Outlook-flavored example flags the Windows TZID with a suggestion.
set +e
outlook_out="$("$PYTHON" -m icalint "$ROOT/examples/outlook-export.ics")"
set -e
echo "$outlook_out" | grep -q 'warning\[T004\]' || fail "T004 not reported"
echo "$outlook_out" | grep -q "Asia/Shanghai" || fail "IANA suggestion missing"
echo "$outlook_out" | grep -q 'warning\[I004\]' || fail "I004 not reported"

# 5. JSON output is valid JSON and carries the same rule ids.
json_out="$("$PYTHON" -m icalint --format json --fail-on never "$ROOT/examples/rrule-traps.ics")"
echo "$json_out" | "$PYTHON" -m json.tool >/dev/null || fail "JSON output does not parse"
echo "$json_out" | grep -q '"rule": "R004"' || fail "JSON output missing R004"

# 6. Selection: --select T sees only timezone rules; --ignore removes them.
select_out="$("$PYTHON" -m icalint --select T --fail-on never "$ROOT/examples/rrule-traps.ics")"
echo "$select_out" | grep -q '\[T002\]' || fail "--select T lost T002"
echo "$select_out" | grep -q '\[R004\]' && fail "--select T leaked an R rule"
ignore_out="$("$PYTHON" -m icalint --ignore T,R --fail-on never "$ROOT/examples/rrule-traps.ics")"
echo "$ignore_out" | grep -q "no problems found" || fail "--ignore T,R left findings"

# 7. Directory input recurses and checks all four examples.
set +e
dir_out="$("$PYTHON" -m icalint "$ROOT/examples")"
set -e
echo "$dir_out" | grep -q "4 files checked" || fail "directory scan missed files"

# 8. stdin via '-' works and labels findings <stdin>.
stdin_out="$(printf 'BEGIN:VCALENDAR\r\nVERSION:2.0\r\nEND:VCALENDAR\r\n' \
  | "$PYTHON" -m icalint --fail-on never -)"
echo "$stdin_out" | grep -q '<stdin>:.*\[S003\]' || fail "stdin lint missing S003"

# 9. --list-rules exposes the registry; --version matches the package.
rules_out="$("$PYTHON" -m icalint --list-rules)"
echo "$rules_out" | grep -q "^T001" || fail "--list-rules missing T001"
version_out="$("$PYTHON" -m icalint --version)"
pkg_version="$("$PYTHON" -c 'import icalint; print(icalint.__version__)')"
[ "$version_out" = "icalint $pkg_version" ] \
  || fail "--version mismatch: '$version_out' vs package '$pkg_version'"

# 10. A fixed file round-trips to clean: repair the floating-time example.
sed -e 's/^DTSTART:20260714T190000\r*$/DTSTART:20260714T190000Z\r/' \
    -e 's/^DTEND:20260714T200000\r*$/DTEND:20260714T200000Z\r/' \
    "$ROOT/examples/floating-time.ics" > "$WORKDIR/fixed.ics"
"$PYTHON" -m icalint "$WORKDIR/fixed.ics" >/dev/null \
  || fail "repaired floating-time.ics should lint clean"

echo "SMOKE OK"

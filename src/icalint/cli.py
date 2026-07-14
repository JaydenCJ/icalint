"""Command-line interface for icalint.

Exit codes follow linter convention:

* ``0`` - no finding at or above ``--fail-on`` (default: warning)
* ``1`` - at least one finding at or above ``--fail-on``
* ``2`` - usage error, unreadable input, or an unknown rule id
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import List, Optional, Sequence, Set, Tuple

from . import __version__
from .engine import lint_text
from .model import SEVERITY_BY_NAME, Diagnostic
from .registry import RULES, expand_selection
from .report import render_json, render_text

EXIT_CLEAN = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="icalint",
        description=(
            "Lint .ics iCalendar files for floating times, missing "
            "VTIMEZONEs, RRULE traps, and other interoperability breakers."
        ),
    )
    parser.add_argument(
        "paths",
        nargs="*",
        metavar="PATH",
        help=".ics files or directories to lint; '-' reads from stdin",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="output format (default: text)",
    )
    parser.add_argument(
        "--select",
        metavar="RULES",
        help="only run these rules: comma-separated ids or prefixes "
        "(e.g. 'T001,R' runs T001 plus every recurrence rule)",
    )
    parser.add_argument(
        "--ignore",
        metavar="RULES",
        help="skip these rules: comma-separated ids or prefixes",
    )
    parser.add_argument(
        "--min-severity",
        choices=("info", "warning", "error"),
        default="info",
        help="hide findings below this severity (default: info, i.e. show all)",
    )
    parser.add_argument(
        "--fail-on",
        choices=("info", "warning", "error", "never"),
        default="warning",
        help="exit 1 when a finding at or above this severity survives "
        "filtering (default: warning)",
    )
    parser.add_argument(
        "--list-rules",
        action="store_true",
        help="print every rule id with severity and summary, then exit",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="icalint %s" % __version__,
    )
    return parser


def _list_rules() -> str:
    lines = ["ID    severity  summary"]
    for rule_id in sorted(RULES):
        rule = RULES[rule_id]
        lines.append("%-5s %-9s %s" % (rule.id, rule.severity, rule.summary))
    return "\n".join(lines)


def _expand_paths(raw_paths: Sequence[str]) -> Tuple[List[str], Optional[str]]:
    """Resolve files/dirs/stdin markers; returns (inputs, error)."""
    inputs: List[str] = []
    for raw in raw_paths:
        if raw == "-":
            inputs.append("-")
            continue
        path = Path(raw)
        if path.is_dir():
            found = sorted(str(p) for p in path.rglob("*.ics"))
            if not found:
                return [], "no .ics files under directory %s" % raw
            inputs.extend(found)
        elif path.is_file():
            inputs.append(str(path))
        else:
            return [], "no such file or directory: %s" % raw
    return inputs, None


def _read(source: str) -> str:
    if source == "-":
        return sys.stdin.read()
    # newline="" is essential: universal-newline mode would translate CRLF
    # to LF before the linter ever sees it, hiding every line-ending issue.
    with open(source, "r", encoding="utf-8", errors="replace", newline="") as fh:
        return fh.read()


def _apply_filters(
    diagnostics: List[Diagnostic],
    selected: Optional[Set[str]],
    ignored: Set[str],
    min_severity: str,
) -> List[Diagnostic]:
    floor = SEVERITY_BY_NAME[min_severity]
    kept = []
    for diagnostic in diagnostics:
        if selected is not None and diagnostic.rule_id not in selected:
            continue
        if diagnostic.rule_id in ignored:
            continue
        if diagnostic.severity < floor:
            continue
        kept.append(diagnostic)
    return kept


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_rules:
        print(_list_rules())
        return EXIT_CLEAN

    if not args.paths:
        parser.print_usage(sys.stderr)
        print("icalint: error: no input files (use '-' for stdin)", file=sys.stderr)
        return EXIT_USAGE

    try:
        selected = expand_selection(args.select) if args.select else None
        ignored = expand_selection(args.ignore) if args.ignore else set()
    except ValueError as exc:
        print("icalint: error: %s" % exc, file=sys.stderr)
        return EXIT_USAGE

    inputs, error = _expand_paths(args.paths)
    if error is not None:
        print("icalint: error: %s" % error, file=sys.stderr)
        return EXIT_USAGE

    diagnostics: List[Diagnostic] = []
    for source in inputs:
        try:
            text = _read(source)
        except OSError as exc:
            print("icalint: error: cannot read %s: %s" % (source, exc), file=sys.stderr)
            return EXIT_USAGE
        label = "<stdin>" if source == "-" else source
        diagnostics.extend(lint_text(text, path=label))

    diagnostics = _apply_filters(diagnostics, selected, ignored, args.min_severity)

    if args.format == "json":
        rendered = render_json(diagnostics, files_checked=len(inputs))
    else:
        rendered = render_text(diagnostics, files_checked=len(inputs))
    try:
        print(rendered)
        sys.stdout.flush()
    except BrokenPipeError:
        # A downstream consumer (e.g. `icalint dir/ | head`) closed the pipe
        # early. Unix convention is to stop quietly, not crash with a
        # traceback. Re-point stdout at devnull so the interpreter's final
        # implicit flush cannot raise a second time, then fall through to the
        # normal exit-code computation.
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())

    if args.fail_on == "never":
        return EXIT_CLEAN
    threshold = SEVERITY_BY_NAME[args.fail_on]
    if any(diagnostic.severity >= threshold for diagnostic in diagnostics):
        return EXIT_FINDINGS
    return EXIT_CLEAN


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

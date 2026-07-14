"""Reporters and the rule registry: stable formats, selection semantics."""

from __future__ import annotations

import pathlib
import re

import pytest

from icalint.model import Diagnostic, Severity
from icalint.registry import RULES, expand_selection
from icalint.report import render_json, render_text, summary_line

from conftest import calendar, event, lint


def _diagnostic(severity, rule_id="T001", line=3):
    return Diagnostic("a.ics", line, rule_id, severity, "message")


def test_summary_line_pluralizes_correctly():
    assert summary_line([], 1) == "1 file checked: no problems found"
    diagnostics = [
        _diagnostic(Severity.ERROR),
        _diagnostic(Severity.WARNING),
        _diagnostic(Severity.WARNING),
        _diagnostic(Severity.INFO),
    ]
    assert (
        summary_line(diagnostics, 2)
        == "2 files checked: 1 error, 2 warnings, 1 info"
    )
    # render_text always ends with that same summary line.
    out = render_text([_diagnostic(Severity.ERROR)], 1)
    assert out.splitlines()[-1] == "1 file checked: 1 error"


def test_text_lines_follow_the_grep_able_contract():
    # path:line: severity[ID] message - documented as a stable interface.
    pattern = re.compile(
        r"^test\.ics:\d+: (error|warning|info)\[[PSTRI]\d{3}\] .+$"
    )
    text = calendar(*event("DTSTART:20260714T190000"))
    for diagnostic in lint(text):
        assert pattern.match(diagnostic.render())


def test_render_json_is_deterministic():
    diagnostics = [
        _diagnostic(Severity.ERROR, "S001", 2),
        _diagnostic(Severity.WARNING, "T001", 9),
    ]
    assert render_json(diagnostics, 1) == render_json(diagnostics, 1)
    assert '"files_checked": 1' in render_json(diagnostics, 1)


def test_expand_selection_accepts_ids_and_prefixes():
    assert expand_selection("T001") == {"T001"}
    assert expand_selection("R") == {
        rule_id for rule_id in RULES if rule_id.startswith("R")
    }
    combined = expand_selection("T001, I")
    assert "T001" in combined and "I003" in combined


def test_expand_selection_rejects_unknown_tokens():
    with pytest.raises(ValueError):
        expand_selection("Q")


def test_every_rule_id_is_well_formed():
    for rule_id, rule in RULES.items():
        assert re.match(r"^[PSTRI]\d{3}$", rule_id)
        assert rule.severity in (Severity.INFO, Severity.WARNING, Severity.ERROR)
        assert rule.summary  # never empty: --list-rules relies on it

    # docs/rules.md is the user-facing reference; it must document every
    # registered rule with its exact severity and summary.
    docs = (
        pathlib.Path(__file__).resolve().parents[1] / "docs" / "rules.md"
    ).read_text(encoding="utf-8")
    for rule_id, rule in RULES.items():
        row = "| `%s` | %s | %s |" % (rule_id, rule.severity, rule.summary)
        assert row in docs, "docs/rules.md is missing or outdated for %s" % rule_id

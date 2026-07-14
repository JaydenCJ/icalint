"""Reporters: render diagnostics as GCC-style text or machine-readable JSON.

Both formats are stable interfaces: the text format is one finding per
line (``path:line: severity[ID] message``) so editors and CI annotations
can regex it, and the JSON schema is documented in the README and only
ever gains keys.
"""

from __future__ import annotations

import json
from typing import Dict, List

from .model import Diagnostic, Severity


def _counts(diagnostics: List[Diagnostic]) -> Dict[str, int]:
    counts = {"error": 0, "warning": 0, "info": 0}
    for diagnostic in diagnostics:
        counts[str(diagnostic.severity)] += 1
    return counts


def summary_line(diagnostics: List[Diagnostic], files_checked: int) -> str:
    """One human summary line, e.g. ``2 files checked: 1 error, 3 warnings``."""
    files = "%d file%s checked" % (files_checked, "" if files_checked == 1 else "s")
    if not diagnostics:
        return "%s: no problems found" % files
    counts = _counts(diagnostics)
    parts = []
    for name in ("error", "warning", "info"):
        if counts[name]:
            plural = "" if counts[name] == 1 else "s"
            label = name if name == "info" else name + plural
            parts.append("%d %s" % (counts[name], label))
    return "%s: %s" % (files, ", ".join(parts))


def render_text(diagnostics: List[Diagnostic], files_checked: int) -> str:
    """Full text report: one line per finding plus a summary line."""
    lines = [diagnostic.render() for diagnostic in diagnostics]
    lines.append(summary_line(diagnostics, files_checked))
    return "\n".join(lines)


def render_json(diagnostics: List[Diagnostic], files_checked: int) -> str:
    """Machine-readable report with per-file grouping and totals."""
    by_path: Dict[str, List[Diagnostic]] = {}
    for diagnostic in diagnostics:
        by_path.setdefault(diagnostic.path, []).append(diagnostic)

    payload = {
        "files": [
            {
                "path": path,
                "diagnostics": [
                    {
                        "line": d.line,
                        "rule": d.rule_id,
                        "severity": str(d.severity),
                        "message": d.message,
                    }
                    for d in items
                ],
            }
            for path, items in sorted(by_path.items())
        ],
        "summary": dict(_counts(diagnostics), files_checked=files_checked),
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def worst_severity(diagnostics: List[Diagnostic]) -> Severity:
    """Highest severity present; INFO when the list is empty."""
    worst = Severity.INFO
    for diagnostic in diagnostics:
        if diagnostic.severity > worst:
            worst = diagnostic.severity
    return worst

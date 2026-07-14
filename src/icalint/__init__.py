"""icalint - a linter for iCalendar (.ics) files.

Public API:

* :func:`lint_text` - lint a string of iCalendar data.
* :func:`lint_path` - lint a file on disk.
* :class:`Diagnostic` / :class:`Severity` - what the linter returns.
* :data:`RULES` - metadata for every rule id.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Union

from .engine import lint_text
from .model import Diagnostic, Severity
from .registry import RULES, Rule

__version__ = "0.1.0"

__all__ = [
    "Diagnostic",
    "RULES",
    "Rule",
    "Severity",
    "__version__",
    "lint_path",
    "lint_text",
]


def lint_path(path: Union[str, Path]) -> List[Diagnostic]:
    """Lint one .ics file on disk and return its diagnostics."""
    file_path = Path(path)
    # newline="" keeps CRLF intact; universal-newline reading would hide
    # every line-ending diagnostic before the linter runs.
    with open(file_path, "r", encoding="utf-8", errors="replace", newline="") as fh:
        text = fh.read()
    return lint_text(text, path=str(file_path))

"""The lint engine: parse once, hand a shared context to every check pass.

Importing this module pulls in the ``rules_*`` modules for their
registration side effects, so :func:`lint_text` is the only entry point
callers need.
"""

from __future__ import annotations

from typing import Dict, Iterator, List, Optional, Tuple

from .model import Component, Diagnostic
from .parser import parse
from .registry import CHECKS, RULES

#: Components that carry user-facing times (as opposed to VTIMEZONE
#: observances, whose DTSTART is *supposed* to be a floating local time).
TIME_COMPONENTS = frozenset(["VEVENT", "VTODO", "VJOURNAL", "VFREEBUSY"])


class LintContext:
    """Everything a check pass needs: the tree, helpers, and an emit sink."""

    def __init__(self, path: str, components: List[Component]):
        self.path = path
        self.components = components
        self.diagnostics: List[Diagnostic] = []
        self._vtimezones: Optional[Dict[str, Component]] = None

    # -- emission ----------------------------------------------------------

    def emit(self, rule_id: str, line: int, message: str) -> None:
        rule = RULES[rule_id]
        self.diagnostics.append(
            Diagnostic(self.path, line, rule_id, rule.severity, message)
        )

    # -- traversal helpers ---------------------------------------------------

    def calendars(self) -> List[Component]:
        """Top-level VCALENDAR components (an .ics stream may hold several)."""
        return [c for c in self.components if c.name == "VCALENDAR"]

    def walk(self, name: Optional[str] = None) -> Iterator[Component]:
        """Every component in the file, optionally filtered by name."""
        for top in self.components:
            yield from top.walk(name)

    def scheduled(self) -> Iterator[Component]:
        """Every component that carries user-facing date/time properties."""
        for component in self.walk():
            if component.name in TIME_COMPONENTS:
                yield component

    def vtimezones(self) -> Dict[str, Component]:
        """TZID -> VTIMEZONE component, for the whole file (cached)."""
        if self._vtimezones is None:
            zones: Dict[str, Component] = {}
            for vtimezone in self.walk("VTIMEZONE"):
                tzid = vtimezone.prop("TZID")
                if tzid is not None and tzid.value:
                    zones.setdefault(tzid.value, vtimezone)
            self._vtimezones = zones
        return self._vtimezones

    def tzid_references(self) -> List[Tuple[str, int]]:
        """Every (TZID value, line) referenced outside VTIMEZONE blocks."""
        references: List[Tuple[str, int]] = []

        def visit(component: Component) -> None:
            if component.name == "VTIMEZONE":
                return
            for prop in component.properties:
                tzid = prop.param("TZID")
                if tzid is not None:
                    references.append((tzid, prop.line))
            for child in component.children:
                visit(child)

        for top in self.components:
            visit(top)
        return references


def lint_text(text: str, path: str = "<string>") -> List[Diagnostic]:
    """Lint iCalendar text and return diagnostics sorted by location."""
    parsed = parse(text, path)
    context = LintContext(path, parsed.components)
    context.diagnostics.extend(parsed.diagnostics)
    for check_pass in CHECKS:
        check_pass(context)
    context.diagnostics.sort(key=lambda diagnostic: diagnostic.sort_key)
    return context.diagnostics


# Import for side effects: each module registers its check passes.
from . import rules_structure  # noqa: E402,F401  (registration import)
from . import rules_timezone  # noqa: E402,F401
from . import rules_recurrence  # noqa: E402,F401
from . import rules_interop  # noqa: E402,F401

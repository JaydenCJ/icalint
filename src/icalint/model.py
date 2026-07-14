"""Data model for icalint: properties, components, and diagnostics.

Everything the parser produces and the rules consume lives here. The model
deliberately keeps the *raw* text of every value: a linter must be able to
point at what the file actually says, not at a normalized reconstruction.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional


class Severity(enum.IntEnum):
    """Diagnostic severity, ordered so that comparisons read naturally."""

    INFO = 1
    WARNING = 2
    ERROR = 3

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.name.lower()


#: Mapping used by the CLI to parse ``--fail-on`` / ``--min-severity``.
SEVERITY_BY_NAME: Dict[str, Severity] = {
    "info": Severity.INFO,
    "warning": Severity.WARNING,
    "error": Severity.ERROR,
}


@dataclass
class Property:
    """One unfolded iCalendar content line (``NAME;PARAM=v:value``)."""

    name: str  # upper-cased property name
    value: str  # raw value text, exactly as written (after unfolding)
    params: Dict[str, List[str]] = field(default_factory=dict)  # upper-cased keys
    line: int = 0  # 1-based physical line where the logical line started

    def param(self, key: str) -> Optional[str]:
        """First value of a parameter, or ``None`` when absent."""
        values = self.params.get(key.upper())
        return values[0] if values else None

    def has_param(self, key: str) -> bool:
        return key.upper() in self.params


@dataclass
class Component:
    """A ``BEGIN:NAME`` … ``END:NAME`` block with properties and children."""

    name: str  # upper-cased component name (VCALENDAR, VEVENT, ...)
    line: int = 0  # 1-based line of the BEGIN
    properties: List[Property] = field(default_factory=list)
    children: List["Component"] = field(default_factory=list)

    def props(self, name: str) -> List[Property]:
        """All properties with the given name, in file order."""
        wanted = name.upper()
        return [p for p in self.properties if p.name == wanted]

    def prop(self, name: str) -> Optional[Property]:
        """The first property with the given name, or ``None``."""
        wanted = name.upper()
        for prop in self.properties:
            if prop.name == wanted:
                return prop
        return None

    def walk(self, name: Optional[str] = None) -> Iterator["Component"]:
        """Yield this component and every descendant, optionally filtered."""
        if name is None or self.name == name.upper():
            yield self
        for child in self.children:
            yield from child.walk(name)


@dataclass(frozen=True)
class Diagnostic:
    """One finding: a rule id, a severity, a location, and a message."""

    path: str
    line: int
    rule_id: str
    severity: Severity
    message: str

    @property
    def sort_key(self):
        return (self.path, self.line, self.rule_id, self.message)

    def render(self) -> str:
        """GCC-style single-line rendering used by the text reporter."""
        return "%s:%d: %s[%s] %s" % (
            self.path,
            self.line,
            self.severity,
            self.rule_id,
            self.message,
        )

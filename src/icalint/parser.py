"""RFC 5545 physical-layer parser: unfolding, content lines, component tree.

The parser is intentionally forgiving: real-world .ics files are full of
violations, and a linter that stops at the first bad byte cannot report the
second problem. Every physical-layer violation becomes a ``P``-series
diagnostic and parsing continues on a best-effort basis, so the semantic
rules still get a component tree to inspect.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .model import Component, Diagnostic, Property, Severity
from .registry import RULES

#: RFC 5545 §3.1: lines SHOULD NOT be longer than 75 octets excluding CRLF.
MAX_LINE_OCTETS = 75


@dataclass
class ParseResult:
    """Component tree plus the physical-layer diagnostics found on the way."""

    components: List[Component] = field(default_factory=list)
    diagnostics: List[Diagnostic] = field(default_factory=list)


def parse(text: str, path: str = "<string>") -> ParseResult:
    """Parse iCalendar text into a component tree, collecting P diagnostics."""
    result = ParseResult()

    def emit(rule_id: str, line: int, message: str) -> None:
        rule = RULES[rule_id]
        result.diagnostics.append(
            Diagnostic(path, line, rule_id, rule.severity, message)
        )

    physical = _split_physical_lines(text, emit)
    logical = _unfold(physical, emit)
    _build_tree(logical, result, emit)
    return result


# --------------------------------------------------------------------------
# Physical lines
# --------------------------------------------------------------------------


def _split_physical_lines(text, emit) -> List[Tuple[int, str]]:
    """Split into (line_number, content) pairs and flag physical violations."""
    raw = text.split("\n")
    if raw and raw[-1] == "":
        raw.pop()  # text ended with a newline; not an extra line

    # Every element except possibly the last was terminated by "\n"; the
    # last one only if the text itself ended with a newline (then the empty
    # trailing element was popped above).
    lf_terminated = len(raw) if text.endswith("\n") else len(raw) - 1

    lines: List[Tuple[int, str]] = []
    bare_lf_reported = False
    for number, line in enumerate(raw, start=1):
        if line.endswith("\r"):
            line = line[:-1]
        elif number <= lf_terminated and not bare_lf_reported:
            # Report only the first bare LF: the whole file almost certainly
            # shares the same line endings, and one finding is actionable.
            emit(
                "P006",
                number,
                "line is terminated by a bare LF; RFC 5545 requires CRLF "
                "(some strict parsers reject LF-only files)",
            )
            bare_lf_reported = True

        for ch in line:
            if ord(ch) < 0x20 and ch != "\t":
                emit(
                    "P009",
                    number,
                    "control character U+%04X embedded in content line; "
                    "escape newlines in values as \\n" % ord(ch),
                )
                break

        if len(line.encode("utf-8")) > MAX_LINE_OCTETS:
            emit(
                "P007",
                number,
                "line is %d octets; RFC 5545 caps physical lines at 75 octets "
                "- fold it with CRLF + space" % len(line.encode("utf-8")),
            )
        lines.append((number, line))
    return lines


def _unfold(physical: List[Tuple[int, str]], emit) -> List[Tuple[int, str]]:
    """Join folded lines (continuations start with one space or tab)."""
    logical: List[Tuple[int, str]] = []
    for number, line in physical:
        if line == "":
            emit(
                "P010",
                number,
                "blank line inside iCalendar data; strict parsers treat this "
                "as end of input",
            )
            continue
        if line[0] in (" ", "\t"):
            if not logical:
                emit(
                    "P002",
                    number,
                    "continuation line at start of input has nothing to "
                    "continue",
                )
                logical.append((number, line[1:]))
            else:
                start, text = logical[-1]
                logical[-1] = (start, text + line[1:])
        else:
            logical.append((number, line))
    return logical


# --------------------------------------------------------------------------
# Content lines
# --------------------------------------------------------------------------

_NAME_CHARS = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-"
)


def parse_content_line(text: str) -> Property:
    """Parse ``NAME;PARAM=value:value`` into a :class:`Property`.

    Raises ``ValueError`` with a human-readable reason on malformed input.
    Quoted parameter values (``TZID="America/New_York"``) and multi-valued
    parameters (``MEMBER=a,b``) are handled per RFC 5545 §3.2.
    """
    i, n = 0, len(text)
    start = i
    while i < n and text[i] in _NAME_CHARS:
        i += 1
    name = text[start:i]
    if not name:
        raise ValueError("property name is empty")

    params: Dict[str, List[str]] = {}
    while i < n and text[i] == ";":
        i += 1
        pstart = i
        while i < n and text[i] in _NAME_CHARS:
            i += 1
        pname = text[pstart:i].upper()
        if not pname:
            raise ValueError("parameter name is empty")
        if i >= n or text[i] != "=":
            raise ValueError("parameter %s is missing '='" % pname)
        i += 1
        values: List[str] = []
        while True:
            if i < n and text[i] == '"':
                i += 1
                vstart = i
                while i < n and text[i] != '"':
                    i += 1
                if i >= n:
                    raise ValueError(
                        "unterminated quoted value for parameter %s" % pname
                    )
                values.append(text[vstart:i])
                i += 1
            else:
                vstart = i
                while i < n and text[i] not in ';:,"':
                    i += 1
                if i < n and text[i] == '"':
                    raise ValueError(
                        'parameter %s has a stray \'"\' inside an unquoted '
                        "value" % pname
                    )
                values.append(text[vstart:i])
            if i < n and text[i] == ",":
                i += 1
                continue
            break
        params.setdefault(pname, []).extend(values)

    if i >= n or text[i] != ":":
        raise ValueError("missing ':' between property name and value")
    return Property(name=name.upper(), value=text[i + 1 :], params=params)


# --------------------------------------------------------------------------
# Component tree
# --------------------------------------------------------------------------


def _build_tree(logical: List[Tuple[int, str]], result: ParseResult, emit) -> None:
    stack: List[Component] = []

    for number, text in logical:
        try:
            prop = parse_content_line(text)
        except ValueError as exc:
            emit("P001", number, "cannot parse content line: %s" % exc)
            continue
        prop.line = number

        if prop.name == "BEGIN":
            component = Component(name=prop.value.strip().upper(), line=number)
            if stack:
                stack[-1].children.append(component)
            else:
                if component.name != "VCALENDAR":
                    emit(
                        "P008",
                        number,
                        "component %s appears outside BEGIN:VCALENDAR"
                        % component.name,
                    )
                result.components.append(component)
            stack.append(component)
        elif prop.name == "END":
            name = prop.value.strip().upper()
            if not stack:
                emit("P005", number, "END:%s has no matching BEGIN" % name)
            elif stack[-1].name != name:
                emit(
                    "P003",
                    number,
                    "END:%s closes nothing; the open component is %s "
                    "(began on line %d)" % (name, stack[-1].name, stack[-1].line),
                )
                # Recover if this END matches an outer frame: pop down to it.
                open_names = [c.name for c in stack]
                if name in open_names:
                    while stack and stack[-1].name != name:
                        stack.pop()
                    stack.pop()
            else:
                stack.pop()
        else:
            if stack:
                stack[-1].properties.append(prop)
            else:
                emit(
                    "P008",
                    number,
                    "property %s appears outside BEGIN:VCALENDAR" % prop.name,
                )

    for component in stack:
        emit(
            "P004",
            component.line,
            "BEGIN:%s is never closed with END:%s"
            % (component.name, component.name),
        )

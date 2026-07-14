"""End-to-end CLI behavior: arguments, filtering, formats, exit codes."""

from __future__ import annotations

import io
import json

import pytest

from icalint import __version__
from icalint.cli import main
from icalint.registry import RULES

from conftest import calendar, event


def write_ics(path, text):
    # newline="" so the CRLF produced by the builders survives on disk.
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


@pytest.fixture
def clean_file(tmp_path, clean_calendar):
    path = tmp_path / "clean.ics"
    write_ics(path, clean_calendar)
    return path


@pytest.fixture
def dirty_file(tmp_path):
    text = calendar(
        *event(
            "DTSTART:20260714T190000",  # T001 floating (warning)
            "RRULE:FREQ=WEEKLY;BYDAY=MO;UNTIL=20261231T190000;COUNT=4",
        )
    )
    path = tmp_path / "dirty.ics"
    write_ics(path, text)
    return path


def test_clean_file_exits_zero_with_no_problems_line(clean_file, capsys):
    assert main([str(clean_file)]) == 0
    assert "no problems found" in capsys.readouterr().out


def test_findings_exit_one_by_default(dirty_file, capsys):
    assert main([str(dirty_file)]) == 1
    out = capsys.readouterr().out
    assert "T001" in out and "R004" in out


def test_fail_on_threshold_controls_the_exit_code(tmp_path, capsys):
    text = calendar(*event("DTSTART:20260714T190000"))  # only T001 (warning)
    path = tmp_path / "warn.ics"
    write_ics(path, text)

    assert main([str(path), "--fail-on", "error"]) == 0
    assert "T001" in capsys.readouterr().out  # still reported, just not fatal

    assert main([str(path), "--fail-on", "never"]) == 0
    capsys.readouterr()

    assert main([str(path), "--fail-on", "info"]) == 1
    capsys.readouterr()


def test_json_output_is_machine_readable(dirty_file, capsys):
    assert main([str(dirty_file), "--format", "json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["files_checked"] == 1
    rules = {d["rule"] for f in payload["files"] for d in f["diagnostics"]}
    assert "T001" in rules and "R004" in rules
    one = payload["files"][0]["diagnostics"][0]
    assert set(one) == {"line", "rule", "severity", "message"}


def test_select_restricts_to_a_category_prefix(dirty_file, capsys):
    main([str(dirty_file), "--select", "R"])
    out = capsys.readouterr().out
    assert "R004" in out
    assert "T001" not in out


def test_ignore_drops_specific_rules(dirty_file, capsys):
    main([str(dirty_file), "--ignore", "T001,R"])
    out = capsys.readouterr().out
    assert "T001" not in out and "R004" not in out


def test_usage_errors_exit_two(dirty_file, capsys):
    assert main([str(dirty_file), "--select", "Z999"]) == 2
    assert "unknown rule" in capsys.readouterr().err

    assert main(["definitely-not-here.ics"]) == 2
    assert "no such file" in capsys.readouterr().err

    assert main([]) == 2
    assert "no input files" in capsys.readouterr().err


def test_stdin_dash_reads_standard_input(monkeypatch, capsys):
    text = calendar(*event("DTSTART:20260714T190000"))
    monkeypatch.setattr("sys.stdin", io.StringIO(text))
    assert main(["-"]) == 1
    out = capsys.readouterr().out
    assert "<stdin>:" in out and "T001" in out


def test_directory_argument_recurses_into_ics_files(
    tmp_path, clean_calendar, capsys
):
    (tmp_path / "sub").mkdir()
    write_ics(tmp_path / "sub" / "a.ics", clean_calendar)
    write_ics(tmp_path / "b.ics", clean_calendar)
    (tmp_path / "notes.txt").write_text("not a calendar", encoding="utf-8")
    assert main([str(tmp_path)]) == 0
    assert "2 files checked" in capsys.readouterr().out


def test_min_severity_hides_and_unfails_lower_findings(tmp_path, capsys):
    text = calendar(*event("DTSTART:20260714T190000"))  # warning only
    path = tmp_path / "warn.ics"
    write_ics(path, text)
    assert main([str(path), "--min-severity", "error"]) == 0
    out = capsys.readouterr().out
    assert "T001" not in out
    assert "no problems found" in out


def test_broken_pipe_exits_without_traceback(tmp_path):
    # `icalint dir/ | head` must not crash: `head` closing the pipe raises
    # BrokenPipeError inside print(), and a traceback there would turn every
    # truncated pipeline into a scary failure. Reproduce end-to-end with a
    # report far larger than the OS pipe buffer (64 KiB) so the write is
    # guaranteed to hit EPIPE after `head` exits.
    import subprocess
    import sys as _sys

    body = []
    for i in range(1500):
        body.extend(
            [
                "BEGIN:VEVENT",
                "UID:evt-%d@example.test" % i,
                "DTSTAMP:20260701T090000Z",
                "DTSTART:20260714T190000",  # T001 x1500 -> ~250 KiB of text
                "END:VEVENT",
            ]
        )
    path = tmp_path / "big.ics"
    write_ics(path, calendar(*body))

    proc = subprocess.run(
        "%s -m icalint %s | head -c 64" % (_sys.executable, path),
        shell=True,
        capture_output=True,
        text=True,
    )
    assert "Traceback" not in proc.stderr
    assert "BrokenPipeError" not in proc.stderr


def test_list_rules_and_version_reflect_the_package(capsys):
    assert main(["--list-rules"]) == 0
    out = capsys.readouterr().out
    for rule_id in RULES:
        assert rule_id in out

    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert capsys.readouterr().out.strip() == "icalint %s" % __version__

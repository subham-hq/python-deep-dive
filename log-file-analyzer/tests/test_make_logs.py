"""Tests for the synthetic log generator in make_logs.py."""

import importlib
import re
import sys
from pathlib import Path

import pytest

import make_logs
from analyzer import ParseStats, parse

LINE = re.compile(r"2026-06-11 10:(\d{2}):(\d{2}) (\S+) (.+)")


def test_importing_make_logs_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Regression: the module used to write app.log at import time.
    monkeypatch.chdir(tmp_path)
    monkeypatch.delitem(sys.modules, "make_logs")

    importlib.import_module("make_logs")

    assert list(tmp_path.iterdir()) == []


def test_fake_lines_yields_the_requested_number_of_lines() -> None:
    assert len(list(make_logs.fake_lines(250))) == 250
    assert list(make_logs.fake_lines(0)) == []


def test_fake_lines_are_well_formed() -> None:
    for i, line in enumerate(make_logs.fake_lines(120)):
        match = LINE.fullmatch(line)
        assert match is not None, line
        minute, second, level, msg = match.groups()
        assert int(minute) == int(second) == i % 60
        assert level in make_logs.LEVELS
        assert msg in make_logs.MESSAGES


def test_main_writes_100000_parseable_lines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)

    make_logs.main()

    assert capsys.readouterr().out == "wrote app.log\n"
    stats = ParseStats()
    levels = {r["level"] for r in parse(tmp_path / "app.log", stats)}
    assert stats == ParseStats(lines_read=100_000, malformed=0)
    assert levels <= set(make_logs.LEVELS)

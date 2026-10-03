"""End-to-end check that the README's two commands work as documented."""

import re
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent


def run_script(name: str, cwd: Path) -> str:
    result = subprocess.run(
        [sys.executable, str(PROJECT / name)],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def test_make_logs_then_analyzer(tmp_path: Path) -> None:
    assert run_script("make_logs.py", tmp_path) == "wrote app.log\n"

    out = run_script("analyzer.py", tmp_path).splitlines()

    first = re.fullmatch(r"first ERROR page ready after reading only (\d+) lines", out[0])
    assert first is not None, out[0]
    assert int(first.group(1)) < 100_000  # the lazy pass stops early
    assert out[1] == "first ERROR page:"
    assert all("'level': 'ERROR'" in line for line in out[2:7])
    assert out[7] == "Ready after reading 100000 lines (0 malformed, skipped)"
    assert out[8].startswith("Counter({")
    assert re.fullmatch(r"main took \d+\.\d{4} seconds", out[9])
    assert re.fullmatch(r"\[Timer\] whole run: \d+\.\d{4} seconds", out[10])

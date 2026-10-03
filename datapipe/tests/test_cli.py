import io
import json
import os
import runpy
import subprocess
import sys
import sysconfig
from pathlib import Path

import pytest

from datapipe.cli import load_records, main

SAMPLE = Path(__file__).resolve().parent.parent / "records.json"


def write_json(path: Path, data: object) -> Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "datapipe", *args],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


# --------------------------------------------------------- load_records ----


def test_load_records_reads_the_sample_file() -> None:
    records = load_records(SAMPLE)
    assert len(records) == 1000
    assert records[0] == {"id": 1, "name": "  CANTALOUPE  ", "value": 174.93}


def test_load_records_rejects_a_non_array(tmp_path: Path) -> None:
    path = write_json(tmp_path / "obj.json", {"id": 1})
    with pytest.raises(ValueError, match="expected a JSON array of records, got dict"):
        load_records(path)


def test_load_records_names_the_index_of_a_malformed_item(tmp_path: Path) -> None:
    path = write_json(
        tmp_path / "r.json",
        [{"id": 1, "name": "a", "value": 1.0}, {"id": 2, "value": 1.0}],
    )
    with pytest.raises(ValueError, match=r"^item 1: missing required key 'name'$"):
        load_records(path)


# ------------------------------------------------------- main (in-proc) ----


def test_main_prints_one_json_object_per_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write_json(
        tmp_path / "r.json",
        [
            {"id": 1, "name": "  CANTALOUPE  ", "value": 174.93},
            {"id": 2, "name": "coconut ", "value": 384.09},
        ],
    )

    assert main([str(path)]) == 0

    out, err = capsys.readouterr()
    assert out.splitlines() == [
        '{"id": 1, "name": "cantaloupe", "value": 192.423}',
        '{"id": 2, "name": "coconut", "value": 422.499}',
    ]
    assert err == ""


def test_main_factor_option(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = write_json(tmp_path / "r.json", [{"id": 1, "name": "a", "value": 2.5}])

    assert main([str(path), "--factor", "2"]) == 0

    assert json.loads(capsys.readouterr().out) == {"id": 1, "name": "a", "value": 5.0}


@pytest.mark.parametrize(
    ("bad_record", "message"),
    [
        ({"id": 2, "name": "   ", "value": 1.0}, "record 2 has an empty name"),
        (
            {"id": 2, "name": "b", "value": -3.0},
            "record 2 has a non-positive value: -3.0",
        ),
    ],
)
def test_main_reports_a_validation_error_and_exits_1(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    bad_record: dict[str, object],
    message: str,
) -> None:
    path = write_json(
        tmp_path / "r.json", [{"id": 1, "name": "a", "value": 1.0}, bad_record]
    )

    assert main([str(path)]) == 1

    out, err = capsys.readouterr()
    # The pipeline is lazy: records before the bad one have already streamed.
    assert out.splitlines() == ['{"id": 1, "name": "a", "value": 1.1}']
    assert err == f"datapipe: error: {message}\n"


def test_main_reports_a_missing_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "nope.json"

    assert main([str(missing)]) == 1

    out, err = capsys.readouterr()
    assert out == ""
    assert err == f"datapipe: error: cannot read {missing}: No such file or directory\n"


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("", "Expecting value: line 1 column 1 (char 0)"),
        ("[1, 2", "Expecting ',' delimiter: line 1 column 6 (char 5)"),
        ('{"id": 1}', "expected a JSON array of records, got dict"),
        ('[{"id": 1, "name": "a"}]', "item 0: missing required key 'value'"),
        (
            '[{"id": 1, "name": "a", "value": 1' + "0" * 400 + "}]",
            "item 0: 'value' is too large to convert to a float",
        ),
        ("[" * 100_000, "JSON is nested too deeply"),
    ],
    ids=["empty", "truncated", "object", "missing-key", "huge-int", "deep-nesting"],
)
def test_main_reports_a_malformed_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], content: str, message: str
) -> None:
    path = tmp_path / "r.json"
    path.write_text(content, encoding="utf-8")

    assert main([str(path)]) == 1

    out, err = capsys.readouterr()
    assert out == ""
    assert err == f"datapipe: error: {path}: {message}\n"


def test_main_refuses_to_emit_non_json_numbers(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # 1e308 * 10 overflows to inf, which has no JSON representation.
    path = write_json(tmp_path / "r.json", [{"id": 1, "name": "a", "value": 1e308}])

    assert main([str(path), "--factor", "10"]) == 1

    assert "not JSON compliant" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("factor", "message"),
    [
        ("abc", "invalid float value: 'abc'"),
        ("nan", "must be a finite number, got 'nan'"),
        ("inf", "must be a finite number, got 'inf'"),
        ("-inf", "must be a finite number, got '-inf'"),
        ("1e400", "must be a finite number, got '1e400'"),
    ],
)
def test_main_rejects_a_bad_factor_as_a_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], factor: str, message: str
) -> None:
    # An empty input must not hide a nonsense factor behind a 0 exit status.
    path = write_json(tmp_path / "r.json", [])

    with pytest.raises(SystemExit) as excinfo:
        main([str(path), f"--factor={factor}"])

    assert excinfo.value.code == 2
    out, err = capsys.readouterr()
    assert out == ""
    assert err.endswith(f"datapipe: error: argument --factor: {message}\n")


def test_main_without_arguments_is_a_usage_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main([])

    assert excinfo.value.code == 2
    assert "usage: datapipe" in capsys.readouterr().err


def test_main_handles_a_closed_stdout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class ClosedPipe(io.StringIO):
        def __init__(self, fd: int) -> None:
            super().__init__()
            self.fd = fd

        def write(self, _s: str) -> int:
            raise BrokenPipeError

        def fileno(self) -> int:
            return self.fd

    fd = os.open(tmp_path / "stdout", os.O_WRONLY | os.O_CREAT)
    try:
        monkeypatch.setattr(sys, "stdout", ClosedPipe(fd))
        assert main([str(SAMPLE)]) == 1
    finally:
        os.close(fd)


def test_python_dash_m_entry_point(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["datapipe", str(SAMPLE)])

    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module("datapipe", run_name="__main__")

    assert excinfo.value.code == 0
    assert len(capsys.readouterr().out.splitlines()) == 1000


# ------------------------------------------------- end to end (subproc) ----


def test_sample_file_end_to_end() -> None:
    result = run_cli(str(SAMPLE))

    assert result.returncode == 0
    assert result.stderr == ""
    lines = result.stdout.splitlines()
    assert len(lines) == 1000
    assert lines[0] == '{"id": 1, "name": "cantaloupe", "value": 192.423}'
    for line in lines:
        record = json.loads(line)
        assert record["name"] == record["name"].strip().lower()


def test_installed_console_script() -> None:
    script = Path(sysconfig.get_path("scripts")) / "datapipe"
    if not script.exists():
        pytest.skip("datapipe is not installed as a console script")

    result = subprocess.run(
        [str(script), str(SAMPLE)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0
    assert len(result.stdout.splitlines()) == 1000


def test_validation_error_end_to_end_has_no_traceback(tmp_path: Path) -> None:
    path = write_json(tmp_path / "r.json", [{"id": 9, "name": "", "value": 1.0}])

    result = run_cli(str(path))

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == "datapipe: error: record 9 has an empty name\n"


def test_reader_closing_the_pipe_early_is_not_a_crash(tmp_path: Path) -> None:
    # Far more output than a pipe buffer holds, so the writer is guaranteed
    # to hit the closed pipe.
    records = [{"id": i, "name": "item", "value": 1.0} for i in range(20_000)]
    path = write_json(tmp_path / "big.json", records)

    proc = subprocess.Popen(
        [sys.executable, "-m", "datapipe", str(path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert proc.stdout is not None
    assert proc.stderr is not None
    first = proc.stdout.readline()  # behave like `datapipe big.json | head -n 1`
    proc.stdout.close()
    returncode = proc.wait(timeout=60)
    stderr = proc.stderr.read()
    proc.stderr.close()

    assert json.loads(first)["id"] == 0
    assert "Traceback" not in stderr
    assert stderr == ""
    assert returncode == 1

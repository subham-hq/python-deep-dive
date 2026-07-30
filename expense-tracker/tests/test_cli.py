"""End-to-end tests for `expense_tracker.cli`.

These drive the real entry point with real argument lists against a real
temporary file -- the same path a user takes. `cli.main` returns an exit code
rather than calling `sys.exit`, which is what makes it callable here without
catching `SystemExit`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest import mock

import pytest

from expense_tracker.cli import (
    EXIT_ERROR,
    EXIT_INTERRUPTED,
    EXIT_OK,
    build_parser,
    main,
)
from expense_tracker.main import main as entry_point

from .conftest import make_expense


def run(data_file: Path, *args: str) -> int:
    """Invoke the CLI against `data_file` and return its exit code."""
    return main(["--data", str(data_file), *args])


@pytest.fixture
def seeded(data_file: Path) -> Path:
    """A data file with three expenses across two categories."""
    records = [
        make_expense("Chai", "Food", "20.00", "2026-01-05").to_dict() | {"txn_id": 1},
        make_expense("Diesel", "Fuel", "2500.50", "2026-01-20").to_dict()
        | {"txn_id": 2},
        make_expense("Lunch", "Food", "480.25", "2026-02-11").to_dict() | {"txn_id": 3},
    ]
    data_file.write_text(json.dumps(records, indent=4), encoding="utf-8")
    return data_file


class TestParser:
    def test_requires_a_subcommand(self) -> None:
        with pytest.raises(SystemExit):
            build_parser().parse_args([])

    def test_rejects_an_unknown_subcommand(self) -> None:
        with pytest.raises(SystemExit):
            build_parser().parse_args(["frobnicate"])

    def test_add_requires_category_and_date(self) -> None:
        with pytest.raises(SystemExit):
            build_parser().parse_args(["add", "Chai", "20"])


class TestAdd:
    def test_writes_the_expense_to_disk(self, data_file: Path) -> None:
        code = run(data_file, "add", "Chai", "20.00", "-c", "Food", "-d", "2026-01-05")
        assert code == EXIT_OK
        stored = json.loads(data_file.read_text(encoding="utf-8"))
        assert len(stored) == 1
        assert stored[0]["title"] == "Chai"
        assert stored[0]["amount"] == "20.00"

    def test_reports_the_assigned_id(
        self, data_file: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        run(data_file, "add", "Chai", "20.00", "-c", "Food", "-d", "2026-01-05")
        assert "#1" in capsys.readouterr().out

    def test_continues_ids_from_existing_data(self, seeded: Path) -> None:
        run(seeded, "add", "Books", "300", "-c", "Education", "-d", "2026-03-01")
        stored = json.loads(seeded.read_text(encoding="utf-8"))
        assert stored[-1]["txn_id"] == 4

    def test_optional_description_is_stored(self, data_file: Path) -> None:
        run(
            data_file,
            "add",
            "Diesel",
            "2500",
            "-c",
            "Fuel",
            "-d",
            "2026-01-20",
            "-m",
            "tank refill",
        )
        stored = json.loads(data_file.read_text(encoding="utf-8"))
        assert stored[0]["description"] == "tank refill"

    @pytest.mark.parametrize(
        ("bad_args", "expected_in_stderr"),
        [
            (
                ["add", "Chai", "-5", "-c", "Food", "-d", "2026-01-05"],
                "greater than zero",
            ),
            (["add", "Chai", "abc", "-c", "Food", "-d", "2026-01-05"], "amount"),
            (["add", "Chai", "20", "-c", "Food", "-d", "2026-13-45"], "2026-13-45"),
            (["add", "  ", "20", "-c", "Food", "-d", "2026-01-05"], "title"),
        ],
    )
    def test_invalid_input_exits_one_with_a_readable_message(
        self,
        data_file: Path,
        capsys: pytest.CaptureFixture[str],
        bad_args: list[str],
        expected_in_stderr: str,
    ) -> None:
        assert run(data_file, *bad_args) == EXIT_ERROR
        err = capsys.readouterr().err
        assert expected_in_stderr in err
        # A traceback would mean an unhandled exception reached the user.
        assert "Traceback" not in err

    def test_invalid_input_does_not_create_a_file(self, data_file: Path) -> None:
        run(data_file, "add", "Chai", "-5", "-c", "Food", "-d", "2026-01-05")
        assert not data_file.exists()


class TestList:
    def test_lists_every_expense(
        self, seeded: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert run(seeded, "list") == EXIT_OK
        out = capsys.readouterr().out
        for title in ("Chai", "Diesel", "Lunch"):
            assert title in out

    def test_filters_by_category(
        self, seeded: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        run(seeded, "list", "-c", "Food")
        out = capsys.readouterr().out
        assert "Chai" in out
        assert "Diesel" not in out

    def test_filters_by_month(
        self, seeded: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        run(seeded, "list", "--month", "2026-02")
        out = capsys.readouterr().out
        assert "Lunch" in out
        assert "Chai" not in out

    def test_limit_shows_the_most_recent(
        self, seeded: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        run(seeded, "list", "-n", "1")
        out = capsys.readouterr().out
        assert "Lunch" in out
        assert "Chai" not in out

    def test_empty_file_says_so(
        self, data_file: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert run(data_file, "list") == EXIT_OK
        assert "No matching expenses" in capsys.readouterr().out

    @pytest.mark.parametrize("bad_month", ["2026-13", "not-a-month", "2026"])
    def test_bad_month_exits_one(
        self, seeded: Path, capsys: pytest.CaptureFixture[str], bad_month: str
    ) -> None:
        assert run(seeded, "list", "--month", bad_month) == EXIT_ERROR
        assert "Traceback" not in capsys.readouterr().err

    def test_zero_limit_exits_one(self, seeded: Path) -> None:
        assert run(seeded, "list", "-n", "0") == EXIT_ERROR


class TestShow:
    def test_prints_every_field(
        self, seeded: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert run(seeded, "show", "2") == EXIT_OK
        out = capsys.readouterr().out
        assert "Diesel" in out
        assert "Fuel" in out
        assert "2,500.50" in out

    def test_unknown_id_exits_one(
        self, seeded: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert run(seeded, "show", "9999") == EXIT_ERROR
        assert "9999" in capsys.readouterr().err


class TestRemove:
    def test_deletes_from_disk(self, seeded: Path) -> None:
        assert run(seeded, "remove", "2") == EXIT_OK
        stored = json.loads(seeded.read_text(encoding="utf-8"))
        assert [r["txn_id"] for r in stored] == [1, 3]

    def test_unknown_id_exits_one_and_changes_nothing(self, seeded: Path) -> None:
        before = seeded.read_text(encoding="utf-8")
        assert run(seeded, "remove", "9999") == EXIT_ERROR
        assert seeded.read_text(encoding="utf-8") == before


class TestTotal:
    def test_prints_the_grand_total(
        self, seeded: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert run(seeded, "total") == EXIT_OK
        assert "3,000.75" in capsys.readouterr().out

    def test_category_total(
        self, seeded: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        run(seeded, "total", "-c", "Food")
        assert "500.25" in capsys.readouterr().out


class TestReport:
    @pytest.mark.parametrize("kind", ["summary", "category", "monthly"])
    def test_every_report_renders(
        self, seeded: Path, capsys: pytest.CaptureFixture[str], kind: str
    ) -> None:
        assert run(seeded, "report", kind) == EXIT_OK
        assert capsys.readouterr().out.strip()

    def test_defaults_to_summary(
        self, seeded: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert run(seeded, "report") == EXIT_OK
        assert "Expense Summary" in capsys.readouterr().out

    def test_unknown_report_is_a_usage_error(self, seeded: Path) -> None:
        with pytest.raises(SystemExit) as exc_info:
            run(seeded, "report", "nonexistent")
        assert exc_info.value.code == 2


class TestCategories:
    def test_lists_categories_alphabetically(
        self, seeded: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert run(seeded, "categories") == EXIT_OK
        assert capsys.readouterr().out.split() == ["Food", "Fuel"]

    def test_empty_file_says_so(
        self, data_file: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        run(data_file, "categories")
        assert "No categories yet" in capsys.readouterr().out


class TestCorruptDataHandling:
    def test_reports_the_real_problem_not_a_generic_message(
        self, data_file: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The whole point of the exception-handling rewrite, end to end."""
        record = make_expense().to_dict()
        record["date"] = "2026-13-45"
        data_file.write_text(json.dumps([record]), encoding="utf-8")

        assert run(data_file, "list") == EXIT_ERROR
        err = capsys.readouterr().err
        assert "2026-13-45" in err
        assert "Traceback" not in err

    def test_malformed_json_exits_one(
        self, data_file: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        data_file.write_text("{{{ not json", encoding="utf-8")
        assert run(data_file, "list") == EXIT_ERROR
        assert "Traceback" not in capsys.readouterr().err


class TestFullWorkflow:
    def test_add_list_report_remove(
        self, data_file: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """One realistic session, start to finish."""
        add_chai = ["add", "Chai", "20", "-c", "Food", "-d", "2026-01-05"]
        add_diesel = ["add", "Diesel", "2500", "-c", "Fuel", "-d", "2026-01-20"]
        assert run(data_file, *add_chai) == 0
        assert run(data_file, *add_diesel) == 0
        capsys.readouterr()

        assert run(data_file, "total") == 0
        assert "2,520.00" in capsys.readouterr().out

        assert run(data_file, "remove", "1") == 0
        capsys.readouterr()

        assert run(data_file, "total") == 0
        assert "2,500.00" in capsys.readouterr().out


class TestInterrupt:
    def test_ctrl_c_exits_130_without_a_traceback(
        self, seeded: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Ctrl-C is a normal way to stop a CLI, not a crash."""

        def interrupt(args: object) -> int:
            raise KeyboardInterrupt

        # HANDLERS captures function references at import time, so patching
        # the module attribute would not change the dispatch table.
        with mock.patch.dict("expense_tracker.cli.HANDLERS", {"list": interrupt}):
            assert run(seeded, "list") == EXIT_INTERRUPTED
        err = capsys.readouterr().err
        assert "Interrupted" in err
        assert "Traceback" not in err


class TestEntryPoint:
    def test_main_module_exits_with_the_returned_code(self, seeded: Path) -> None:
        """`main.main` is the console-script shim: it turns cli.main's return
        value into a process exit status and does nothing else.
        """
        with (
            mock.patch.object(
                sys, "argv", ["expense-tracker", "--data", str(seeded), "total"]
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            entry_point()
        assert exc_info.value.code == EXIT_OK

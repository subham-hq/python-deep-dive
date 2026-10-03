"""Tests for `expense_tracker.storage`.

The atomicity and error-propagation tests here are regression tests: each one
reproduces a bug that existed in an earlier version of this code.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from unittest import mock

import pytest

from expense_tracker.exceptions import (
    CorruptRecordError,
    InvalidAmountValueError,
    InvalidDateError,
    LoadError,
    SaveError,
)
from expense_tracker.expense import Expense
from expense_tracker.storage import JSONStorage, MemoryStorage, Storage

from .conftest import make_expense


class TestProtocolConformance:
    """Both implementations satisfy `Storage` without inheriting from it."""

    @pytest.mark.parametrize(
        "storage", [MemoryStorage(), JSONStorage(Path("unused.json"))]
    )
    def test_satisfies_storage_protocol(self, storage: object) -> None:
        assert isinstance(storage, Storage)


class TestLoad:
    def test_missing_file_returns_empty_list(self, data_file: Path) -> None:
        """A first run is not an error."""
        assert JSONStorage(data_file).load() == []

    def test_loads_every_record(self, populated_file: Path) -> None:
        assert len(JSONStorage(populated_file).load()) == 3

    def test_preserves_stored_ids(self, populated_file: Path) -> None:
        """IDs come from the file; loading must not renumber them."""
        loaded = JSONStorage(populated_file).load()
        assert [e.txn_id for e in loaded] == [1, 2, 7]

    def test_accepts_str_path(self, populated_file: Path) -> None:
        """A str path is coerced, not left to fail later on .exists()."""
        loaded = JSONStorage(str(populated_file)).load()  # type: ignore[arg-type]
        assert len(loaded) == 3

    def test_malformed_json_raises_load_error(self, data_file: Path) -> None:
        data_file.write_text("{not json at all", encoding="utf-8")
        with pytest.raises(LoadError):
            JSONStorage(data_file).load()

    def test_top_level_must_be_a_list(self, data_file: Path) -> None:
        data_file.write_text('{"txn_id": 1}', encoding="utf-8")
        with pytest.raises(LoadError):
            JSONStorage(data_file).load()

    def test_missing_field_names_the_field(self, data_file: Path) -> None:
        data_file.write_text(
            json.dumps([{"txn_id": 1, "date": "2026-01-05", "title": "Chai"}]),
            encoding="utf-8",
        )
        with pytest.raises(CorruptRecordError) as exc_info:
            JSONStorage(data_file).load()
        message = str(exc_info.value)
        assert "amount" in message
        assert "category" in message

    def test_corrupt_record_reports_its_position(self, data_file: Path) -> None:
        good = make_expense().to_dict()
        data_file.write_text(json.dumps([good, good, "not a record"]), encoding="utf-8")
        with pytest.raises(CorruptRecordError) as exc_info:
            JSONStorage(data_file).load()
        assert "position 2" in str(exc_info.value)

    def test_non_utf8_file_raises_load_error(self, data_file: Path) -> None:
        """Regression: a UnicodeDecodeError used to escape unwrapped, so the
        message never said which file was the problem.
        """
        data_file.write_bytes(b"\xff\xfe[]")
        with pytest.raises(LoadError) as exc_info:
            JSONStorage(data_file).load()
        assert str(data_file) in str(exc_info.value)
        assert isinstance(exc_info.value.__cause__, UnicodeDecodeError)

    def test_records_without_ids_are_loaded(self, data_file: Path) -> None:
        """`null` is a legal stored ID; the tracker assigns one on load."""
        record = make_expense().to_dict()
        assert record["txn_id"] is None
        data_file.write_text(json.dumps([record]), encoding="utf-8")
        assert [e.txn_id for e in JSONStorage(data_file).load()] == [None]


class TestTxnIdValidation:
    """Regression: `txn_id` was the one field nothing validated. A string ID
    loaded fine and then crashed the tracker inside `max()` with a TypeError.
    """

    @pytest.mark.parametrize("bad_id", ["7", 7.0, True, [7]])
    def test_non_integer_id_is_a_corrupt_record(
        self, data_file: Path, bad_id: object
    ) -> None:
        record = make_expense().to_dict() | {"txn_id": bad_id}
        data_file.write_text(json.dumps([record]), encoding="utf-8")
        with pytest.raises(CorruptRecordError) as exc_info:
            JSONStorage(data_file).load()
        assert "txn_id" in str(exc_info.value)

    def test_duplicate_id_names_both_positions(self, data_file: Path) -> None:
        """Two records sharing an ID would make `remove` delete whichever came
        first and leave the other one still answering to that ID.
        """
        records = [
            make_expense("Chai").to_dict() | {"txn_id": 1},
            make_expense("Tea").to_dict() | {"txn_id": 2},
            make_expense("Coffee").to_dict() | {"txn_id": 1},
        ]
        data_file.write_text(json.dumps(records), encoding="utf-8")
        with pytest.raises(CorruptRecordError) as exc_info:
            JSONStorage(data_file).load()
        message = str(exc_info.value)
        assert "position 2" in message
        assert "position 0" in message

    def test_several_records_without_ids_are_not_duplicates(
        self, data_file: Path
    ) -> None:
        records = [make_expense().to_dict(), make_expense().to_dict()]
        data_file.write_text(json.dumps(records), encoding="utf-8")
        assert len(JSONStorage(data_file).load()) == 2


class TestLoadErrorPropagation:
    """Regression: a bare `except:` used to replace every load failure with a
    generic "could not load JSON file", destroying the real diagnostic and
    swallowing KeyboardInterrupt along with it.
    """

    def test_invalid_date_surfaces_as_invalid_date_error(self, data_file: Path) -> None:
        record = make_expense().to_dict()
        record["date"] = "2026-13-45"
        data_file.write_text(json.dumps([record]), encoding="utf-8")

        with pytest.raises(InvalidDateError) as exc_info:
            JSONStorage(data_file).load()
        # The message names the offending value, not just the filename.
        assert "2026-13-45" in str(exc_info.value)

    def test_validation_error_notes_which_record_failed(self, data_file: Path) -> None:
        """The exception type is unchanged; a note says where it came from."""
        good = make_expense().to_dict() | {"txn_id": 1}
        bad = make_expense().to_dict() | {"txn_id": 2, "date": "2026-13-45"}
        data_file.write_text(json.dumps([good, bad]), encoding="utf-8")

        with pytest.raises(InvalidDateError) as exc_info:
            JSONStorage(data_file).load()
        notes = exc_info.value.__notes__
        assert len(notes) == 1
        assert "position 1" in notes[0]
        assert str(data_file) in notes[0]

    def test_invalid_amount_surfaces_as_invalid_amount_error(
        self, data_file: Path
    ) -> None:
        record = make_expense().to_dict()
        record["amount"] = "-500.00"
        data_file.write_text(json.dumps([record]), encoding="utf-8")

        with pytest.raises(InvalidAmountValueError):
            JSONStorage(data_file).load()

    def test_amount_at_the_limit_is_rejected_on_load(self, data_file: Path) -> None:
        """The amount limit applies to stored records as well as new input,
        and the error says which record to fix.
        """
        record = make_expense().to_dict() | {"amount": "1000000000000000.00"}
        data_file.write_text(json.dumps([record]), encoding="utf-8")

        with pytest.raises(InvalidAmountValueError) as exc_info:
            JSONStorage(data_file).load()
        assert "less than" in str(exc_info.value)
        assert "position 0" in exc_info.value.__notes__[0]

    def test_wrapped_errors_keep_their_cause(self, data_file: Path) -> None:
        """`raise ... from e` means the traceback still shows the real cause."""
        data_file.write_text("{{{", encoding="utf-8")
        with pytest.raises(LoadError) as exc_info:
            JSONStorage(data_file).load()
        assert isinstance(exc_info.value.__cause__, json.JSONDecodeError)

    def test_keyboard_interrupt_is_not_swallowed(self, data_file: Path) -> None:
        """Ctrl-C must never be converted into a domain error."""
        data_file.write_text("[]", encoding="utf-8")
        with (
            mock.patch("json.load", side_effect=KeyboardInterrupt),
            pytest.raises(KeyboardInterrupt),
        ):
            JSONStorage(data_file).load()


class TestSave:
    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        nested = tmp_path / "a" / "b" / "expenses.json"
        JSONStorage(nested).save([make_expense()])
        assert nested.exists()

    def test_round_trips_through_disk(self, data_file: Path) -> None:
        original = [
            make_expense("Chai", "Food", "20.00", "2026-01-05"),
            make_expense("Diesel", "Fuel", "2500.50", "2026-01-20"),
        ]
        storage = JSONStorage(data_file)
        storage.save(original)
        assert storage.load() == original

    @pytest.mark.parametrize("amount", ["999999999999999.99", "999999999999999.994"])
    def test_round_trips_the_largest_allowed_amount(
        self, data_file: Path, amount: str
    ) -> None:
        """Whatever validation lets in, a later load must accept again."""
        storage = JSONStorage(data_file)
        storage.save([make_expense(amount=amount)])
        [loaded] = storage.load()
        assert str(loaded.amount) == "999999999999999.99"

    def test_round_trips_an_expense_dated_with_a_datetime(
        self, data_file: Path
    ) -> None:
        storage = JSONStorage(data_file)
        storage.save([Expense("Chai", "Food", "20", datetime(2026, 1, 5, 9, 30))])
        [loaded] = storage.load()
        assert loaded.date == date(2026, 1, 5)

    def test_save_replaces_rather_than_appends(self, data_file: Path) -> None:
        """Regression: an earlier version appended on every save."""
        storage = JSONStorage(data_file)
        storage.save([make_expense(), make_expense()])
        storage.save([make_expense()])
        assert len(storage.load()) == 1

    def test_writes_valid_json(self, data_file: Path) -> None:
        JSONStorage(data_file).save([make_expense()])
        assert isinstance(json.loads(data_file.read_text(encoding="utf-8")), list)

    def test_leaves_no_temporary_files_behind(self, tmp_path: Path) -> None:
        JSONStorage(tmp_path / "expenses.json").save([make_expense()])
        assert [p.name for p in tmp_path.iterdir()] == ["expenses.json"]


class TestSaveIsAtomic:
    """Regression: `open(path, "w")` truncated the file before writing, so an
    interruption mid-save destroyed the existing data.
    """

    def test_interrupted_save_leaves_the_original_intact(self, data_file: Path) -> None:
        storage = JSONStorage(data_file)
        original = [make_expense("Rent", "Housing", "12000.00", "2026-01-01")]
        storage.save(original)
        before = data_file.read_text(encoding="utf-8")

        def die_halfway(*args: object, **kwargs: object) -> None:
            raise KeyboardInterrupt

        replacement = make_expense("Books", "Education", "300.00", "2026-02-02")
        with (
            mock.patch("json.dump", side_effect=die_halfway),
            pytest.raises(KeyboardInterrupt),
        ):
            storage.save([replacement])

        # The original file is byte-for-byte unchanged, and still loads.
        assert data_file.read_text(encoding="utf-8") == before
        assert storage.load() == original

    def test_failed_save_cleans_up_its_temp_file(self, tmp_path: Path) -> None:
        data_file = tmp_path / "expenses.json"
        storage = JSONStorage(data_file)
        storage.save([make_expense()])

        with (
            mock.patch("json.dump", side_effect=OSError("disk full")),
            pytest.raises(SaveError),
        ):
            storage.save([make_expense()])

        assert [p.name for p in tmp_path.iterdir()] == ["expenses.json"]

    def test_os_error_becomes_save_error_with_cause(self, data_file: Path) -> None:
        storage = JSONStorage(data_file)
        with (
            mock.patch("json.dump", side_effect=OSError("disk full")),
            pytest.raises(SaveError) as exc_info,
        ):
            storage.save([make_expense()])
        assert isinstance(exc_info.value.__cause__, OSError)


class TestSaveSetupFailures:
    """Regression: creating the directory and the temp file happened outside
    the `try`, so failures there escaped as raw OSErrors -- a traceback at
    the CLI instead of a SaveError.
    """

    def test_parent_that_is_a_file_raises_save_error(self, tmp_path: Path) -> None:
        blocker = tmp_path / "not-a-directory"
        blocker.write_text("", encoding="utf-8")
        with pytest.raises(SaveError) as exc_info:
            JSONStorage(blocker / "expenses.json").save([make_expense()])
        assert isinstance(exc_info.value.__cause__, OSError)

    def test_temp_file_failure_raises_save_error_and_keeps_original(
        self, data_file: Path
    ) -> None:
        storage = JSONStorage(data_file)
        storage.save([make_expense()])
        before = data_file.read_text(encoding="utf-8")

        with (
            mock.patch("tempfile.mkstemp", side_effect=PermissionError("read-only")),
            pytest.raises(SaveError) as exc_info,
        ):
            storage.save([make_expense("Other")])

        assert isinstance(exc_info.value.__cause__, PermissionError)
        assert data_file.read_text(encoding="utf-8") == before


class TestMemoryStorage:
    def test_starts_empty(self) -> None:
        assert MemoryStorage().load() == []

    def test_round_trips(self) -> None:
        storage = MemoryStorage()
        expenses = [make_expense()]
        storage.save(expenses)
        assert storage.load() == expenses

    def test_load_returns_a_copy(self) -> None:
        """Mutating the returned list must not corrupt stored state."""
        storage = MemoryStorage([make_expense()])
        storage.load().clear()
        assert len(storage.load()) == 1

    def test_save_copies_the_input(self) -> None:
        storage = MemoryStorage()
        expenses: list[Expense] = [make_expense()]
        storage.save(expenses)
        expenses.clear()
        assert len(storage.load()) == 1


class TestUnreadableFile:
    def test_os_error_becomes_load_error_with_cause(self, data_file: Path) -> None:
        """A file that exists but cannot be opened -- permissions, a bad
        mount, a directory where a file was expected.
        """
        data_file.write_text("[]", encoding="utf-8")
        with (
            mock.patch.object(Path, "open", side_effect=PermissionError("denied")),
            pytest.raises(LoadError) as exc_info,
        ):
            JSONStorage(data_file).load()
        assert isinstance(exc_info.value.__cause__, OSError)

"""Tests for `expense_tracker.storage`.

The atomicity and error-propagation tests here are regression tests: each one
reproduces a bug that existed in an earlier version of this code.
"""

from __future__ import annotations

import json
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

    def test_invalid_amount_surfaces_as_invalid_amount_error(
        self, data_file: Path
    ) -> None:
        record = make_expense().to_dict()
        record["amount"] = "-500.00"
        data_file.write_text(json.dumps([record]), encoding="utf-8")

        with pytest.raises(InvalidAmountValueError):
            JSONStorage(data_file).load()

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

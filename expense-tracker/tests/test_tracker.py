"""Tests for `expense_tracker.tracker`."""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import get_type_hints

import pytest

from expense_tracker.exceptions import ExpenseNotFoundError, InvalidDateError
from expense_tracker.expense import Expense
from expense_tracker.storage import JSONStorage, MemoryStorage
from expense_tracker.tracker import ExpenseTracker

from .conftest import make_expense


class TestAdd:
    def test_assigns_sequential_ids_from_one(
        self, empty_tracker: ExpenseTracker
    ) -> None:
        ids = [empty_tracker.add(make_expense()).txn_id for _ in range(3)]
        assert ids == [1, 2, 3]

    def test_overwrites_any_id_supplied_by_the_caller(
        self, empty_tracker: ExpenseTracker
    ) -> None:
        """The tracker owns IDs. An expense arriving with one does not keep it."""
        expense = make_expense()
        expense.txn_id = 999
        assert empty_tracker.add(expense).txn_id == 1

    def test_returns_the_same_object(self, empty_tracker: ExpenseTracker) -> None:
        expense = make_expense()
        assert empty_tracker.add(expense) is expense

    def test_ids_do_not_repeat_after_a_removal(
        self, empty_tracker: ExpenseTracker
    ) -> None:
        """Reusing a deleted ID would make old references silently wrong."""
        for _ in range(3):
            empty_tracker.add(make_expense())
        empty_tracker.remove(2)
        assert empty_tracker.add(make_expense()).txn_id == 4


class TestRemove:
    def test_removes_the_matching_expense(self, tracker: ExpenseTracker) -> None:
        before = len(tracker)
        tracker.remove(2)
        assert len(tracker) == before - 1
        assert 2 not in tracker

    def test_returns_the_removed_expense(self, tracker: ExpenseTracker) -> None:
        assert tracker.remove(1).title == "Chai"

    def test_unknown_id_raises(self, tracker: ExpenseTracker) -> None:
        with pytest.raises(ExpenseNotFoundError) as exc_info:
            tracker.remove(9999)
        assert "9999" in str(exc_info.value)

    def test_removes_by_identity_not_equality(
        self, empty_tracker: ExpenseTracker
    ) -> None:
        """Two identical expenses must not be confused for one another.

        `list.remove(x)` searches by equality and would delete whichever came
        first; deleting by index removes the one actually asked for.
        """
        first = empty_tracker.add(make_expense())
        second = empty_tracker.add(make_expense())
        # Identical in every field except the ID the tracker assigned.
        assert (first.title, first.amount, first.date) == (
            second.title,
            second.amount,
            second.date,
        )

        empty_tracker.remove(2)
        remaining = empty_tracker.expenses
        assert len(remaining) == 1
        assert remaining[0].txn_id == first.txn_id


class TestQueries:
    def test_total_sums_every_amount(self, tracker: ExpenseTracker) -> None:
        assert tracker.total == Decimal("17000.74")

    def test_total_of_empty_tracker_is_decimal_zero(
        self, empty_tracker: ExpenseTracker
    ) -> None:
        """Without an explicit Decimal start, sum() returns the int 0 here."""
        total = empty_tracker.total
        assert total == Decimal("0.00")
        assert isinstance(total, Decimal)

    def test_get_returns_the_matching_expense(self, tracker: ExpenseTracker) -> None:
        assert tracker.get(2).title == "Diesel"

    def test_get_unknown_id_raises(self, tracker: ExpenseTracker) -> None:
        with pytest.raises(ExpenseNotFoundError):
            tracker.get(9999)

    def test_by_category_is_case_insensitive(self, tracker: ExpenseTracker) -> None:
        assert len(tracker.by_category("food")) == 2
        assert len(tracker.by_category("FOOD")) == 2
        assert len(tracker.by_category("  Food  ")) == 2

    def test_by_category_unknown_returns_empty(self, tracker: ExpenseTracker) -> None:
        assert tracker.by_category("Nonexistent") == []

    def test_by_month(self, tracker: ExpenseTracker) -> None:
        assert len(tracker.by_month(2026, 1)) == 2
        assert len(tracker.by_month(2026, 2)) == 2
        assert len(tracker.by_month(2026, 12)) == 0

    def test_between_is_inclusive(self, tracker: ExpenseTracker) -> None:
        found = tracker.between(date(2026, 1, 5), date(2026, 2, 1))
        assert len(found) == 3

    def test_categories_are_sorted_and_deduplicated(
        self, tracker: ExpenseTracker
    ) -> None:
        assert tracker.categories() == ["Food", "Fuel", "Housing"]

    def test_expenses_property_returns_a_copy(self, tracker: ExpenseTracker) -> None:
        """Otherwise a caller could append and bypass ID assignment."""
        before = len(tracker)
        tracker.expenses.append(make_expense())
        assert len(tracker) == before


class TestCollectionProtocol:
    def test_iterates_in_insertion_order(self, tracker: ExpenseTracker) -> None:
        assert [e.txn_id for e in tracker] == [1, 2, 3, 4, 5]

    def test_iteration_is_independent_per_call(self, tracker: ExpenseTracker) -> None:
        """Two concurrent loops must not share a cursor."""
        pairs = [(a.txn_id, b.txn_id) for a in tracker for b in tracker]
        assert len(pairs) == len(tracker) ** 2

    def test_len(self, tracker: ExpenseTracker) -> None:
        assert len(tracker) == 5

    def test_contains_by_id(self, tracker: ExpenseTracker) -> None:
        assert 1 in tracker
        assert 9999 not in tracker

    def test_contains_non_int_is_false_not_an_error(
        self, tracker: ExpenseTracker
    ) -> None:
        assert "1" not in tracker


class TestPersistence:
    def test_save_then_load_round_trips(self, data_file: Path) -> None:
        storage = JSONStorage(data_file)
        original = ExpenseTracker(storage)
        original.add(make_expense("Chai", "Food", "20.00", "2026-01-05"))
        original.add(make_expense("Diesel", "Fuel", "2500.50", "2026-01-20"))
        original.save()

        reloaded = ExpenseTracker(storage)
        reloaded.load()
        assert reloaded.expenses == original.expenses
        assert reloaded.total == original.total

    def test_load_replaces_rather_than_appends(self, populated_file: Path) -> None:
        """Regression: loading twice used to double the expense list."""
        tracker = ExpenseTracker(JSONStorage(populated_file))
        tracker.load()
        tracker.load()
        tracker.load()
        assert len(tracker) == 3

    def test_load_continues_ids_from_the_highest_stored(
        self, populated_file: Path
    ) -> None:
        """The file's highest ID is 7, so the next assigned ID must be 8."""
        tracker = ExpenseTracker(JSONStorage(populated_file))
        tracker.load()
        assert tracker.add(make_expense()).txn_id == 8

    def test_load_from_empty_file_starts_ids_at_one(self, data_file: Path) -> None:
        data_file.write_text("[]", encoding="utf-8")
        tracker = ExpenseTracker(JSONStorage(data_file))
        tracker.load()
        assert tracker.add(make_expense()).txn_id == 1

    def test_load_errors_propagate_unwrapped(self, data_file: Path) -> None:
        """The tracker must not mask what the storage layer reported."""
        record = make_expense().to_dict()
        record["date"] = "2026-13-45"
        data_file.write_text(json.dumps([record]), encoding="utf-8")

        tracker = ExpenseTracker(JSONStorage(data_file))
        with pytest.raises(InvalidDateError):
            tracker.load()

    def test_save_returns_none(self, empty_tracker: ExpenseTracker) -> None:
        """Presentation belongs to the CLI, not the domain object.

        An earlier version returned "Saved expenses to {path}." -- a domain
        object writing English for a terminal it should know nothing about.
        """
        empty_tracker.save()
        assert get_type_hints(ExpenseTracker.save)["return"] is type(None)

    def test_clear_resets_ids(self, tracker: ExpenseTracker) -> None:
        tracker.clear()
        assert len(tracker) == 0
        assert tracker.add(make_expense()).txn_id == 1


class TestLoadPerformance:
    """Regression: `next_id` was recomputed with `max()` inside the load loop,
    making loading O(n^2). At 4,000 records that cost ~340 ms.

    Asserting on wall-clock time would be flaky on shared CI runners, so this
    counts operations instead: `max` must be called once per load, not once
    per record.
    """

    def test_next_id_is_computed_once_per_load(
        self, data_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        records = [
            make_expense(date="2026-01-05").to_dict() | {"txn_id": i}
            for i in range(1, 501)
        ]
        data_file.write_text(json.dumps(records), encoding="utf-8")

        calls = 0
        real_max = max

        def counting_max(ids: Iterable[int], *, default: int = 0) -> int:
            nonlocal calls
            calls += 1
            return real_max(ids, default=default)

        # The tracker's module globals are searched before builtins, so
        # binding `max` there shadows the builtin for that module only.
        monkeypatch.setattr("expense_tracker.tracker.max", counting_max, raising=False)

        tracker = ExpenseTracker(JSONStorage(data_file))
        tracker.load()

        assert len(tracker) == 500
        assert calls == 1, f"max() called {calls} times for 500 records; expected 1"

    def test_scales_linearly(self, tmp_path: Path) -> None:
        """A sanity check that 4x the data does not cost ~16x the work."""
        import time

        def time_load(n: int) -> float:
            path = tmp_path / f"{n}.json"
            records = [
                make_expense(date="2026-01-05").to_dict() | {"txn_id": i}
                for i in range(1, n + 1)
            ]
            path.write_text(json.dumps(records), encoding="utf-8")
            tracker = ExpenseTracker(JSONStorage(path))
            start = time.perf_counter()
            tracker.load()
            return time.perf_counter() - start

        small = time_load(500)
        large = time_load(2000)
        # Quadratic growth would be ~16x. Allow generous headroom for noise.
        assert large < small * 8, f"4x data took {large / small:.1f}x the time"


class TestStorageInjection:
    def test_works_with_memory_storage(self) -> None:
        """The tracker never names a concrete storage class."""
        storage = MemoryStorage()
        tracker = ExpenseTracker(storage)
        tracker.add(make_expense())
        tracker.save()

        other = ExpenseTracker(storage)
        other.load()
        assert len(other) == 1

    def test_accepts_any_conforming_object(self) -> None:
        """Structural typing: no inheritance required."""

        class ListStorage:
            def __init__(self) -> None:
                self.items: list[Expense] = []

            def load(self) -> list[Expense]:
                return list(self.items)

            def save(self, expenses: list[Expense]) -> None:
                self.items = list(expenses)

        tracker = ExpenseTracker(ListStorage())
        tracker.add(make_expense())
        tracker.save()
        assert len(tracker) == 1

"""Shared fixtures.

pytest discovers this file automatically -- test modules use these fixtures
by naming them as parameters, with no import required.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from expense_tracker.expense import Expense, ExpenseRecord
from expense_tracker.storage import JSONStorage, MemoryStorage
from expense_tracker.tracker import ExpenseTracker


def make_expense(
    title: str = "Chai",
    category: str = "Food",
    amount: str = "20.00",
    date: str = "2026-01-05",
    description: str = "",
) -> Expense:
    """Build an `Expense` with sensible defaults.

    A factory rather than a fixture: a test that needs three different
    expenses would otherwise need three fixtures.
    """
    return Expense(
        title=title,
        category=category,
        amount=amount,
        date=date,
        description=description,
    )


@pytest.fixture
def expense() -> Expense:
    """A single valid expense."""
    return make_expense()


@pytest.fixture
def expenses() -> list[Expense]:
    """A small, deliberately varied set spanning categories and months."""
    return [
        make_expense("Chai", "Food", "20.00", "2026-01-05"),
        make_expense("Diesel", "Fuel", "2500.50", "2026-01-20"),
        make_expense("Lunch", "Food", "480.25", "2026-02-11"),
        make_expense("Rent", "Housing", "12000.00", "2026-02-01"),
        make_expense("Petrol", "Fuel", "1999.99", "2026-03-03"),
    ]


@pytest.fixture
def tracker(expenses: list[Expense]) -> ExpenseTracker:
    """A tracker holding `expenses`, backed by memory rather than disk."""
    tracker = ExpenseTracker(MemoryStorage())
    for expense in expenses:
        tracker.add(expense)
    return tracker


@pytest.fixture
def empty_tracker() -> ExpenseTracker:
    """A tracker with no expenses."""
    return ExpenseTracker(MemoryStorage())


@pytest.fixture
def data_file(tmp_path: Path) -> Path:
    """A path inside pytest's per-test temporary directory.

    `tmp_path` is created fresh for every test and cleaned up afterwards, so
    tests never share state through the filesystem.
    """
    return tmp_path / "expenses.json"


@pytest.fixture
def json_storage(data_file: Path) -> JSONStorage:
    """A `JSONStorage` pointing at a throwaway file."""
    return JSONStorage(data_file)


@pytest.fixture
def populated_file(data_file: Path) -> Path:
    """A data file containing three valid records."""
    records: list[ExpenseRecord] = [
        {
            "txn_id": 1,
            "date": "2026-01-05",
            "title": "Chai",
            "category": "Food",
            "amount": "20.00",
            "description": "",
        },
        {
            "txn_id": 2,
            "date": "2026-01-20",
            "title": "Diesel",
            "category": "Fuel",
            "amount": "2500.50",
            "description": "tank refill",
        },
        {
            "txn_id": 7,
            "date": "2026-02-01",
            "title": "Rent",
            "category": "Housing",
            "amount": "12000.00",
            "description": "",
        },
    ]
    data_file.write_text(json.dumps(records, indent=4), encoding="utf-8")
    return data_file


@pytest.fixture
def money() -> Decimal:
    """A representative amount, as a `Decimal`."""
    return Decimal("1234.56")

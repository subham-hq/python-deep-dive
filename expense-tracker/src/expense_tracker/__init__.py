"""A command-line expense tracker.

The public API is re-exported here so callers can write
``from expense_tracker import Expense, ExpenseTracker`` rather than reaching
into submodules.
"""

from __future__ import annotations

from expense_tracker.exceptions import (
    CorruptRecordError,
    ExpenseError,
    ExpenseNotFoundError,
    InvalidAmountTypeError,
    InvalidAmountValueError,
    InvalidDateError,
    InvalidTextFieldError,
    LoadError,
    SaveError,
    StorageError,
)
from expense_tracker.expense import Expense, ExpenseRecord
from expense_tracker.reports import (
    CategoryBreakdownReport,
    MonthlyReport,
    Report,
    SummaryReport,
    get_report,
)
from expense_tracker.storage import JSONStorage, MemoryStorage, Storage
from expense_tracker.tracker import ExpenseTracker

__version__ = "1.0.0"

__all__ = [
    "CategoryBreakdownReport",
    "CorruptRecordError",
    "Expense",
    "ExpenseError",
    "ExpenseNotFoundError",
    "ExpenseRecord",
    "ExpenseTracker",
    "InvalidAmountTypeError",
    "InvalidAmountValueError",
    "InvalidDateError",
    "InvalidTextFieldError",
    "JSONStorage",
    "LoadError",
    "MemoryStorage",
    "MonthlyReport",
    "Report",
    "SaveError",
    "Storage",
    "StorageError",
    "SummaryReport",
    "__version__",
    "get_report",
]

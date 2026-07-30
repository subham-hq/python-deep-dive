"""Exception hierarchy for the expense tracker.

Every error raised by this package inherits from `ExpenseError`, so a caller
can catch the whole domain with one `except` and still narrow to a specific
failure when it needs to.

The rule this package follows: a low-level failure is wrapped in a domain
exception with `raise ... from e`, so the original cause stays attached to
the traceback. A domain exception is never wrapped in another one -- if
`InvalidDateError` is raised while loading a file, that is the error the
caller sees, not a generic "could not load".
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path


class ExpenseError(Exception):
    """Base exception for the expense tracker."""


# --------------------------------------------------------------------------
# Validation errors -- raised by Expense when a field fails its invariant.
# --------------------------------------------------------------------------


class InvalidAmountTypeError(ExpenseError):
    """Raised when an expense amount is of an unsupported type."""

    def __init__(self, amount: object) -> None:
        self.amount = amount
        super().__init__(
            f"Invalid amount type: {type(amount).__name__!r} ({amount!r}). "
            f"Amount must be a Decimal, int, or numeric string."
        )


class InvalidAmountValueError(ExpenseError):
    """Raised when an expense amount is not a positive value."""

    def __init__(self, amount: Decimal | int | str) -> None:
        self.amount = amount
        super().__init__(f"Invalid amount: {amount}. Amount must be greater than zero.")


class InvalidDateError(ExpenseError):
    """Raised when an expense date is not a valid ISO (YYYY-MM-DD) date."""

    def __init__(self, date: object) -> None:
        self.date = date
        super().__init__(
            f"Invalid date: {date!r}. Date must be a real calendar date "
            f"in YYYY-MM-DD format."
        )


class InvalidTextFieldError(ExpenseError):
    """Raised when a required text field (title, category) is blank."""

    def __init__(self, field: str) -> None:
        self.field = field
        super().__init__(f"Invalid {field}: must be a non-empty string.")


# --------------------------------------------------------------------------
# Storage errors -- raised by the storage layer.
# --------------------------------------------------------------------------


class StorageError(ExpenseError):
    """Base class for failures in the storage layer."""


class LoadError(StorageError):
    """Raised when stored data cannot be read or parsed."""

    def __init__(self, path: Path, reason: str = "") -> None:
        self.path = path
        detail = f": {reason}" if reason else ""
        super().__init__(f"Could not load expenses from {path}{detail}")


class SaveError(StorageError):
    """Raised when expenses cannot be written to disk."""

    def __init__(self, path: Path, reason: str = "") -> None:
        self.path = path
        detail = f": {reason}" if reason else ""
        super().__init__(f"Could not save expenses to {path}{detail}")


class CorruptRecordError(StorageError):
    """Raised when a stored record is missing fields or has the wrong shape.

    This is distinct from `LoadError`: the file was readable and the JSON
    parsed fine, but a record inside it does not describe an expense.
    """

    def __init__(self, index: int, reason: str) -> None:
        self.index = index
        super().__init__(f"Record at position {index} is invalid: {reason}")


# --------------------------------------------------------------------------
# Tracker errors.
# --------------------------------------------------------------------------


class ExpenseNotFoundError(ExpenseError):
    """Raised when no expense exists with the requested transaction ID."""

    def __init__(self, txn_id: int) -> None:
        self.txn_id = txn_id
        super().__init__(f"No expense found with transaction ID {txn_id}.")

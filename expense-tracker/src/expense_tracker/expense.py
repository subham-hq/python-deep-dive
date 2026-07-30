"""The `Expense` domain model.

Design notes
------------
* **Money is `Decimal`, never `float`.** `0.1 + 0.2` is not `0.3` in binary
  floating point, and that error compounds across a ledger. Amounts are
  normalised to exactly two decimal places using `ROUND_HALF_UP`, which is
  what people expect from currency rounding (Python's default is banker's
  rounding, which rounds 2.5 to 2).

* **`float` is rejected outright.** Accepting it would silently reintroduce
  the precision problem the `Decimal` choice exists to avoid. Pass a
  `Decimal`, an `int`, or a numeric string instead.

* **Dates are `datetime.date` objects in memory, ISO strings on disk.**
  Storing them as strings would make sorting and month filtering into string
  manipulation. The JSON representation is unchanged, so existing data files
  load without migration.

* **Validation lives in property setters,** so an `Expense` cannot exist in
  an invalid state -- not after construction, and not after later mutation.
"""

from __future__ import annotations

import datetime as dt
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import TypedDict

from expense_tracker.exceptions import (
    InvalidAmountTypeError,
    InvalidAmountValueError,
    InvalidDateError,
    InvalidTextFieldError,
)

#: Every amount is quantised to this many decimal places.
CENTS = Decimal("0.01")

#: Types accepted where a money value is expected. `float` is deliberately
#: absent -- see the module docstring.
MoneyLike = Decimal | int | str

#: Types accepted where a date is expected.
DateLike = dt.date | str


class ExpenseRecord(TypedDict):
    """The JSON shape of a stored expense.

    This is the on-disk contract. Changing it is a data migration, so it is
    declared explicitly rather than left implicit in `to_dict`.
    """

    txn_id: int | None
    date: str
    title: str
    category: str
    amount: str
    description: str


def to_money(value: MoneyLike) -> Decimal:
    """Normalise `value` to a two-decimal-place `Decimal`.

    Raises:
        InvalidAmountTypeError: if `value` is not a supported type, or is a
            string that does not parse as a number.
    """
    # bool is a subclass of int, so `isinstance(True, int)` is True. Catch it
    # explicitly -- True would otherwise become an amount of 1.00.
    if isinstance(value, bool) or not isinstance(value, (Decimal, int, str)):
        raise InvalidAmountTypeError(value)

    try:
        amount = Decimal(value)
    except (InvalidOperation, ValueError) as e:
        raise InvalidAmountTypeError(value) from e

    if not amount.is_finite():
        # Decimal("NaN") and Decimal("Infinity") parse successfully but are
        # not usable as money.
        raise InvalidAmountTypeError(value)

    return amount.quantize(CENTS, rounding=ROUND_HALF_UP)


def to_date(value: DateLike) -> dt.date:
    """Normalise `value` to a `datetime.date`.

    Raises:
        InvalidDateError: if `value` is not a date or a valid ISO date string.
    """
    if isinstance(value, dt.date):
        return value

    if not isinstance(value, str):
        raise InvalidDateError(value)

    try:
        # strptime rejects impossible dates like 2026-02-30, which a manual
        # split-and-int-parse would happily accept.
        return dt.datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as e:
        raise InvalidDateError(value) from e


class Expense:
    """A single expense entry.

    `txn_id` is `None` until the expense is added to an `ExpenseTracker`.
    The tracker owns ID assignment; the expense just carries the value.
    """

    __slots__ = ("_amount", "_category", "_date", "_description", "_title", "txn_id")

    def __init__(
        self,
        title: str,
        category: str,
        amount: MoneyLike,
        date: DateLike,
        description: str = "",
        txn_id: int | None = None,
    ) -> None:
        # Assigning through the properties means construction runs the same
        # validation as any later mutation -- there is no way to build an
        # invalid Expense by going through __init__.
        self.txn_id = txn_id
        self.title = title
        self.category = category
        self.amount = amount
        self.date = date
        self.description = description

    # -- title ------------------------------------------------------------

    @property
    def title(self) -> str:
        return self._title

    @title.setter
    def title(self, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise InvalidTextFieldError("title")
        self._title = value.strip()

    # -- category ---------------------------------------------------------

    @property
    def category(self) -> str:
        return self._category

    @category.setter
    def category(self, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise InvalidTextFieldError("category")
        self._category = value.strip()

    # -- description ------------------------------------------------------

    @property
    def description(self) -> str:
        return self._description

    @description.setter
    def description(self, value: str) -> None:
        # Unlike title and category, an empty description is meaningful.
        if not isinstance(value, str):
            raise InvalidTextFieldError("description")
        self._description = value.strip()

    # -- amount -----------------------------------------------------------

    @property
    def amount(self) -> Decimal:
        return self._amount

    @amount.setter
    def amount(self, value: MoneyLike) -> None:
        amount = to_money(value)
        if amount <= 0:
            raise InvalidAmountValueError(value)
        self._amount = amount

    # -- date -------------------------------------------------------------

    @property
    def date(self) -> dt.date:
        return self._date

    @date.setter
    def date(self, value: DateLike) -> None:
        self._date = to_date(value)

    # -- serialisation ----------------------------------------------------

    def to_dict(self) -> ExpenseRecord:
        """Return the JSON-serialisable form of this expense."""
        return {
            "txn_id": self.txn_id,
            "date": self.date.isoformat(),
            "title": self.title,
            "category": self.category,
            # str() rather than float() -- a float here would undo the whole
            # point of storing money as Decimal.
            "amount": str(self.amount),
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: ExpenseRecord) -> Expense:
        """Rebuild an expense from its stored form.

        Raises the same validation errors as the constructor, so corrupt
        stored data is caught at load time rather than surfacing later.
        """
        return cls(
            txn_id=data["txn_id"],
            title=data["title"],
            category=data["category"],
            amount=data["amount"],
            date=data["date"],
            description=data["description"],
        )

    # -- dunders ----------------------------------------------------------

    def __str__(self) -> str:
        txn = "--" if self.txn_id is None else str(self.txn_id)
        return (
            f"{txn} | {self.date.isoformat()} | {self.title} | "
            f"{self.category} | \u20b9{self.amount:,.2f}"
        )

    def __repr__(self) -> str:
        return (
            f"Expense(txn_id={self.txn_id!r}, title={self.title!r}, "
            f"category={self.category!r}, amount={self.amount!r}, "
            f"date={self.date!r}, description={self.description!r})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Expense):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __hash__(self) -> int:
        return hash(tuple(sorted(self.to_dict().items())))

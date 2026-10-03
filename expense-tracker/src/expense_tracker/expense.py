"""The `Expense` domain model.

Design notes
------------
* **Money is `Decimal`, never `float`.** `0.1 + 0.2` is not `0.3` in binary
  floating point, and that error compounds across a ledger. Amounts are
  normalised to exactly two decimal places using `ROUND_HALF_UP`, which is
  what people expect from currency rounding (Python's default is banker's
  rounding, which rounds 2.5 to 2). Amounts must be below `MAX_AMOUNT` so
  that totals stay inside the range where `Decimal` arithmetic is exact.

* **`float` is rejected outright.** Accepting it would silently reintroduce
  the precision problem the `Decimal` choice exists to avoid. Pass a
  `Decimal`, an `int`, or a numeric string instead.

* **Dates are `datetime.date` objects in memory, ISO strings on disk.**
  Storing them as strings would make sorting and month filtering into string
  manipulation. The JSON representation of a date is unchanged, so stored
  dates need no migration.

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

#: Amounts must be smaller than this. Decimal arithmetic is exact only while
#: results fit in the context's 28 significant digits; keeping each amount
#: below 10**15 leaves room for any realistic total to stay exact. Without a
#: bound, "1e30" makes `quantize` raise `InvalidOperation`.
MAX_AMOUNT = Decimal(10**15)

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
        InvalidAmountValueError: if `value`, once rounded to two places, is
            not smaller than `MAX_AMOUNT` in magnitude.
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

    too_large = f"Amount must be less than {MAX_AMOUNT:,}."

    if amount.copy_abs() >= MAX_AMOUNT:
        # Checked before quantize(), which raises InvalidOperation once the
        # result needs more digits than the decimal context provides.
        raise InvalidAmountValueError(value, too_large)

    rounded = amount.quantize(CENTS, rounding=ROUND_HALF_UP)

    if rounded.copy_abs() >= MAX_AMOUNT:
        # And checked again after it: 999999999999999.995 is below the limit
        # but rounds up to it. Accepting that value would save a record that
        # the next load rejects, leaving the file unusable from the CLI.
        raise InvalidAmountValueError(value, too_large)

    return rounded


def to_date(value: DateLike) -> dt.date:
    """Normalise `value` to a `datetime.date`.

    A `datetime` is accepted and reduced to its date.

    Raises:
        InvalidDateError: if `value` is not a date or a valid ISO date string.
    """
    if isinstance(value, dt.datetime):
        # datetime subclasses date, so it would pass the check below as-is.
        # Kept whole, it would be saved as "2026-01-05T09:30:00", which the
        # next load rejects, and comparing it with a date raises TypeError.
        return value.date()

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

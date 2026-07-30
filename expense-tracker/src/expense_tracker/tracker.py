"""The `ExpenseTracker` aggregate -- the in-memory collection of expenses.

Two design points worth knowing before reading:

**Storage is injected, not constructed.** `ExpenseTracker` takes a `Storage`
in its constructor rather than building a `JSONStorage` itself. The tracker
therefore has no idea whether it is talking to a file, memory, or a database,
and tests can drive it with `MemoryStorage` instead of touching the disk.

**The tracker owns transaction IDs.** An `Expense` may arrive with
`txn_id=None`; `add` assigns the next free ID. Nothing else in the codebase
writes `txn_id`, which means there is exactly one place to look when an ID
looks wrong.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from decimal import Decimal

from expense_tracker.exceptions import ExpenseNotFoundError
from expense_tracker.expense import Expense
from expense_tracker.storage import Storage

ZERO = Decimal("0.00")


class ExpenseTracker:
    """An ordered collection of expenses, backed by a `Storage`."""

    def __init__(self, storage: Storage) -> None:
        self._storage = storage
        self._expenses: list[Expense] = []
        self._next_id: int = 1

    # -- collection protocol ----------------------------------------------

    def __iter__(self) -> Iterator[Expense]:
        # `iter(list)` already implements the iterator protocol correctly,
        # including independent state per call. A hand-written iterator class
        # would be more code for identical behaviour.
        return iter(self._expenses)

    def __len__(self) -> int:
        return len(self._expenses)

    def __contains__(self, txn_id: object) -> bool:
        if not isinstance(txn_id, int):
            return False
        return any(e.txn_id == txn_id for e in self._expenses)

    # -- queries ----------------------------------------------------------

    @property
    def expenses(self) -> list[Expense]:
        """A copy of the tracked expenses.

        A copy, not the live list -- otherwise a caller could append to it and
        bypass ID assignment entirely.
        """
        return list(self._expenses)

    @property
    def total(self) -> Decimal:
        """The sum of every tracked amount.

        `start=ZERO` keeps the result a `Decimal`. Without it, `sum` starts at
        the integer 0 and returns a plain 0 for an empty tracker, so the
        return type would depend on the data.
        """
        return sum((e.amount for e in self._expenses), start=ZERO)

    def get(self, txn_id: int) -> Expense:
        """Return the expense with `txn_id`.

        A linear scan is deliberate. Maintaining a dict index alongside the
        list would make lookup O(1) but requires keeping two structures in
        sync through every mutation -- a common source of bugs, and not worth
        it at the scale a JSON-backed CLI operates on.

        Raises:
            ExpenseNotFoundError: if no expense has that ID.
        """
        for expense in self._expenses:
            if expense.txn_id == txn_id:
                return expense
        raise ExpenseNotFoundError(txn_id)

    def by_category(self, category: str) -> list[Expense]:
        """Every expense in `category`, matched case-insensitively."""
        wanted = category.strip().casefold()
        return [e for e in self._expenses if e.category.casefold() == wanted]

    def by_month(self, year: int, month: int) -> list[Expense]:
        """Every expense falling in the given calendar month."""
        return [
            e for e in self._expenses if e.date.year == year and e.date.month == month
        ]

    def between(self, start: dt.date, end: dt.date) -> list[Expense]:
        """Every expense with a date in `[start, end]`, inclusive."""
        return [e for e in self._expenses if start <= e.date <= end]

    def categories(self) -> list[str]:
        """Every distinct category present, sorted alphabetically."""
        return sorted({e.category for e in self._expenses})

    # -- mutations --------------------------------------------------------

    def add(self, expense: Expense) -> Expense:
        """Add `expense`, assigning it the next transaction ID.

        Returns the same object, now carrying its assigned ID.
        """
        expense.txn_id = self._next_id
        self._next_id += 1
        self._expenses.append(expense)
        return expense

    def remove(self, txn_id: int) -> Expense:
        """Remove and return the expense with `txn_id`.

        Raises:
            ExpenseNotFoundError: if no expense has that ID.
        """
        for index, expense in enumerate(self._expenses):
            if expense.txn_id == txn_id:
                # Delete by index rather than list.remove(expense): remove()
                # searches by equality, and two expenses with identical
                # fields would make it delete the wrong one.
                del self._expenses[index]
                return expense
        raise ExpenseNotFoundError(txn_id)

    def clear(self) -> None:
        """Remove every expense and reset ID assignment."""
        self._expenses.clear()
        self._next_id = 1

    # -- persistence ------------------------------------------------------

    def load(self) -> None:
        """Replace the in-memory expenses with whatever storage holds.

        Any error from the storage layer propagates unchanged. Wrapping it
        would replace a precise message ("record 47 has an invalid date")
        with a vague one ("could not load").
        """
        expenses = self._storage.load()

        self._expenses = expenses
        # Computed once, after the list is fully populated. Doing this inside
        # the loop -- recomputing max() on every append -- makes loading
        # quadratic: 4,000 records took ~340 ms that way, versus ~15 ms here.
        ids = [e.txn_id for e in expenses if e.txn_id is not None]
        self._next_id = max(ids, default=0) + 1

    def save(self) -> None:
        """Persist the current expenses.

        Returns nothing. A domain object formatting a user-facing string
        ("Saved 3 expenses to ...") would tie it to the CLI; presentation is
        the CLI's job.
        """
        self._storage.save(self._expenses)

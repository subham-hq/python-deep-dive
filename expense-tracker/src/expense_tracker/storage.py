"""Persistence for expenses.

The tracker depends on the `Storage` protocol, not on `JSONStorage`. That
inversion is what makes the tracker testable without touching the disk:
tests inject `MemoryStorage` and run in microseconds.

`JSONStorage.save` is **atomic**. Writing straight into the target file with
mode `"w"` truncates it before the new bytes arrive, so an interruption at
the wrong moment (Ctrl-C, power loss, a full disk, an exception raised while
serialising) destroys the previous contents and leaves nothing usable behind.
Writing to a temporary file and then calling `os.replace` means the target is
only ever swapped for a complete file: `os.replace` is atomic on POSIX and on
Windows, so a reader sees either the whole old file or the whole new one.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from expense_tracker.exceptions import CorruptRecordError, LoadError, SaveError
from expense_tracker.expense import Expense, ExpenseRecord

#: Every key an `ExpenseRecord` must contain to be considered well-formed.
REQUIRED_FIELDS = frozenset(ExpenseRecord.__annotations__)


@runtime_checkable
class Storage(Protocol):
    """Anything that can persist and retrieve a list of expenses.

    Structural typing: a class satisfies this by having matching methods, and
    does not need to inherit from anything. Adding a `SQLiteStorage` or a
    `CSVStorage` later requires no change to `ExpenseTracker`.
    """

    def load(self) -> list[Expense]:
        """Return every stored expense, or an empty list if none exist."""
        ...

    def save(self, expenses: list[Expense]) -> None:
        """Persist `expenses`, replacing anything previously stored."""
        ...


def _validate_record(raw: Any, index: int) -> ExpenseRecord:
    """Check that `raw` has the shape of an `ExpenseRecord`.

    `json.load` returns `Any`, which mypy will happily let flow anywhere. This
    function is the boundary where untyped external data becomes typed
    internal data, so the `Any` stops here instead of leaking through the
    codebase.
    """
    if not isinstance(raw, dict):
        raise CorruptRecordError(index, f"expected an object, got {type(raw).__name__}")

    missing = REQUIRED_FIELDS - raw.keys()
    if missing:
        raise CorruptRecordError(
            index, f"missing field(s): {', '.join(sorted(missing))}"
        )

    return {
        "txn_id": raw["txn_id"],
        "date": raw["date"],
        "title": raw["title"],
        "category": raw["category"],
        "amount": raw["amount"],
        "description": raw["description"],
    }


class JSONStorage:
    """Stores expenses as a JSON array in a single file."""

    def __init__(self, path: Path) -> None:
        # Coerce rather than merely annotate: a caller passing a str would
        # otherwise fail later with an opaque AttributeError on .exists().
        self.path = Path(path)

    def load(self) -> list[Expense]:
        """Read every expense from disk.

        Returns an empty list if the file does not exist -- a first run is not
        an error.

        Raises:
            LoadError: if the file cannot be read or is not valid JSON.
            CorruptRecordError: if a record has the wrong shape.
            InvalidAmountValueError, InvalidDateError, ...: if a record's
                values fail validation. These propagate unwrapped, so the
                caller learns what is actually wrong with the data.
        """
        if not self.path.exists():
            return []

        try:
            with self.path.open("r", encoding="utf-8") as file:
                raw_data = json.load(file)
        except OSError as e:
            raise LoadError(self.path, str(e)) from e
        except json.JSONDecodeError as e:
            raise LoadError(self.path, f"invalid JSON at line {e.lineno}") from e

        if not isinstance(raw_data, list):
            raise LoadError(
                self.path, f"expected a list of records, got {type(raw_data).__name__}"
            )

        # Note what is *not* wrapped here: Expense.from_dict raises
        # InvalidDateError, InvalidAmountValueError and friends, and those are
        # allowed straight through. Catching them and re-raising a generic
        # LoadError would tell the user "could not load the file" when the
        # real answer is "record 47 has the date 2026-13-45".
        return [
            Expense.from_dict(_validate_record(raw, i))
            for i, raw in enumerate(raw_data)
        ]

    def save(self, expenses: list[Expense]) -> None:
        """Write `expenses` to disk atomically.

        Raises:
            SaveError: if the data cannot be serialised or written.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = [expense.to_dict() for expense in expenses]

        # The temporary file must live in the same directory as the target:
        # os.replace is only atomic within a single filesystem, and /tmp is
        # often mounted separately.
        tmp_fd, tmp_name = tempfile.mkstemp(
            dir=self.path.parent, prefix=f".{self.path.name}.", suffix=".tmp"
        )
        tmp_path = Path(tmp_name)

        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as file:
                json.dump(data, file, indent=4)
                file.flush()
                # Push the bytes past the OS write cache. Without this,
                # os.replace can complete while the new file's contents are
                # still only in memory -- a crash then leaves an empty file
                # where the data used to be.
                os.fsync(file.fileno())
            tmp_path.replace(self.path)
        except (OSError, TypeError, ValueError) as e:
            # The original file is untouched: the failure happened before the
            # replace, so there is nothing to roll back except the temp file.
            tmp_path.unlink(missing_ok=True)
            raise SaveError(self.path, str(e)) from e
        except BaseException:
            # KeyboardInterrupt and SystemExit are not Exceptions. Clean up
            # the temp file, then let them propagate untouched -- swallowing
            # Ctrl-C is never correct.
            tmp_path.unlink(missing_ok=True)
            raise


class MemoryStorage:
    """In-memory `Storage` implementation, for tests and dry runs.

    Satisfies the `Storage` protocol without inheriting from it.
    """

    def __init__(self, expenses: list[Expense] | None = None) -> None:
        self._expenses: list[Expense] = list(expenses or [])

    def load(self) -> list[Expense]:
        # Return a copy so callers mutating the result cannot corrupt the
        # stored state behind our back.
        return list(self._expenses)

    def save(self, expenses: list[Expense]) -> None:
        self._expenses = list(expenses)

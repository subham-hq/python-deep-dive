"""Command-line interface.

This is the only layer that prints. The domain layer returns data and raises
exceptions; turning either into text a person reads happens here and nowhere
else. That separation is what lets the tracker and reports be tested without
capturing stdout.

Exit codes follow the usual shell convention:

===== ==========================================================
Code  Meaning
===== ==========================================================
0     Success
1     A domain error (bad input, missing record, unreadable file)
2     Wrong command-line usage (argparse's own exit code)
130   Interrupted with Ctrl-C
===== ==========================================================
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from expense_tracker.exceptions import ExpenseError
from expense_tracker.expense import Expense
from expense_tracker.reports import REPORTS, format_money, get_report, total_of
from expense_tracker.storage import JSONStorage
from expense_tracker.tracker import ExpenseTracker

DEFAULT_DATA_PATH = Path.home() / ".expense-tracker" / "expenses.json"

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_INTERRUPTED = 130


def build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser.

    Separate from `main` so tests can inspect parsing behaviour without
    running any commands.
    """
    parser = argparse.ArgumentParser(
        prog="expense-tracker",
        description="Track personal expenses from the command line.",
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=DEFAULT_DATA_PATH,
        metavar="PATH",
        help=f"path to the expense data file (default: {DEFAULT_DATA_PATH})",
    )

    subcommands = parser.add_subparsers(dest="command", required=True)

    # -- add --------------------------------------------------------------
    add = subcommands.add_parser("add", help="record a new expense")
    add.add_argument("title", help="what the expense was, e.g. 'Diesel'")
    add.add_argument("amount", help="amount in rupees, e.g. 249.50")
    add.add_argument("-c", "--category", required=True, help="e.g. 'Fuel'")
    add.add_argument(
        "-d",
        "--date",
        required=True,
        metavar="YYYY-MM-DD",
        help="date the expense occurred",
    )
    add.add_argument("-m", "--description", default="", help="optional note")

    # -- list -------------------------------------------------------------
    listing = subcommands.add_parser("list", help="list recorded expenses")
    listing.add_argument("-c", "--category", help="show only this category")
    listing.add_argument(
        "--month",
        metavar="YYYY-MM",
        help="show only expenses in this calendar month",
    )
    listing.add_argument(
        "-n", "--limit", type=int, help="show at most this many expenses"
    )

    # -- show -------------------------------------------------------------
    show = subcommands.add_parser("show", help="show one expense in full")
    show.add_argument("txn_id", type=int, help="transaction ID")

    # -- remove -----------------------------------------------------------
    remove = subcommands.add_parser("remove", help="delete an expense")
    remove.add_argument("txn_id", type=int, help="transaction ID")

    # -- total ------------------------------------------------------------
    total = subcommands.add_parser("total", help="print the total spend")
    total.add_argument("-c", "--category", help="total for this category only")

    # -- report -----------------------------------------------------------
    report = subcommands.add_parser("report", help="print a summary report")
    report.add_argument(
        "kind",
        choices=sorted(REPORTS),
        nargs="?",
        default="summary",
        help="which report to render (default: summary)",
    )

    # -- categories -------------------------------------------------------
    subcommands.add_parser("categories", help="list the categories in use")

    return parser


def _parse_month(value: str) -> tuple[int, int]:
    """Parse a ``YYYY-MM`` string into a ``(year, month)`` pair."""
    try:
        year_text, month_text = value.split("-")
        year, month = int(year_text), int(month_text)
    except ValueError as e:
        raise ValueError(f"Invalid month {value!r}: expected YYYY-MM.") from e

    if not 1 <= month <= 12:
        raise ValueError(f"Invalid month {value!r}: month must be 01-12.")
    return year, month


def _load(path: Path) -> ExpenseTracker:
    """Build a tracker backed by `path` and load its contents."""
    tracker = ExpenseTracker(JSONStorage(path))
    tracker.load()
    return tracker


# --------------------------------------------------------------------------
# Command handlers. Each returns an exit code.
# --------------------------------------------------------------------------


def cmd_add(args: argparse.Namespace) -> int:
    tracker = _load(args.data)
    expense = tracker.add(
        Expense(
            title=args.title,
            category=args.category,
            amount=args.amount,
            date=args.date,
            description=args.description,
        )
    )
    tracker.save()
    print(f"Added #{expense.txn_id}: {expense}")
    return EXIT_OK


def cmd_list(args: argparse.Namespace) -> int:
    tracker = _load(args.data)

    expenses = tracker.expenses
    if args.category:
        expenses = tracker.by_category(args.category)
    if args.month:
        year, month = _parse_month(args.month)
        expenses = [e for e in expenses if (e.date.year, e.date.month) == (year, month)]

    expenses.sort(key=lambda e: (e.date, e.txn_id or 0))
    if args.limit is not None:
        if args.limit < 1:
            raise ValueError("--limit must be 1 or greater.")
        expenses = expenses[-args.limit :]

    if not expenses:
        print("No matching expenses.")
        return EXIT_OK

    for expense in expenses:
        print(expense)
    print("-" * 60)
    print(f"{len(expenses)} expense(s), {format_money(total_of(expenses))}")
    return EXIT_OK


def cmd_show(args: argparse.Namespace) -> int:
    tracker = _load(args.data)
    expense = tracker.get(args.txn_id)
    fields = [
        ("Transaction", str(expense.txn_id)),
        ("Date", expense.date.isoformat()),
        ("Title", expense.title),
        ("Category", expense.category),
        ("Amount", format_money(expense.amount)),
        ("Description", expense.description or "(none)"),
    ]
    for label, value in fields:
        print(f"{label:<14}{value}")
    return EXIT_OK


def cmd_remove(args: argparse.Namespace) -> int:
    tracker = _load(args.data)
    expense = tracker.remove(args.txn_id)
    tracker.save()
    print(f"Removed #{args.txn_id}: {expense.title} ({format_money(expense.amount)})")
    return EXIT_OK


def cmd_total(args: argparse.Namespace) -> int:
    tracker = _load(args.data)
    if args.category:
        expenses = tracker.by_category(args.category)
        print(
            f"{args.category}: {format_money(total_of(expenses))} "
            f"across {len(expenses)} expense(s)"
        )
    else:
        print(f"Total: {format_money(tracker.total)} across {len(tracker)} expense(s)")
    return EXIT_OK


def cmd_report(args: argparse.Namespace) -> int:
    tracker = _load(args.data)
    print(get_report(args.kind).render(tracker.expenses))
    return EXIT_OK


def cmd_categories(args: argparse.Namespace) -> int:
    tracker = _load(args.data)
    categories = tracker.categories()
    if not categories:
        print("No categories yet.")
        return EXIT_OK
    for category in categories:
        print(category)
    return EXIT_OK


HANDLERS = {
    "add": cmd_add,
    "list": cmd_list,
    "show": cmd_show,
    "remove": cmd_remove,
    "total": cmd_total,
    "report": cmd_report,
    "categories": cmd_categories,
}


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point. Returns the process exit code rather than calling exit().

    Returning instead of exiting keeps this callable from tests: a test can
    assert on the returned code without catching `SystemExit`.
    """
    args = build_parser().parse_args(argv)

    try:
        return HANDLERS[args.command](args)
    except ExpenseError as e:
        # Every expected failure in this package inherits from ExpenseError,
        # and each one carries a message written for a human. Printing that
        # message beats printing a traceback.
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_ERROR
    except ValueError as e:
        # Raised by argument parsing helpers such as _parse_month.
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_ERROR
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return EXIT_INTERRUPTED

"""Report rendering.

`Report` is an abstract base class with three concrete implementations. The
abstraction earns its place here because the CLI selects a report by name at
runtime and calls `render` without knowing which one it got -- that is
polymorphism doing real work, not an interface added on principle.

Every method that subclasses must implement is decorated with
`@abstractmethod`. An abstract class with an undecorated empty method is a
trap: subclasses inherit a method that silently returns `None` while its
annotation promises a `str`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Sequence
from decimal import Decimal

from expense_tracker.expense import Expense

ZERO = Decimal("0.00")
RUPEE = "\u20b9"


def format_money(amount: Decimal) -> str:
    """Format `amount` with a rupee sign and thousands separators."""
    return f"{RUPEE}{amount:,.2f}"


def total_of(expenses: Sequence[Expense]) -> Decimal:
    """Sum the amounts of `expenses`, returning `Decimal("0.00")` if empty."""
    return sum((e.amount for e in expenses), start=ZERO)


class Report(ABC):
    """Base class for anything that turns expenses into printable text."""

    @property
    @abstractmethod
    def title(self) -> str:
        """The heading shown above this report's body."""

    @abstractmethod
    def render_body(self, expenses: Sequence[Expense]) -> str:
        """Return the report body, without the heading."""

    def render(self, expenses: Sequence[Expense]) -> str:
        """Return the complete report: heading, rule, then body.

        Concrete because every report shares this structure. Subclasses
        override `title` and `render_body` and inherit the layout.
        """
        heading = self.title
        rule = "=" * max(len(heading), 48)
        if not expenses:
            return f"{heading}\n{rule}\n(no expenses)"
        return f"{heading}\n{rule}\n{self.render_body(expenses)}"


class SummaryReport(Report):
    """Headline figures: count, total, mean, and the date range covered."""

    @property
    def title(self) -> str:
        return "Expense Summary"

    def render_body(self, expenses: Sequence[Expense]) -> str:
        total = total_of(expenses)
        count = len(expenses)
        # Decimal / int stays exact; no float ever enters the calculation.
        average = (total / count).quantize(Decimal("0.01"))
        earliest = min(e.date for e in expenses)
        latest = max(e.date for e in expenses)

        rows = [
            ("Expenses", str(count)),
            ("Total", format_money(total)),
            ("Average", format_money(average)),
            ("Earliest", earliest.isoformat()),
            ("Latest", latest.isoformat()),
        ]
        return "\n".join(f"{label:<12}{value:>20}" for label, value in rows)


class CategoryBreakdownReport(Report):
    """Total per category, sorted by spend, with each share of the total."""

    @property
    def title(self) -> str:
        return "Spending by Category"

    def render_body(self, expenses: Sequence[Expense]) -> str:
        totals: defaultdict[str, Decimal] = defaultdict(lambda: ZERO)
        counts: defaultdict[str, int] = defaultdict(int)
        for expense in expenses:
            totals[expense.category] += expense.amount
            counts[expense.category] += 1

        grand_total = total_of(expenses)
        ordered = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)

        lines = [f"{'Category':<16}{'Count':>7}{'Total':>16}{'Share':>9}"]
        lines.append("-" * 48)
        for category, amount in ordered:
            share = (amount / grand_total * 100).quantize(Decimal("0.1"))
            lines.append(
                f"{category:<16}{counts[category]:>7}"
                f"{format_money(amount):>16}{share:>8}%"
            )
        lines.append("-" * 48)
        lines.append(f"{'TOTAL':<16}{len(expenses):>7}{format_money(grand_total):>16}")
        return "\n".join(lines)


class MonthlyReport(Report):
    """Total per calendar month, oldest first."""

    @property
    def title(self) -> str:
        return "Spending by Month"

    def render_body(self, expenses: Sequence[Expense]) -> str:
        totals: defaultdict[tuple[int, int], Decimal] = defaultdict(lambda: ZERO)
        counts: defaultdict[tuple[int, int], int] = defaultdict(int)
        for expense in expenses:
            key = (expense.date.year, expense.date.month)
            totals[key] += expense.amount
            counts[key] += 1

        lines = [f"{'Month':<12}{'Count':>8}{'Total':>18}"]
        lines.append("-" * 48)
        for (year, month), amount in sorted(totals.items()):
            lines.append(
                f"{year}-{month:02d}   {counts[(year, month)]:>8}"
                f"{format_money(amount):>18}"
            )
        lines.append("-" * 48)
        lines.append(
            f"{'TOTAL':<12}{len(expenses):>8}{format_money(total_of(expenses)):>18}"
        )
        return "\n".join(lines)


#: Report names as exposed on the command line.
REPORTS: dict[str, type[Report]] = {
    "summary": SummaryReport,
    "category": CategoryBreakdownReport,
    "monthly": MonthlyReport,
}


def get_report(name: str) -> Report:
    """Instantiate the report registered under `name`.

    Raises:
        KeyError: if no report is registered under that name.
    """
    return REPORTS[name]()

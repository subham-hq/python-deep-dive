"""Tests for `expense_tracker.reports`."""

from __future__ import annotations

from decimal import Decimal

import pytest

from expense_tracker.expense import Expense
from expense_tracker.reports import (
    REPORTS,
    CategoryBreakdownReport,
    MonthlyReport,
    Report,
    SummaryReport,
    format_money,
    get_report,
    total_of,
)

from .conftest import make_expense


class TestHelpers:
    def test_format_money_adds_separators_and_symbol(self) -> None:
        assert format_money(Decimal("1234567.5")) == "\u20b91,234,567.50"

    def test_total_of_empty_is_decimal_zero(self) -> None:
        total = total_of([])
        assert total == Decimal("0.00")
        assert isinstance(total, Decimal)

    def test_total_of_is_exact(self) -> None:
        """The classic float trap: 0.1 + 0.2 != 0.3 in binary floating point."""
        expenses = [make_expense(amount="0.10"), make_expense(amount="0.20")]
        assert total_of(expenses) == Decimal("0.30")


class TestAbstractBase:
    def test_report_cannot_be_instantiated(self) -> None:
        """Regression: `header()` was an empty method with no @abstractmethod,
        so subclasses silently inherited a method returning None despite an
        annotation promising str.
        """
        with pytest.raises(TypeError):
            Report()  # type: ignore[abstract]

    def test_incomplete_subclass_cannot_be_instantiated(self) -> None:
        class Partial(Report):
            @property
            def title(self) -> str:
                return "Partial"

            # render_body deliberately not implemented

        with pytest.raises(TypeError):
            Partial()  # type: ignore[abstract]


@pytest.mark.parametrize("name", sorted(REPORTS))
class TestEveryReport:
    """Behaviour every report must share, checked against all of them."""

    def test_handles_empty_input(self, name: str) -> None:
        rendered = get_report(name).render([])
        assert "no expenses" in rendered

    def test_includes_its_own_title(self, name: str) -> None:
        report = get_report(name)
        assert report.title in report.render([make_expense()])

    def test_renders_a_string(self, name: str, expenses: list[Expense]) -> None:
        assert isinstance(get_report(name).render(expenses), str)

    def test_single_expense_does_not_divide_by_zero(self, name: str) -> None:
        assert get_report(name).render([make_expense()])


class TestSummaryReport:
    def test_reports_count_and_total(self, expenses: list[Expense]) -> None:
        rendered = SummaryReport().render(expenses)
        assert "5" in rendered
        assert "17,000.74" in rendered

    def test_reports_the_date_range(self, expenses: list[Expense]) -> None:
        rendered = SummaryReport().render(expenses)
        assert "2026-01-05" in rendered
        assert "2026-03-03" in rendered

    def test_average_is_exact(self) -> None:
        expenses = [make_expense(amount="10.00"), make_expense(amount="21.00")]
        assert "15.50" in SummaryReport().render(expenses)


class TestCategoryBreakdownReport:
    def test_lists_every_category(self, expenses: list[Expense]) -> None:
        rendered = CategoryBreakdownReport().render(expenses)
        for category in ("Food", "Fuel", "Housing"):
            assert category in rendered

    def test_orders_by_spend_descending(self, expenses: list[Expense]) -> None:
        rendered = CategoryBreakdownReport().render(expenses)
        housing, fuel, food = (rendered.index(c) for c in ("Housing", "Fuel", "Food"))
        assert housing < fuel < food

    def test_shares_sum_to_one_hundred(self) -> None:
        expenses = [
            make_expense(category="A", amount="25.00"),
            make_expense(category="B", amount="75.00"),
        ]
        rendered = CategoryBreakdownReport().render(expenses)
        assert "25.0%" in rendered
        assert "75.0%" in rendered


class TestMonthlyReport:
    def test_groups_by_calendar_month(self, expenses: list[Expense]) -> None:
        rendered = MonthlyReport().render(expenses)
        for month in ("2026-01", "2026-02", "2026-03"):
            assert month in rendered

    def test_orders_chronologically(self, expenses: list[Expense]) -> None:
        rendered = MonthlyReport().render(expenses)
        jan, feb, mar = (rendered.index(m) for m in ("2026-01", "2026-02", "2026-03"))
        assert jan < feb < mar


class TestRegistry:
    def test_every_registered_name_resolves(self) -> None:
        for name in REPORTS:
            assert isinstance(get_report(name), Report)

    def test_unknown_name_raises_key_error(self) -> None:
        with pytest.raises(KeyError):
            get_report("nonexistent")

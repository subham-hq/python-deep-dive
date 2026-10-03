"""Tests for `expense_tracker.expense`."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from expense_tracker.exceptions import (
    InvalidAmountTypeError,
    InvalidAmountValueError,
    InvalidDateError,
    InvalidTextFieldError,
)
from expense_tracker.expense import MAX_AMOUNT, Expense, to_date, to_money

from .conftest import make_expense


class TestToMoney:
    """`to_money` is the single place a value becomes an amount."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("20", "20.00"),
            ("20.5", "20.50"),
            ("20.555", "20.56"),  # ROUND_HALF_UP
            ("20.554", "20.55"),
            (Decimal("2.5"), "2.50"),
            (7, "7.00"),
            ("0.005", "0.01"),  # banker's rounding would give 0.00
            ("2.5", "2.50"),
        ],
    )
    def test_normalises_to_two_places(
        self, value: str | int | Decimal, expected: str
    ) -> None:
        assert to_money(value) == Decimal(expected)

    def test_rejects_float(self) -> None:
        """float is refused on purpose -- it cannot represent money exactly."""
        with pytest.raises(InvalidAmountTypeError):
            to_money(19.99)  # type: ignore[arg-type]

    def test_rejects_bool(self) -> None:
        """bool subclasses int; True must not silently become 1.00."""
        with pytest.raises(InvalidAmountTypeError):
            to_money(True)

    @pytest.mark.parametrize("value", ["", "abc", "12.3.4", "₹20", None, [], {}])
    def test_rejects_junk(self, value: object) -> None:
        with pytest.raises(InvalidAmountTypeError):
            to_money(value)  # type: ignore[arg-type]

    @pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
    def test_rejects_non_finite(self, value: str) -> None:
        """These parse as Decimal but are not usable amounts."""
        with pytest.raises(InvalidAmountTypeError):
            to_money(value)

    @pytest.mark.parametrize(
        "value",
        ["1e30", "-1e30", 10**30, "1e15", "1000000000000000", MAX_AMOUNT],
    )
    def test_rejects_amounts_too_large_to_stay_exact(
        self, value: str | int | Decimal
    ) -> None:
        """Regression: "1e30" used to escape as a raw decimal.InvalidOperation
        from quantize(), which the CLI printed as a traceback.
        """
        with pytest.raises(InvalidAmountValueError) as exc_info:
            to_money(value)
        assert "less than" in str(exc_info.value)

    @pytest.mark.parametrize(
        "value",
        ["999999999999999.99", "999999999999999.994", "999999999999999.9949"],
    )
    def test_accepts_the_largest_amount_below_the_limit(self, value: str) -> None:
        assert to_money(value) == MAX_AMOUNT - Decimal("0.01")

    @pytest.mark.parametrize(
        "value",
        [
            "999999999999999.995",
            "-999999999999999.995",
            Decimal("999999999999999.999"),
        ],
    )
    def test_rejects_amounts_that_round_up_to_the_limit(
        self, value: str | Decimal
    ) -> None:
        """Regression: the limit used to be checked before rounding, so
        999999999999999.995 was accepted and stored as 1000000000000000.00,
        a value the next load then rejected.
        """
        with pytest.raises(InvalidAmountValueError) as exc_info:
            to_money(value)
        assert "less than" in str(exc_info.value)


class TestToDate:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("2026-01-05", date(2026, 1, 5)),
            ("2024-02-29", date(2024, 2, 29)),  # a real leap day
            (date(2026, 7, 29), date(2026, 7, 29)),
        ],
    )
    def test_accepts_valid_dates(self, value: str | date, expected: date) -> None:
        assert to_date(value) == expected

    def test_datetime_is_reduced_to_its_date(self) -> None:
        """Regression: a datetime (a date subclass) used to be kept whole,
        saved as an ISO timestamp the next load rejected, and made date
        comparisons raise TypeError.
        """
        result = to_date(datetime(2026, 1, 5, 9, 30))
        assert type(result) is date
        assert result == date(2026, 1, 5)

    @pytest.mark.parametrize(
        "value",
        [
            "2026-13-45",  # month 13, day 45
            "2026-02-30",  # February never has 30 days
            "2025-02-29",  # 2025 is not a leap year
            "05-01-2026",  # wrong field order
            "2026/01/05",  # wrong separator
            "not-a-date",
            "",
            20260105,
            None,
        ],
    )
    def test_rejects_invalid_dates(self, value: object) -> None:
        with pytest.raises(InvalidDateError):
            to_date(value)  # type: ignore[arg-type]

    def test_impossible_date_reports_the_offending_value(self) -> None:
        """The error must name what was wrong, not just that something was."""
        with pytest.raises(InvalidDateError) as exc_info:
            to_date("2026-13-45")
        assert "2026-13-45" in str(exc_info.value)


class TestExpenseValidation:
    def test_valid_expense_constructs(self) -> None:
        expense = make_expense()
        assert expense.title == "Chai"
        assert expense.amount == Decimal("20.00")
        assert expense.date == date(2026, 1, 5)

    def test_txn_id_defaults_to_none(self) -> None:
        """An expense has no ID until a tracker assigns one."""
        assert make_expense().txn_id is None

    @pytest.mark.parametrize("amount", ["0", "0.00", "-1", "-0.01", Decimal("-500")])
    def test_rejects_non_positive_amount(self, amount: str | Decimal) -> None:
        with pytest.raises(InvalidAmountValueError) as exc_info:
            make_expense(amount=amount)  # type: ignore[arg-type]
        assert "greater than zero" in str(exc_info.value)

    def test_rejects_an_amount_that_rounds_to_zero(self) -> None:
        """0.004 is positive, but it is 0.00 once quantised to cents."""
        with pytest.raises(InvalidAmountValueError):
            make_expense(amount="0.004")

    @pytest.mark.parametrize("blank", ["", "   ", "\t\n"])
    def test_rejects_blank_title(self, blank: str) -> None:
        with pytest.raises(InvalidTextFieldError):
            make_expense(title=blank)

    @pytest.mark.parametrize("blank", ["", "   "])
    def test_rejects_blank_category(self, blank: str) -> None:
        with pytest.raises(InvalidTextFieldError):
            make_expense(category=blank)

    def test_allows_blank_description(self) -> None:
        """An empty description is meaningful; an empty title is not."""
        assert make_expense(description="").description == ""

    def test_strips_surrounding_whitespace(self) -> None:
        expense = make_expense(title="  Chai  ", category=" Food ")
        assert expense.title == "Chai"
        assert expense.category == "Food"

    def test_validation_also_runs_on_later_assignment(self) -> None:
        """The invariant holds for the object's whole life, not just at birth.

        This is why validation lives in the property setters rather than in
        __init__: assigning a bad value later must fail just as loudly.
        """
        expense = make_expense()
        with pytest.raises(InvalidAmountValueError):
            expense.amount = "-5"
        with pytest.raises(InvalidDateError):
            expense.date = "2026-99-99"
        # The failed assignments left the object untouched.
        assert expense.amount == Decimal("20.00")
        assert expense.date == date(2026, 1, 5)


class TestSerialisation:
    def test_round_trip_preserves_every_field(self) -> None:
        original = make_expense(
            "Diesel", "Fuel", "2500.50", "2026-01-20", "tank refill"
        )
        original.txn_id = 42
        assert Expense.from_dict(original.to_dict()) == original

    def test_amount_serialises_as_string_not_float(self) -> None:
        """A float in the JSON would undo the Decimal guarantee."""
        record = make_expense(amount="2500.50").to_dict()
        assert record["amount"] == "2500.50"
        assert isinstance(record["amount"], str)

    def test_date_serialises_as_iso_string(self) -> None:
        """The on-disk format is unchanged, so old data files still load."""
        assert make_expense(date="2026-01-05").to_dict()["date"] == "2026-01-05"

    def test_from_dict_validates(self) -> None:
        """Corrupt stored data fails at load, not at some later use."""
        record = make_expense().to_dict()
        record["date"] = "2026-13-45"
        with pytest.raises(InvalidDateError):
            Expense.from_dict(record)


class TestDunders:
    def test_equality_compares_by_value(self) -> None:
        assert make_expense() == make_expense()
        assert make_expense() != make_expense(amount="999.00")

    def test_equality_with_other_types_is_not_an_error(self) -> None:
        assert make_expense() != "not an expense"

    def test_hashable(self) -> None:
        assert len({make_expense(), make_expense(), make_expense(title="Tea")}) == 2

    def test_str_includes_the_key_fields(self) -> None:
        expense = make_expense("Diesel", "Fuel", "2500.50", "2026-01-20")
        expense.txn_id = 3
        rendered = str(expense)
        assert "Diesel" in rendered
        assert "Fuel" in rendered
        assert "2026-01-20" in rendered
        assert "2,500.50" in rendered

    def test_repr_round_trips_the_important_state(self) -> None:
        assert "Chai" in repr(make_expense())


class TestDescriptionValidation:
    def test_rejects_non_string_description(self) -> None:
        with pytest.raises(InvalidTextFieldError):
            make_expense(description=123)  # type: ignore[arg-type]

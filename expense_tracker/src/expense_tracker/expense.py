from __future__ import annotations

import decimal
from datetime import datetime
from typing import TypedDict
from decimal import Decimal
from expense_tracker.exceptions import InvalidAmountTypeError, InvalidAmountValueError, \
    InvalidDateError


class ExpenseRecord(TypedDict):
    txn_id: int | None
    date: str
    title: str
    category: str
    amount: str
    description: str


class Expense:
    def __init__(
             self,
             txn_id: int | None,
             title: str,
             category: str,
             description: str,
             amount: decimal.Decimal,
             date: str,
    ) -> None:

        self.txn_id = txn_id
        self.title = title
        self.category = category
        self.description = description
        self.amount = amount
        self.date = date

    @property
    def amount(self) -> decimal.Decimal:
        return self._amount

    @amount.setter
    def amount(self, value: str | Decimal) -> None:
        if not isinstance(value, (int, float, Decimal)):
            raise InvalidAmountTypeError(amount=value)

        if value <= 0:
            raise InvalidAmountValueError(amount=value)

        self._amount = decimal.Decimal(str(value)).quantize(decimal.Decimal("0.01"))

    @property
    def date(self) -> str:
        return self._date

    @date.setter
    def date(self, date: str) -> None:
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except:
            raise InvalidDateError(date=date)

        self._date = date

    def __str__(self) -> str:
        return f"{self.txn_id} - {self.date} - {self.title} - {self.category} - \u20B9 {self.amount:0.2f} - {self.description}"

    def to_dict(self) -> ExpenseRecord:

        return {
            "txn_id": self.txn_id,
            "date": self.date,
            "title": self.title,
            "category": self.category,
            "amount": str(self.amount),
            "description": self.description,
        }

    @classmethod
    def from_dict(
            cls,
            data: ExpenseRecord
    ) -> Expense:

        return cls(
            txn_id=data["txn_id"],
            title=data["title"],
            category=data["category"],
            description=data["description"],
            amount=Decimal(data["amount"]),
            date=data["date"]
        )
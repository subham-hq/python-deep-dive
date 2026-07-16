from __future__ import annotations

import decimal
import time
import json
from functools import wraps
from pathlib import Path
from datetime import datetime
from typing import TypedDict, Callable, TypeVar, ParamSpec
from decimal import Decimal

P = ParamSpec("P")
R = TypeVar('R')

class ExpenseRecord(TypedDict):
    txn_id: int | None
    date: str
    title: str
    category: str
    amount: str
    description: str

file = Path("personal_expenses.json")

if not file.exists():
    with file.open("w") as f:
        json.dump([], f, indent=4)

def log_analyzer(func: Callable[P, R]) -> Callable[P, R]:
    @wraps(func)                                  # you imported wraps but never used it
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        print(f"Starting {func.__name__}", end="", flush=True)
        for _ in range(3):
            time.sleep(0.4)
            print(".", end="", flush=True)        # flush => dots appear one at a time
        print("", end="\n\n")
        # close the line
        start_time = time.perf_counter()          # clock starts AFTER the animation
        result = func(*args, **kwargs)
        end_time = time.perf_counter()

        print("", end="\n")
        print(f"Finished {func.__name__} in {end_time - start_time:.6f} seconds.")
        return result
    return wrapper


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
    def amount(self, value: Decimal) -> None:
        if not isinstance(value, (int, float, Decimal)):
            raise TypeError("Expense amount must be an integer or float.")

        if value <= 0:
            raise ValueError("Expense amount must be a positive number.")

        self._amount = decimal.Decimal(str(value)).quantize(decimal.Decimal("0.01"))

    @property
    def date(self) -> str:
        return self._date

    @date.setter
    def date(self, date: str) -> None:
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Date must be in YYYY-MM-DD format and be a valid date.")

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

class ExpenseIterator:
    def __init__(self, expenses: list[Expense]) -> None:
        self.expenses = expenses
        self.index = 0

    def __iter__(self) -> ExpenseIterator:
        return self

    def __next__(self) -> Expense:
        if self.index >= len(self.expenses):
            raise StopIteration
        expense = self.expenses[self.index]
        self.index += 1
        return expense

class ExpenseTracker:
    def __init__(self) -> None:
        self.expenses: list[Expense] = []
        self.next_id: int | None = None

    def add_expense(self, expense: Expense) -> None:
        if self.next_id is None:
            self.next_id = 1

        expense.txn_id = self.next_id
        self.expenses.append(expense)
        self.next_id += 1

    def remove_expense(self, txn_id: int) -> bool:
        for expense in self.expenses:
            if expense.txn_id == txn_id:
                self.expenses.remove(expense)
                return True
        return False

    @property
    def total_expenses(self) -> decimal.Decimal:
        return sum(
            (expense.amount for expense in self.expenses),
            start=Decimal("0.00")
        )

    def save_expenses(self, filename: Path) -> str:
        data = [expense.to_dict() for expense in self.expenses]
        with open(filename, "w") as json_file:
            json.dump(data, json_file, indent=4)
        return f"Saved expenses to {filename}."

    def load_expenses(self, filename: str | Path) -> None:
        self.expenses.clear()

        with (open(filename) as json_file):
            data = json.load(json_file)
            for expense in data:
                expense = Expense.from_dict(expense)
                self.expenses.append(expense)

            if self.expenses:
                self.next_id = max(exp.txn_id
                                   for exp in self.expenses
                                   if exp.txn_id is not None
                                   ) + 1
            else:
                self.next_id = 1

    def __iter__(self) -> ExpenseIterator:
        return ExpenseIterator(self.expenses)

tracker = ExpenseTracker()
tracker.load_expenses("personal_expenses.json")

@log_analyzer
def print_expenses():

    total = tracker.total_expenses

    for expense in tracker:
        print(expense)

    for _ in range(90):
        print("=", end="")
    print()

    print(f"Total expenses: \u20B9 {total:.2f}")

    return tracker

print_expenses()

@log_analyzer
def update_value(filename, txn_id, parameter, value):

    for expense in tracker:
        if expense.txn_id == txn_id:
            setattr(expense, parameter, value)
            break

    tracker.save_expenses(filename)

    for expense in tracker:
        print(expense)

    return tracker

update_value(
    "personal_expenses.json",
    10,
    "amount",
    120
)

def expense_by_category(category):
    for expense in tracker:
        if expense.category == category:
            yield expense

for exp in expense_by_category("Food"):
    print(exp)


def search_expense(txn_id):
    for expense in tracker:
        if expense.txn_id == txn_id:
            yield expense

for exp in search_expense(2):
    print(exp)

if tracker.remove_expense(2):
    print("Successfully removed expense.")
else:
    print("Failed to remove expense.")

print_expenses()

tracker.add_expense(Expense(txn_id=None, title = "Uber Ride", category = "Travel", description = "Ride from office to home", amount = 420, date = "2026-06-27"))

print_expenses()
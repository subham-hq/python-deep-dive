from __future__ import annotations

import decimal
from pathlib import Path
from decimal import Decimal
from expense_tracker.storage import JSONStorage
from expense_tracker.expense import Expense
from expense_tracker.exceptions import JSONSavingError, JSONLoadingError

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
        try:
            JSONStorage(filename).save(self.expenses)
            return f"Saved expenses to {filename}."
        except:
            raise JSONSavingError(filename)

    def load_expenses(self, filename: str | Path) -> None:
        self.expenses.clear()

        try:
            expenses = JSONStorage(filename).load()
            for expense in expenses:
                self.expenses.append(expense)

                if self.expenses:
                    self.next_id = max(exp.txn_id
                                       for exp in self.expenses
                                       if exp.txn_id is not None
                                       ) + 1
                else:
                    self.next_id = 1
        except:
            raise JSONLoadingError(filename)

    def __iter__(self) -> ExpenseIterator:
        return ExpenseIterator(self.expenses)
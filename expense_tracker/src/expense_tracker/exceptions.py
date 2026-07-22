from decimal import Decimal
from pathlib import Path


class ExpenseError(Exception):
    """Base exception for the Expense Tracker."""
    pass

class InvalidAmountValueError(ExpenseError):
    """Raised when an expense amount is invalid value."""
    def __init__(self, amount: int | float | Decimal):
        self.amount = amount
        super().__init__(f"Invalid Expense Amount: {amount}\nExpense amount must be a positive value.")

class InvalidAmountTypeError(ExpenseError):
    """Raised when an expense amount is invalid type."""
    def __init__(self, amount: str):
        self.amount = amount
        super().__init__(f"Invalid Expense Amount Type: {amount}\nExpense amount must be of type int or float.")

class InvalidDateError(ExpenseError):
    """Raised when an expense date is invalid."""
    def __init__(self, date: str):
        self.date = date
        super().__init__(f"Invalid Date: {date}\nDate must be in YYYY-MM-DD format and be a valid date.")

class JSONLoadingError(ExpenseError):
    """Raised when a JSON file is failed to load."""
    def __init__(self, path: Path):
        self.path = path
        super().__init__(f"Could not load JSON file '{path}'")

class JSONSavingError(ExpenseError):
    """Raised when a JSON file is failed to save."""
    def __init__(self, path: Path):
        self.path = path
        super().__init__(f"Could not save JSON file '{path}'")
import json
from pathlib import Path

from expense_tracker.expense import ExpenseRecord, Expense


class JSONStorage:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> list[Expense]:
        # Ensure the file exists
        if not self.path.exists():
            return []

        # Load the JSON file
        with self.path.open("r", encoding="utf-8") as file:
            raw_data = json.load(file)

        return [Expense.from_dict(item) for item in raw_data]

    def save(self, expenses: list[Expense]) -> None:
        # Ensure the folder exists
        self.path.parent.mkdir(parents=True, exist_ok=True)

        data = [expense.to_dict() for expense in expenses]

        # Save the JSON file
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(data, file, indent=4)
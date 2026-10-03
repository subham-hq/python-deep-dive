"""Allow ``python -m expense_tracker`` as an alternative to the console script."""

from __future__ import annotations

from expense_tracker.main import main

if __name__ == "__main__":
    main()

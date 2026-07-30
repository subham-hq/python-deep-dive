"""Console-script entry point.

Deliberately thin. `cli.main` returns an exit code; this module is the only
place that turns it into a process exit, which keeps `cli.main` importable
and testable.
"""

from __future__ import annotations

import sys

from expense_tracker.cli import main as cli_main


def main() -> None:
    sys.exit(cli_main())


if __name__ == "__main__":
    main()

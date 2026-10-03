"""Console-script entry point.

Deliberately thin. `cli.main` returns an exit code; this module is the only
place that turns it into a process exit, which keeps `cli.main` importable
and testable.

It also owns the one failure that belongs to the process rather than to any
command: stdout being closed by the reader, as in
``expense-tracker list | head``.
"""

from __future__ import annotations

import os
import sys

from expense_tracker.cli import EXIT_BROKEN_PIPE
from expense_tracker.cli import main as cli_main


def main() -> None:
    try:
        code = cli_main()
        # Piped output is block-buffered, so a reader that has gone away is
        # often only discovered on this final flush.
        sys.stdout.flush()
    except BrokenPipeError:
        # The reader stopped reading; that is not worth a traceback. Point
        # stdout at devnull so the interpreter's own flush at exit cannot
        # raise BrokenPipeError a second time.
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        code = EXIT_BROKEN_PIPE
    sys.exit(code)


if __name__ == "__main__":
    main()

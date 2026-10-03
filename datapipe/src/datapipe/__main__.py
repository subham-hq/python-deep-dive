"""Allow ``python -m datapipe`` as an alias for the ``datapipe`` command."""

from datapipe.cli import main

if __name__ == "__main__":
    raise SystemExit(main())

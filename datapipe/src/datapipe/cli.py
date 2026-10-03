import argparse
import json
import math
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from datapipe.models import Record, parse_record
from datapipe.pipeline import Normalize, Pipeline, Scale
from datapipe.steps import RequireName, RequirePositiveValue


def load_records(path: Path) -> list[Record]:
    """Read a JSON array of records from ``path``.

    Raises:
        OSError: if the file cannot be opened.
        ValueError: if the file is not valid JSON, is nested too deeply to
            parse, is not an array, or holds a malformed record.
    """
    with path.open("r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except RecursionError:
            # Valid JSON such as 100,000 nested "[" exhausts the parser's
            # recursion limit; report it like any other unreadable input.
            raise ValueError("JSON is nested too deeply") from None
    if not isinstance(data, list):
        raise ValueError(f"expected a JSON array of records, got {type(data).__name__}")

    records: list[Record] = []
    for index, raw in enumerate(data):
        try:
            records.append(parse_record(raw))
        except ValueError as exc:
            raise ValueError(f"item {index}: {exc}") from exc
    return records


def _finite_float(text: str) -> float:
    """``argparse`` type for ``--factor``: a float that is not NaN or infinite.

    Plain ``type=float`` accepts ``nan``, ``inf`` and ``1e400``, which would
    only fail later, once per record, with a confusing message about the
    output. Rejecting them here makes them a usage error (exit status 2).
    """
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid float value: {text!r}") from None
    if not math.isfinite(value):
        raise argparse.ArgumentTypeError(f"must be a finite number, got {text!r}")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="datapipe",
        description=(
            "Validate, normalize and scale a JSON array of records, "
            "printing one JSON object per line."
        ),
    )
    parser.add_argument("path", type=Path, help="path to a JSON array of records")
    parser.add_argument(
        "--factor",
        type=_finite_float,
        default=1.1,
        help="multiplier applied to every value (default: %(default)s)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        records = load_records(args.path)
    except OSError as exc:
        return _error(f"cannot read {args.path}: {exc.strerror or exc}")
    except ValueError as exc:
        return _error(f"{args.path}: {exc}")

    pipeline = Pipeline[Record](
        [
            RequireName(),
            RequirePositiveValue(),
            Normalize(),
            Scale(args.factor),
        ]
    )

    try:
        for result in pipeline.run(records):
            print(json.dumps(result, allow_nan=False))
        sys.stdout.flush()
    except ValueError as exc:
        return _error(str(exc))
    except BrokenPipeError:
        # The reader (e.g. `head`) exited early. Point stdout at /dev/null so
        # the interpreter's final flush does not raise a second time.
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        return 1
    return 0


def _error(message: str) -> int:
    print(f"datapipe: error: {message}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

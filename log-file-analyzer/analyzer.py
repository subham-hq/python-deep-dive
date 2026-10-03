import time
from collections import Counter
from collections.abc import Generator, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from os import PathLike
from typing import Generic, Self, TypedDict, TypeVar

from decorators import time_it

T = TypeVar("T")


class Record(TypedDict):
    """One parsed log line, as yielded by parse()."""

    ts: str
    level: str
    msg: str


@dataclass
class ParseStats:
    """Read counters for one parse() pass.

    parse() updates these as a side effect so the pipeline can report how many
    lines were touched without threading a count through every generator.
    The caller creates one per pass, so one pass's numbers never leak into
    the next.
    """

    lines_read: int = 0
    malformed: int = 0


def parse(
    path: str | PathLike[str], stats: ParseStats | None = None
) -> Generator[Record, None, None]:
    """Yield one dict per log line, lazily — never loads the whole file.

    A line that doesn't split into date, time, level and message (blank,
    truncated, mis-spaced) is skipped and counted in `stats.malformed`
    rather than crashing the whole run.
    """
    if stats is None:
        stats = ParseStats()
    with open(path, encoding="utf-8") as f:
        for line in f:
            stats.lines_read += 1
            fields = line.rstrip("\n").split(" ", 3)
            if len(fields) < 4 or not all(fields[:3]):
                stats.malformed += 1
                continue
            ts_date, ts_time, level, msg = fields
            yield {"ts": f"{ts_date} {ts_time}", "level": level, "msg": msg}


def only(records: Iterable[Record], level: str) -> Iterator[Record]:
    """Filtering generator: pass through only records matching `level`."""
    for record in records:
        if record["level"] == level:
            yield record


class Paginator(Generic[T]):
    """Wraps any iterable and yields it in fixed-size pages (lists).

    Works over a generator, not just a list — it pulls items one at a time
    with next(), so it never needs the full dataset in memory.
    """

    def __init__(self, iterable: Iterable[T], page_size: int) -> None:
        if page_size < 1:
            raise ValueError(f"page_size must be at least 1, got {page_size}")
        self.source = iter(iterable)        # iter() so a list works too, not just a generator
        self.page_size = page_size

    def __iter__(self) -> Self:
        return self

    def __next__(self) -> list[T]:
        page: list[T] = []
        for _ in range(self.page_size):
            try:
                page.append(next(self.source))
            except StopIteration:
                break
        if not page:
            raise StopIteration
        return page


@contextmanager
def timer() -> Iterator[None]:
    """Time a block. The try/finally guarantees the time prints even if the
    block raises — that guarantee is the whole reason to use a context manager
    here instead of a manual start/stop pair."""
    start = time.perf_counter()
    try:
        yield
    finally:
        print(f"[Timer] whole run: {time.perf_counter() - start:.4f} seconds")


@time_it
def main() -> None:
    """
    Runs the log analysis in two passes over app.log.

    Pass 1 (lazy proof): builds the parse -> filter -> paginate pipeline and
    pulls only the FIRST page of ERROR records, to show that producing one page
    touches only a few dozen lines, not the whole file. Nothing reads the file
    before this pass, so its count is everything read when the page prints.

    Pass 2 (full report): consumes a FRESH parse() generator to tally records
    per level. Pass 1's generators are partially consumed and cannot rewind,
    so Pass 2 must start its own. It reads every line, so its count is the
    file's length: the figure to compare pass 1's against.
    """
    path = "app.log"

    # --- Pass 1: lazy proof — pull ONE page, report how little was read ---
    pass1 = ParseStats()
    records = parse(path, pass1)
    errors = only(records, "ERROR")
    pages = Paginator(errors, 5)

    first_page = next(iter(pages), [])  # [] instead of StopIteration if there are no ERRORs
    records.close()                     # release pass 1's file handle now, not at GC time

    print(f"first ERROR page ready after reading only {pass1.lines_read} lines")
    print("first ERROR page:")
    for record in first_page:
        print(f"  {record}")

    # --- Pass 2: full report — FRESH generator (Pass 1's can't rewind) ---
    pass2 = ParseStats()
    all_records = parse(path, pass2)

    counts: Counter[str] = Counter()    # Counter defaults missing keys to 0, so += just works
    for record in all_records:
        counts[record["level"]] += 1

    print(f"Ready after reading {pass2.lines_read} lines ({pass2.malformed} malformed, skipped)")
    print(counts)


if __name__ == "__main__":
    with timer():
        main()

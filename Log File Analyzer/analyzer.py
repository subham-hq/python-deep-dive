import time
from contextlib import contextmanager
from collections import Counter
from decorators import time_it

# Module-level read counter. parse() increments it as a side effect so the
# pipeline can report how many lines were touched without threading a count
# through every generator. A mutable global is a deliberate shortcut here for
# the lazy-proof demo — in production you'd track this inside a class or wrap
# the file object instead.
LINES_READ = 0

def parse(path):
    """Yield one dict per log line, lazily — never loads the whole file."""
    with open(path, "r") as f:
        global LINES_READ
        for line in f:
            LINES_READ += 1
            ts_date, ts_time, level, msg = line.rstrip("\n").split(" ", 3)
            yield {"ts": f"{ts_date} {ts_time}", "level": level, "msg": msg}

def only(records, level):
    """Filtering generator: pass through only records matching `level`."""
    for record in records:
        if record["level"] == level:
            yield record

class Paginator:
    """Wraps any iterable and yields it in fixed-size pages (lists).

    Works over a generator, not just a list — it pulls items one at a time
    with next(), so it never needs the full dataset in memory.
    """
    def __init__(self, iterable, page_size):
        self.source = iterable
        self.page_size = page_size

    def __iter__(self):
        return self

    def __next__(self):
        page = []
        for _ in range(self.page_size):
            try:
                page.append(next(self.source))
            except StopIteration:
                break
        if not page:
            raise StopIteration
        return page

@contextmanager
def timer():
    """Time a block. The try/finally guarantees the time prints even if the
    block raises — that guarantee is the whole reason to use a context manager
    here instead of a manual start/stop pair."""
    start = time.perf_counter()
    try:
        yield
    finally:
        print(f"[Timer] whole run: {time.perf_counter() - start:.4f} seconds")

@time_it
def main():
    """
    Runs the log analysis in two passes over app.log.

    Pass 1 (lazy proof): builds the parse -> filter -> paginate pipeline and
    pulls only the FIRST page of ERROR records, to show that producing one page
    touches only a few dozen lines, not the whole file.

    Pass 2 (full report): consumes a FRESH parse() generator to tally records
    per level. Pass 1's generators are partially consumed, so Pass 2 must start
    its own — a consumed generator yields nothing.
    """
    global LINES_READ
    LINES_READ = 0

    # --- Pass 1: lazy proof — pull ONE page, report how little was read ---
    records = parse("app.log")
    errors = only(records, "ERROR")
    pages = Paginator(errors, 5)

    first_page = next(iter(pages))

    print(f"first ERROR page ready after reading only {LINES_READ} of 100000 lines")
    print(f"first ERROR page: \n{first_page}")

    # --- Pass 2: full report — FRESH generator (Pass 1's is exhausted) ---
    all_records = parse("app.log")

    counts = Counter()                  # Counter defaults missing keys to 0, so += just works
    for record in all_records:
        counts[record["level"]] += 1

    print(f"Ready after reading {LINES_READ} lines")
    print(counts)

if __name__ == "__main__":
    with timer():
        main()
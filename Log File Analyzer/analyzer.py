import time
from contextlib import contextmanager

lines_read = 0

def parse(path):
    with open(path, "r") as f:
        global lines_read
        for line in f:
            lines_read += 1
            ts_date, ts_time, level, msg = line.rstrip("\n").split(" ", 3)
            yield {"ts": f"{ts_date} {ts_time}", "level": level, "msg": msg}

def only(records, level):
    for record in records:
        if record["level"] == level:
            yield record

class Paginator:
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
    start = time.perf_counter()
    try:
        yield
    finally:
        print(f"[timer] {time.perf_counter() - start:.4f} seconds")

def main():
    records = parse("app.log")
    errors = only(records, "ERROR")
    pages = Paginator(errors, 5)

    first_page = next(pages)

    print(f"first ERROR page ready after reading only {lines_read} of 100000 lines")

    print(f"first ERROR page: \n{first_page}")

if __name__ == "__main__":
    main()
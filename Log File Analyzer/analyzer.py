def parse(path):
    with open(path, "r") as f:
        lines_read = 0
        for line in f:
            lines_read += 1
            yield line.split(" ", 3)

def only(records, level):
    for record in records:
        if record[2] == level:
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
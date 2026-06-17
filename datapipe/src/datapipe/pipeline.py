from typing import Protocol, Iterable, Iterator

from datapipe.models import Record


class Step[T](Protocol):
    def run(self, item: T) -> T: ...

class Normalize:
    def run(self, item: Record) -> Record:
        return {**item, "name": item["name"].strip().lower()}

class Scale:
    def __init__(self, factor: float) -> None:
        self.factor = factor

    def run(self, item: Record) -> Record:
        return {**item, "value": item["value"] * self.factor}

class Pipeline[T]:
    def __init__(self, steps: list[Step[T]]) -> None:
        self.steps = steps
    def run(self, item: Iterable[T]) -> Iterator[T]:
        for i in item:
            current = i
            for step in self.steps:
                current = step.run(current)
            yield current
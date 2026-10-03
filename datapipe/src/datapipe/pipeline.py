from collections.abc import Iterable, Iterator, Sequence
from decimal import Decimal
from typing import Protocol

from datapipe.models import Record


class Step[T](Protocol):
    def run(self, item: T) -> T: ...


class Normalize:
    def run(self, item: Record) -> Record:
        return {**item, "name": item["name"].strip().lower()}


class Scale:
    """Multiply each record's ``value`` by ``factor``.

    The product is computed in ``Decimal`` from each float's shortest repr,
    so ``174.93 * 1.1`` comes out as ``192.423`` rather than binary
    floating point's ``192.42300000000003``.
    """

    def __init__(self, factor: float) -> None:
        self.factor = factor

    def run(self, item: Record) -> Record:
        scaled = Decimal(str(item["value"])) * Decimal(str(self.factor))
        return {**item, "value": float(scaled)}


class Pipeline[T]:
    def __init__(self, steps: Sequence[Step[T]]) -> None:
        self.steps = steps

    def run(self, items: Iterable[T]) -> Iterator[T]:
        for item in items:
            current = item
            for step in self.steps:
                current = step.run(current)
            yield current

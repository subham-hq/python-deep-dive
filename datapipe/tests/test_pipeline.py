from datapipe.models import Record
from datapipe.pipeline import Pipeline

class SpyStep:
    def __init__(self) -> None:
        self.calls: list[int] = []
    def run(self, item: Record) -> Record:
        self.calls.append(item["id"])
        return item

def test_steps_run_in_order() -> None:
    spy = SpyStep()
    pipeline = Pipeline[Record]([spy])
    records: list[Record] = [
        {"id": 1, "name": "a", "value": 1.0},
        {"id": 2, "name": "b", "value": 2.0},
    ]
    out = list(pipeline.run(records))
    assert spy.calls == [1, 2]
    assert len(out) == 2
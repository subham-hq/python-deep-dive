import itertools
from collections.abc import Iterator

import pytest

from datapipe.models import Record
from datapipe.pipeline import Normalize, Pipeline, Scale, Step


class SpyStep:
    def __init__(self) -> None:
        self.calls: list[int] = []

    def run(self, item: Record) -> Record:
        self.calls.append(item["id"])
        return item


class Append:
    """A ``Step[str]`` used to check that steps compose left to right."""

    def __init__(self, suffix: str) -> None:
        self.suffix = suffix

    def run(self, item: str) -> str:
        return item + self.suffix


def make_record(id_: int = 1, name: str = "a", value: float = 1.0) -> Record:
    return {"id": id_, "name": name, "value": value}


# ------------------------------------------------------------- Pipeline ----


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


def test_steps_compose_left_to_right() -> None:
    pipeline = Pipeline[str]([Append("1"), Append("2"), Append("3")])
    assert list(pipeline.run(["a", "b"])) == ["a123", "b123"]


def test_pipeline_with_no_steps_is_identity() -> None:
    records = [make_record(1), make_record(2)]
    assert list(Pipeline[Record]([]).run(records)) == records


def test_pipeline_on_empty_input_yields_nothing() -> None:
    assert list(Pipeline[Record]([Normalize()]).run([])) == []


def test_pipeline_accepts_any_sequence_of_steps() -> None:
    steps: tuple[Step[str], ...] = (Append("!"),)
    assert list(Pipeline[str](steps).run(["hi"])) == ["hi!"]


def test_run_is_lazy() -> None:
    spy = SpyStep()
    results = Pipeline[Record]([spy]).run([make_record(1), make_record(2)])

    assert isinstance(results, Iterator)
    assert spy.calls == []  # nothing happens until the caller pulls a value
    next(results)
    assert spy.calls == [1]


def test_run_streams_an_unbounded_source() -> None:
    source = (make_record(i) for i in itertools.count())
    first_three = itertools.islice(Pipeline[Record]([Normalize()]).run(source), 3)
    assert [r["id"] for r in first_three] == [0, 1, 2]


def test_a_failing_step_stops_the_stream_after_earlier_items() -> None:
    class FailOnTwo:
        def run(self, item: Record) -> Record:
            if item["id"] == 2:
                raise ValueError("boom")
            return item

    results = Pipeline[Record]([FailOnTwo()]).run([make_record(1), make_record(2)])
    assert next(results)["id"] == 1
    with pytest.raises(ValueError, match="boom"):
        next(results)


# ------------------------------------------------------------ Normalize ----


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  CANTALOUPE  ", "cantaloupe"),
        ("coconut ", "coconut"),
        ("  ApplE", "apple"),
        ("kiwi", "kiwi"),
    ],
)
def test_normalize_strips_and_lowercases_name(raw: str, expected: str) -> None:
    assert Normalize().run(make_record(name=raw))["name"] == expected


def test_normalize_leaves_other_fields_and_input_untouched() -> None:
    original = make_record(id_=7, name="  MANGO ", value=3.5)
    result = Normalize().run(original)

    assert result == {"id": 7, "name": "mango", "value": 3.5}
    assert original["name"] == "  MANGO "  # returns a new dict, no mutation


# ---------------------------------------------------------------- Scale ----


@pytest.mark.parametrize(
    ("value", "factor", "expected"),
    [
        (174.93, 1.1, 192.423),  # plain float math gives 192.42300000000003
        (0.1, 3, 0.3),  # plain float math gives 0.30000000000000004
        (10, 2.5, 25.0),
        (881.98, 1, 881.98),
        (5.0, 0, 0.0),
        (2.5, -2, -5.0),
    ],
)
def test_scale_multiplies_without_float_noise(
    value: float, factor: float, expected: float
) -> None:
    assert Scale(factor).run(make_record(value=value))["value"] == expected


def test_scale_returns_a_float_and_leaves_input_untouched() -> None:
    original = make_record(id_=3, name="x", value=4)
    result = Scale(1.5).run(original)

    assert result == {"id": 3, "name": "x", "value": 6.0}
    assert isinstance(result["value"], float)
    assert original["value"] == 4


def test_transforms_satisfy_the_step_protocol_structurally() -> None:
    # Neither class inherits from Step; mypy accepts them because they have
    # a matching ``run`` method.
    steps: list[Step[Record]] = [Normalize(), Scale(2)]
    out = list(Pipeline[Record](steps).run([make_record(name=" A ", value=1.5)]))
    assert out == [{"id": 1, "name": "a", "value": 3.0}]

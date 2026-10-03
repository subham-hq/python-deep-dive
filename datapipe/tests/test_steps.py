import pytest

from datapipe.models import Record
from datapipe.steps import RequireName, RequirePositiveValue, ValidatingStep


def make_record(id_: int = 1, name: str = "a", value: float = 1.0) -> Record:
    return {"id": id_, "name": name, "value": value}


# ------------------------------------------------------- ValidatingStep ----


def test_validating_step_is_abstract() -> None:
    with pytest.raises(TypeError, match="abstract"):
        ValidatingStep()  # type: ignore[abstract]


def test_subclass_only_needs_validate_and_inherits_run() -> None:
    class RequireEvenId(ValidatingStep):
        def validate(self, item: Record) -> None:
            if item["id"] % 2:
                raise ValueError("odd id")

    step = RequireEvenId()
    record = make_record(id_=2)
    assert step.run(record) is record
    with pytest.raises(ValueError, match="odd id"):
        step.run(make_record(id_=3))


# ---------------------------------------------------------- RequireName ----


@pytest.mark.parametrize("name", ["apple", "  apple  ", "x"])
def test_require_name_passes_the_record_through_unchanged(name: str) -> None:
    record = make_record(name=name)
    assert RequireName().run(record) is record


@pytest.mark.parametrize("name", ["", " ", "\t\n  "])
def test_require_name_rejects_blank_names(name: str) -> None:
    with pytest.raises(ValueError, match=r"^record 42 has an empty name$"):
        RequireName().run(make_record(id_=42, name=name))


# ------------------------------------------------- RequirePositiveValue ----


@pytest.mark.parametrize("value", [0.01, 1, 959.96])
def test_require_positive_value_passes_positive_values(value: float) -> None:
    record = make_record(value=value)
    assert RequirePositiveValue().run(record) is record


@pytest.mark.parametrize("value", [0, 0.0, -0.01, -100])
def test_require_positive_value_rejects_zero_and_negatives(value: float) -> None:
    with pytest.raises(ValueError, match=r"^record 7 has a non-positive value: "):
        RequirePositiveValue().run(make_record(id_=7, value=value))

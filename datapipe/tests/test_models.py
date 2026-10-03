import re

import pytest

from datapipe.models import parse_record


def test_parse_record_accepts_a_well_formed_object() -> None:
    raw = {"id": 1, "name": "  Mango ", "value": 881.98}
    assert parse_record(raw) == raw


def test_parse_record_accepts_an_integer_value() -> None:
    assert parse_record({"id": 1, "name": "a", "value": 5})["value"] == 5


def test_parse_record_accepts_an_integer_value_that_fits_in_a_float() -> None:
    # 10**308 is just below the largest float (about 1.8e308).
    assert parse_record({"id": 1, "name": "a", "value": 10**308})["value"] == 10**308


@pytest.mark.parametrize("value", [10**309, 10**400, -(10**400)])
def test_parse_record_rejects_an_integer_too_large_for_a_float(value: int) -> None:
    # json.load parses integers of any size. The message must not echo the
    # number back, since it can be thousands of digits long.
    with pytest.raises(
        ValueError, match=r"^'value' is too large to convert to a float$"
    ):
        parse_record({"id": 1, "name": "a", "value": value})


def test_parse_record_drops_unknown_keys() -> None:
    raw = {"id": 1, "name": "a", "value": 1.0, "colour": "red"}
    assert parse_record(raw) == {"id": 1, "name": "a", "value": 1.0}


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ([1, "a", 1.0], "expected a JSON object, got list"),
        ("record", "expected a JSON object, got str"),
        (None, "expected a JSON object, got NoneType"),
        ({"name": "a", "value": 1.0}, "missing required key 'id'"),
        ({"id": 1, "value": 1.0}, "missing required key 'name'"),
        ({"id": 1, "name": "a"}, "missing required key 'value'"),
        ({"id": "1", "name": "a", "value": 1.0}, "'id' must be an integer, got '1'"),
        ({"id": 1.0, "name": "a", "value": 1.0}, "'id' must be an integer, got 1.0"),
        ({"id": True, "name": "a", "value": 1.0}, "'id' must be an integer, got True"),
        ({"id": 1, "name": None, "value": 1.0}, "'name' must be a string, got None"),
        ({"id": 1, "name": "a", "value": "9"}, "'value' must be a number, got '9'"),
        ({"id": 1, "name": "a", "value": False}, "'value' must be a number, got False"),
        ({"id": 1, "name": "a", "value": float("nan")}, "'value' must be finite"),
        ({"id": 1, "name": "a", "value": float("inf")}, "'value' must be finite"),
    ],
)
def test_parse_record_rejects_malformed_input(raw: object, message: str) -> None:
    with pytest.raises(ValueError, match="^" + re.escape(message)):
        parse_record(raw)

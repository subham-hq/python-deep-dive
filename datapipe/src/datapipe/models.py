import math
from typing import TypedDict


class Record(TypedDict):
    id: int
    name: str
    value: float


def parse_record(raw: object) -> Record:
    """Check that ``raw`` has the shape of a ``Record`` and return it as one.

    ``Record`` is a static type only: ``json.load`` will happily return a dict
    with a missing key or a string where a number should be. This is the one
    place untrusted data is checked before the rest of the package relies on
    the ``Record`` type. Keys other than ``id``, ``name`` and ``value`` are
    dropped.

    Raises:
        ValueError: if ``raw`` is not an object, a key is missing, a value
            has the wrong type, or ``value`` does not fit in a finite float.
    """
    if not isinstance(raw, dict):
        raise ValueError(f"expected a JSON object, got {type(raw).__name__}")

    for key in ("id", "name", "value"):
        if key not in raw:
            raise ValueError(f"missing required key {key!r}")

    id_, name, value = raw["id"], raw["name"], raw["value"]
    # bool is a subclass of int, so it has to be ruled out explicitly.
    if not isinstance(id_, int) or isinstance(id_, bool):
        raise ValueError(f"'id' must be an integer, got {id_!r}")
    if not isinstance(name, str):
        raise ValueError(f"'name' must be a string, got {name!r}")
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ValueError(f"'value' must be a number, got {value!r}")
    # Python's json module accepts NaN and Infinity, which JSON itself does not.
    # It also parses an integer of any size, and one past ~1.8e308 has no float
    # equivalent. Do not echo that one back: it can be thousands of digits long.
    try:
        finite = math.isfinite(value)
    except OverflowError:
        raise ValueError("'value' is too large to convert to a float") from None
    if not finite:
        raise ValueError(f"'value' must be finite, got {value!r}")

    return {"id": id_, "name": name, "value": value}

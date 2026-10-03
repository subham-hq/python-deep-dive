# datapipe

A tiny, fully typed data pipeline that validates, normalizes and scales JSON records through composable steps, using only the standard library.

<!-- TODO(you): optional one or two sentences, in your own words, on why you built this. -->

## What it is

`datapipe` reads a JSON array of records shaped like
`{"id": 1, "name": "  CANTALOUPE  ", "value": 174.93}`, pushes each one through
a chain of steps, and prints the results as [JSON Lines](https://jsonlines.org/)
(one JSON object per line):

```text
records.json ─▶ load_records ─▶ RequireName ─▶ RequirePositiveValue ─▶ Normalize ─▶ Scale(1.1) ─▶ stdout
                (shape check)   (validate)     (validate)              (transform)  (transform)
```

It is small on purpose. The point is the shape of the code: a typed step
interface, two different ways of implementing it, a generic engine that runs
them lazily, and a CLI that fails cleanly.

- Python 3.12+ (uses PEP 695 generic syntax), no runtime dependencies
- `mypy --strict` clean, `ruff` clean, 100% branch coverage enforced in `pytest`

## Project layout

```text
datapipe/
├── pyproject.toml          # hatchling build, console script, ruff / mypy / pytest config
├── records.json            # 1,000 sample records with messy names
├── src/datapipe/
│   ├── models.py           # Record (TypedDict) + parse_record: the untrusted-data boundary
│   ├── pipeline.py         # Step[T] Protocol, Pipeline[T] engine, Normalize, Scale
│   ├── steps.py            # ValidatingStep ABC, RequireName, RequirePositiveValue
│   ├── cli.py              # argparse entry point, error handling, JSON Lines output
│   ├── __main__.py         # enables `python -m datapipe`
│   └── py.typed            # PEP 561 marker: ship the type hints to users
└── tests/                  # test_cli, test_models, test_pipeline, test_steps
```

## Design

### Two kinds of step: Protocol vs ABC

Every step has the same interface, declared once in `pipeline.py`:

```python
class Step[T](Protocol):
    def run(self, item: T) -> T: ...
```

`Step` is a `typing.Protocol`, so conformance is **structural**. `Normalize`
and `Scale` do not inherit from anything; they satisfy `Step[Record]` simply
because they have a matching `run` method, and mypy checks that at every call
site. The same is true of the throwaway spy classes in the tests.

The validators in `steps.py` take the other route. `ValidatingStep` is an
`abc.ABC` that implements `run` once (call `validate`, then pass the item
through unchanged) and leaves `validate` abstract. That is the template-method
pattern: `RequireName` and `RequirePositiveValue` only state their rule, and
the ABC refuses to instantiate a subclass that forgot to.

Both kinds plug into the same `Pipeline` because the Protocol does not care
how a class came to have `run`. The trade-off the code illustrates:

| | `Step` Protocol | `ValidatingStep` ABC |
| --- | --- | --- |
| Conformance | structural (has the method) | nominal (inherits the class) |
| Checked by | the type checker | the runtime, at instantiation |
| Shares behaviour | no | yes (`run` is inherited) |
| Best for | an open interface anyone can satisfy | a family of steps with common logic |

### Generics with PEP 695

`Step[T]` and `Pipeline[T]` use the Python 3.12 type-parameter syntax, so the
engine knows nothing about `Record`. `Pipeline[Record]` runs records;
`Pipeline[str]` runs strings (there is a test that does exactly that). Steps
are accepted as any `Sequence[Step[T]]`, so a list or a tuple both work.

### A lazy, generator-based engine

```python
def run(self, items: Iterable[T]) -> Iterator[T]:
    for item in items:
        current = item
        for step in self.steps:
            current = step.run(current)
        yield current
```

`Pipeline.run` is a generator. Nothing executes until the caller asks for the
next item, each item goes through every step before the next one is read, and
the input can be any iterable, including an infinite one
(`tests/test_pipeline.py` feeds it `itertools.count()`). It also means a
validation error stops the stream at the offending record, after the records
before it have already been emitted.

### Validating at the boundary

A `TypedDict` is a static type only. `json.load` will happily return a dict
with a missing key or a string where a number should be. `parse_record` in
`models.py` is the single place where raw JSON is checked (required keys,
`int` id that is not a `bool`, `str` name, a numeric value that is not `NaN`
or `Infinity` and is not an integer too large for a float) and turned into a
real `Record`. Everything downstream can then trust the type. Business
rules (non-empty name, positive value) stay in the validating steps.

### Exact decimal scaling

`174.93 * 1.1` in binary floating point is `192.42300000000003`. `Scale`
multiplies in `decimal.Decimal`, built from each float's shortest repr, so the
output is `192.423`.

### A CLI that fails cleanly

- Output is JSON Lines, so it composes with `head`, `wc -l`, `grep` and `jq`.
- Bad input (missing file, invalid or too deeply nested JSON, malformed record,
  failed validation) prints a single `datapipe: error: ...` line to stderr and
  exits with status 1.
- Usage errors exit with status 2, as argparse does by default. That includes
  a `--factor` that is not a finite number (`nan`, `inf`, `1e400`), which is
  rejected before any input is read.
- Closing the pipe early (`datapipe records.json | head`) does not produce a
  `BrokenPipeError` traceback.

## Install and run

Requires Python 3.12 or newer.

```bash
cd datapipe
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .
```

This installs a `datapipe` command. Run it on the bundled sample:

```console
$ datapipe records.json | head -n 3
{"id": 1, "name": "cantaloupe", "value": 192.423}
{"id": 2, "name": "coconut", "value": 422.499}
{"id": 3, "name": "cantaloupe", "value": 151.624}
$ datapipe records.json | wc -l
1000
```

The scaling factor defaults to `1.1` and can be changed:

```console
$ datapipe records.json --factor 2 | tail -n 2
{"id": 999, "name": "lemon", "value": 1586.74}
{"id": 1000, "name": "lemon", "value": 1520.34}
```

`python -m datapipe records.json` works too.

When a record fails validation, the records before it have already streamed
to stdout; the error goes to stderr and the exit status is non-zero:

```console
$ printf '[{"id": 1, "name": "Mango", "value": 2.0}, {"id": 2, "name": "   ", "value": 5.0}]' > /tmp/bad.json
$ datapipe /tmp/bad.json
{"id": 1, "name": "mango", "value": 2.2}
datapipe: error: record 2 has an empty name
$ echo $?
1
$ datapipe missing.json
datapipe: error: cannot read missing.json: No such file or directory
$ datapipe records.json --factor nan
usage: datapipe [-h] [--factor FACTOR] path
datapipe: error: argument --factor: must be a finite number, got 'nan'
$ echo $?
2
```

```console
$ datapipe --help
usage: datapipe [-h] [--factor FACTOR] path

Validate, normalize and scale a JSON array of records, printing one JSON
object per line.

positional arguments:
  path             path to a JSON array of records

options:
  -h, --help       show this help message and exit
  --factor FACTOR  multiplier applied to every value (default: 1.1)
```

## Testing

Install the dev tools, then run the same checks CI should run:

```bash
pip install -e ".[dev]"
ruff check .
ruff format --check .
mypy
pytest
```

`mypy` runs in strict mode over both `src/` and `tests/`. `pytest` measures
branch coverage and fails if it drops below 100%. The suite passes on
Python 3.12 and 3.13.

| Test module | What it covers |
| --- | --- |
| `test_pipeline.py` | step order, left-to-right composition, laziness, infinite input, a step failing mid-stream, `Normalize`, `Scale` (including the float-noise cases), structural Protocol conformance |
| `test_steps.py` | the ABC cannot be instantiated, subclasses inherit `run`, each validator's pass and fail cases (zero counts as non-positive) |
| `test_models.py` | `parse_record` accepts good input and rejects every malformed shape: wrong types, missing keys, `bool` ids, `NaN`, `Infinity`, and integers too large for a float |
| `test_cli.py` | `main()` in-process with `tmp_path` files, every error path and its message (including deeply nested JSON), `--factor` and its non-finite rejects, `python -m datapipe`, the installed console script, and subprocess end-to-end runs including a reader that closes the pipe early |

## Limitations and next steps

- **Input is not streamed.** The engine is lazy, but `load_records` parses the
  whole file with `json.load` before the first record runs. Reading JSON Lines
  from a file or stdin would keep memory flat end to end.
- **The first bad record ends the run.** There is no skip or dead-letter mode;
  a `--skip-invalid` flag that reports rejects to stderr would be a natural
  addition.
- **Steps cannot change the item type.** `Step[T]` maps `T -> T`. A step that
  turns a `Record` into something else would need a two-parameter
  `Step[In, Out]` and typed composition.
- **The pipeline is fixed in `cli.py`.** Only the scale factor is configurable
  from the command line.
- **Unknown keys are dropped** by `parse_record`, and `Normalize` only strips
  and lowercases (no internal whitespace collapsing or Unicode case folding).

# Log File Analyzer

A memory-constant log analysis pipeline built on Python generators.

The program answers one question — *"show me the first page of errors in a 100,000-line log"* — and answers it after reading **about 30 lines**, not 100,000. That gap is the entire point of the project: it is a working demonstration that lazy evaluation is not a style preference but a difference in how much work the machine does.

Standard library only. No dependencies. Covered by a pytest suite on Python 3.11–3.13, and clean under `ruff` and `mypy --strict`.

---

## Contents

- [Why this exists](#why-this-exists)
- [How it works](#how-it-works)
- [Project structure](#project-structure)
- [Getting started](#getting-started)
- [Example output](#example-output)
- [Testing](#testing)
- [Concepts demonstrated](#concepts-demonstrated)
- [Design notes](#design-notes)
- [Known limitations](#known-limitations)
- [Roadmap](#roadmap)

---

## Why this exists

The obvious way to analyze a log file is to read it into a list and then filter it:

```python
lines = open("app.log").readlines()          # entire file in memory
errors = [l for l in lines if "ERROR" in l]  # second full copy in memory
first_page = errors[:5]                      # 99,995 records computed and discarded
```

That works on a 4 MB file and fails on a 4 GB one. It also does an enormous amount of pointless work: to produce five records, it parses one hundred thousand.

This project builds the same feature as a chain of generators. Each stage pulls one record from the stage below it on demand, so memory use is constant regardless of file size, and only the records actually needed are ever parsed.

---

## How it works

Three composable stages, wired together in `main()`:

```
app.log ──> parse() ──> only(level="ERROR") ──> Paginator(page_size=5) ──> page
            generator     generator                iterator class
```

- **`parse(path, stats)`** — a generator that opens the file and `yield`s one `dict` per line (`ts`, `level`, `msg`). The file object is itself lazy, so the file is streamed line by line and never held in memory. Lines that don't split into date, time, level and message are skipped and counted rather than crashing the run, and the optional `ParseStats` object records how many lines were read and how many were malformed.
- **`only(records, level)`** — a filtering generator. Consumes the stage above it and re-yields only the records whose level matches.
- **`Paginator(iterable, page_size)`** — an iterator class implementing `__iter__` / `__next__`. It pulls items one at a time with `next()` and accumulates them into fixed-size lists, so it paginates a generator without ever materializing the full dataset. It calls `iter()` on its input, so a plain list works as well as a generator.

Nothing is read from disk until the final consumer asks for a page. Requesting one page of five errors walks the file only as far as the fifth error.

### The two passes

`main()` runs deliberately as two separate passes over the log:

**Pass 1 — the laziness proof.** Builds the full pipeline, pulls exactly one page, then reports how many lines were read to produce it. This is the measurement that makes the design claim falsifiable.

**Pass 2 — the full report.** Tallies records per level with `collections.Counter`. This requires a *fresh* `parse()` generator: the pass 1 generators are partially consumed and cannot be rewound, so they can never yield the lines pass 1 already read. That constraint is a property of generators, not a workaround. Each pass gets its own `ParseStats`, so pass 2's lines-read figure is the true file length rather than carrying pass 1's count on top.

The trade-off is explicit — pass 2 reads the file a second time. Laziness here means constant memory and minimal work *per pipeline*, not a single pass over the data. Those two passes are the only reads. Nothing touches the file before pass 1, so its figure is everything read at the moment the page prints. The file's length is not counted up front, because that would read every line before the "lazy" answer. Pass 2's lines-read figure is the length, and it is the number to compare pass 1's against.

---

## Project structure

```
log-file-analyzer/
├── analyzer.py           # the pipeline: parse -> only -> Paginator, timer(), main()
├── decorators.py         # @time_it and @retry, plus runnable demos
├── make_logs.py          # generates the synthetic 100,000-line app.log
├── tests/
│   ├── test_analyzer.py    # parse, only, Paginator edge cases, timer, main
│   ├── test_decorators.py  # @time_it and @retry
│   ├── test_make_logs.py   # the log generator
│   └── test_scripts.py     # end-to-end: runs both scripts as documented below
├── pyproject.toml        # pytest, ruff and mypy configuration
├── requirements-dev.txt  # dev tools (pytest, ruff, mypy); the scripts need none
└── README.md
```

`app.log` is generated, not committed. Run `make_logs.py` to create it.

---

## Getting started

Requires Python 3.11 or newer; tested on 3.11, 3.12 and 3.13. No third-party packages.

This project is one folder of the [python-deep-dive](https://github.com/subham-hq/python-deep-dive) repository:

```bash
git clone https://github.com/subham-hq/python-deep-dive.git
cd python-deep-dive/log-file-analyzer

python3 make_logs.py    # writes app.log — 100,000 lines, ~4.3 MB
python3 analyzer.py     # runs both passes
```

Both scripts write and read `app.log` in the current directory, so run them from this folder.

The decorators are independently runnable and print their own demos:

```bash
python3 decorators.py
```

The `@retry` demo fails at random on purpose: each attempt fails 70% of the time, so about one run in three uses up all three attempts and ends with the re-raised `ValueError` traceback.

---

## Example output

```text
first ERROR page ready after reading only 29 lines
first ERROR page:
  {'ts': '2026-06-11 10:01:01', 'level': 'ERROR', 'msg': 'payment processed'}
  {'ts': '2026-06-11 10:02:02', 'level': 'ERROR', 'msg': 'cache miss'}
  {'ts': '2026-06-11 10:18:18', 'level': 'ERROR', 'msg': 'invalid token'}
  {'ts': '2026-06-11 10:24:24', 'level': 'ERROR', 'msg': 'cache miss'}
  {'ts': '2026-06-11 10:28:28', 'level': 'ERROR', 'msg': 'timeout contacting service'}
Ready after reading 100000 lines (0 malformed, skipped)
Counter({'INFO': 50001, 'ERROR': 16782, 'DEBUG': 16672, 'WARNING': 16545})
main took 0.1152 seconds
[Timer] whole run: 0.1152 seconds
```

Lines 1 and 7 together are the result that matters. The five-record page took **29 lines**, and the full report confirms the file has **100,000**.

`make_logs.py` generates levels at random, so exact counts differ between runs. The level mix is weighted roughly 50% `INFO`, with `DEBUG`, `WARNING`, and `ERROR` each near 17%. With one line in six an `ERROR`, the first page of five takes 30 lines on average.

---

## Testing

Install the dev tools into a virtual environment, then run the three checks from this folder:

```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements-dev.txt

python -m pytest    # test suite
ruff check .        # lint
mypy                # strict type check of the scripts and the tests
```

Configuration for all three lives in `pyproject.toml`. The suite covers:

- **`parse()`** — field splitting, that it opens nothing until the first record is pulled and reads only as far as it is pulled, each kind of malformed line (blank, whitespace-only, truncated, mis-spaced) skipped and counted, and that two passes keep separate counts.
- **`only()` and `Paginator`** — empty input, an exact multiple of the page size, the final short page, a page larger than the input, invalid page sizes, staying exhausted, single use, and that one page pulls only one page's worth of items from its source.
- **`@time_it` and `@retry`** — arguments, return values and `__name__`/`__doc__` passed through; retry counts; no sleep after the final attempt; `KeyboardInterrupt` not retried; bad arguments rejected up front. `time.sleep` is patched out, so none of it actually waits.
- **`main()`** — the lines-read figure for each pass, a log with no errors, and the order of events. The tests record every line read and every print, then check that the first page prints after reading only its own lines and that the run reads the file exactly twice.
- **`make_logs.py`** — importing it writes nothing, and every line it generates parses cleanly.
- **End to end** — runs `make_logs.py` then `analyzer.py` as subprocesses in a temporary directory, exactly as in [Getting started](#getting-started).

---

## Concepts demonstrated

| Concept | Where | What it shows |
|---|---|---|
| Generator function | `parse()`, `only()` | `yield` for constant-memory streaming |
| Generator composition | `main()` | Stages chained into a pull-based pipeline |
| Iterator protocol | `Paginator` | `__iter__` / `__next__` implemented by hand, including raising `StopIteration` on exhaustion |
| Generator exhaustion | Pass 2 | Why a consumed generator must be rebuilt, not reused |
| Context manager | `timer()` | `@contextmanager` with `try/finally`, so the timing prints even if the block raises |
| Decorator | `@time_it` | Wrapping a call to measure it, with `functools.wraps` to preserve `__name__` and `__doc__` |
| Decorator factory | `@retry(times, delay)` | Three-level closure: factory returns decorator returns wrapper |
| Typed decorators | `@time_it`, `@retry` | `ParamSpec` and `TypeVar`, so a decorated function keeps its exact signature under `mypy --strict` |
| Generic class | `Paginator[T]` | Pages keep the item type of whatever they paginate |
| `collections.Counter` | Pass 2 | Missing keys default to `0`, so `+=` works without initialization |

---

## Design notes

**`perf_counter`, not `time.time`.** Both decorators and `timer()` use `time.perf_counter()` — monotonic and high-resolution. `time.time()` reads the wall clock, which can jump backwards on an NTP correction and quietly produce negative durations.

**`try/finally` in `timer()`.** This is the reason to use a context manager instead of a manual start/stop pair. If the timed block raises, the `finally` still reports the elapsed time and the exception still propagates.

**`retry` re-raises on the final attempt.** It does not swallow the exception once the attempts are used up. A retry decorator that hides the last failure is worse than no retry at all, because the caller believes the operation succeeded.

**`retry` is not used by the pipeline.** It ships as a demonstration of the decorator-factory pattern, exercised by the demo block in `decorators.py`. Log parsing is a local, deterministic operation with nothing to retry.

**A per-pass `ParseStats`, not a global counter.** `parse()` updates a small stats object as a side effect so the pipeline can report lines read without threading a count through every stage — only the source stage takes it. The caller creates one per pass, so one pass's numbers cannot leak into the next, which is exactly what a module-level counter did.

**Malformed lines are counted, not fatal.** One bad line in a large log should not cost the whole run. `parse()` skips any line that does not split into date, time, level and message, tallies it in `ParseStats.malformed`, and pass 2 reports the total.

---

## Known limitations

Stated plainly, because they define what this project is: a focused study of lazy evaluation, not a production log tool.

1. **The input path is hardcoded** to `"app.log"` inside `main()`. There is no CLI, so the level, page size, and file cannot be changed without editing source.
2. **`Paginator` is single-use.** Its `__iter__` returns `self`, so it is an iterator rather than a re-iterable container. A second loop over the same instance yields nothing.
3. **Malformed-line detection is structural only.** A line is accepted if it has a non-empty date, time and level followed by a message; the values themselves are not validated, so `2026-99-99 xx:yy NOTALEVEL hello` parses as a record.
4. **The log is synthetic.** Timestamps cycle within a single hour and messages are drawn at random, so levels and text are uncorrelated — `ERROR payment processed` is a valid line here. Real log analysis would surface patterns this data does not contain.

---

## Roadmap

In priority order. Each item started as a limitation; ticked items are done and covered by tests.

- [x] Make `parse()` fault-tolerant: skip malformed lines, count them, report the count
- [x] Replace the global `LINES_READ` counter with a per-pass `ParseStats` passed to `parse()`
- [x] Derive the line total instead of hardcoding it (pass 2 reports it, so pass 1 never waits on a full read)
- [ ] Add an `argparse` CLI for `--path`, `--level`, and `--page-size`
- [ ] Add a `--follow` mode that tails a live file, since a generator pipeline is the natural shape for streaming input
- [ ] Benchmark against the eager list-based implementation to quantify the memory difference, not just the line count
- [x] Add `pytest` coverage for pagination edges: empty input, exact multiples of page size, and the final short page

---

## License

MIT — see [LICENSE](../LICENSE) at the repository root.

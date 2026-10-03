# Log File Analyzer

A memory-constant log analysis pipeline built on Python generators.

The program answers one question — *"show me the first page of errors in a 100,000-line log"* — and answers it after reading **32 lines**, not 100,000. That gap is the entire point of the project: it is a working demonstration that lazy evaluation is not a style preference but a difference in how much work the machine does.

Standard library only. No dependencies.

---

## Contents

- [Why this exists](#why-this-exists)
- [How it works](#how-it-works)
- [Project structure](#project-structure)
- [Getting started](#getting-started)
- [Example output](#example-output)
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

- **`parse(path)`** — a generator that opens the file and `yield`s one `dict` per line (`ts`, `level`, `msg`). The file object is itself lazy, so the file is streamed line by line and never held in memory.
- **`only(records, level)`** — a filtering generator. Consumes the stage above it and re-yields only the records whose level matches.
- **`Paginator(iterable, page_size)`** — an iterator class implementing `__iter__` / `__next__`. It pulls items one at a time with `next()` and accumulates them into fixed-size lists, so it paginates a generator without ever materializing the full dataset.

Nothing is read from disk until the final consumer asks for a page. Requesting one page of five errors walks the file only as far as the fifth error.

### The two passes

`main()` runs deliberately as two separate passes over the log:

**Pass 1 — the laziness proof.** Builds the full pipeline, pulls exactly one page, then reports how many lines were read to produce it. This is the measurement that makes the design claim falsifiable.

**Pass 2 — the full report.** Tallies records per level with `collections.Counter`. This requires a *fresh* `parse()` generator: the pass 1 generators are partially consumed, and a consumed generator yields nothing. That constraint is a property of generators, not a workaround.

The trade-off is explicit — pass 2 reads the file a second time. Laziness here means constant memory and minimal work *per pipeline*, not a single pass over the data.

---

## Project structure

```
log-file-analyzer/
├── analyzer.py      # the pipeline: parse -> only -> Paginator, timer(), main()
├── decorators.py    # @time_it and @retry, plus runnable demos
├── make_logs.py     # generates the synthetic 100,000-line app.log
└── README.md
```

`app.log` is generated, not committed. Run `make_logs.py` to create it.

---

## Getting started

Requires Python 3.9 or newer. No third-party packages.

```bash
git clone https://github.com/<your-username>/log-file-analyzer.git
cd log-file-analyzer

python make_logs.py    # writes app.log — 100,000 lines, ~4.3 MB
python analyzer.py     # runs both passes
```

The decorators are independently runnable and print their own demos:

```bash
python decorators.py
```

---

## Example output

```text
first ERROR page ready after reading only 32 of 100000 lines
first ERROR page:
[{'ts': '2026-06-11 10:01:01', 'level': 'ERROR', 'msg': 'payment processed'},
 {'ts': '2026-06-11 10:02:02', 'level': 'ERROR', 'msg': 'db connection slow'},
 {'ts': '2026-06-11 10:07:07', 'level': 'ERROR', 'msg': 'user logged in'},
 {'ts': '2026-06-11 10:11:11', 'level': 'ERROR', 'msg': 'user logged in'},
 {'ts': '2026-06-11 10:31:31', 'level': 'ERROR', 'msg': 'cache miss'}]
Ready after reading 100032 lines
Counter({'INFO': 50301, 'DEBUG': 16654, 'WARNING': 16644, 'ERROR': 16401})
main took 0.0668 seconds
[Timer] whole run: 0.0668 seconds
```

Line 1 is the result that matters: **32 lines read out of 100,000** to produce a five-record page.

`make_logs.py` generates levels at random, so exact counts differ between runs. The level mix is weighted roughly 50% `INFO`, with `DEBUG`, `WARNING`, and `ERROR` each near 17%.

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
| `collections.Counter` | Pass 2 | Missing keys default to `0`, so `+=` works without initialization |

---

## Design notes

**`perf_counter`, not `time.time`.** Both decorators and `timer()` use `time.perf_counter()` — monotonic and high-resolution. `time.time()` reads the wall clock, which can jump backwards on an NTP correction and quietly produce negative durations.

**`try/finally` in `timer()`.** This is the reason to use a context manager instead of a manual start/stop pair. If the timed block raises, the `finally` still reports the elapsed time and the exception still propagates.

**`retry` re-raises on the final attempt.** It does not swallow the exception once the attempts are used up. A retry decorator that hides the last failure is worse than no retry at all, because the caller believes the operation succeeded.

**`retry` is not used by the pipeline.** It ships as a demonstration of the decorator-factory pattern, exercised by the demo block in `decorators.py`. Log parsing is a local, deterministic operation with nothing to retry.

**Module-level `LINES_READ`.** `parse()` increments a module-level counter as a side effect so the pipeline can report lines read without threading a count through every stage. This is a deliberate shortcut in service of the measurement, and it is the design decision in this codebase I would change first — see below.

---

## Known limitations

Stated plainly, because they define what this project is: a focused study of lazy evaluation, not a production log tool.

1. **`parse()` assumes every line is well-formed.** It unpacks four space-separated fields, so a blank or truncated line raises `ValueError: not enough values to unpack` and kills the whole run. A real analyzer would skip and count malformed lines instead of crashing on them.
2. **`LINES_READ` is not reset between passes.** The pass 2 figure reads `100032` rather than `100000` because it still carries pass 1's 32 lines. The number is off by exactly the amount pass 1 consumed.
3. **The line total is hardcoded.** `main()` prints `of 100000 lines` as a literal, so the message goes stale the moment the log size changes.
4. **The input path is hardcoded** to `"app.log"` inside `main()`. There is no CLI, so the level, page size, and file cannot be changed without editing source.
5. **`Paginator` is single-use.** Its `__iter__` returns `self`, so it is an iterator rather than a re-iterable container. A second loop over the same instance yields nothing.
6. **`make_logs.py` writes on import.** It has no `if __name__ == "__main__"` guard, so importing it overwrites `app.log` as a side effect.
7. **The log is synthetic.** Timestamps cycle within a single hour and messages are drawn at random, so levels and text are uncorrelated — `ERROR payment processed` is a valid line here. Real log analysis would surface patterns this data does not contain.

---

## Roadmap

In priority order — each item is a limitation above, turned into work:

- [ ] Make `parse()` fault-tolerant: skip malformed lines, count them, report the count
- [ ] Reset `LINES_READ` per pass, or replace the global with a counter passed through the pipeline
- [ ] Derive the line total instead of hardcoding it
- [ ] Add an `argparse` CLI for `--path`, `--level`, and `--page-size`
- [ ] Add a `--follow` mode that tails a live file, since a generator pipeline is the natural shape for streaming input
- [ ] Benchmark against the eager list-based implementation to quantify the memory difference, not just the line count
- [ ] Add `pytest` coverage for pagination edges: empty input, exact multiples of page size, and the final short page

---

## License

MIT

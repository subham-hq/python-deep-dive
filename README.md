# python-deep-dive

[![CI](https://github.com/subham-hq/python-deep-dive/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/subham-hq/python-deep-dive/actions/workflows/ci.yml)
[![Python 3.11 | 3.12 | 3.13](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-3776AB?logo=python&logoColor=white)](#quality-bar)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

> Small, tested Python projects on core language mechanics and backend
> fundamentals: generators, iterators, decorators and context managers;
> Protocols and generics under `mypy --strict`; asyncio, threads and processes;
> and two installable command-line tools. Python 3.11+ (datapipe needs 3.12+).
> No runtime dependencies outside the standard library, except aiohttp and
> httpx in one benchmark.

<!-- TODO(you): one or two sentences in your OWN words — what this repo is and why
     you're building it. Keep it true. Do NOT write "closed-book" for code you
     worked through with help; an interviewer who probes that will not enjoy it. -->

## Projects

<!-- This table is built by scripts/update_readme.py, and the Update README
     workflow re-runs it on pushes to main that change a README. Don't hand-edit
     between the markers. To change a row, edit that project's own README.md —
     the first heading becomes the title, the first line of text becomes the
     blurb. -->
<!-- PROJECTS:START -->

| Project | What it covers |
| --- | --- |
| [datapipe](./datapipe) | A tiny, fully typed data pipeline that validates, normalizes and scales JSON records through composable steps, using only the standard library. |
| [Expense Tracker](./expense-tracker) | A typed, tested command-line expense tracker built on the Python standard library, with exact decimal money and atomic saves. |
| [Log File Analyzer](./log-file-analyzer) | A memory-constant log analysis pipeline built on Python generators. |
| [notifier](./notifier) | Work in progress: this project is not implemented yet, and the package is currently an empty placeholder. |
| [Practice: asyncio, concurrency and OOP drills](./practice) | Small, runnable Python exercises on asyncio, threads vs. processes and the GIL, and OOP building blocks, plus a benchmark that makes 200 HTTP requests sequentially, with threads, and with asyncio. |

<!-- PROJECTS:END -->

## What to look at first

### Expense Tracker: crash-safe storage and exact money

- **Crash-safe saves.** `JSONStorage.save` in
  [`storage.py`](expense-tracker/src/expense_tracker/storage.py) writes to a
  temporary file in the same directory, `fsync`s it, then swaps it in with
  `os.replace`. Any failure, Ctrl-C included, removes the temporary file and
  leaves the old data alone. A test in
  [`test_storage.py`](expense-tracker/tests/test_storage.py) interrupts a save
  halfway and checks the original file byte for byte.
- **Exact money.** `to_money` in
  [`expense.py`](expense-tracker/src/expense_tracker/expense.py) accepts
  `Decimal`, `int` or a numeric string and rejects `float`, `bool`, NaN and
  infinity. It rounds half up to cents and checks the 10<sup>15</sup> limit both
  before and after rounding.
- **Storage behind a `Protocol`.** `ExpenseTracker` in
  [`tracker.py`](expense-tracker/src/expense_tracker/tracker.py) is handed any
  `Storage` and never names `JSONStorage`, so the tests inject an in-memory
  `MemoryStorage` instead ([`conftest.py`](expense-tracker/tests/conftest.py)).
- **Errors that say what is wrong.** One exception hierarchy
  ([`exceptions.py`](expense-tracker/src/expense_tracker/exceptions.py)); a bad
  record on load is reported with its position in the file, and
  [`cli.py`](expense-tracker/src/expense_tracker/cli.py) maps failures to
  distinct exit codes: 1 for a domain error such as bad input or a missing
  record, 2 for wrong usage, 130 for Ctrl-C and 141 for a closed pipe.

### Log File Analyzer: laziness you can measure

- **A pull-based pipeline.** [`analyzer.py`](log-file-analyzer/analyzer.py)
  chains two generators (`parse`, `only`) into a hand-written iterator class
  (`Paginator`). The first page of five errors in a 100,000-line log is ready
  after reading about 30 lines.
- **The claim is tested.** A test in
  [`test_analyzer.py`](log-file-analyzer/tests/test_analyzer.py) swaps in a
  recording `open()` and `print()`, then asserts that only the page's 5 lines
  are read before the first output, and 105 lines in total (5 for the page,
  100 for the full count).
- **Typed decorators.** `@time_it` and the `@retry(times, delay)` factory in
  [`decorators.py`](log-file-analyzer/decorators.py) use `ParamSpec`, so a
  decorated function keeps its exact signature under `mypy --strict`.

### datapipe: Protocols, ABCs and generics

- **Structural and nominal interfaces side by side.** In
  [`pipeline.py`](datapipe/src/datapipe/pipeline.py), `Step[T]` is a
  `Protocol` written with PEP 695 generics, and `Normalize` and `Scale` satisfy
  it without inheriting anything. In [`steps.py`](datapipe/src/datapipe/steps.py)
  the validators share behaviour through a template-method ABC. One generic,
  generator-based `Pipeline[T]` runs both; a test feeds it `itertools.count()`.
- **One boundary for untyped data.** `parse_record` in
  [`models.py`](datapipe/src/datapipe/models.py) turns raw JSON into a `Record`
  `TypedDict`, rejecting `bool` ids, NaN, infinity and integers too large for a
  float. The test suite fails below 100% branch coverage.

### practice/async-lab: asyncio semantics, demonstrated

- **Cancellation.** [`03_cancellation.py`](practice/async-lab/03_cancellation.py)
  shows that `except Exception` does not catch `CancelledError`, and that a
  coroutine which swallows it leaves `task.cancelled()` as `False`.
- **Timeouts.** [`04_timeout.py`](practice/async-lab/04_timeout.py) nests
  `asyncio.timeout()` and `asyncio.wait_for()`, shows where each one raises
  `TimeoutError`, and why the `try` has to wrap the `async with`.
- **The GIL.** [`06_gil_and_executors.py`](practice/async-lab/06_gil_and_executors.py)
  runs one CPU-bound job sequentially, with `to_thread()`, with a thread pool
  and with a process pool. Threads give no speed-up; only the process pool is
  faster.
- **A benchmark with its pitfalls written up.** The
  [fetch benchmark](practice/README.md#fetch-benchmark) sends 200 requests to a
  local server that answers each one after 50 ms. Sequential clients take just
  over 10 s (200 × 50 ms); 200 threads or asyncio take under 0.25 s on a 4-vCPU
  VM. Its README also documents two setup costs that were first being timed as
  network I/O.

## Quick start

Needs Python 3.11 or newer as `python3`. The log analyzer runs with no
install:

```bash
git clone https://github.com/subham-hq/python-deep-dive.git
cd python-deep-dive/log-file-analyzer

python3 make_logs.py    # writes app.log: 100,000 random log lines
python3 analyzer.py     # first page of errors (lazily), then a full count
```

```text
wrote app.log
first ERROR page ready after reading only 31 lines
first ERROR page:
  {'ts': '2026-06-11 10:03:03', 'level': 'ERROR', 'msg': 'db connection slow'}
  {'ts': '2026-06-11 10:11:11', 'level': 'ERROR', 'msg': 'timeout contacting service'}
  {'ts': '2026-06-11 10:14:14', 'level': 'ERROR', 'msg': 'cache miss'}
  {'ts': '2026-06-11 10:23:23', 'level': 'ERROR', 'msg': 'timeout contacting service'}
  {'ts': '2026-06-11 10:30:30', 'level': 'ERROR', 'msg': 'cache miss'}
Ready after reading 100000 lines (0 malformed, skipped)
Counter({'INFO': 50068, 'WARNING': 16762, 'DEBUG': 16605, 'ERROR': 16565})
main took 0.0756 seconds
[Timer] whole run: 0.0756 seconds
```

The log is random, so the counts change from run to run.

The expense tracker is an installable package with a console script:

```bash
cd ../expense-tracker
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest                  # test suite with a branch-coverage report

expense-tracker --data /tmp/demo.json add "Chai" 20 -c Food -d 2026-01-05
expense-tracker --data /tmp/demo.json add "Rent" 12000 -c Housing -d 2026-02-01
expense-tracker --data /tmp/demo.json report category
```

```text
Added #1: Chai (₹20.00)
Added #2: Rent (₹12,000.00)
Spending by Category
================================================
Category          Count           Total    Share
------------------------------------------------
Housing               1      ₹12,000.00    99.8%
Food                  1          ₹20.00     0.2%
------------------------------------------------
TOTAL                 2      ₹12,020.00
```

For the other two, see the setup steps in the
[datapipe](datapipe/README.md#install-and-run) and
[practice](practice/README.md#development) READMEs.

## Repository layout

```text
python-deep-dive/
├── .github/workflows/
│   ├── ci.yml                 # lint, format, type-check and test each project
│   └── update-readme.yml      # regenerates the Projects table above
├── datapipe/                  # installable package (src/ layout), `datapipe` command
├── expense-tracker/           # installable package (src/ layout), `expense-tracker` command
├── log-file-analyzer/         # standalone scripts, no install needed
├── notifier/                  # placeholder, not implemented yet
├── practice/
│   ├── async-lab/             # asyncio, threads vs. processes, fetch benchmark
│   └── oop/                   # iterator protocol and decorators in small classes
├── scripts/update_readme.py   # builds the Projects table from each project's README
├── .pre-commit-config.yaml    # ruff and file-hygiene git hooks for the whole repo
└── LICENSE
```

Each project with code is self-contained: its own README, its own
`pyproject.toml` with ruff, mypy and pytest settings, and its own `tests/`
folder. Run a project's commands from inside its folder.

## Quality bar

[`ci.yml`](.github/workflows/ci.yml) runs one job per project on every push to
`main` and every pull request. Each job runs inside the project's folder, so
that project's own `pyproject.toml` settings apply.

| Project | Python | Lint | Format | Types | Tests |
| --- | --- | --- | --- | --- | --- |
| datapipe | 3.12, 3.13 | `ruff check` | `ruff format --check` | `mypy`, strict | `pytest`, fails below 100% branch coverage |
| expense-tracker | 3.11, 3.12, 3.13 | `ruff check` | `ruff format --check` | `mypy`, strict | `pytest`, fails below 90% branch coverage (currently 100%) |
| log-file-analyzer | 3.11, 3.12, 3.13 | `ruff check` | not run | `mypy`, strict | `pytest` |
| practice | 3.11, 3.12, 3.13 | `ruff check` | `ruff format --check` | `mypy`, strict | `pytest` |
| scripts | 3.12 | `ruff check` | `ruff format --check` | `mypy --strict` | runs `update_readme.py` once |

- **mypy is strict everywhere**, and it checks the tests as well as the code
  (`strict = true` in each `pyproject.toml`, `--strict` for `scripts/`).
- **log-file-analyzer is linted but not auto-formatted**, because it keeps
  hand-aligned end-of-line comments.
- **Ruff and basic file-hygiene checks also run as git hooks.** From the
  repository root: `pip install pre-commit && pre-commit install` (see
  [`.pre-commit-config.yaml`](.pre-commit-config.yaml)).

## Roadmap

A structured backend-engineering study plan. Boxes are checked only when the
work is actually in the repo.

- [x] Decorators, iterators, generators, context managers
  ([log-file-analyzer](log-file-analyzer), [practice/oop](practice/oop))
- [x] Typing: `mypy --strict` runs in CI on every project that has code
  (`notifier` is still an empty placeholder)
- [x] `asyncio` ([practice/async-lab](practice/async-lab))

<!-- TODO(you): add the capstone project here (name + link) once it ships.
     Keep this list honest — it's the first thing a reviewer cross-checks
     against the actual folders. -->

## License

Released under the [MIT License](LICENSE).

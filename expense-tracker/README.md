# Expense Tracker

<!-- ─────────────────────────────────────────────────────────────────────
     Coming Soon:
       1. Replace the one-line description below.
       2. Write the "Why I built this" section.
       3. Add the CI badge once the repo is pushed:
          ![CI](https://github.com/subham-hq/expense-tracker/actions/workflows/ci.yml/badge.svg)
     Everything else is technical reference and is ready to ship.
     ───────────────────────────────────────────────────────────────────── -->

A command-line expense tracker built on the Python standard library — typed,
tested, and durable against interrupted writes.

## Why I built this

<!-- TODO: your paragraph. What you set out to learn, what you'd do
     differently, what surprised you. Keep it honest and specific. -->

## Install

```bash
git clone https://github.com/subham-hq/expense-tracker.git
cd expense-tracker
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

This installs an `expense-tracker` command on your `PATH`.

## Usage

```bash
expense-tracker add "Diesel" 2500.50 -c Fuel -d 2026-01-20 -m "tank refill"

expense-tracker list                      # everything, oldest first
expense-tracker list -c Food              # one category
expense-tracker list --month 2026-01      # one calendar month
expense-tracker list -n 10                # the 10 most recent

expense-tracker show 42                   # one expense in full
expense-tracker remove 42

expense-tracker total                     # grand total
expense-tracker total -c Fuel             # one category

expense-tracker report summary            # count, total, mean, date range
expense-tracker report category           # per-category totals and shares
expense-tracker report monthly            # per-month totals

expense-tracker categories                # categories currently in use
```

Data lives at `~/.expense-tracker/expenses.json` by default. Override it with
`--data PATH` — useful for keeping separate ledgers, and what the test suite
uses.

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | A domain error — bad input, missing record, unreadable file |
| `2` | Wrong command-line usage |
| `130` | Interrupted with Ctrl-C |

## Architecture

```
cli.py          Argument parsing and all printing. The only layer that
                knows a terminal exists.
      │
tracker.py      ExpenseTracker — the in-memory collection. Owns transaction
                ID assignment. Depends on the Storage protocol, not on any
                concrete storage class.
      │
storage.py      Storage protocol + JSONStorage (atomic writes) and
                MemoryStorage (tests). The boundary where untyped JSON
                becomes typed Expense objects.
      │
expense.py      The Expense model. Validation lives in property setters, so
                an invalid Expense cannot exist.

reports.py      Report ABC + three concrete reports, selected by name at
                runtime.
exceptions.py   One hierarchy rooted at ExpenseError.
```

## Design decisions

**Money is `Decimal`, and `float` is rejected outright.** `0.1 + 0.2` is not
`0.3` in binary floating point, and the error compounds across a ledger.
Amounts are quantised to two places with `ROUND_HALF_UP` — Python's default
is banker's rounding, which turns 2.5 into 2. Accepting `float` at the
boundary would silently reintroduce the problem, so `to_money` takes
`Decimal`, `int`, or a numeric string and refuses anything else.

**Saves are atomic.** Writing straight into the target file with mode `"w"`
truncates it before the new bytes arrive; an interruption in that window
leaves a half-written file and no way back to the old data. `JSONStorage.save`
writes to a temporary file in the same directory, `fsync`s it, and then calls
`os.replace`, which is atomic on POSIX and Windows. A reader sees either the
complete old file or the complete new one, never a fragment.

**Storage is a `Protocol`, injected into the tracker.** The tracker never
names `JSONStorage`. Tests inject `MemoryStorage` and run without touching
the disk; adding a SQLite backend later would require no change to the
tracker.

**Domain exceptions propagate; only foreign errors get wrapped.** A bare
`except:` in the loader used to convert every failure — a bad date, a missing
file, even Ctrl-C — into one generic "could not load" message. Now `OSError`
and `JSONDecodeError` are wrapped with `raise ... from e` so the cause stays
on the traceback, and validation errors travel to the surface untouched. A
corrupt record reports *which* record and *what* is wrong with it.

**The domain layer returns data; the CLI prints it.** `tracker.save()` returns
`None` rather than a message like `"Saved 3 expenses to ..."`. Formatting for
a human is presentation, and presentation lives in one place.

**Dates are `datetime.date` in memory, ISO strings on disk.** Sorting and
month filtering are date operations, not string operations. The JSON format
is unchanged, so data files written by earlier versions load as-is.

## Development

```bash
ruff check .        # lint
ruff format .       # format
mypy                # strict type check, src and tests
pytest              # test suite with coverage gate
```

CI runs all three on Python 3.11, 3.12, and 3.13. `pre-commit install` runs
them locally before each commit.

## License

MIT

# Expense Tracker

A typed, tested command-line expense tracker built on the Python standard library, with exact decimal money and atomic saves.

<!-- TODO(you): a short paragraph on why you built this: what you set out to
     learn, what you would do differently, what surprised you. Keep it honest
     and specific. -->

- **No runtime dependencies.** Standard library only.
- **Exact money.** Amounts are `Decimal`, rounded half up to two places;
  `float` is rejected at the boundary.
- **Crash-safe saves.** Each save writes a temporary file, `fsync`s it, and
  swaps it in with `os.replace`, so an interrupted save never corrupts the
  ledger.
- **Strictly typed.** `mypy --strict` passes on `src/` and `tests/`, and the
  package ships a `py.typed` marker.
- **Tested.** Every `pytest` run enforces at least 90% branch coverage
  (currently 100%). Lint, format, type and test checks pass on Python 3.11,
  3.12 and 3.13.

## Quick start

```console
$ expense-tracker add "Chai" 20 -c Food -d 2026-01-05
Added #1: Chai (₹20.00)
$ expense-tracker add "Diesel" 2500.50 -c Fuel -d 2026-01-20 -m "tank refill"
Added #2: Diesel (₹2,500.50)
$ expense-tracker add "Rent" 12000 -c Housing -d 2026-02-01
Added #3: Rent (₹12,000.00)
$ expense-tracker add "Lunch" 480.25 -c Food -d 2026-02-11
Added #4: Lunch (₹480.25)

$ expense-tracker list
1 | 2026-01-05 | Chai | Food | ₹20.00
2 | 2026-01-20 | Diesel | Fuel | ₹2,500.50
3 | 2026-02-01 | Rent | Housing | ₹12,000.00
4 | 2026-02-11 | Lunch | Food | ₹480.25
------------------------------------------------------------
4 expense(s), ₹15,000.75

$ expense-tracker report category
Spending by Category
================================================
Category          Count           Total    Share
------------------------------------------------
Housing               1      ₹12,000.00    80.0%
Fuel                  1       ₹2,500.50    16.7%
Food                  2         ₹500.25     3.3%
------------------------------------------------
TOTAL                 4      ₹15,000.75

$ expense-tracker add "Chai" 20 -c Food -d 2026-02-30
Error: Invalid date: '2026-02-30'. Date must be a real calendar date in YYYY-MM-DD format.
```

## Install

Requires Python 3.11 or newer. The project lives in the `expense-tracker/`
folder of the [python-deep-dive](https://github.com/subham-hq/python-deep-dive)
repository.

```bash
git clone https://github.com/subham-hq/python-deep-dive.git
cd python-deep-dive/expense-tracker
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

This installs an `expense-tracker` command on your `PATH`, plus the
development tools. To install just the command, straight from GitHub:

```bash
pip install "git+https://github.com/subham-hq/python-deep-dive.git#subdirectory=expense-tracker"
```

`python -m expense_tracker` works too, and takes the same arguments.

## Usage

```bash
expense-tracker add "Diesel" 2500.50 -c Fuel -d 2026-01-20 -m "tank refill"

expense-tracker list                      # everything, oldest first
expense-tracker list -c Food              # one category (case-insensitive)
expense-tracker list --month 2026-01      # one calendar month
expense-tracker list -n 10                # the 10 most recent

expense-tracker show 2                    # one expense in full
expense-tracker remove 2

expense-tracker total                     # grand total
expense-tracker total -c Fuel             # one category

expense-tracker report summary            # count, total, mean, date range
expense-tracker report category           # per-category totals and shares
expense-tracker report monthly            # per-month totals

expense-tracker categories                # categories currently in use
```

Run `expense-tracker --help`, or `expense-tracker <command> --help`, for every
option.

### Data file

Data lives at `~/.expense-tracker/expenses.json` by default. Pass `--data PATH`
before the command to use a different file, for example to keep separate
ledgers:

```bash
expense-tracker --data ~/ledgers/work.json add "Train" 150 -c Travel -d 2026-03-02
```

The file is a plain JSON array. Amounts are stored as strings, so no binary
floating point ever touches them:

```json
[
    {
        "txn_id": 1,
        "date": "2026-01-05",
        "title": "Chai",
        "category": "Food",
        "amount": "20.00",
        "description": ""
    }
]
```

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | A domain error: bad input, missing record, unreadable or unwritable file |
| `2` | Wrong command-line usage |
| `130` | Interrupted with Ctrl-C |
| `141` | Output pipe closed early, as in `expense-tracker list \| head` |

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
main.py         Console-script entry point: turns cli.main's return value
                into the process exit status. __main__.py reuses it for
                `python -m expense_tracker`.
```

## Design decisions

**Money is `Decimal`, and `float` is rejected outright.** `0.1 + 0.2` is not
`0.3` in binary floating point, and the error compounds across a ledger.
Amounts are quantised to two places with `ROUND_HALF_UP` — Python's default
is banker's rounding, which turns 2.5 into 2. Accepting `float` at the
boundary would silently reintroduce the problem, so `to_money` takes
`Decimal`, `int`, or a numeric string and refuses anything else. Amounts must
also be below 10<sup>15</sup> after rounding. `Decimal` works to 28
significant digits by default, so under that limit any ledger of up to
10<sup>11</sup> expenses totals exactly.

**Saves are atomic.** Writing straight into the target file with mode `"w"`
truncates it before the new bytes arrive; an interruption in that window
leaves a half-written file and no way back to the old data. `JSONStorage.save`
writes to a temporary file in the same directory, `fsync`s it, and then calls
`os.replace`, which is atomic on POSIX and Windows. A reader sees either the
complete old file or the complete new one, never a fragment. Any failure
along the way, including creating the directory or the temporary file,
surfaces as a `SaveError` and leaves the old file untouched.

**Storage is a `Protocol`, injected into the tracker.** The tracker never
names `JSONStorage`. Tests inject `MemoryStorage` and run without touching
the disk; adding a SQLite backend later would require no change to the
tracker.

**Domain exceptions propagate; only foreign errors get wrapped.** A bare
`except:` in the loader used to convert every failure — a bad date, a missing
file, even Ctrl-C — into one generic "could not load" message. Now `OSError`,
`UnicodeDecodeError` and `JSONDecodeError` are wrapped with `raise ... from e`
so the cause stays on the traceback, and validation errors travel to the
surface untouched. A corrupt record reports *which* record and *what* is
wrong with it: shape problems (a missing field, a non-integer or duplicate
`txn_id`) raise `CorruptRecordError` with the record's position, and value
problems keep their own type and gain an exception note naming the record,
which the CLI prints.

**The domain layer returns data; the CLI prints it.** `tracker.save()` returns
`None` rather than a message like `"Saved 3 expenses to ..."`. Formatting for
a human is presentation, and presentation lives in one place.

**Dates are `datetime.date` in memory, ISO strings on disk.** Sorting and
month filtering are date operations, not string operations. On disk a date is
still a plain `YYYY-MM-DD` string, so moving to `date` objects in memory
needed no data migration.

## Known limitations

- **IDs can be reissued across runs.** IDs are unique among stored records
  and never repeat within one process. The file stores only the records,
  though, so if the highest-numbered expense is removed, a later `add` can
  receive that number again. SQLite rowids without `AUTOINCREMENT` behave the
  same way.
- **One bad record blocks the whole file.** Every record is validated on
  load, by the same rules as new input, and each `txn_id` must be an integer
  (or `null`) that no other record uses. A record that fails, such as one
  with an amount of 10<sup>15</sup> or more, stops every command with an
  error that gives the record's position in the file. It then has to be
  fixed or deleted in the JSON by hand. `expense-tracker` never saves such a
  record itself. A hand-edited file can contain one, and so can a file that
  stored an amount of 10<sup>15</sup> or more before that limit was added.
- **No file locking.** Two `expense-tracker` processes writing the same file
  at the same moment do not corrupt it, but the last save wins.
- **One currency.** Amounts are always displayed in rupees (₹).

## Development

Run these from the `expense-tracker/` folder:

```bash
ruff check .              # lint
ruff format --check .     # formatting (drop --check to apply it)
mypy                      # strict type check of src/ and tests/
pytest                    # test suite and coverage report; fails below 90%
```

CI runs the same four commands on Python 3.11, 3.12 and 3.13. Running
`pre-commit install` once, anywhere in the repository, adds git hooks for ruff
and basic file hygiene from the repository-wide
[`.pre-commit-config.yaml`](../.pre-commit-config.yaml).

## License

MIT. See [LICENSE](../LICENSE) at the repository root.

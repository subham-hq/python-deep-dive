# python-deep-dive

A hands-on study of core Python internals — the language machinery that
FastAPI, async frameworks, and production codebases are built on. Each
concept is implemented by hand before reaching for the standard-library
shortcut, written closed-book, and verified on Python 3.12.

This is a learning repository. The goal is depth — understanding *why* a
generator is lazy and *what* a context manager guarantees — not just
using them.

## Topics

- **Decorators** — parameterized decorators (`@retry(times, delay)`),
  `functools.wraps`, the three-level closure structure
- **Iterators** — the `__iter__` / `__next__` protocol, built by hand
- **Generators** — lazy evaluation, `yield`, generator pipelines
- **Context managers** — both the class form (`__enter__` / `__exit__`)
  and `@contextmanager`, with cleanup guaranteed on exceptions

## Capstone — Log Analyzer

A lazy log-processing pipeline that ties every topic together. It reads a
100,000-line log file, filters and paginates entries, and times itself —
while reading only as many lines as the result actually requires.

```
first ERROR page ready after reading only 32 of 100000 lines
INFO     50301
DEBUG    16654
WARNING  16644
ERROR    16401
main took 0.0340 seconds
[Timer] whole run: 0.0340 seconds
```

Producing a 5-item page after reading 32 lines — instead of loading all
100,000 into memory — is the entire point. That is what laziness buys.

The pipeline (`parse → filter → paginate`) is built from a generator, a
filtering generator, and a hand-rolled `Paginator` iterator. Timing comes
from a custom `@time_it` decorator and a `Timer` context manager.

## Running

```bash
cd log-analyzer
python make_logs.py     # generates app.log (100,000 lines)
python analyzer.py      # runs the pipeline
python decorators.py    # runs the decorator demos directly
```

Python 3.12+. No third-party dependencies.

## Status

Active. Built as part of a structured backend-engineering roadmap
(Deep Python phase). Topics are added as they're worked through —
typing/`mypy` and `asyncio` are next, with full type annotations
applied to the existing code in that pass.

# Practice: asyncio, concurrency and OOP drills

Small, runnable Python exercises on asyncio, threads vs. processes and the GIL, and OOP building blocks, plus a benchmark that makes 200 HTTP requests sequentially, with threads, and with asyncio.

<!-- TODO(you): optional, one or two sentences in your own words on what you were
     practising here. Keep it true. -->

Each script is self-contained: run it, read the output, then read the notes in its comments. Python 3.11+ (the scripts use `asyncio.TaskGroup`, `asyncio.timeout()` and `except*`). Everything uses only the standard library except the fetch benchmark, which needs `aiohttp` and `httpx` ([`requirements.txt`](requirements.txt)).

Lint-clean under `ruff`, type-clean under `mypy --strict`, and covered by a pytest suite that passes on Python 3.11, 3.12 and 3.13. See [Development](#development).

## Layout

```text
practice/
├── async-lab/
│   ├── 01_gather_vs_taskgroup.py
│   ├── 02_semaphore_bound.py
│   ├── 03_cancellation.py
│   ├── 04_timeout.py
│   ├── 05_blocking_call.py
│   ├── 06_gil_and_executors.py
│   └── fetch-benchmark/
│       ├── server.py                # aiohttp server: every request takes 50 ms
│       ├── bench_fetch_urllib.py    # sequential, standard library
│       ├── bench_fetch_httpx.py     # sequential, httpx with one shared client
│       ├── bench_fetch_threaded.py  # 200 threads
│       └── bench_fetch_asyncio.py   # asyncio + aiohttp, concurrency limit from argv
├── oop/
│   ├── library_book_lending_system.py
│   └── task_manager.py
├── tests/                           # pytest suite for all of the above
├── pyproject.toml                   # ruff, mypy and pytest settings
├── requirements.txt                 # aiohttp, httpx (fetch benchmark only)
└── requirements-dev.txt             # + ruff, mypy, pytest
```

## Exercises

Run each command from this `practice/` folder.

| Exercise | What it demonstrates | Run | Takes |
| --- | --- | --- | --- |
| Gather vs. TaskGroup | `gather(return_exceptions=True)` returns a failing job's error as a value and lets the rest finish; `TaskGroup` cancels the siblings and raises an `ExceptionGroup`, handled with `except*`. | `python async-lab/01_gather_vs_taskgroup.py` | up to 10 s (random sleeps) |
| Bounded concurrency | `asyncio.Semaphore(10)` over 99 jobs; tracks and prints the peak number running at once (10). | `python async-lab/02_semaphore_bound.py` | ~3 s |
| Cancellation | `task.cancel()` raises `CancelledError` inside the coroutine; `except Exception` does not catch it, and swallowing it leaves `task.cancelled()` False. | `python async-lab/03_cancellation.py` | ~1 s |
| Timeouts | `asyncio.timeout()` vs. `asyncio.wait_for()`: where each raises `TimeoutError`, and what happens when both are nested. | `python async-lab/04_timeout.py` | ~8 s |
| Blocking calls | A blocking `time.sleep()` moved to a `ProcessPoolExecutor` with `run_in_executor()`, so 18 other tasks keep running; started with `asyncio.run(debug=True)`. | `python async-lab/05_blocking_call.py` | ~18 s |
| GIL and executors | The same CPU-bound job run sequentially, with `to_thread()`, with a `ThreadPoolExecutor` and with a `ProcessPoolExecutor`. The module docstring is a set of notes on the GIL, threads, processes and executors. | `python async-lab/06_gil_and_executors.py` | ~2.5 s |
| Fetch benchmark | 200 requests to a local 50 ms server: sequential (urllib, httpx), 200 threads, and asyncio with a concurrency limit. | [see below](#fetch-benchmark) | 0.1–11 s per script |
| Library lending system | A class with a custom iterator (`__iter__` / `__next__`) and a logging decorator; borrowing a borrowed book or an unknown title raises. | `python oop/library_book_lending_system.py` | ~2 s (deliberate "..." delay) |
| Task manager | The same iterator/iterable split and a timing decorator built with `functools.wraps`. | `python oop/task_manager.py` | instant |

## GIL and executors: sample output

`06_gil_and_executors.py` counts the primes below 100,000 seven times, four different ways. One run on a 4-vCPU Linux VM with Python 3.12 (numbers vary by machine):

```text
no_concurrency took 0.7045 second(s)
[9592, 9592, 9592, 9592, 9592, 9592, 9592]
with_to_thread took 0.8676 second(s)
[9592, 9592, 9592, 9592, 9592, 9592, 9592]
with_thread_pool took 0.7266 second(s)
[9592, 9592, 9592, 9592, 9592, 9592, 9592]
with_process_pool took 0.2103 second(s)
[9592, 9592, 9592, 9592, 9592, 9592, 9592]
main took 2.5093 second(s)
```

Threads give no speed-up on CPU-bound work, because the GIL lets only one thread run Python bytecode at a time. Worker processes each have their own interpreter and GIL, so they run in parallel: about 3.3x faster here on 4 cores.

## Fetch benchmark

`server.py` answers every request with `OK` after a 50 ms `asyncio.sleep`. Each client makes 200 requests and reports how many succeeded and how long they took.

```bash
pip install -r requirements.txt
cd async-lab/fetch-benchmark

# terminal 1: start the server and leave it running (Ctrl+C to stop)
python server.py

# terminal 2: run the clients
python bench_fetch_urllib.py
python bench_fetch_httpx.py
python bench_fetch_threaded.py
python bench_fetch_asyncio.py      # concurrency limit 200 (the default)
python bench_fetch_asyncio.py 5    # or any other limit
```

Each client prints three lines:

```text
Completed 200 requests
Successful: 200
Elapsed time: 10.349 s
```

The asyncio client also prints its limit first (`Semaphore: 200`).

### Results

Three runs of each script on a 4-vCPU Linux VM (Intel Xeon @ 2.80 GHz) with Python 3.12, aiohttp 3.14.3 and httpx 0.28.1. All 200 requests succeeded in every run. **Numbers vary by machine**, so treat the ratios as the result, not the absolute times.

| Script | Strategy | In flight at once | Elapsed (min–max of 3 runs) |
| --- | --- | --- | --- |
| `bench_fetch_urllib.py` | `urlopen()` in a loop, new connection per request | 1 | 10.349–10.371 s |
| `bench_fetch_httpx.py` | `httpx.Client` in a loop, one reused connection | 1 | 10.515–10.545 s |
| `bench_fetch_threaded.py` | `urlopen()` in a `ThreadPoolExecutor(200)` | 200 | 0.163–0.204 s |
| `bench_fetch_asyncio.py 5` | aiohttp + `asyncio.Semaphore(5)` | 5 | 2.081–2.085 s |
| `bench_fetch_asyncio.py 20` | aiohttp + `asyncio.Semaphore(20)` | 20 | 0.528–0.530 s |
| `bench_fetch_asyncio.py 50` | aiohttp + `asyncio.Semaphore(50)` | 50 | 0.227–0.235 s |
| `bench_fetch_asyncio.py 100` | aiohttp + `asyncio.Semaphore(100)` | 100 | 0.136–0.144 s |
| `bench_fetch_asyncio.py` (200) | aiohttp + `asyncio.Semaphore(200)` | 100 (see below) | 0.135–0.139 s |

What the numbers show:

- **Sequential clients hit the 10 s floor** (200 × 50 ms). Reusing one httpx connection is no faster than urllib opening a new one each time: the server's 50 ms dominates either way.
- **With asyncio, time tracks the limit**: about (200 / limit) × 50 ms, down to a limit of 100.
- **Limits above 100 change nothing**, because an aiohttp `ClientSession` opens at most 100 connections at once by default (`TCPConnector(limit=100)`). At 200 it is still two rounds of 50 ms, plus overhead.
- **Threads come close to asyncio at this scale**: 200 threads took 0.16–0.20 s against asyncio's 0.14 s. This benchmark stops at 200 concurrent requests; it does not test the thousands-of-connections range, where per-thread memory and scheduling costs come into play.

### Two setup costs that were being timed as I/O

Two of the clients originally measured object setup rather than network waiting. Both are fixed. The "before" numbers are from runs of the original code on the same machine with Python 3.12: three runs for httpx, and ten for the threaded client, whose time varied widely.

| Script | Problem | Before | After |
| --- | --- | --- | --- |
| `bench_fetch_threaded.py` | `urlopen()` builds its shared opener lazily on first use, so threads making their first call at the same moment can each build their own. On Python 3.12+ building an opener also creates an SSL context (about 25 ms of CPU), and with 200 threads 40–120 openers were built instead of one. On Python 3.11 building an opener is cheap, so the slowdown does not appear: the original code already took 0.15–0.19 s there. The opener is now built once before the timer starts, which is correct on every version. | 0.86–4.77 s | 0.163–0.204 s |
| `bench_fetch_httpx.py` | A new `httpx.Client` was created for every request (about 50 ms each) and its connection discarded. The script now uses one client for all 200 requests. | 20.586–21.447 s | 10.515–10.545 s |

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

ruff check .            # lint
ruff format --check .   # formatting
mypy                    # --strict, settings in pyproject.toml
pytest                  # 34 tests, about 2 s
```

All four pass on Python 3.11, 3.12 and 3.13. The tests import each script as a module (the numbered `async-lab` files through `importlib`, since their names start with a digit). The fetch-benchmark tests start `server.py`'s app on a free port in a background thread and point every client at it with 5 requests instead of 200. They are skipped if `aiohttp` or `httpx` is not installed.

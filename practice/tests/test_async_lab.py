"""Fast checks for the numbered async-lab scripts.

The scripts' file names start with a digit, so they cannot be imported with a
plain `import` statement; importlib.import_module() accepts any file name.
"""

import asyncio
import importlib
import inspect
import re

import pytest

gather_vs_taskgroup = importlib.import_module("01_gather_vs_taskgroup")
semaphore_bound = importlib.import_module("02_semaphore_bound")
cancellation = importlib.import_module("03_cancellation")
timeout = importlib.import_module("04_timeout")
blocking_call = importlib.import_module("05_blocking_call")
gil_and_executors = importlib.import_module("06_gil_and_executors")

TIMING_LINE = r"{name} took \d+\.\d{{4}} second\(s\)\n"


# --------------------------------------------------------------- time_it ----


def test_time_it_wraps_sync_functions(capsys: pytest.CaptureFixture[str]) -> None:
    def add(a: int, b: int) -> int:
        return a + b

    timed = gather_vs_taskgroup.time_it(add)
    assert timed(2, 3) == 5
    assert timed.__name__ == "add"
    assert not inspect.iscoroutinefunction(timed)
    assert re.fullmatch(TIMING_LINE.format(name="add"), capsys.readouterr().out)


def test_time_it_wraps_async_functions(capsys: pytest.CaptureFixture[str]) -> None:
    async def fetch() -> str:
        await asyncio.sleep(0)
        return "done"

    timed = gather_vs_taskgroup.time_it(fetch)
    assert inspect.iscoroutinefunction(timed)
    assert asyncio.run(timed()) == "done"
    assert re.fullmatch(TIMING_LINE.format(name="fetch"), capsys.readouterr().out)


# ------------------------------------------------- 01 gather vs TaskGroup ----


def test_worker_returns_result_and_rejects_bad_input() -> None:
    assert asyncio.run(gather_vs_taskgroup.worker(0)) == "Job result: 0"
    with pytest.raises(TypeError):
        asyncio.run(gather_vs_taskgroup.worker("x"))


def test_gather_vs_taskgroup_demo(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Zero-second jobs so the demo finishes instantly.
    monkeypatch.setattr(gather_vs_taskgroup.random, "randint", lambda _a, _b: 0)
    monkeypatch.setattr(gather_vs_taskgroup.random, "choice", lambda _seq: "x")
    asyncio.run(gather_vs_taskgroup.main())
    out = capsys.readouterr().out
    # gather(return_exceptions=True) keeps going and returns the error as a value...
    assert "['Job result: 0', 'Job result: 0', TypeError(" in out
    # ...while TaskGroup re-raises it inside an ExceptionGroup.
    assert "TaskGroup raised ExceptionGroup('unhandled errors in a TaskGroup', [TypeError(" in out


# --------------------------------------------------------- 02 semaphore ----


def test_semaphore_caps_concurrency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(semaphore_bound, "current_running", 0)
    monkeypatch.setattr(semaphore_bound, "peak_running", 0)

    async def run() -> list[str]:
        bound = asyncio.Semaphore(3)
        results: list[str] = await asyncio.gather(
            *(semaphore_bound.worker(0.01, bound) for _ in range(10))
        )
        return results

    assert len(asyncio.run(run())) == 10
    assert semaphore_bound.peak_running == 3
    assert semaphore_bound.current_running == 0


# ------------------------------------------------------ 03 cancellation ----


def test_worker_intercepts_cancellation(capsys: pytest.CaptureFixture[str]) -> None:
    async def run() -> tuple[str | None, bool]:
        task = asyncio.create_task(cancellation.long_running_worker(100))
        await asyncio.sleep(0.01)
        task.cancel()
        result = await task
        return result, task.cancelled()

    # The worker catches CancelledError and returns normally, so the task is
    # *not* marked cancelled - exactly what the script's comments warn about.
    assert asyncio.run(run()) == (None, False)
    assert "CancelledError\nCleaning up...\nJob-100 canceled\n" in capsys.readouterr().out


# ----------------------------------------------------------- 04 timeout ----


def test_wait_for_times_out_and_still_runs_cleanup(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(TimeoutError):
        asyncio.run(asyncio.wait_for(timeout.operation(10), 0.05))
    assert capsys.readouterr().out.endswith("Cleaning up...\nJob-10 canceled\n")


# ----------------------------------------------------- 05 blocking call ----


def test_normal_and_blocking_tasks_return_results() -> None:
    assert asyncio.run(blocking_call.normal_task(0)) == "Job result: 0"
    assert blocking_call.blocking_task(0) == "Job result: 0"


# ------------------------------------------------- 06 GIL and executors ----


@pytest.mark.parametrize(
    ("limit", "expected"),
    [(1, 0), (2, 1), (10, 4), (100, 25), (100_000, 9592)],
)
def test_count_primes(limit: int, expected: int) -> None:
    assert gil_and_executors.count_primes(limit) == expected

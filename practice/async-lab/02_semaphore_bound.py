import asyncio
import inspect
import random
import time
from collections.abc import Callable
from datetime import datetime
from functools import wraps
from typing import Any, ParamSpec, TypeVar, cast

P = ParamSpec("P")
R = TypeVar("R")

current_running = 0
peak_running = 0


def time_it(func: Callable[P, R]) -> Callable[P, R]:
    if inspect.iscoroutinefunction(func):

        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
            start = time.perf_counter()
            result = await func(*args, **kwargs)
            end = time.perf_counter()
            print(f"{func.__name__} took {end - start:.4f} second(s)")
            return result

        # Calling async_wrapper returns a coroutine, exactly like calling func, but a
        # type checker cannot follow that through the iscoroutinefunction() branch.
        return cast(Callable[P, R], async_wrapper)

    @wraps(func)
    def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        start = time.perf_counter()
        result = func(*args, **kwargs)
        end = time.perf_counter()
        print(f"{func.__name__} took {end - start:.4f} second(s)")
        return result

    return sync_wrapper


async def worker(param: float, semaphore: asyncio.Semaphore) -> str:
    async with semaphore:
        global current_running
        global peak_running
        current_running += 1
        peak_running = max(current_running, peak_running)
        print(f"Job-{param} started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        await asyncio.sleep(param)
        current_running -= 1
        print("Worker finished")
        return f"Job result: {param}"


@time_it
async def main() -> None:
    bound = asyncio.Semaphore(10)
    coroutines = [worker(random.uniform(0.1, 0.5), semaphore=bound) for _ in range(1, 100)]
    result = await asyncio.gather(*coroutines, return_exceptions=True)
    print(result)
    print(f"Peak Concurrency: {peak_running}")


if __name__ == "__main__":
    asyncio.run(main())

# Bounded Concurrency with Semaphore of 10 workers: 3.1655 second(s) | Peak Concurrency: 10
# Unbounded Concurrency: 0.5006 second(s) | Peak Concurrency: 99
# (To reproduce the unbounded run, raise the Semaphore limit to 99 or more.)


# ----------- Understanding & Notes -----------
#
# Here it clearly shows that unbounded concurrency is faster as here the tasks are not
# CPU bound: by using a semaphore at most 10 jobs are sleeping at any moment (a sliding
# window - a new job starts as soon as one finishes - rather than fixed batches of 10).
# Unbounded concurrency is not always faster, but bounded concurrency is good practice
# whenever the work hits a real constrained resource (HTTP servers, rate-limited APIs,
# database connection pools, open file handles), so we don't overwhelm it.
# A semaphore does nothing for CPU-bound work: asyncio runs on one thread, so only one
# coroutine executes at a time anyway.
# This comparison becomes meaningful only when the work involves a real constrained
# resource (HTTP, database, file I/O, etc.); with plain sleeps the bounded version is
# meaningfully slower in my view.

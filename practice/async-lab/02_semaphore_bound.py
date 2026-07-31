import inspect
import time
from datetime import datetime
import asyncio
from collections.abc import Callable
from typing import ParamSpec, TypeVar
from functools import wraps
import random

P = ParamSpec("P")
R = TypeVar("R")

current_running = 0
peak_running = 0

def time_it(func: Callable[P, R]) -> Callable[P, R]:
    if inspect.iscoroutinefunction(func):
        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            start = time.perf_counter()
            result = await func(*args, **kwargs)
            end = time.perf_counter()
            print(f"{func.__name__} took {end - start:.4f} second(s)")
            return result

        return async_wrapper

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
        print(f"Job-{param} started at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}")
        await asyncio.sleep(param)
        current_running -= 1
        print(f"Worker finished")
        return f"Job result: {param}"

@time_it
async def main() -> None:
    bound = asyncio.Semaphore(10)
    coroutines = [worker(random.uniform(0.1, 0.5), semaphore=bound) for _ in range(1,100)]
    result = await asyncio.gather(*coroutines, return_exceptions=True)
    print(result)
    print(f"Peak Concurrency: {peak_running}")

if __name__ == "__main__":
    asyncio.run(main())

# Bounded Concurrency with Semaphore of 10 workers: 3.1655 second(s) | Peak Concurrency: 10
# Unbounded Concurrency: 0.5006 second(s) | Peak Concurrency: 99


# ----------- Understanding & Notes -----------
#
# Here it clearly shows that unbounded concurrency is faster as here the tasks are not CPU bound,
# by using semaphore we are sleeping the system in batches of 10 which clearly is the issue.
# Unbounded concurrency not always necessarily faster, but it is a good practice to use bounded concurrency,
# Just so we don't bog down servers or overheat our machines for CPU bound tasks.
# This comparison becomes meaningful only when the work involves a real constrained resource (HTTP, database, file I/O, etc.)
# bounded version is meaningfully slower in my view.
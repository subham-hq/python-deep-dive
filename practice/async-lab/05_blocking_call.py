import inspect
import time
import asyncio
from concurrent.futures import ProcessPoolExecutor
from functools import wraps
from collections.abc import Callable
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")

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

async def normal_task(param: int) -> None:
    print(f"Normal Task-{param} started")
    await asyncio.sleep(param)
    print(f"Normal Task-{param} finished")
    return f"Job result: {param}"

def blocking_task(param: int) -> None:
    print(f"Blocking Task-{param} started")
    time.sleep(param)
    print(f"Blocking Task-{param} finished")
    return f"Job result: {param}"

@time_it
async def main() -> None:

    # Gather Coroutines
    # coroutines = [normal_task(i) for i in range(18)]
    # coroutines.append(to_thread(blocking_task, 18))
    #
    # results = await asyncio.gather(*coroutines, return_exceptions=True)
    #
    # print(results)

    # Gather Tasks
    tasks = [asyncio.create_task(normal_task(i)) for i in range(18)]
    loop = asyncio.get_event_loop()
    with ProcessPoolExecutor() as executor:
        # When the with block exits, Python calls:
        # executor.shutdown(wait=True)
        blocking_future = loop.run_in_executor(executor, blocking_task, 18)
        results = await asyncio.gather(
            *tasks,
            blocking_future
        )

    print(results)



if __name__ == "__main__":
    asyncio.run(main(), debug=True)

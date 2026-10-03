import asyncio
import inspect
import time
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from functools import wraps
from typing import Any, ParamSpec, TypeVar, cast

P = ParamSpec("P")
R = TypeVar("R")


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


async def normal_task(param: int) -> str:
    print(f"Normal Task-{param} started")
    await asyncio.sleep(param)
    print(f"Normal Task-{param} finished")
    return f"Job result: {param}"


def blocking_task(param: int) -> str:
    print(f"Blocking Task-{param} started")
    time.sleep(param)
    print(f"Blocking Task-{param} finished")
    return f"Job result: {param}"


@time_it
async def main() -> None:

    # Gather Coroutines
    # coroutines = [normal_task(i) for i in range(18)]
    # coroutines.append(asyncio.to_thread(blocking_task, 18))
    #
    # results = await asyncio.gather(*coroutines, return_exceptions=True)
    #
    # print(results)

    # Gather Tasks
    # The blocking call runs in a separate process, so the event loop stays free and
    # the 18 normal tasks run alongside it: total time is ~18 s (the longest job).
    # Calling blocking_task(18) directly here instead would block the event loop for
    # 18 s before any task could run (~35 s total), and debug=True would log
    # "Executing <Task ...> took 18.0 seconds".
    tasks = [asyncio.create_task(normal_task(i)) for i in range(18)]
    loop = asyncio.get_running_loop()
    with ProcessPoolExecutor() as executor:
        # When the with block exits, Python calls:
        # executor.shutdown(wait=True)
        blocking_future = loop.run_in_executor(executor, blocking_task, 18)
        results = await asyncio.gather(*tasks, blocking_future)

    print(results)


if __name__ == "__main__":
    asyncio.run(main(), debug=True)

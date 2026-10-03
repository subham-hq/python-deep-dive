import asyncio
import inspect
import random
import string
import time
from collections.abc import Callable
from datetime import datetime
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


async def worker(param: int | str) -> str:
    print(f"Job-{param} started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    # A str here is the deliberate bad input: asyncio.sleep() raises TypeError.
    await asyncio.sleep(param)  # type: ignore[arg-type]
    print("Worker finished")
    return f"Job result: {param}"


@time_it
async def main() -> None:
    params: list[int | str] = []
    for i in range(4):
        if i == 2:
            params.append(random.choice(string.ascii_lowercase))
        random_num = random.randint(1, 10)
        params.append(random_num)

    # gather(return_exceptions=True): the bad job's error comes back as a value
    # in the result list and every other job still runs to completion.
    coroutines = [worker(i) for i in params]
    result = await asyncio.gather(*coroutines, return_exceptions=True)
    print(result)

    # TaskGroup: the first failure cancels every other task in the group, and the
    # error is re-raised wrapped in an ExceptionGroup, so it is handled with except*.
    tasks: list[asyncio.Task[str]] = []
    try:
        async with asyncio.TaskGroup() as task_group:
            tasks = [task_group.create_task(worker(i)) for i in params]
    except* TypeError as group:
        print(f"TaskGroup raised {group!r}")
    print(f"Cancelled: {[task.cancelled() for task in tasks]}")


if __name__ == "__main__":
    asyncio.run(main())


# ----------- Understanding & Notes -----------
#
# Usage of Task Group:
# 1. Want it to fail together
# 2. During order placement or charging a card

# Usage of Gather Coroutines:
# 1. Run multiple async calls
# 2. Run independent tasks
# 3. Only need results
# 4. Task starts only after we await the coroutines

# Usage of Gather Tasks:
# 1. It could be used when we want to hold on for the results
# 2. Task is scheduled as soon as this line runs and starts at the next await:
#    [asyncio.create_task(func_name(i)) for i in range(1,3)]
# 3. For gather coroutines it never starts unless we await the task.

# For a crawler worker pool, a bare TaskGroup is a poor fit: if any website is down,
# that one failure cancels every other fetch. Use gather(return_exceptions=True), or
# have each worker catch its own errors (e.g. workers pulling URLs from an asyncio.Queue).

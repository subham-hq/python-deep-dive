import inspect
import time
import asyncio
import random
import string
from functools import wraps
from datetime import datetime
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

params = []

async def worker(param: int) -> str:
    print(f"Job-{param} started at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}")
    await asyncio.sleep(param)
    print(f"Worker finished")
    return f"Job result: {param}"

@time_it
async def main() -> None:
    for i in range(4):
        if i == 2:
            params.append(random.choice(string.ascii_lowercase))
        random_num = random.randint(1, 10)
        params.append(random_num)

    coroutines = [worker(i) for i in params]
    result = await asyncio.gather(*coroutines, return_exceptions=True)
    print(result)

    # Commented as this will break the programme
    # async with asyncio.TaskGroup() as task_group:
    #     tasks = [task_group.create_task(worker(i)) for i in params]
    # print(tasks)

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
# 2. Task starts right after this line : [asyncio.create_task(func_name(i)) for i in range(1,3)]
# 3. For gather coroutines it never starts unless we await the task.

# For a crawler worker pool, TaskGroup cannot be  used because if any website is down it wil fail together,
# Therefore it is best approach to use gather and before that need to await them in a queue.

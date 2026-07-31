import inspect
import time
import asyncio
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

async def long_running_worker(param: int) -> None | str:
    try:
        while True:
            try:
                print(f"Job-{param} started at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}")
                await asyncio.sleep(param)
                print(f"Worker finished")
                return f"Job result: {param}"
            except Exception as e: # This will not catch the error
                print(f"Worker failed: {e}")
            except BaseException as e:
                print(type(e).__name__)
                break # without this the task becomes unkillable
    finally:
        print(f"Cleaning up...")
        print(f"Job-{param} canceled")

@time_it
async def main() -> None:
    task = asyncio.create_task(long_running_worker(100))

    await asyncio.sleep(1)

    task.cancel()

    await task


if __name__ == "__main__":
    asyncio.run(main())

# Cancellation is not like pulling the power plug. It’s a request for the coroutine to stop.
# Generic except block is not able to detect asyncio.CancelledError exceptions. Only the below code detects it
#             except BaseException as e:
#                 print(type(e).__name__)
# It is by design a base exception because if it raised The task would ignore cancellation.
# and the tasks would refuse to die forever and each time it will raise an exception and continue looping.


# Imagine:
# while True:
#     try:
#         do_work()
#     except Exception:
#         pass
# If you press Ctrl+C, you expect the program to stop.
#
# If KeyboardInterrupt were an Exception, the loop would swallow it
# and continue forever. You’d have to kill the process from the operating system.

# These are base exceptions by design:
# * KeyboardInterrupt
# * SystemExit
# * CancelledError

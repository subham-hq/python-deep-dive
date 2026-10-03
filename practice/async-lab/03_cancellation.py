import asyncio
import inspect
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


async def long_running_worker(param: int) -> str | None:
    try:
        while True:
            try:
                print(f"Job-{param} started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                await asyncio.sleep(param)
                print("Worker finished")
                return f"Job result: {param}"
            except Exception as e:  # This will not catch the error
                print(f"Worker failed: {e}")
            except BaseException as e:
                print(type(e).__name__)
                # Without this break the loop swallows the cancellation and keeps
                # running, so the task becomes unkillable. Demo only: real code
                # should `raise` here so the task actually ends up cancelled.
                break
    finally:
        print("Cleaning up...")
        print(f"Job-{param} canceled")
    return None


@time_it
async def main() -> None:
    task = asyncio.create_task(long_running_worker(100))

    await asyncio.sleep(1)

    task.cancel()

    await task
    # False: the worker caught CancelledError and returned normally instead.
    print(f"task.cancelled() = {task.cancelled()}")


if __name__ == "__main__":
    asyncio.run(main())

# Cancellation is not like pulling the power plug. It's a request for the coroutine to stop.
# A generic `except Exception` block does not catch asyncio.CancelledError
# (Python 3.8+). Only the below code detects it:
#             except BaseException as e:
#                 print(type(e).__name__)
# It is a BaseException by design: if it were an Exception, every generic
# `except Exception` block would swallow it, the task would ignore cancellation,
# and it would refuse to die, catching the error each time and continuing to loop.


# Imagine:
# while True:
#     try:
#         do_work()
#     except Exception:
#         pass
# If you press Ctrl+C, you expect the program to stop.
#
# If KeyboardInterrupt were an Exception, the loop would swallow it
# and continue forever. You'd have to kill the process from the operating system.

# These are base exceptions by design:
# * KeyboardInterrupt
# * SystemExit
# * CancelledError

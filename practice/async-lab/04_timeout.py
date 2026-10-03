import asyncio
import inspect
import time
from asyncio import CancelledError
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


async def operation(param: int) -> str | None:

    try:
        async with asyncio.timeout(5):
            while True:
                try:
                    print(f"Job-{param} started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    await asyncio.sleep(param)
                    print("Worker finished")
                    return f"Job result: {param}"
                except TimeoutError as e:
                    # Never reached: asyncio.timeout() injects a *cancellation* into the
                    # task, so what arrives here is CancelledError, not TimeoutError. It
                    # only becomes TimeoutError when the context manager exits. (If this
                    # caught CancelledError instead, no TimeoutError would be raised.)
                    print(f"Canceled due to {type(e).__name__}")
                    break
    except TimeoutError as e:  # try commenting out this block to see the difference
        print(f"Canceled due to {type(e).__name__}")
    finally:
        print("Cleaning up...")
        print(f"Job-{param} canceled")
    return None


@time_it
async def main() -> None:
    task = asyncio.create_task(operation(10))

    await asyncio.sleep(1)

    await task

    # The try must wrap the `async with`, not sit inside it: asyncio.timeout() raises
    # its TimeoutError when the block exits, which is outside any try placed within it.
    try:
        async with asyncio.timeout(5):
            # if we do both timeout and wait_for @ 3 s timeout fires first,
            # if we change the time obviously the one with less time kicks in first
            try:
                response = await asyncio.wait_for(operation(10), 3)
                print(response)
            except CancelledError as e:
                # Reached when the outer timeout fires first. Catching it here swallows
                # the cancellation, so the outer timeout never turns it into TimeoutError.
                print(f"Canceled due to {type(e).__name__}")
            except TimeoutError as e:
                # wait_for() fired first: it cancels operation() and raises TimeoutError
                # itself, so this is a plain exception from the awaited call.
                print(f"Canceled due to wait_for: {type(e).__name__}")
    except TimeoutError as e:
        # Reached when the outer timeout fires first and nothing above swallowed the
        # CancelledError (set the outer timeout below 3 s and remove that branch to see it).
        print(f"Canceled due to timeout: {type(e).__name__}")


if __name__ == "__main__":
    asyncio.run(main())

# Use wait_for() when you want to time-limit one operation:
# response = await asyncio.wait_for(client.get(url), timeout=5)

# Use asyncio.timeout() when several awaits together must complete within a deadline:
# async with asyncio.timeout(30):
#     await authenticate()
#     await fetch_data()
#     await write_results()


# What happens to the in-flight socket when a request times out?
#
# Timeline:
# 1. The client sends the HTTP request over an open TCP socket.
# 2. The server may already be processing the request.
# 3. The client's timeout expires (e.g., asyncio.wait_for() / asyncio.timeout()).
# 4. The client coroutine is cancelled (CancelledError internally), and the HTTP
#    library performs cleanup by closing the socket or removing it from the
#    connection pool if its state is uncertain.
# 5. The server is NOT automatically notified to stop processing. It may continue
#    executing the request, writing to a database, or performing other work.
# 6. If the server later sends a response, the client has already abandoned the
#    request, so the response is discarded (or the server notices the connection
#    has been closed and aborts the response).
#
# Key takeaway:
# A client-side timeout only stops the CLIENT from waiting. It does NOT guarantee
# that the SERVER stopped processing the request. This is why retrying non-
# idempotent requests (e.g., money transfers) can be dangerous unless the API
# supports idempotency keys.
#
# Concise version:
# Timeout cancels the client task and cleans up the socket, but the server may
# continue processing the in-flight request. The client simply stops waiting for
# the response.

# Client                     Network                     Server
# ------                     -------                     ------
#
# Send request  ---------------------------------------->
#                            Request in-flight
#                                                     Processing...
#                                                     Processing...
#
# <----- Waiting for response -----
#
# (5 second timeout expires)
#
# Client cancels coroutine
# Client closes/discards socket
# Raises TimeoutError to caller
#
#                                                     Still processing...
#                                                     Writes to database...
#                                                     Generates response...
#
#                          <--------------------------- Response
#
# Response is discarded because the client has already
# abandoned the request (or the server detects the closed
# connection and stops sending).
#
# Important:
# A timeout only affects the CLIENT. It does NOT automatically
# cancel work already running on the SERVER.

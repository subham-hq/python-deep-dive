

"""
===============================================================================
PYTHON CONCURRENCY NOTES: GIL, ASYNCIO, THREADS, PROCESSES & EXECUTORS
===============================================================================

1. Global Interpreter Lock (GIL)
--------------------------------
- CPython has a Global Interpreter Lock (GIL).
- The GIL allows only ONE thread to execute Python bytecode at a time.
- Therefore, multiple Python threads DO NOT execute CPU-bound Python code in
  parallel, even on a multi-core CPU.
- The GIL exists to simplify memory management and keep Python objects thread-safe.

Example:
    Thread A -> Running Python code
    Thread B -> Waiting for the GIL
    Thread C -> Waiting for the GIL

Threads take turns executing Python bytecode.

-------------------------------------------------------------------------------

2. When Threads ARE Useful
--------------------------
Although the GIL prevents true parallel execution of Python bytecode, threads
are excellent for I/O-bound work because they release the GIL while waiting.

Examples:
    - time.sleep()
    - Reading/Writing files
    - HTTP requests
    - Database queries
    - Socket communication

While one thread waits for I/O, another thread can execute.

-------------------------------------------------------------------------------

3. CPU-bound vs I/O-bound
-------------------------

CPU-bound:
    - Heavy mathematical computation
    - Image processing
    - Machine learning inference/training
    - Compression
    - Large loops

Use:
    ProcessPoolExecutor

Reason:
    Each process has its own Python interpreter and its own GIL, allowing
    true parallel execution across multiple CPU cores.

--------------------------------------------------

I/O-bound:
    - Network requests
    - File operations
    - Sleeping
    - Database access
    - Legacy blocking libraries

Use:
    asyncio
    asyncio.to_thread()
    ThreadPoolExecutor

Reason:
    Threads spend most of their time waiting rather than executing Python code.

-------------------------------------------------------------------------------

4. Asyncio
----------
asyncio is SINGLE-THREADED.

It achieves concurrency through cooperative multitasking.

A coroutine voluntarily gives control back to the event loop whenever it hits:

    await ...

The event loop then schedules another coroutine.

Nothing runs in parallel inside the event loop.

-------------------------------------------------------------------------------

5. NEVER call blocking functions inside a coroutine
---------------------------------------------------

BAD:

    async def task():
        time.sleep(1)

time.sleep() blocks the ENTIRE event loop.

Every coroutine stops running until it finishes.

GOOD:

    async def task():
        await asyncio.sleep(1)

asyncio.sleep() suspends ONLY the current coroutine and lets the event loop
continue executing other coroutines.

-------------------------------------------------------------------------------

6. Slow Callback Warning
------------------------
Run:

    asyncio.run(main(), debug=True)

If a coroutine blocks the event loop for too long, asyncio prints:

    Executing <Task ...> took 1.002 seconds

This is called the "slow callback warning".

It means:
    "Something blocked the event loop."

Common causes:
    - time.sleep()
    - Heavy CPU computation
    - Large synchronous file operations
    - Blocking third-party libraries

-------------------------------------------------------------------------------

7. Executors
------------
An Executor manages worker threads or worker processes.

Instead of creating threads/processes manually, you submit work to an executor.

Two built-in executors:

1) ThreadPoolExecutor
2) ProcessPoolExecutor

-------------------------------------------------------------------------------

8. ThreadPoolExecutor
---------------------
Uses worker THREADS.

Best for:
    - Blocking I/O
    - Legacy synchronous code
    - time.sleep()
    - File operations
    - Requests library

Works alongside asyncio.

Example:

    await asyncio.to_thread(blocking_function)

or

    loop.run_in_executor(None, blocking_function)

(None = default ThreadPoolExecutor)

-------------------------------------------------------------------------------

9. ProcessPoolExecutor
----------------------
Uses worker PROCESSES.

Each process has:
    - Separate memory
    - Separate interpreter
    - Separate GIL

Best for:
    - CPU-intensive work

Examples:
    - Image processing
    - Video encoding
    - Scientific computing
    - Large numerical algorithms

-------------------------------------------------------------------------------

10. asyncio.to_thread()
------------------------
Runs a synchronous blocking function in a background thread without blocking
the event loop.

Correct:

    await asyncio.to_thread(blocking_function, arg1, arg2)

Incorrect:

    await asyncio.to_thread(blocking_function())

The second version executes the function BEFORE creating the thread.

-------------------------------------------------------------------------------

11. run_in_executor()
---------------------
Low-level API for executing blocking code in an executor.

Thread pool:

    loop = asyncio.get_running_loop()

    await loop.run_in_executor(
        None,
        blocking_function,
        arg
    )

Process pool:

    with ProcessPoolExecutor() as executor:
        await loop.run_in_executor(
            executor,
            cpu_bound_function,
            arg
        )

-------------------------------------------------------------------------------

12. Rule of Thumb
-----------------

Need many concurrent network/file operations?
    -> asyncio

Need to call one blocking synchronous function?
    -> asyncio.to_thread()

Need custom thread management?
    -> ThreadPoolExecutor

Need true parallel CPU execution?
    -> ProcessPoolExecutor

Heavy calculations?
    -> Processes

Waiting for I/O?
    -> Threads

-------------------------------------------------------------------------------

Summary
-------

asyncio
    = Cooperative concurrency (single thread)

ThreadPoolExecutor
    = Blocking I/O

ProcessPoolExecutor
    = CPU parallelism

time.sleep()
    = Blocks the event loop (BAD inside coroutines)

asyncio.sleep()
    = Non-blocking (GOOD)

asyncio.to_thread()
    = Move blocking I/O to a background thread

run_in_executor()
    = Low-level API to execute blocking work in a thread/process pool

ProcessPoolExecutor
    = Bypasses the GIL using multiple Python processes
===============================================================================
"""
import concurrent
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

def count_primes(limit: int) -> int:
    count = 0

    for n in range(2, limit + 1):
        is_prime = True

        for i in range(2, int(n ** 0.5) + 1):
            if n % i == 0:
                is_prime = False
                break

        if is_prime:
            count += 1

    return count

@time_it
async def main():

    # No concurrency
    # results = []
    # for _ in range(7):
    #     results.append(count_primes(100000))
    #
    # print(results)
    #
    # # main took 0.3060 second(s)


    # Run inside coroutines
    # coroutines = [asyncio.to_thread(count_primes, 100000) for _ in range(7)]
    # results = await asyncio.gather(*coroutines)
    # print(results)

    # main took 0.3143 second(s)

    # With ThreadPoolExecutors

    threads = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        for _ in range(7):
            threads.append(executor.submit(count_primes, 100000))

        result = [thread.result() for thread in threads]

    print(result)

    # main took 0.2766 second(s)
    # Slight edge over sync code

    # With ProcessPoolExecutors
    # loop = asyncio.get_running_loop()
    #
    # processes = []
    # with ProcessPoolExecutor() as executor:
    #     for _ in range(7):
    #         processes.append(loop.run_in_executor(executor, count_primes, 100000))
    #
    #     result = await asyncio.gather(*processes)
    #
    # print(result)

    # main took 0.1769 second(s)
    # Significantly faster

if __name__ == '__main__':
    asyncio.run(main())

# if __name__ == '__main__':
#     main()
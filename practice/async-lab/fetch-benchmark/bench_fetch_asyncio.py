import asyncio
import sys
import time

import aiohttp

URL = "http://127.0.0.1:8000"
REQUESTS = 200


async def fetch(
    session: aiohttp.ClientSession, request_id: int, semaphore: asyncio.Semaphore
) -> tuple[int, str, int]:
    async with semaphore, session.get(URL) as response:
        text = await response.text()
        return request_id, text, response.status


async def main(limit: int) -> None:
    # Concurrency limit from the command line, e.g. `python bench_fetch_asyncio.py 5`.
    # Values used in the notes below: 5, 20, 50, 100, 200 (the default).
    bound = asyncio.Semaphore(limit)

    start = time.perf_counter()

    async with aiohttp.ClientSession() as session:
        tasks = [fetch(session, i, bound) for i in range(REQUESTS)]
        results = await asyncio.gather(*tasks)

    elapsed = time.perf_counter() - start

    print(f"Semaphore: {limit}")
    print(f"Completed {len(results)} requests")
    print(f"Successful: {sum(status == 200 for _, _, status in results)}")
    print(f"Elapsed time: {elapsed:.3f} s")


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else REQUESTS))

# One run per limit on each machine (numbers vary by machine): the author's machine,
# running an earlier version that also printed every response inside the timed block,
# and a 4-vCPU Linux VM with Python 3.12. The server sleeps 50 ms per request, so the
# floor is (200 / limit) rounds x 50 ms:
#
#   Semaphore   200 / limit   expected   author's machine   4-vCPU VM
#   5           40 rounds     ~2.0 s     2.085 s            2.085 s
#   20          10 rounds     ~0.5 s     0.526 s            0.528 s
#   50           4 rounds     ~0.2 s     0.217 s            0.235 s
#   100          2 rounds     ~0.1 s     0.116 s            0.144 s
#   200          1 round      ~50 ms     0.118 s            0.139 s
#
# But we don't see 50 ms at 200. Two reasons:
#
# 1. aiohttp's ClientSession opens at most 100 connections at once by default
#    (TCPConnector(limit=100)), so above 100 the semaphore is no longer the limit
#    and it is still 2 rounds.
# 2. 50 ms is only the simulated work. There's additional overhead:
#
# * creating 200 coroutine tasks
# * scheduling them in the event loop
# * opening/managing TCP connections
# * sending HTTP requests
# * parsing HTTP responses
# * switching between coroutines
# * Python interpreter overhead
# * operating system networking

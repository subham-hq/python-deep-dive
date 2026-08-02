import asyncio
import time

import aiohttp

URL = "http://localhost:8000"


async def fetch(session, request_id, semaphore):
    async with semaphore:
        async with session.get(URL) as response:
            text = await response.text()
            return request_id, text, response.status


async def main():
    # bound = asyncio.Semaphore(5)
    # bound = asyncio.Semaphore(20)
    # bound = asyncio.Semaphore(50)
    # bound = asyncio.Semaphore(100)
    bound = asyncio.Semaphore(200)

    start = time.perf_counter()

    async with aiohttp.ClientSession() as session:
        tasks = [fetch(session, i, bound) for i in range(200)]
        results = await asyncio.gather(*tasks)

    for request_id, text, status in results:
        print(f"{request_id}: {text} ({status})")

    elapsed = time.perf_counter() - start

    print(f"Semaphore: {bound}")
    print(f"Completed {len(results)} requests")
    print(f"Successful: {sum(status == 200 for _, _, status in results)}")
    print(f"Elapsed time: {elapsed:.3f} s")


if __name__ == "__main__":
    asyncio.run(main())

# Semaphore: <asyncio.locks.Semaphore object at 0x108cfd160 [unlocked, value:5]>
# Completed 200 requests
# Successful: 200
# Elapsed time: 2.085 s
# 200 requests
# ÷ 5 at a time
# = 40 batches
#
# 40 × 50 ms
# ≈ 2.0 s

# Semaphore: <asyncio.locks.Semaphore object at 0x108b51160 [unlocked, value:20]>
# Completed 200 requests
# Successful: 200
# Elapsed time: 0.526 s
# 200
# ÷ 20
# = 10 batches
#
# 10 × 50 ms
# ≈ 0.5 s

# Semaphore: <asyncio.locks.Semaphore object at 0x1091cd160 [unlocked, value:50]>
# Completed 200 requests
# Successful: 200
# Elapsed time: 0.217 s
# 200
# ÷ 50
# = 4 batches
#
# 4 × 50 ms
# ≈ 0.2 s

# Semaphore: <asyncio.locks.Semaphore object at 0x106b29160 [unlocked, value:100]>
# Completed 200 requests
# Successful: 200
# Elapsed time: 0.116 s
# 200
# ÷ 100
# = 2 batches
#
# 2 × 50 ms
# ≈ 0.1 s

# Semaphore: <asyncio.locks.Semaphore object at 0x10b61d160 [unlocked, value:200]>
# Completed 200 requests
# Successful: 200
# Elapsed time: 0.118 s
# 200
# ÷ 200
# = 1 batch
#
# 1 × 50 ms
# ≈ 50 ms

# But we dont see 50 ms, Because 50 ms is only the simulated work. There’s additional overhead:
#
# * creating 200 coroutine tasks
# * scheduling them in the event loop
# * opening/managing TCP connections
# * sending HTTP requests
# * parsing HTTP responses
# * switching between coroutines
# * Python interpreter overhead
# * operating system networking

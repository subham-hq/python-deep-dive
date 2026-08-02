import asyncio
import time

import aiohttp

URL = "http://localhost:8000"


async def fetch(session, request_id):
    async with session.get(URL) as response:
        text = await response.text()
        return request_id, text, response.status


# C. asyncio: AsyncClient, Semaphore(20)
async def main():
    start = time.perf_counter()

    async with aiohttp.ClientSession() as session:
        tasks = [fetch(session, i) for i in range(200)]
        results = await asyncio.gather(*tasks)

    for request_id, text, status in results:
        print(f"{request_id}: {text} ({status})")

    elapsed = time.perf_counter() - start

    print(f"Completed {len(results)} requests")
    print(f"Successful: {sum(status == 200 for _, _, status in results)}")
    print(f"Elapsed time: {elapsed:.3f} s")


if __name__ == "__main__":
    asyncio.run(main())
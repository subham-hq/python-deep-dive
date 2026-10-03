import time
from concurrent.futures import ThreadPoolExecutor
from urllib.request import build_opener, install_opener, urlopen

URL = "http://127.0.0.1:8000"
REQUESTS = 200


def fetch_data(url: str, request_id: int) -> tuple[int, str, int]:
    with urlopen(url) as response:
        text = response.read().decode()
        return request_id, text, response.status


def main() -> None:
    # urlopen() builds a shared "opener" lazily on its first call, so 200 threads
    # making that first call at the same moment can each see no opener yet and build
    # their own. On Python 3.12+ building an opener creates an SSL context (~25 ms of
    # CPU apiece), and the 40-120 racing builds seen in test runs swamp the 50 ms
    # requests. On 3.11 building one is cheap and the race costs nothing. Building it
    # once here, before the timer, is correct on every version.
    install_opener(build_opener())

    start = time.perf_counter()

    # One thread per request.
    with ThreadPoolExecutor(REQUESTS) as executor:
        futures = [executor.submit(fetch_data, URL, i) for i in range(REQUESTS)]

        results = [future.result() for future in futures]

    elapsed = time.perf_counter() - start

    print(f"Completed {len(results)} requests")
    print(f"Successful: {sum(status == 200 for _, _, status in results)}")
    print(f"Elapsed time: {elapsed:.3f} s")


if __name__ == "__main__":
    main()

# Sample runs (numbers vary by machine).
#
# 4-vCPU Linux VM, Python 3.12:
# Completed 200 requests
# Successful: 200
# Elapsed time: 0.204 s
#
# Author's machine, earlier version without the pre-built opener:
# Completed 200 requests
# Successful: 200
# Elapsed time: 0.550 s

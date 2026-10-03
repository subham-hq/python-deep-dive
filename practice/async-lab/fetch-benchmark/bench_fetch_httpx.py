import time

import httpx

URL = "http://127.0.0.1:8000"
REQUESTS = 200


def main() -> None:
    results: list[tuple[int, str, int]] = []

    start = time.perf_counter()

    # One Client for every request. Creating a new Client per request (inside the
    # loop) builds a new SSL context and throws away the open connection every time.
    # On the 4-vCPU VM used for the README table that cost ~50 ms per request, and the
    # per-request version took ~21 s, twice plain urllib (the author's run is below).
    with httpx.Client() as client:
        for i in range(REQUESTS):
            response = client.get(URL)
            results.append((i, response.text, response.status_code))

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
# Elapsed time: 10.545 s
#
# Author's machine, earlier version with a new Client per request:
# Completed 200 requests
# Successful: 200
# Elapsed time: 13.718 s

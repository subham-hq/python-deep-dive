import time
from urllib.request import urlopen

URL = "http://127.0.0.1:8000"
REQUESTS = 200


def main() -> None:
    results: list[tuple[int, str, int]] = []

    start = time.perf_counter()

    for i in range(REQUESTS):
        with urlopen(URL) as response:
            text = response.read().decode()
            results.append((i, text, response.status))

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
# Elapsed time: 10.349 s
#
# Author's machine:
# Completed 200 requests
# Successful: 200
# Elapsed time: 10.697 s

import concurrent
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.request import urlopen

URL = "http://localhost:8000"

results = []

def fetch_data(url, request_id):
    with urlopen(url) as response:
        text = response.read().decode()
        return request_id, text, response.status


def main():
    start = time.perf_counter()

    with concurrent.futures.ThreadPoolExecutor(200) as executor:
        futures = [executor.submit(fetch_data, URL, i) for i in range(200)]

        results = [future.result() for future in futures]

    print(results)

    elapsed = time.perf_counter() - start

    print(f"Completed {len(results)} requests")
    print(f"Successful: {sum(status == 200 for _, _, status in results)}")
    print(f"Elapsed time: {elapsed:.3f} s")

if __name__ == "__main__":
    main()

# Completed 200 requests
# Successful: 200
# Elapsed time: 0.550 s
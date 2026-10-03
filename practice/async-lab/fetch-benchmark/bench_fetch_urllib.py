import time
from urllib.request import urlopen

URL = "http://localhost:8000"

results = []

def main():
    start = time.perf_counter()

    for i in range(200):
        with urlopen(URL) as response:
            text = response.read().decode()
            results.append((i, text, response.status))

    print(results)

    elapsed = time.perf_counter() - start

    print(f"Completed {len(results)} requests")
    print(f"Successful: {sum(status == 200 for _, _, status in results)}")
    print(f"Elapsed time: {elapsed:.3f} s")

if __name__ == "__main__":
    main()

# Completed 200 requests
# Successful: 200
# Elapsed time: 10.697 s
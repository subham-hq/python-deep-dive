import time
import httpx

URL = "http://localhost:8000"

results = []

def main():
    start = time.perf_counter()

    for i in range(200):
        with httpx.Client() as client:
            response = client.get(URL)
            results.append((i, response.text, response.status_code))

    print(results)

    elapsed = time.perf_counter() - start

    print(f"Completed {len(results)} requests")
    print(f"Successful: {sum(status == 200 for _, _, status in results)}")
    print(f"Elapsed time: {elapsed:.3f} s")

if __name__ == "__main__":
    main()

# Completed 200 requests
# Successful: 200
# Elapsed time: 13.718 s
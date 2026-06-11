import time
from functools import wraps
import random

def retry(times, delay):

    def decorator(func):

        @wraps(func)
        def wrapper(*args, **kwargs):
            for i in range(1, times+1):
                try:
                    print(f"{func.__name__} - ({i})")
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    print(f"{func.__name__} - attempt {i} failed: {e}")
                    if i == times:
                        raise
                    print(f"Retrying in {delay} seconds...")
                    time.sleep(delay)


        return wrapper
    return decorator


@retry(times=3, delay=1)
def flaky():
    """Simulates an unreliable API call."""
    if random.random() < 0.7:
        raise ValueError("simulated failure")
    return 42

result = flaky()
print(result)
print(flaky.__name__, flaky.__doc__)
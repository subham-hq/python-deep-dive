import time
from functools import wraps


def time_it(func):
    """Decorator that prints how long the wrapped function took to run.

    Uses perf_counter (monotonic, high-resolution) rather than time.time,
    and functools.wraps so the wrapped function keeps its own __name__
    and __doc__ instead of reporting as 'wrapper'.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)        # nothing between start/end but the call
        end = time.perf_counter()
        print(f"{func.__name__} took {end - start:.4f} seconds")
        return result                          # pass the return value straight through
    return wrapper


def retry(times, delay):
    """Decorator factory: re-runs the wrapped function on failure.

    Parameterized (takes times/delay), so it's three levels deep:
    retry() returns decorator, decorator returns wrapper, wrapper does the work.
    On the final attempt it re-raises rather than swallowing the error —
    a retry that hides failures is worse than no retry at all.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for i in range(1, times + 1):
                try:
                    print(f"{func.__name__} - ({i})")
                    result = func(*args, **kwargs)
                    return result              # success: stop retrying immediately
                except Exception as e:
                    print(f"{func.__name__} - attempt {i} failed: {e}")
                    if i == times:
                        raise                  # last attempt: re-raise with full traceback
                    print(f"Retrying in {delay} seconds...")
                    time.sleep(delay)          # wait only BETWEEN attempts, never after the last
        return wrapper
    return decorator


# Demos run only when this file is executed directly (python decorators.py),
# never when it's imported elsewhere — that's what the guard guarantees.
if __name__ == "__main__":
    import random

    # --- time_it demo ---
    @time_it
    def slow_task():
        """Pretends to do expensive work."""
        time.sleep(1)
        return "done"

    slow_task()                                # prints: slow_task took 1.00xx seconds

    # --- retry demo ---
    @retry(times=3, delay=1)
    def flaky():
        """Simulates an unreliable API call."""
        if random.random() < 0.7:
            raise ValueError("simulated failure")
        return 42

    result = flaky()                           # run a few times to see all 3 outcomes
    print(result)
    print(flaky.__name__, flaky.__doc__)       # proves @wraps preserved name + docstring
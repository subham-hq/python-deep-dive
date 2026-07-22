from __future__ import annotations


import time
from functools import wraps
from typing import Callable, TypeVar, ParamSpec


P = ParamSpec("P")
R = TypeVar('R')

def log_analyzer(func: Callable[P, R]) -> Callable[P, R]:
    @wraps(func)                                  # you imported wraps but never used it
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        print(f"Starting {func.__name__}", end="", flush=True)
        for _ in range(3):
            time.sleep(0.4)
            print(".", end="", flush=True)        # flush => dots appear one at a time
        print("", end="\n\n")
        # close the line
        start_time = time.perf_counter()          # clock starts AFTER the animation
        result = func(*args, **kwargs)
        end_time = time.perf_counter()

        print("", end="\n")
        print(f"Finished {func.__name__} in {end_time - start_time:.6f} seconds.")
        return result
    return wrapper
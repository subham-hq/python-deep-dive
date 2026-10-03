import time
from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")


# -----------------------
# Decorator
# -----------------------
def log_execution(func: Callable[P, R]) -> Callable[P, R]:
    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        start = time.perf_counter()

        print(f"\nRunning: {func.__name__}")

        result = func(*args, **kwargs)

        end = time.perf_counter()
        print(f"Finished in {end - start:.4f} seconds")

        return result

    return wrapper


# -----------------------
# Task Class
# -----------------------
class Task:
    def __init__(self, title: str, priority: str) -> None:
        self.title = title
        self.priority = priority

    def __str__(self) -> str:
        return f"{self.title} (Priority: {self.priority})"


# -----------------------
# Iterator
# -----------------------
class TaskIterator:
    def __init__(self, tasks: list[Task]) -> None:
        self.tasks = tasks
        self.index = 0

    def __iter__(self) -> "TaskIterator":
        return self

    def __next__(self) -> Task:
        if self.index >= len(self.tasks):
            raise StopIteration

        task = self.tasks[self.index]
        self.index += 1
        return task


# -----------------------
# Iterable
# -----------------------
class TaskCollection:
    def __init__(self) -> None:
        self.tasks: list[Task] = []

    def add_task(self, task: Task) -> None:
        self.tasks.append(task)

    def __iter__(self) -> TaskIterator:
        return TaskIterator(self.tasks)


# -----------------------
# Functions using Decorator
# -----------------------
@log_execution
def display_tasks(task_collection: TaskCollection) -> None:
    for task in task_collection:
        print(task)


# -----------------------
# Main Program
# -----------------------
def main() -> None:
    tasks = TaskCollection()

    tasks.add_task(Task("Learn Python Decorators", "High"))
    tasks.add_task(Task("Practice Iterators", "Medium"))
    tasks.add_task(Task("Complete Mini Project", "High"))

    display_tasks(tasks)


if __name__ == "__main__":
    main()

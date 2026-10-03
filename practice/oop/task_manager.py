import time


# -----------------------
# Decorator
# -----------------------
def log_execution(func):
    def wrapper(*args, **kwargs):
        start = time.time()

        print(f"\nRunning: {func.__name__}")

        result = func(*args, **kwargs)

        end = time.time()
        print(f"Finished in {end - start:.4f} seconds")

        return result

    return wrapper


# -----------------------
# Task Class
# -----------------------
class Task:
    def __init__(self, title, priority):
        self.title = title
        self.priority = priority

    def __str__(self):
        return f"{self.title} (Priority: {self.priority})"


# -----------------------
# Iterator
# -----------------------
class TaskIterator:
    def __init__(self, tasks):
        self.tasks = tasks
        self.index = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self.index >= len(self.tasks):
            raise StopIteration

        task = self.tasks[self.index]
        self.index += 1
        return task


# -----------------------
# Iterable
# -----------------------
class TaskCollection:
    def __init__(self):
        self.tasks = []

    def add_task(self, task):
        self.tasks.append(task)

    def __iter__(self):
        return TaskIterator(self.tasks)


# -----------------------
# Functions using Decorator
# -----------------------
@log_execution
def display_tasks(task_collection):
    for task in task_collection:
        print(task)


# -----------------------
# Main Program
# -----------------------
tasks = TaskCollection()

tasks.add_task(Task("Learn Python Decorators", "High"))
tasks.add_task(Task("Practice Iterators", "Medium"))
tasks.add_task(Task("Complete Mini Project", "High"))

display_tasks(tasks)
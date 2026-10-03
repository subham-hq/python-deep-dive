import time
from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")


def log_actions(func: Callable[P, R]) -> Callable[P, R]:
    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        start = time.perf_counter()
        print(f"Executing {func.__name__}", end="")
        time.sleep(0.2)
        print(".", end="")
        time.sleep(0.2)
        print(".", end="")
        time.sleep(0.2)
        print(".")
        result = func(*args, **kwargs)
        end = time.perf_counter()
        print(f"Completed {func.__name__} in {end - start:.2f} seconds.")
        print("")
        print("")
        return result

    return wrapper


class Book:
    def __init__(self, title: str, author: str, is_borrowed: bool = False) -> None:
        self.title = title
        self.author = author
        self.is_borrowed = is_borrowed

    def __str__(self) -> str:
        if self.is_borrowed:
            return f"{self.title} by {self.author} (Borrowed)"
        else:
            return f"{self.title} by {self.author} (Available)"


class Library:
    def __init__(self) -> None:
        self.books: list[Book] = []

    def add_book(self, book: Book) -> None:
        self.books.append(book)

    def remove_book(self, book: Book) -> None:
        self.books.remove(book)

    def borrow_book(self, title: str) -> None:
        for book in self.books:
            if book.title == title:
                if book.is_borrowed:
                    raise ValueError(f"{title!r} is already borrowed")
                book.is_borrowed = True
                return
        raise LookupError(f"No book titled {title!r}")

    def return_book(self, title: str) -> None:
        for book in self.books:
            if book.title == title:
                if not book.is_borrowed:
                    raise ValueError(f"{title!r} is not borrowed")
                book.is_borrowed = False
                return
        raise LookupError(f"No book titled {title!r}")

    def __iter__(self) -> "LibraryIterator":
        return LibraryIterator(self.books)


class LibraryIterator:
    def __init__(self, books: list[Book]) -> None:
        self.books = books
        self.index = 0

    def __iter__(self) -> "LibraryIterator":
        return self

    def __next__(self) -> Book:
        if self.index < len(self.books):
            self.index += 1
            book = self.books[self.index - 1]
            return book
        else:
            raise StopIteration


@log_actions
def display_function(library: Library) -> None:
    for book in library:
        print(book)


def main() -> None:
    books = Library()

    books.add_book(Book("Ultralearning", "Scott H. Young", False))
    books.add_book(Book("Deep Work", "Cal Newport", False))
    books.add_book(Book("The Alchemist", "Paulo Coelho", True))

    display_function(books)

    books.borrow_book("Ultralearning")

    display_function(books)

    books.return_book("The Alchemist")

    display_function(books)


if __name__ == "__main__":
    main()

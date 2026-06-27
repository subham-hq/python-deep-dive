import time


def log_actions(func):
    def wrapper(*args, **kwargs):
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
    def __init__(self, title, author, is_borrowed):
        self.title = title
        self.author = author
        self.is_borrowed = is_borrowed

    def __str__(self):
        if self.is_borrowed:
            return f"{self.title} by {self.author} (Borrowed)"
        else:
            return f"{self.title} by {self.author} (Available)"

class Library:
    def __init__(self):
        self.books = []

    def add_book(self, book):
        self.books.append(book)

    def remove_book(self, book):
        self.books.remove(book)

    def borrow_book(self, title):
        for book in self.books:
            if book.title == title:
                book.is_borrowed = True

    def return_book(self, title):
        for book in self.books:
            if book.title == title:
                book.is_borrowed = False

    def __iter__(self):
        return LibraryIterator(self.books)

class LibraryIterator:
    def __init__(self, books):
        self.books = books
        self.index = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self.index < len(self.books):
            self.index += 1
            book = self.books[self.index-1]
            return book
        else:
            raise StopIteration

@log_actions
def display_function(Library):
    for book in Library:
        print(book)

books = Library()

books.add_book(Book("Ultralearning", "Cal Newport", False))
books.add_book(Book("Deep Work", "Cal Newport", False))
books.add_book(Book("Alchemist", "N/A", True))

display_function(books)

books.borrow_book("Ultralearning")

display_function(books)

books.return_book("Alchemist")

display_function(books)
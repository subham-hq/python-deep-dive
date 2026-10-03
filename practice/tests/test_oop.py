"""Tests for the two OOP exercises in oop/."""

import time

import pytest

import library_book_lending_system as lending
import task_manager
from library_book_lending_system import Book, Library, LibraryIterator
from task_manager import Task, TaskCollection, TaskIterator


@pytest.fixture
def library() -> Library:
    lib = Library()
    lib.add_book(Book("Deep Work", "Cal Newport"))
    lib.add_book(Book("The Alchemist", "Paulo Coelho", is_borrowed=True))
    return lib


@pytest.fixture
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip the 0.6 s "Executing..." animation in log_actions (restored after the test)."""
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)


# --------------------------------------------------------------- library ----


def test_book_str_shows_availability() -> None:
    assert str(Book("Deep Work", "Cal Newport")) == "Deep Work by Cal Newport (Available)"
    assert str(Book("Deep Work", "Cal Newport", True)) == "Deep Work by Cal Newport (Borrowed)"


def test_library_iterates_in_insertion_order(library: Library) -> None:
    assert [book.title for book in library] == ["Deep Work", "The Alchemist"]


def test_library_can_be_iterated_more_than_once(library: Library) -> None:
    # Each iter() call returns a fresh LibraryIterator, so a second loop is not empty.
    assert len(list(library)) == len(list(library)) == 2


def test_library_iterator_is_its_own_iterator_and_exhausts(library: Library) -> None:
    iterator = iter(library)
    assert isinstance(iterator, LibraryIterator)
    assert iter(iterator) is iterator
    next(iterator)
    next(iterator)
    with pytest.raises(StopIteration):
        next(iterator)


def test_borrow_and_return_toggle_status(library: Library) -> None:
    library.borrow_book("Deep Work")
    assert library.books[0].is_borrowed
    library.return_book("Deep Work")
    assert not library.books[0].is_borrowed


def test_cannot_borrow_a_borrowed_book(library: Library) -> None:
    with pytest.raises(ValueError, match="already borrowed"):
        library.borrow_book("The Alchemist")


def test_cannot_return_a_book_that_is_not_borrowed(library: Library) -> None:
    with pytest.raises(ValueError, match="not borrowed"):
        library.return_book("Deep Work")


@pytest.mark.parametrize("action", ["borrow_book", "return_book"])
def test_unknown_title_raises_lookup_error(library: Library, action: str) -> None:
    with pytest.raises(LookupError, match="No book titled 'Missing'"):
        getattr(library, action)("Missing")


def test_remove_book(library: Library) -> None:
    first = library.books[0]
    library.remove_book(first)
    assert first not in library.books


@pytest.mark.usefixtures("no_sleep")
def test_display_function_is_decorated_and_prints_each_book(
    library: Library, capsys: pytest.CaptureFixture[str]
) -> None:
    assert lending.display_function.__name__ == "display_function"  # functools.wraps
    lending.display_function(library)
    out = capsys.readouterr().out
    assert out.startswith("Executing display_function...\n")
    assert "Deep Work by Cal Newport (Available)\n" in out
    assert "The Alchemist by Paulo Coelho (Borrowed)\n" in out
    assert "Completed display_function in" in out


@pytest.mark.usefixtures("no_sleep")
def test_lending_demo_runs(capsys: pytest.CaptureFixture[str]) -> None:
    lending.main()
    out = capsys.readouterr().out
    assert out.count("Executing display_function...") == 3
    # Final state: Ultralearning was borrowed, The Alchemist was returned.
    last_block = out.rsplit("Executing display_function...", 1)[1]
    assert "Ultralearning by Scott H. Young (Borrowed)" in last_block
    assert "The Alchemist by Paulo Coelho (Available)" in last_block


# ---------------------------------------------------------- task manager ----


def test_task_str() -> None:
    assert str(Task("Ship it", "High")) == "Ship it (Priority: High)"


def test_task_iterator_yields_tasks_then_stops() -> None:
    tasks = [Task("a", "Low"), Task("b", "High")]
    iterator = TaskIterator(tasks)
    assert iter(iterator) is iterator
    assert list(iterator) == tasks
    with pytest.raises(StopIteration):
        next(iterator)


def test_task_collection_is_reiterable() -> None:
    collection = TaskCollection()
    collection.add_task(Task("a", "Low"))
    collection.add_task(Task("b", "High"))
    assert [t.title for t in collection] == [t.title for t in collection] == ["a", "b"]


def test_task_manager_demo_runs(capsys: pytest.CaptureFixture[str]) -> None:
    assert task_manager.display_tasks.__name__ == "display_tasks"  # functools.wraps
    task_manager.main()
    lines = capsys.readouterr().out.splitlines()
    assert lines[:5] == [
        "",
        "Running: display_tasks",
        "Learn Python Decorators (Priority: High)",
        "Practice Iterators (Priority: Medium)",
        "Complete Mini Project (Priority: High)",
    ]
    assert lines[5].startswith("Finished in ")

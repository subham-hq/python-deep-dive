"""Tests for @time_it and @retry in decorators.py."""

import re
import time

import pytest

from decorators import retry, time_it


@pytest.fixture
def sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Replace time.sleep with a recorder, so retry tests run instantly.

    decorators.py calls time.sleep through the module, so it sees the patch.
    """
    calls: list[float] = []
    monkeypatch.setattr(time, "sleep", calls.append)
    return calls


class FlakyService:
    """A stand-in for an unreliable call: `fetch` fails `failures` times, then returns 'ok'."""

    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.calls = 0

    def fetch(self) -> str:
        self.calls += 1
        if self.calls <= self.failures:
            raise ConnectionError(f"failure {self.calls}")
        return "ok"


# ---------------------------------------------------------------- time_it ----


def test_time_it_passes_arguments_and_return_value_through() -> None:
    @time_it
    def add(a: int, b: int = 0) -> int:
        return a + b

    assert add(2, b=3) == 5


def test_time_it_prints_the_function_name_and_duration(
    capsys: pytest.CaptureFixture[str],
) -> None:
    @time_it
    def work() -> None:
        pass

    work()

    assert re.fullmatch(r"work took \d+\.\d{4} seconds\n", capsys.readouterr().out)


def test_time_it_preserves_name_and_docstring() -> None:
    @time_it
    def documented() -> None:
        """The original docstring."""

    assert documented.__name__ == "documented"
    assert documented.__doc__ == "The original docstring."


def test_time_it_lets_exceptions_propagate() -> None:
    @time_it
    def broken() -> None:
        raise KeyError("missing")

    with pytest.raises(KeyError, match="missing"):
        broken()


# ------------------------------------------------------------------ retry ----


def test_retry_returns_immediately_on_first_success(sleeps: list[float]) -> None:
    service = FlakyService(failures=0)

    assert retry(times=3, delay=1)(service.fetch)() == "ok"
    assert service.calls == 1
    assert sleeps == []


def test_retry_recovers_after_transient_failures(sleeps: list[float]) -> None:
    service = FlakyService(failures=2)

    assert retry(times=3, delay=0.5)(service.fetch)() == "ok"
    assert service.calls == 3
    assert sleeps == [0.5, 0.5]


def test_retry_reraises_the_last_error_and_never_sleeps_after_it(sleeps: list[float]) -> None:
    service = FlakyService(failures=10)

    with pytest.raises(ConnectionError, match="failure 3"):
        retry(times=3, delay=2)(service.fetch)()

    assert service.calls == 3
    assert sleeps == [2, 2]  # between attempts only: 3 attempts, 2 waits


def test_retry_with_a_single_attempt_never_sleeps(sleeps: list[float]) -> None:
    service = FlakyService(failures=1)

    with pytest.raises(ConnectionError):
        retry(times=1, delay=5)(service.fetch)()

    assert service.calls == 1
    assert sleeps == []


def test_retry_does_not_catch_keyboard_interrupt(sleeps: list[float]) -> None:
    calls = 0

    @retry(times=3, delay=1)
    def interrupted() -> None:
        nonlocal calls
        calls += 1
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        interrupted()

    assert calls == 1  # only Exception subclasses are retried
    assert sleeps == []


def test_retry_reports_each_attempt(
    sleeps: list[float], capsys: pytest.CaptureFixture[str]
) -> None:
    service = FlakyService(failures=1)

    retry(times=2, delay=1)(service.fetch)()

    assert capsys.readouterr().out.splitlines() == [
        "fetch - (1)",
        "fetch - attempt 1 failed: failure 1",
        "Retrying in 1 seconds...",
        "fetch - (2)",
    ]


def test_retry_preserves_name_and_docstring() -> None:
    @retry(times=2, delay=0)
    def fetch() -> None:
        """Fetch something."""

    assert fetch.__name__ == "fetch"
    assert fetch.__doc__ == "Fetch something."


@pytest.mark.parametrize(
    ("times", "delay", "message"),
    [
        (0, 1, "times must be at least 1"),
        (-2, 1, "times must be at least 1"),
        (3, -1, "delay must be non-negative"),
    ],
)
def test_retry_rejects_bad_arguments_up_front(times: int, delay: float, message: str) -> None:
    # Regression: times=0 used to produce a wrapper that silently returned None.
    with pytest.raises(ValueError, match=message):
        retry(times=times, delay=delay)

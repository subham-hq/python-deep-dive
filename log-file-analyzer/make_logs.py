import random
from collections.abc import Iterator

LEVELS = ["INFO", "INFO", "INFO", "DEBUG", "WARNING", "ERROR"]
MESSAGES = [
    "user logged in", "payment processed", "cache miss",
    "db connection slow", "invalid token", "timeout contacting service",
]


def fake_lines(n: int) -> Iterator[str]:
    for i in range(n):
        yield (
            f"2026-06-11 10:{i % 60:02d}:{i % 60:02d} "
            f"{random.choice(LEVELS)} {random.choice(MESSAGES)}"
        )


def main() -> None:
    """Write 100,000 synthetic log lines to app.log in the current directory."""
    with open("app.log", "w", encoding="utf-8") as f:
        for line in fake_lines(100_000):
            f.write(line + "\n")
    print("wrote app.log")


# Guarded so that importing this module (e.g. from tests) never overwrites app.log.
if __name__ == "__main__":
    main()

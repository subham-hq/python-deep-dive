import random

LEVELS = ["INFO", "INFO", "INFO", "DEBUG", "WARNING", "ERROR"]
MESSAGES = [
    "user logged in", "payment processed", "cache miss",
    "db connection slow", "invalid token", "timeout contacting service",
]

def fake_lines(n):
    for i in range(n):
        yield f"2026-06-11 10:{i % 60:02d}:{i % 60:02d} {random.choice(LEVELS)} {random.choice(MESSAGES)}"

with open("app.log", "w") as f:
    for line in fake_lines(100_000):
        f.write(line + "\n")
print("wrote app.log")
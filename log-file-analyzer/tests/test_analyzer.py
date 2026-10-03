"""Tests for the parse -> only -> Paginator pipeline in analyzer.py."""

import itertools
import re
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from analyzer import Paginator, ParseStats, Record, main, only, parse, timer

INFO = "2026-06-11 10:00:00 INFO user logged in"
ERROR = "2026-06-11 10:01:01 ERROR timeout contacting service"


def write_log(path: Path, *lines: str) -> Path:
    """Write `lines` to `path`, one per line with a trailing newline, and return it."""
    path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
    return path


def record(level: str, msg: str = "m", ts: str = "2026-06-11 10:00:00") -> Record:
    return {"ts": ts, "level": level, "msg": msg}


# ------------------------------------------------------------------ parse ----


def test_parse_splits_each_line_into_a_record(tmp_path: Path) -> None:
    log = write_log(tmp_path / "app.log", INFO, ERROR)

    assert list(parse(log)) == [
        {"ts": "2026-06-11 10:00:00", "level": "INFO", "msg": "user logged in"},
        {"ts": "2026-06-11 10:01:01", "level": "ERROR", "msg": "timeout contacting service"},
    ]


def test_parse_keeps_spaces_inside_the_message(tmp_path: Path) -> None:
    log = write_log(tmp_path / "app.log", "2026-06-11 10:00:00 WARNING  two  spaces  ")

    assert next(parse(log))["msg"] == " two  spaces  "


def test_parse_reads_the_last_line_without_a_trailing_newline(tmp_path: Path) -> None:
    log = tmp_path / "app.log"
    log.write_text(f"{INFO}\n{ERROR}", encoding="utf-8")

    assert [r["level"] for r in parse(log)] == ["INFO", "ERROR"]


def test_parse_does_not_open_the_file_until_first_pulled(tmp_path: Path) -> None:
    records = parse(tmp_path / "missing.log")  # a generator: nothing has run yet

    with pytest.raises(FileNotFoundError):
        next(records)


def test_parse_reads_only_as_far_as_the_consumer_pulls(tmp_path: Path) -> None:
    log = write_log(tmp_path / "app.log", *[INFO] * 100)
    stats = ParseStats()

    records = parse(log, stats)
    next(records)
    next(records)
    records.close()

    assert stats.lines_read == 2


@pytest.mark.parametrize(
    "bad_line",
    [
        pytest.param("", id="blank"),
        pytest.param("   ", id="whitespace-only"),
        pytest.param("2026-06-11 10:00:00 ERROR", id="truncated-no-message"),
        pytest.param("2026-06-11 10:00:00", id="truncated-no-level"),
        pytest.param("garbage", id="single-field"),
        pytest.param("2026-06-11  10:00:00 INFO double space", id="empty-field"),
    ],
)
def test_parse_skips_and_counts_malformed_lines(tmp_path: Path, bad_line: str) -> None:
    log = write_log(tmp_path / "app.log", INFO, bad_line, ERROR)
    stats = ParseStats()

    levels = [r["level"] for r in parse(log, stats)]

    assert levels == ["INFO", "ERROR"]
    assert stats == ParseStats(lines_read=3, malformed=1)


def test_parse_works_without_a_stats_object(tmp_path: Path) -> None:
    log = write_log(tmp_path / "app.log", INFO, "", ERROR)

    assert len(list(parse(log))) == 2


def test_parse_stats_are_independent_per_pass(tmp_path: Path) -> None:
    # Regression: a shared module-level counter carried pass 1's lines into pass 2.
    log = write_log(tmp_path / "app.log", *[INFO] * 10)
    first, second = ParseStats(), ParseStats()

    next(parse(log, first))
    list(parse(log, second))

    assert first.lines_read == 1
    assert second.lines_read == 10


# ------------------------------------------------------------------- only ----


def test_only_keeps_matching_records_in_order() -> None:
    records = [
        record("INFO", "a"),
        record("ERROR", "b"),
        record("DEBUG", "c"),
        record("ERROR", "d"),
    ]

    assert [r["msg"] for r in only(records, "ERROR")] == ["b", "d"]


def test_only_matches_the_level_exactly() -> None:
    records = [record("error"), record("ERRORS"), record("ERROR")]

    assert list(only(records, "ERROR")) == [record("ERROR")]


def test_only_with_no_matches_yields_nothing() -> None:
    assert list(only([record("INFO"), record("DEBUG")], "ERROR")) == []


def test_only_is_lazy_over_an_endless_source() -> None:
    endless = itertools.cycle([record("INFO"), record("ERROR")])

    errors = only(endless, "ERROR")

    assert next(errors)["level"] == "ERROR"
    assert next(errors)["level"] == "ERROR"


# -------------------------------------------------------------- Paginator ----


def test_paginator_over_empty_input_yields_no_pages() -> None:
    assert list(Paginator([], 3)) == []


def test_paginator_exact_multiple_has_no_trailing_empty_page() -> None:
    assert list(Paginator(range(6), 3)) == [[0, 1, 2], [3, 4, 5]]


def test_paginator_final_page_is_short() -> None:
    assert list(Paginator(range(7), 3)) == [[0, 1, 2], [3, 4, 5], [6]]


def test_paginator_page_larger_than_input_is_one_short_page() -> None:
    assert list(Paginator(["a", "b"], 10)) == [["a", "b"]]


def test_paginator_page_size_one() -> None:
    assert list(Paginator("abc", 1)) == [["a"], ["b"], ["c"]]


def test_paginator_accepts_a_plain_list() -> None:
    # Regression: next() on a list raised TypeError before the source was wrapped in iter().
    assert next(Paginator([1, 2, 3], 2)) == [1, 2]


@pytest.mark.parametrize("page_size", [0, -1])
def test_paginator_rejects_a_page_size_below_one(page_size: int) -> None:
    with pytest.raises(ValueError, match="page_size must be at least 1"):
        Paginator([1, 2, 3], page_size)


def test_paginator_stays_exhausted() -> None:
    pages = Paginator([1], 5)

    assert next(pages) == [1]
    with pytest.raises(StopIteration):
        next(pages)
    with pytest.raises(StopIteration):
        next(pages)


def test_paginator_is_its_own_iterator_and_single_use() -> None:
    pages = Paginator(range(4), 2)

    assert iter(pages) is pages
    assert list(pages) == [[0, 1], [2, 3]]
    assert list(pages) == []


def test_paginator_pulls_only_one_page_from_its_source() -> None:
    source = itertools.count()

    first = next(Paginator(source, 3))

    assert first == [0, 1, 2]
    assert next(source) == 3  # nothing beyond the first page was consumed


def test_pipeline_pages_skip_malformed_lines(tmp_path: Path) -> None:
    log = write_log(tmp_path / "app.log", ERROR, "", INFO, "garbage", ERROR, "   ", ERROR)
    stats = ParseStats()

    pages = list(Paginator(only(parse(log, stats), "ERROR"), 2))

    assert [len(page) for page in pages] == [2, 1]
    assert all(r["level"] == "ERROR" for page in pages for r in page)
    assert stats == ParseStats(lines_read=7, malformed=3)


# ------------------------------------------------------------------ timer ----


def test_timer_prints_elapsed_time(capsys: pytest.CaptureFixture[str]) -> None:
    with timer():
        pass

    assert re.fullmatch(r"\[Timer\] whole run: \d+\.\d{4} seconds\n", capsys.readouterr().out)


def test_timer_still_prints_when_the_block_raises(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(RuntimeError, match="boom"), timer():
        raise RuntimeError("boom")

    assert "[Timer] whole run:" in capsys.readouterr().out


# ------------------------------------------------------------------- main ----


@pytest.fixture
def in_tmp_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run the test from an empty temporary directory, where main() looks for app.log."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_main_reports_lines_read_per_pass(
    in_tmp_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # 5 ERRORs end on line 9, so pass 1 stops there; one blank line is malformed.
    lines = [INFO, ERROR, ERROR, INFO, "", ERROR, INFO, ERROR, ERROR, INFO, ERROR, INFO]
    write_log(in_tmp_dir / "app.log", *lines)

    main()

    out = capsys.readouterr().out.splitlines()
    assert out[0] == "first ERROR page ready after reading only 9 lines"
    assert out[1] == "first ERROR page:"
    assert out[2:7] == [
        "  {'ts': '2026-06-11 10:01:01', 'level': 'ERROR', 'msg': 'timeout contacting service'}"
    ] * 5
    assert out[7] == "Ready after reading 12 lines (1 malformed, skipped)"
    assert out[8] == "Counter({'ERROR': 6, 'INFO': 5})"
    assert re.fullmatch(r"main took \d+\.\d{4} seconds", out[9])


def test_main_handles_a_log_with_no_errors(
    in_tmp_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Regression: next() on an empty Paginator used to escape main() as StopIteration.
    write_log(in_tmp_dir / "app.log", INFO, INFO)

    main()

    out = capsys.readouterr().out.splitlines()
    assert out[0] == "first ERROR page ready after reading only 2 lines"
    assert out[2] == "Ready after reading 2 lines (0 malformed, skipped)"


def test_main_prints_the_first_page_before_reading_the_rest_of_the_file(
    in_tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Regression: a line count taken before pass 1 read the whole file before
    # the "lazy" page was printed. Log every line read and every print, in order.
    write_log(in_tmp_dir / "app.log", *[ERROR] * 5, *[INFO] * 95)
    events: list[str] = []

    def logged(lines: Iterable[str]) -> Iterator[str]:
        for line in lines:
            events.append("read")
            yield line

    @contextmanager
    def logging_open(path: str, encoding: str) -> Iterator[Iterator[str]]:
        with open(path, encoding=encoding) as f:
            yield logged(f)

    def logging_print(*args: object) -> None:
        events.append("print")

    monkeypatch.setattr("analyzer.open", logging_open, raising=False)
    monkeypatch.setattr("analyzer.print", logging_print, raising=False)

    main()

    assert events.index("print") == 5           # only the page's 5 lines read before output
    assert events.count("read") == 5 + 100      # pass 1's page, then pass 2's full read

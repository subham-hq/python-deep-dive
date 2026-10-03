"""End-to-end check of the fetch benchmarks against the real server app.

The server from server.py is started in a background thread on a free port,
and each benchmark is pointed at it with a handful of requests instead of 200.
Skipped when aiohttp or httpx is not installed (see requirements.txt).
"""

import asyncio
import threading
from collections.abc import Iterator
from types import ModuleType

import pytest

pytest.importorskip("aiohttp")
pytest.importorskip("httpx")

from aiohttp import web

import bench_fetch_asyncio
import bench_fetch_httpx
import bench_fetch_threaded
import bench_fetch_urllib
import server

REQUESTS = 5


@pytest.fixture(scope="module")
def server_url() -> Iterator[str]:
    loop = asyncio.new_event_loop()
    runner = web.AppRunner(server.app)
    loop.run_until_complete(runner.setup())
    site = web.TCPSite(runner, "127.0.0.1", 0)  # port 0: let the OS pick a free port
    loop.run_until_complete(site.start())
    host, port = runner.addresses[0][:2]

    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    try:
        yield f"http://{host}:{port}"
    finally:
        asyncio.run_coroutine_threadsafe(runner.cleanup(), loop).result(timeout=5)
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=5)
        loop.close()


BENCHMARKS = (bench_fetch_urllib, bench_fetch_threaded, bench_fetch_httpx, bench_fetch_asyncio)


@pytest.fixture
def point_at(server_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    for module in BENCHMARKS:
        monkeypatch.setattr(module, "URL", server_url)
        monkeypatch.setattr(module, "REQUESTS", REQUESTS)


def assert_all_succeeded(out: str) -> None:
    assert f"Completed {REQUESTS} requests\n" in out
    assert f"Successful: {REQUESTS}\n" in out
    assert "Elapsed time: " in out


@pytest.mark.usefixtures("point_at")
@pytest.mark.parametrize(
    "bench", [bench_fetch_urllib, bench_fetch_threaded, bench_fetch_httpx], ids=lambda m: m.__name__
)
def test_sync_benchmarks(bench: ModuleType, capsys: pytest.CaptureFixture[str]) -> None:
    bench.main()
    assert_all_succeeded(capsys.readouterr().out)


@pytest.mark.usefixtures("point_at")
@pytest.mark.parametrize("limit", [1, REQUESTS])
def test_asyncio_benchmark(limit: int, capsys: pytest.CaptureFixture[str]) -> None:
    asyncio.run(bench_fetch_asyncio.main(limit))
    out = capsys.readouterr().out
    assert f"Semaphore: {limit}\n" in out
    assert_all_succeeded(out)

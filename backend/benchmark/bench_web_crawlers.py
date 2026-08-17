"""Benchmark suite for web crawler telemetry (roadmap
development_tool.md §12.7, issue #70).

Per-request timing/response-code tracking as literally specced isn't
available from Python: the actual HTTP requests happen inside the compiled
`base` C++ extension (`base.run_board_crawler`), which only calls back into
Python once per successful download (`on_image_saved`) and via free-form
`on_status` progress strings -- no per-request hook crosses the pybind
boundary. `ImageBoardCrawler` (backend/src/web/crawlers/image_board_crawler.py)
now instruments what IS available: exact whole-crawl elapsed time and
images/sec (from the real on_image_saved count), plus best-effort
timeout/CAPTCHA/error counters derived by substring-matching on_status text.
See that file's docstring for the same caveat in more detail.

This benchmark drives that instrumentation against the real Danbooru/
Gelbooru/Sankaku crawlers with a small `limit`, producing a "General-suite"
JSON (BenchmarkManager.save_json()'s {suite, system, results} schema) the
frontend dashboard already parses generically via its `kind: 'General'`
discriminator (frontend/src/math/benchmark.ts).

This makes real outbound HTTP requests to third-party image boards and
requires network access plus whatever API keys/config those crawlers need
(assets/api/*_api_key.json.enc) -- **not run automatically** by CI or by
`run_all.py`. Standalone only, and only when explicitly opted in:

    RUN_LIVE_CRAWLER_BENCHMARK=1 python backend/benchmark/bench_web_crawlers.py

Without that env var, every benchmark no-ops (prints why) so the file can
still be imported/collected safely and its telemetry-shape contract stays
exercised by backend/test/web/test_image_board_crawler.py.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from backend.benchmark.managers import BenchmarkManager  # noqa: E402

_LIVE = os.environ.get("RUN_LIVE_CRAWLER_BENCHMARK", "0") != "0"
_CRAWL_LIMIT = int(os.environ.get("CRAWLER_BENCHMARK_LIMIT", "20"))

runner = BenchmarkManager("Web Crawler Telemetry")


def _run_crawler_and_record(crawler_cls, tag: str, extra_config: dict) -> None:
    if not _LIVE:
        print(
            f"    [{tag}] skipped — set RUN_LIVE_CRAWLER_BENCHMARK=1 to make "
            "real network requests to this board."
        )
        return
    config = {"selection_mode": "Download All (Default)", "limit": _CRAWL_LIMIT, **extra_config}
    crawler = crawler_cls(config)
    t0 = time.perf_counter()
    total = crawler.run()
    wall_sec = round(time.perf_counter() - t0, 3)
    telemetry = dict(crawler.telemetry)
    telemetry["total_downloaded"] = total
    telemetry["wall_sec"] = wall_sec
    print(f"    [{tag}] {telemetry}")


@runner.benchmark("danbooru_crawl_telemetry", iterations=1, warmup=0)
def bench_danbooru():
    from backend.src.web.crawlers.danbooru_crawler import DanbooruCrawler

    _run_crawler_and_record(DanbooruCrawler, "danbooru", {})


@runner.benchmark("gelbooru_crawl_telemetry", iterations=1, warmup=0)
def bench_gelbooru():
    from backend.src.web.crawlers.gelbooru_crawler import GelbooruCrawler

    _run_crawler_and_record(GelbooruCrawler, "gelbooru", {})


@runner.benchmark("sankaku_crawl_telemetry", iterations=1, warmup=0)
def bench_sankaku():
    from backend.src.web.crawlers.sankaku_crawler import SankakuCrawler

    _run_crawler_and_record(SankakuCrawler, "sankaku", {})


if __name__ == "__main__":
    if not _LIVE:
        print(
            "RUN_LIVE_CRAWLER_BENCHMARK is not set — every benchmark below will "
            "no-op. This is the default: this file makes real outbound HTTP "
            f"requests when enabled (limit={_CRAWL_LIMIT} images/board)."
        )
    runner.run()
    runner.print_results()
    runner.save_json()

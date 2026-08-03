"""Tests for ImageBoardCrawler's §12.7 (issue #70) telemetry instrumentation
— per-crawl timing/throughput and best-effort timeout/CAPTCHA/error counters
derived from the on_status/on_image_saved signals.
"""

import json
from unittest.mock import patch

from backend.src.web.crawlers.image_board_crawler import ImageBoardCrawler


def _crawler(config=None):
    return ImageBoardCrawler(config or {"url": "http://example.com"})


def test_telemetry_starts_zeroed():
    crawler = _crawler()
    assert crawler.telemetry == {
        "images_saved": 0,
        "status_messages": 0,
        "timeout_count": 0,
        "captcha_count": 0,
        "error_count": 0,
        "elapsed_sec": None,
        "images_per_sec": None,
    }


def test_on_image_saved_increments_counter():
    crawler = _crawler()
    crawler.on_image_saved.emit("/tmp/img1.jpg")
    crawler.on_image_saved.emit("/tmp/img2.jpg")
    assert crawler.telemetry["images_saved"] == 2


def test_status_message_counts_timeout():
    crawler = _crawler()
    crawler.on_status.emit("Request to page 3 timed out, retrying")
    assert crawler.telemetry["timeout_count"] == 1
    assert crawler.telemetry["status_messages"] == 1


def test_status_message_counts_captcha():
    crawler = _crawler()
    crawler.on_status.emit("CAPTCHA challenge encountered, pausing")
    assert crawler.telemetry["captcha_count"] == 1


def test_status_message_counts_error():
    crawler = _crawler()
    crawler.on_status.emit("Critical Error in C++ crawler: connection refused")
    assert crawler.telemetry["error_count"] == 1


def test_normal_status_message_not_miscounted():
    crawler = _crawler()
    crawler.on_status.emit("Crawl starting with selection mode: Download All (Default)")
    assert crawler.telemetry["status_messages"] == 1
    assert crawler.telemetry["timeout_count"] == 0
    assert crawler.telemetry["captcha_count"] == 0
    assert crawler.telemetry["error_count"] == 0


@patch("backend.src.web.crawlers.image_board_crawler.base")
def test_run_records_elapsed_and_throughput(mock_base):
    def _fake_run(crawler_name, config_json, callback_obj):
        callback_obj.on_image_saved.emit("/tmp/a.jpg")
        callback_obj.on_image_saved.emit("/tmp/b.jpg")
        return 2

    mock_base.run_board_crawler.side_effect = _fake_run
    config = {"url": "http://example.com"}
    crawler = ImageBoardCrawler(config)

    result = crawler.run()

    assert result == 2
    mock_base.run_board_crawler.assert_called_once_with(
        "imageboard", json.dumps(config), crawler
    )
    assert crawler.telemetry["images_saved"] == 2
    assert crawler.telemetry["elapsed_sec"] is not None
    assert crawler.telemetry["elapsed_sec"] >= 0
    assert crawler.telemetry["images_per_sec"] is not None


@patch("backend.src.web.crawlers.image_board_crawler.base")
def test_run_failure_still_records_elapsed(mock_base):
    mock_base.run_board_crawler.side_effect = Exception("C++ crawler crash")
    crawler = ImageBoardCrawler({"url": "http://example.com"})

    result = crawler.run()

    assert result == 0
    assert crawler.telemetry["elapsed_sec"] is not None
    assert crawler.telemetry["error_count"] == 1  # "Critical Error..." status emitted

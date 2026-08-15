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


@patch("backend.src.web.crawlers.image_board_crawler.base")
def test_rating_filter_normalization(mock_base):
    mock_base.run_board_crawler.return_value = 0
    crawler = ImageBoardCrawler({"url": "http://example.com", "tags": "scenery", "rating": "general"})
    crawler.run()

    # Verify rating:general was appended to tags
    expected_config = {"url": "http://example.com", "tags": "scenery rating:general", "rating": "general"}
    mock_base.run_board_crawler.assert_called_once_with(
        "imageboard", json.dumps(expected_config), crawler
    )


@patch("backend.src.web.crawlers.image_board_crawler.base")
def test_safebooru_crawler_backend_name_and_preset(mock_base):
    from backend.src.web.crawlers.safebooru_crawler import SafebooruCrawler

    mock_base.run_board_crawler.return_value = 0
    crawler = SafebooruCrawler({"tags": "landscape", "rating": "general"})
    assert crawler.config["url"] == "https://safebooru.org"
    assert crawler.get_crawler_backend_name() == "gelbooru"
    assert crawler.normalize_rating_tag("general") is None

    # Verify Safebooru ignores rating filter (no-op)
    crawler.run()
    expected_config = {"tags": "landscape", "rating": "general", "url": "https://safebooru.org"}
    mock_base.run_board_crawler.assert_called_once_with(
        "gelbooru", json.dumps(expected_config), crawler
    )


def test_sankaku_rating_normalization():
    from backend.src.web.crawlers.sankaku_crawler import SankakuCrawler

    crawler = SankakuCrawler({})
    assert crawler.normalize_rating_tag("safe") == "rating:safe"
    assert crawler.normalize_rating_tag("general") == "rating:safe"
    assert crawler.normalize_rating_tag("questionable") == "rating:questionable"
    assert crawler.normalize_rating_tag("explicit") == "rating:explicit"



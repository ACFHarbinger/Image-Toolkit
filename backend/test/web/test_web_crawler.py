import json
import pytest
from unittest.mock import MagicMock, patch
from backend.src.web.crawlers.image_crawler import ImageCrawler


def test_init():
    config = {"url": "http://example.com", "download_dir": "/tmp"}
    crawler = ImageCrawler(config)
    assert crawler.config == config
    assert crawler._is_running is True


def test_stop():
    config = {"url": "http://example.com", "download_dir": "/tmp"}
    crawler = ImageCrawler(config)
    crawler.on_status = MagicMock()
    
    crawler.stop()
    assert crawler._is_running is False
    crawler.on_status.emit.assert_called_once_with("Cancellation pending...")


def test_on_status_emitted():
    config = {"url": "http://example.com", "download_dir": "/tmp"}
    crawler = ImageCrawler(config)
    crawler.on_status = MagicMock()
    
    crawler.on_status_emitted("Test status message")
    crawler.on_status.emit.assert_called_once_with("Test status message")


def test_on_error_emitted():
    config = {"url": "http://example.com", "download_dir": "/tmp"}
    crawler = ImageCrawler(config)
    crawler.on_status = MagicMock()
    
    crawler.on_error_emitted("Test error message")
    crawler.on_status.emit.assert_called_once_with("ERROR: Test error message")


@patch("backend.src.web.crawlers.image_crawler.base")
def test_run_success(mock_base):
    mock_base.run_image_crawler.return_value = 42
    config = {"url": "http://example.com", "download_dir": "/tmp"}
    crawler = ImageCrawler(config)
    crawler.on_finished = MagicMock()

    result = crawler.run()
    
    assert result == 42
    mock_base.run_image_crawler.assert_called_once_with(json.dumps(config), crawler)
    crawler.on_finished.emit.assert_called_once_with("Finished. Downloaded 42 images.")


@patch("backend.src.web.crawlers.image_crawler.base")
def test_run_failure(mock_base):
    mock_base.run_image_crawler.side_effect = Exception("C++ crawler crash")
    config = {"url": "http://example.com", "download_dir": "/tmp"}
    crawler = ImageCrawler(config)
    crawler.on_status = MagicMock()
    crawler.on_finished = MagicMock()

    result = crawler.run()
    
    assert result == 0
    mock_base.run_image_crawler.assert_called_once_with(json.dumps(config), crawler)
    crawler.on_status.emit.assert_called_once_with("ERROR: Critical error in C++ crawler: C++ crawler crash")
    crawler.on_finished.emit.assert_called_once_with("Finished with error: C++ crawler crash")

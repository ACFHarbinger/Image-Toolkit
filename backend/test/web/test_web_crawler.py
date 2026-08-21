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


def test_clean_image_url():
    config = {"url": "http://example.com", "download_dir": "/tmp"}
    crawler = ImageCrawler(config)

    assert crawler._clean_image_url("data:image/png;base64,...") is None
    assert crawler._clean_image_url("http://example.com/icon.svg") is None
    assert (
        crawler._clean_image_url("https://i0.wp.com/example.com/photo.jpg")
        == "https://example.com/photo.jpg"
    )
    assert (
        crawler._clean_image_url("https://example.com/sample.png")
        == "https://example.com/sample.png"
    )


@patch.object(ImageCrawler, "_try_init_driver", return_value=None)
@patch.object(ImageCrawler, "_process_requests_page")
@patch.object(ImageCrawler, "_download_single_image")
def test_run_success(mock_download, mock_requests_page, mock_init_driver):
    mock_requests_page.return_value = ["https://example.com/img1.jpg"]
    mock_download.return_value = "/tmp/img1.jpg"

    config = {"url": "https://example.com", "download_dir": "/tmp"}
    crawler = ImageCrawler(config)
    crawler.on_finished = MagicMock()
    crawler.on_image_saved = MagicMock()

    result = crawler.run()

    assert result == 1
    call_args = crawler.on_image_saved.emit.call_args[0][0]
    assert "/tmp/img1.jpg" in call_args
    assert "https://example.com" in call_args
    crawler.on_finished.emit.assert_called_once_with(
        "Crawl finished. Downloaded **1** image(s)!"
    )

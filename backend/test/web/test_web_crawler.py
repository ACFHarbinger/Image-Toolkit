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
    crawler.on_status.publish.assert_called_once_with("Cancellation pending...")


def test_on_status_emitted():
    config = {"url": "http://example.com", "download_dir": "/tmp"}
    crawler = ImageCrawler(config)
    crawler.on_status = MagicMock()

    crawler.on_status_emitted("Test status message")
    crawler.on_status.publish.assert_called_once_with("Test status message")


def test_on_error_emitted():
    config = {"url": "http://example.com", "download_dir": "/tmp"}
    crawler = ImageCrawler(config)
    crawler.on_status = MagicMock()

    crawler.on_error_emitted("Test error message")
    crawler.on_status.publish.assert_called_once_with("ERROR: Test error message")


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
    call_args = crawler.on_image_saved.publish.call_args[0][0]
    assert "/tmp/img1.jpg" in call_args
    assert "https://example.com" in call_args
    crawler.on_finished.publish.assert_called_once_with(
        "Crawl finished. Downloaded **1** image(s)!"
    )


def test_process_selenium_actions_all_types():
    config = {"url": "https://example.com/gallery", "download_dir": "/tmp"}
    crawler = ImageCrawler(config)

    mock_driver = MagicMock()
    mock_driver.current_url = "https://example.com/gallery/img_direct.png"
    mock_driver.page_source = "<html><body>Gallery Page</body></html>"

    # Mock img elements
    img1 = MagicMock()
    img1.get_attribute.side_effect = lambda attr: "https://cdn.example.com/photo1.jpg" if attr == "src" else None
    img2 = MagicMock()
    img2.get_attribute.side_effect = lambda attr: "/photos/photo2.webp" if attr == "data-src" else None

    mock_driver.find_elements.return_value = [img1, img2]

    # Test Download Simple Thumbnail (Legacy)
    actions = [{"type": "Download Simple Thumbnail (Legacy)", "param": None}]
    extracted = crawler._process_selenium_actions(mock_driver, actions, "https://example.com/gallery")
    assert "https://cdn.example.com/photo1.jpg" in extracted
    assert "https://example.com/photos/photo2.webp" in extracted

    # Test Find Element by CSS Selector
    el = MagicMock()
    el.tag_name = "img"
    el.get_attribute.side_effect = lambda attr: "https://cdn.example.com/selected.jpg" if attr == "src" else None
    mock_driver.find_elements.return_value = [el]
    actions = [{"type": "Find Element by CSS Selector", "param": ".photos-list img"}]
    extracted = crawler._process_selenium_actions(mock_driver, actions, "https://example.com/gallery")
    assert "https://cdn.example.com/selected.jpg" in extracted

    # Test Find <img> Number X on Page
    mock_driver.find_elements.return_value = [img1, img2]
    actions = [{"type": "Find <img> Number X on Page", "param": "2"}]
    extracted = crawler._process_selenium_actions(mock_driver, actions, "https://example.com/gallery")
    assert "https://example.com/photos/photo2.webp" in extracted

    # Test Download Current URL as Image
    actions = [{"type": "Download Current URL as Image", "param": None}]
    extracted = crawler._process_selenium_actions(mock_driver, actions, "https://example.com/gallery")
    assert "https://example.com/gallery/img_direct.png" in extracted


def test_sync_cookies_to_session():
    import requests

    config = {"url": "https://example.com", "download_dir": "/tmp"}
    crawler = ImageCrawler(config)

    session = requests.Session()
    mock_driver = MagicMock()
    mock_driver.get_cookies.return_value = [
        {"name": "session_id", "value": "xyz123", "domain": ".example.com", "path": "/"}
    ]

    crawler._sync_cookies_to_session(mock_driver, session)
    assert session.cookies.get("session_id") == "xyz123"


@patch.object(ImageCrawler, "_try_init_driver")
@patch.object(ImageCrawler, "_perform_login")
@patch.object(ImageCrawler, "_sync_cookies_to_session")
@patch.object(ImageCrawler, "_process_selenium_actions", return_value=[])
@patch.object(ImageCrawler, "_process_requests_page", return_value=[])
def test_login_invoked_when_configured(
    mock_requests_page, mock_actions, mock_sync, mock_login, mock_init_driver
):
    mock_driver = MagicMock()
    mock_init_driver.return_value = mock_driver

    config = {
        "url": "https://example.com/album",
        "download_dir": "/tmp",
        "login_config": {
            "url": "https://example.com/login",
            "username": "testuser@example.com",
            "password": "secretpassword",
        },
    }
    crawler = ImageCrawler(config)
    crawler.run()

    mock_login.assert_called_once_with(
        mock_driver,
        "https://example.com/login",
        "testuser@example.com",
        "secretpassword",
    )
    assert mock_sync.call_count >= 1


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
def test_run_success(mock_download, mock_requests_page, mock_init_driver, tmp_path):
    mock_requests_page.return_value = ["https://example.com/img1.jpg"]
    mock_download.return_value = str(tmp_path / "img1.jpg")

    config = {"url": "https://example.com", "download_dir": str(tmp_path)}
    crawler = ImageCrawler(config)
    crawler.on_finished = MagicMock()
    crawler.on_image_saved = MagicMock()

    result = crawler.run()

    assert result == 1
    call_args = crawler.on_image_saved.publish.call_args[0][0]
    assert str(tmp_path / "img1.jpg") in call_args
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
    mock_requests_page, mock_actions, mock_sync, mock_login, mock_init_driver, tmp_path
):
    mock_driver = MagicMock()
    mock_init_driver.return_value = mock_driver

    config = {
        "url": "https://example.com/album",
        "download_dir": str(tmp_path),
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



def test_lazy_sources_are_used_in_browser_and_http():
    from bs4 import BeautifulSoup

    crawler = ImageCrawler({})
    html = '''<img src="data:image/gif;base64,AAAA" data-src="/photos/one.jpg">
              <img src="/placeholder.svg" data-original="/photos/two.jpg">
              <img src="/thumb.jpg" srcset="/large.jpg 1600w, /small.jpg 400w">'''
    soup = BeautifulSoup(html, "html.parser")
    driver = MagicMock()
    elements = []
    for tag in soup.find_all("img"):
        element = MagicMock()
        element.get_attribute.side_effect = tag.get
        elements.append(element)
    driver.find_elements.return_value = elements
    expected = [f"https://example.com/{path}" for path in (
        "photos/one.jpg", "photos/two.jpg", "large.jpg",
    )]
    assert crawler._process_selenium_actions(
        driver, [{"type": "Extract High-Res Preview URL"}], "https://example.com/album"
    ) == expected
    session = MagicMock()
    session.get.return_value.status_code = 200
    session.get.return_value.text = html
    session.get.return_value.url = "https://example.com/album"
    assert crawler._process_requests_page(session, "https://example.com/album", {}) == expected


def test_css_container_extracts_every_image():
    crawler = ImageCrawler({})
    driver = MagicMock()
    container = MagicMock()
    container.tag_name = "div"
    images = []
    for index in range(10):
        image = MagicMock()
        image.get_attribute.side_effect = {"src": f"/photos/{index}.jpg"}.get
        images.append(image)
    container.find_elements.return_value = images
    driver.find_elements.return_value = [container]
    urls = crawler._process_selenium_actions(
        driver, [{"type": "Find Element by CSS Selector", "param": ".photos-list"}],
        "https://example.com/album",
    )
    assert urls == [f"https://example.com/photos/{index}.jpg" for index in range(10)]


def test_http_challenge_is_reported():
    crawler = ImageCrawler({})
    crawler.on_status = MagicMock()
    session = MagicMock()
    session.get.return_value.status_code = 403
    assert crawler._process_requests_page(session, "https://example.com/album", {}) == []
    assert "HTTP 403" in crawler.on_status.publish.call_args.args[0]


def test_browser_download_after_http_rejection(tmp_path):
    import base64

    crawler = ImageCrawler({})
    session = MagicMock()
    session.get.return_value.status_code = 403
    session.get.return_value.headers = {"Content-Type": "text/html"}
    driver = MagicMock()
    content = b"\xff\xd8\xff" + b"x" * 200
    driver.execute_async_script.return_value = {"data": base64.b64encode(content).decode()}
    result = crawler._download_single_image(
        session, "https://example.com/photo.jpg", str(tmp_path), {}, driver=driver,
    )
    assert result == str(tmp_path / "photo.jpg")
    assert (tmp_path / "photo.jpg").read_bytes() == content
    assert driver.execute_async_script.call_args.args[1] == "https://example.com/photo.jpg"


def test_browser_html_is_never_saved_as_image(tmp_path):
    import base64

    crawler = ImageCrawler({})
    session = MagicMock()
    session.get.return_value.status_code = 403
    driver = MagicMock()
    driver.execute_async_script.return_value = {
        "data": base64.b64encode(b"<html>" + b"x" * 200).decode(),
    }
    assert crawler._download_single_image(
        session, "https://example.com/photo.jpg", str(tmp_path), {}, driver=driver,
    ) is None
    assert list(tmp_path.iterdir()) == []


@patch("backend.src.web.crawlers.image_crawler.time.sleep")
def test_configured_eight_pages_download_all_images(mock_sleep, tmp_path):
    import json

    crawler = ImageCrawler({
        "url": "https://example.com/album/abc.html?page=1&hl=en",
        "replace_str": "page=1",
        "replacements": ",".join(f"page={i}" for i in range(2, 9)),
        "download_dir": str(tmp_path),
    })
    crawler.on_image_saved = MagicMock()
    pages = [[f"https://example.com/photos/{i}.jpg" for i in range(start, min(start + 10, 76))]
             for start in range(0, 76, 10)]
    with (
        patch.object(crawler, "_try_init_driver", return_value=None),
        patch.object(crawler, "_process_requests_page", side_effect=pages) as parse,
        patch.object(crawler, "_download_single_image", return_value=str(tmp_path / "image.jpg")) as download,
    ):
        assert crawler.run() == 76
    assert [call.args[1] for call in parse.call_args_list] == [
        f"https://example.com/album/abc.html?page={i}&hl=en" for i in range(1, 9)
    ]
    assert download.call_args_list[-1].args[3]["Referer"].endswith("page=8&hl=en")
    last = json.loads(crawler.on_image_saved.publish.call_args.args[0])
    assert (last["page_num"], last["index_on_page"], last["global_id"]) == (8, 6, 76)


def test_verification_waits_and_reports_timeout():
    # Headless sessions fail immediately on a challenge (cannot solve visual check).
    crawler = ImageCrawler({"headless": True})
    crawler.on_status = MagicMock()
    driver = MagicMock()
    driver.title = "Just a moment..."
    assert crawler._wait_for_browser_access(driver) is False
    assert crawler._access_blocked
    published = crawler.on_status.publish.call_args.args[0]
    assert "headless" in published.lower()


@patch("backend.src.web.crawlers.image_crawler.time.sleep")
def test_failed_download_is_retried_on_following_page(mock_sleep, tmp_path):
    crawler = ImageCrawler({
        "url": "https://example.com/album?page=1",
        "replace_str": "page=1", "replacements": "page=2,page=3",
        "download_dir": str(tmp_path),
    })
    with (
        patch.object(crawler, "_try_init_driver", return_value=None),
        patch.object(crawler, "_process_requests_page", return_value=["https://example.com/image.jpg"]),
        patch.object(crawler, "_download_single_image", side_effect=[None, str(tmp_path / "image.jpg")]) as download,
    ):
        assert crawler.run() == 1
    assert download.call_count == 2


def test_security_verification_detected_from_body():
    crawler = ImageCrawler({})
    driver = MagicMock()
    driver.title = "www.example.com"
    driver.find_element.return_value.text = (
        "Performing security verification\n"
        "This page is displayed while the website verifies you are not a bot."
    )
    assert crawler._browser_has_challenge(driver)
    driver.find_element.return_value.text = "Album photos"
    assert not crawler._browser_has_challenge(driver)


@patch("backend.src.web.crawlers.image_crawler.time.sleep")
def test_verification_resumes_after_challenge_clears(mock_sleep):
    import threading

    crawler = ImageCrawler({})  # non-headless
    driver = MagicMock()
    driver.title = "www.example.com"
    body = MagicMock()
    from unittest.mock import PropertyMock
    type(body).text = PropertyMock(return_value="Album photos")
    driver.find_element.return_value = body

    # After the first challenge fires on_verification_required, simulate the
    # user pressing OK by calling resume() shortly afterwards.
    def _resume_after_event(msg):
        crawler.resume()

    crawler.on_verification_required.subscribe(_resume_after_event)
    with patch.object(crawler, "_browser_has_challenge", side_effect=[True, False]):
        assert crawler._wait_for_browser_access(driver)
    assert not crawler._access_blocked


def test_navigation_timeout_on_challenge_enters_verification_wait():
    from selenium.common.exceptions import TimeoutException

    crawler = ImageCrawler({})
    driver = MagicMock()
    driver.get.side_effect = TimeoutException()
    driver.title = "Just a moment..."
    with patch.object(crawler, "_wait_for_browser_access", return_value=False) as wait:
        assert not crawler._navigate_browser(driver, "https://example.com/album")
    driver.set_page_load_timeout.assert_called_once_with(30)
    wait.assert_called_once_with(driver)


def test_challenge_timeout_stops_entire_crawl(tmp_path):
    crawler = ImageCrawler({
        "url": "https://example.com/album?page=1",
        "replace_str": "page=1", "replacements": "page=2,page=3",
        "download_dir": str(tmp_path), "headless": True,
    })
    crawler.on_finished = MagicMock()
    driver = MagicMock()
    driver.title = "www.example.com"
    driver.find_element.return_value.text = "Performing security verification"
    with (
        patch.object(crawler, "_try_init_driver", return_value=driver),
        patch.object(crawler, "_process_requests_page") as http,
        patch("backend.src.web.crawlers.image_crawler.time.monotonic", side_effect=[0, 16]),
    ):
        assert crawler.run() == 0
    driver.get.assert_called_once_with(crawler.config["url"])
    http.assert_not_called()
    driver.quit.assert_called_once()
    assert "Crawl stopped" in crawler.completion_message
    crawler.on_finished.publish.assert_called_once_with(crawler.completion_message)


def test_login_challenge_prevents_album_navigation(tmp_path):
    crawler = ImageCrawler({
        "url": "https://example.com/album",
        "download_dir": str(tmp_path), "headless": True,
        "login_config": {"url": "https://example.com/login", "username": "test"},
    })
    driver = MagicMock()
    driver.title = "Just a moment..."
    with (
        patch.object(crawler, "_try_init_driver", return_value=driver),
        patch("backend.src.web.crawlers.image_crawler.time.monotonic", side_effect=[0, 16]),
    ):
        assert crawler.run() == 0
    driver.get.assert_called_once_with("https://example.com/login")
    driver.quit.assert_called_once()
    assert "Crawl stopped" in crawler.completion_message


def test_existing_session_never_falls_back_to_fresh_browser(tmp_path):
    crawler = ImageCrawler({
        "url": "https://example.com/album", "download_dir": str(tmp_path),
        "browser": "brave", "attach_existing": True,
    })
    with (
        patch.object(crawler, "_is_port_open", return_value=False),
        patch("selenium.webdriver.Chrome") as chrome,
        patch.object(crawler, "_process_requests_page") as http,
    ):
        assert crawler.run() == 0
    chrome.assert_not_called()
    http.assert_not_called()
    assert "no existing browser session" in crawler.completion_message


def test_existing_session_connects_to_dedicated_port():
    crawler = ImageCrawler({"browser": "brave", "attach_existing": True})
    with (
        patch.object(crawler, "_is_port_open", return_value=True) as port,
        patch.object(crawler, "_find_browser_binary", return_value=None),
        patch.object(crawler, "_connect_debug_browser") as chrome,
    ):
        assert crawler._try_init_driver() is chrome.return_value
    port.assert_called_once_with("127.0.0.1", 9223)
    chrome.assert_called_once_with(9223)
    assert crawler._attached_browser


@patch("backend.src.web.crawlers.image_crawler.time.sleep")
def test_existing_session_skips_login_and_keeps_browser_open(mock_sleep, tmp_path):
    crawler = ImageCrawler({
        "url": "https://example.com/album", "download_dir": str(tmp_path),
        "attach_existing": True,
        "login_config": {"url": "https://example.com/login", "username": "test"},
    })
    driver = MagicMock()
    crawler._attached_browser = True
    with (
        patch.object(crawler, "_try_init_driver", return_value=driver),
        patch.object(crawler, "_perform_login") as login,
        patch.object(crawler, "_process_selenium_actions", return_value=["https://example.com/image.jpg"]),
        patch.object(crawler, "_download_single_image", return_value=str(tmp_path / "image.jpg")),
    ):
        assert crawler.run() == 1
    login.assert_not_called()
    driver.get.assert_called_once_with("https://example.com/album")
    driver.quit.assert_not_called()
    driver.service.stop.assert_called_once()


def test_brave_native_binary_takes_precedence():
    crawler = ImageCrawler({})
    with patch("backend.src.web.crawlers.image_crawler_parts._browser_setup.subprocess.run") as run:
        assert crawler._find_brave_launch_command("/usr/bin/brave") == ["/usr/bin/brave"]
    run.assert_not_called()


def test_flatpak_brave_detection():
    crawler = ImageCrawler({})
    with (
        patch("backend.src.web.crawlers.image_crawler_parts._browser_setup.shutil.which", return_value="/usr/bin/flatpak"),
        patch("backend.src.web.crawlers.image_crawler_parts._browser_setup.subprocess.run") as run,
    ):
        run.return_value.returncode = 0
        assert crawler._find_brave_launch_command(None) == ["/usr/bin/flatpak", "run", "com.brave.Browser"]
        assert run.call_args.args[0] == ["/usr/bin/flatpak", "info", "com.brave.Browser"]
        run.return_value.returncode = 1
        assert crawler._find_brave_launch_command(None) == []


def test_flatpak_detection_timeout():
    import subprocess

    crawler = ImageCrawler({})
    with (
        patch("backend.src.web.crawlers.image_crawler_parts._browser_setup.shutil.which", return_value="/usr/bin/flatpak"),
        patch("backend.src.web.crawlers.image_crawler_parts._browser_setup.subprocess.run", side_effect=subprocess.TimeoutExpired("flatpak", 5)),
    ):
        assert crawler._find_brave_launch_command(None) == []


@patch("backend.src.web.crawlers.image_crawler.time.sleep")
def test_flatpak_launch_uses_app_profile_and_debugger(mock_sleep):
    crawler = ImageCrawler({"browser": "brave", "headless": False})
    with (
        patch.object(crawler, "_find_browser_binary", return_value=None),
        patch.object(crawler, "_find_brave_launch_command", return_value=["/usr/bin/flatpak", "run", "com.brave.Browser"]),
        patch.object(crawler, "_is_port_open", return_value=False),
        patch("backend.src.web.crawlers.image_crawler.os.makedirs"),
        patch("backend.src.web.crawlers.image_crawler_parts._browser_setup.subprocess.Popen") as launch,
        patch.object(crawler, "_connect_debug_browser") as chrome,
        patch("selenium.webdriver.Remote") as remote,
    ):
        assert crawler._try_init_driver() is chrome.return_value
    command = launch.call_args.args[0]
    assert command[:3] == ["/usr/bin/flatpak", "run", "com.brave.Browser"]
    assert any(arg.endswith("/.var/app/com.brave.Browser/config/image-toolkit-crawler") for arg in command)
    assert "--headless=new" not in command
    chrome.assert_called_once_with(9222)
    remote.assert_not_called()


def test_debug_browser_selects_driver_from_running_chromium_version():
    crawler = ImageCrawler({})
    with (
        patch("backend.src.web.crawlers.image_crawler_parts._browser_setup.requests.Session") as session,
        patch("selenium.webdriver.common.selenium_manager.SeleniumManager.binary_paths") as resolve,
        patch("selenium.webdriver.Chrome") as chrome,
        patch("selenium.webdriver.chrome.service.Service") as service,
    ):
        http = session.return_value.__enter__.return_value
        http.get.return_value.json.return_value = {"Browser": "Chrome/142.0.7444.163"}
        resolve.return_value = {"driver_path": "/cache/chromedriver142"}
        assert crawler._connect_debug_browser(9223) is chrome.return_value
    http.get.assert_called_once_with("http://127.0.0.1:9223/json/version", timeout=5)
    assert http.trust_env is False
    args = resolve.call_args.args[0]
    assert args[args.index("--browser-version") + 1] == "142"
    assert "--skip-driver-in-path" in args
    assert "--skip-browser-in-path" in args
    assert "--avoid-browser-download" in args
    service.assert_called_once_with(executable_path="/cache/chromedriver142")
    assert chrome.call_args.kwargs["service"] is service.return_value
    assert chrome.call_args.kwargs["options"].experimental_options["debuggerAddress"] == "127.0.0.1:9223"


def test_driver_connection_error_is_preserved_in_completion(tmp_path):
    from selenium.common.exceptions import SessionNotCreatedException

    crawler = ImageCrawler({
        "url": "https://example.com/album", "download_dir": str(tmp_path),
        "attach_existing": True, "browser": "brave",
    })
    with (
        patch.object(crawler, "_is_port_open", return_value=True),
        patch.object(crawler, "_connect_debug_browser", side_effect=SessionNotCreatedException("driver/browser mismatch")),
        patch.object(crawler, "_process_requests_page") as http,
    ):
        assert crawler.run() == 0
    assert "driver/browser mismatch" in crawler.completion_message
    assert "no existing browser session" not in crawler.completion_message
    http.assert_not_called()


def test_album_login_gate_stops_before_downloading_preview(tmp_path):
    crawler = ImageCrawler({
        "url": "https://example.com/album?page=1", "download_dir": str(tmp_path),
        "replace_str": "page=1", "replacements": "page=2", "headless": True,
    })
    driver = MagicMock()
    driver.title = "Album"
    driver.find_element.return_value.text = "You need to log in to view more content of this album."
    driver.find_elements.return_value = []
    with (
        patch.object(crawler, "_try_init_driver", return_value=driver),
        patch.object(crawler, "_process_selenium_actions") as extract,
        patch.object(crawler, "_download_single_image") as download,
        # First call: login_deadline = monotonic() + 120 = 0+120 = 120
        # Second call (inside loop): 200 >= 120 → deadline exceeded → stops
        patch("backend.src.web.crawlers.image_crawler.time.monotonic", side_effect=[0, 200]),
    ):
        assert crawler.run() == 0
    extract.assert_not_called()
    download.assert_not_called()
    driver.get.assert_called_once()
    assert "login is required" in crawler.completion_message


@patch("backend.src.web.crawlers.image_crawler.time.sleep")
def test_login_wait_requires_gallery_not_just_disappearing_notice(mock_sleep):
    crawler = ImageCrawler({})
    driver = MagicMock()
    driver.title = "Album"
    driver.current_url = "https://example.com/album"
    driver.find_element.return_value.text = "You need to log in to view more content of this album."
    driver.find_elements.side_effect = [[], [], [MagicMock()]]
    assert crawler._wait_for_browser_access(driver)
    assert mock_sleep.call_count == 2
    assert not crawler._access_blocked


def test_http_login_gate_does_not_extract_cover():
    crawler = ImageCrawler({})
    session = MagicMock()
    session.get.return_value.status_code = 200
    session.get.return_value.text = '''<main>
        <p>You need to log in to view more content of this album.</p>
        <img src="https://example.com/cover.jpg"></main>'''
    assert crawler._process_requests_page(session, "https://example.com/album", {}) == []
    assert crawler._login_blocked
    assert crawler._access_blocked

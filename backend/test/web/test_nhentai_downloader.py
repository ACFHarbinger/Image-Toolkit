"""Tests for NhentaiDownloader.

Regression coverage for the crash fixed after the app SIGSEGV'd/heap-
corrupted the first time a real download was triggered from the Media
Loader tab against https://nhentai.net/g/111006/ -- root-caused to the
original aiohttp/asyncio implementation running an event loop inside a
QThread (see the module docstring in ``nhentai_downloader.py``). These
tests exercise the rewritten, synchronous ``requests``-based
implementation with no live network calls.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from backend.src.web.downloaders.nhentai_downloader import (
    NhentaiDownloadConfig,
    NhentaiDownloader,
)

_GALLERY_HTML = """<html><body><script type="text/javascript">
window._gallery = JSON.parse("{}");
</script></body></html>"""


def _gallery_json_blob(media_id="123456", page_types=("j", "p", "g")):
    payload = {
        "media_id": media_id,
        "images": {"pages": [{"t": t} for t in page_types]},
    }
    # Mirrors nhentai's real markup: the JSON is embedded as a JSON-escaped
    # string literal inside JS source, so it must round-trip through
    # json.dumps twice (once for the payload, once to escape it as a JS
    # string literal) to match what the real regex/parse path expects.
    escaped = json.dumps(json.dumps(payload))[1:-1]
    return _GALLERY_HTML.format(escaped)


def _resp(status_code=200, text=None, content=None):
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.text = text or ""
    resp.content = content or b""
    return resp


def _downloader(tmp_path, **overrides):
    config = NhentaiDownloadConfig(
        gallery=overrides.pop("gallery", "https://nhentai.net/g/111006/"),
        download_dir=str(tmp_path),
        **overrides,
    )
    return NhentaiDownloader(config)


class TestParseGalleryId:
    def test_bare_id(self):
        assert NhentaiDownloader._parse_gallery_id("111006") == "111006"

    def test_full_url(self):
        assert (
            NhentaiDownloader._parse_gallery_id("https://nhentai.net/g/111006/")
            == "111006"
        )

    def test_no_digits_raises(self):
        with pytest.raises(ValueError):
            NhentaiDownloader._parse_gallery_id("not-a-gallery")


class TestRun:
    @patch("requests.Session")
    def test_downloads_every_page(self, mock_session_cls, tmp_path):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        gallery_html = _gallery_json_blob(media_id="999", page_types=("j", "p"))
        mock_session.get.side_effect = [
            _resp(200, text=gallery_html),          # gallery page
            _resp(200, content=b"fake-jpg-bytes"),   # page 1
            _resp(200, content=b"fake-png-bytes"),   # page 2
        ]

        downloader = _downloader(tmp_path, gallery="111006")
        saved_paths = []
        downloader.on_image_saved.connect(saved_paths.append)
        finished = []
        downloader.on_finished.connect(lambda count, msg: finished.append((count, msg)))

        result = downloader.run()

        assert result == 2
        assert finished == [(2, "Finished. Downloaded 2 page(s).")]
        assert len(saved_paths) == 2
        assert (tmp_path / "111006_001.jpg").read_bytes() == b"fake-jpg-bytes"
        assert (tmp_path / "111006_002.png").read_bytes() == b"fake-png-bytes"
        mock_session.close.assert_called_once()

    @patch("requests.Session")
    def test_missing_metadata_blob_emits_error(self, mock_session_cls, tmp_path):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = _resp(200, text="<html>no gallery data here</html>")

        downloader = _downloader(tmp_path, gallery="111006")
        errors = []
        downloader.on_error.connect(errors.append)

        result = downloader.run()

        assert result == 0
        assert len(errors) == 1
        assert "Could not locate gallery metadata" in errors[0]

    @patch("requests.Session")
    def test_non_200_gallery_page_emits_error(self, mock_session_cls, tmp_path):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = _resp(404, text="")

        downloader = _downloader(tmp_path, gallery="111006")
        errors = []
        downloader.on_error.connect(errors.append)

        result = downloader.run()

        assert result == 0
        assert len(errors) == 1
        assert "HTTP 404" in errors[0]

    @patch("requests.Session")
    def test_stop_halts_remaining_pages(self, mock_session_cls, tmp_path):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        gallery_html = _gallery_json_blob(media_id="1", page_types=("j", "j", "j"))
        mock_session.get.side_effect = [
            _resp(200, text=gallery_html),
        ]

        downloader = _downloader(tmp_path, gallery="1")
        downloader.stop()  # cancel before run() even starts iterating pages

        result = downloader.run()

        assert result == 0

    @patch("requests.Session")
    def test_page_download_failure_is_skipped_not_fatal(self, mock_session_cls, tmp_path):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        gallery_html = _gallery_json_blob(media_id="1", page_types=("j", "j"))
        mock_session.get.side_effect = [
            _resp(200, text=gallery_html),
            _resp(500, content=b""),
            _resp(200, content=b"ok"),
        ]

        downloader = _downloader(tmp_path, gallery="1")
        result = downloader.run()

        assert result == 1

class TestRunRetryAndCollision:
    @patch("requests.Session")
    def test_transient_500_is_retried_within_one_run(self, mock_session_cls, tmp_path):
        """A 5xx on a page image is retried inside the same run rather than
        silently dropped -- the previous behaviour that made the user click
        Download again to get the remaining pages."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        gallery_html = _gallery_json_blob(media_id="1", page_types=("j", "j"))
        mock_session.get.side_effect = [
            _resp(200, text=gallery_html),
            _resp(500, content=b""),   # page 1 transient failure
            _resp(200, content=b"retried"),  # page 1 retry succeeds
            _resp(200, content=b"page2"),    # page 2
        ]

        downloader = _downloader(tmp_path, gallery="1")
        result = downloader.run()

        assert result == 2
        assert (tmp_path / "1_001.jpg").read_bytes() == b"retried"
        assert (tmp_path / "1_002.jpg").read_bytes() == b"page2"

    @patch("requests.Session")
    def test_on_exists_rename_keeps_both_copies(self, mock_session_cls, tmp_path):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        gallery_html = _gallery_json_blob(media_id="1", page_types=("j",))
        mock_session.get.side_effect = [
            _resp(200, text=gallery_html),
            _resp(200, content=b"new"),
        ]

        existing = tmp_path / "1_001.jpg"
        existing.write_bytes(b"old")

        downloader = _downloader(tmp_path, gallery="1", on_exists="rename")
        result = downloader.run()

        assert result == 1
        assert existing.read_bytes() == b"old"
        assert (tmp_path / "1_001(1).jpg").read_bytes() == b"new"

    @patch("requests.Session")
    def test_on_exists_skip_skips_existing_page(self, mock_session_cls, tmp_path):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        gallery_html = _gallery_json_blob(media_id="1", page_types=("j",))
        mock_session.get.side_effect = [
            _resp(200, text=gallery_html),
        ]

        existing = tmp_path / "1_001.jpg"
        existing.write_bytes(b"old")

        downloader = _downloader(tmp_path, gallery="1", on_exists="skip")
        result = downloader.run()

        assert result == 0
        assert existing.read_bytes() == b"old"

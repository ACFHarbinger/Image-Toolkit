"""Tests for RedditDownloader (synchronous ``requests``-based, no asyncpraw/
aiohttp -- see the module docstring for why)."""

from unittest.mock import MagicMock, patch

import requests

from backend.src.web.downloaders.reddit_downloader import (
    RedditDownloadConfig,
    RedditDownloader,
)


def _resp(status_code=200, json_data=None):
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.content = b"image-bytes"
    resp.json.return_value = json_data or {}
    resp.raise_for_status.side_effect = (
        None if status_code < 400 else requests.HTTPError(f"{status_code}")
    )
    return resp


def _listing(posts):
    return {"data": {"children": [{"data": p} for p in posts]}}


def _downloader(tmp_path, **overrides):
    config = RedditDownloadConfig(
        source=overrides.pop("source", "EarthPorn"),
        download_dir=str(tmp_path),
        **overrides,
    )
    return RedditDownloader(config)


class TestExtractMediaUrls:
    def test_direct_image_url(self, tmp_path):
        downloader = _downloader(tmp_path)
        post = {"url": "https://i.redd.it/abc123.jpg"}
        assert downloader._extract_media_urls(post) == ["https://i.redd.it/abc123.jpg"]

    def test_gallery_media_metadata(self, tmp_path):
        downloader = _downloader(tmp_path)
        post = {
            "media_metadata": {
                "img1": {"e": "Image", "s": {"u": "https://preview.redd.it/1.jpg?a=1&amp;b=2"}},
                "img2": {"e": "Image", "s": {"u": "https://preview.redd.it/2.jpg"}},
            }
        }
        urls = downloader._extract_media_urls(post)
        assert urls == [
            "https://preview.redd.it/1.jpg?a=1&b=2",
            "https://preview.redd.it/2.jpg",
        ]

    def test_reddit_video_fallback_url(self, tmp_path):
        downloader = _downloader(tmp_path)
        post = {
            "secure_media": {
                "reddit_video": {"fallback_url": "https://v.redd.it/xyz/DASH_480.mp4?source=fallback"}
            }
        }
        urls = downloader._extract_media_urls(post)
        assert urls == ["https://v.redd.it/xyz/DASH_480.mp4"]

    def test_video_skipped_when_disabled(self, tmp_path):
        downloader = _downloader(tmp_path, download_videos=False)
        post = {"secure_media": {"reddit_video": {"fallback_url": "https://v.redd.it/x/DASH_480.mp4"}}}
        assert downloader._extract_media_urls(post) == []

    def test_images_skipped_when_disabled(self, tmp_path):
        downloader = _downloader(tmp_path, download_images=False)
        post = {"url": "https://i.redd.it/abc123.jpg"}
        assert downloader._extract_media_urls(post) == []

    def test_non_media_post_returns_empty(self, tmp_path):
        downloader = _downloader(tmp_path)
        post = {"url": "https://reddit.com/r/EarthPorn/comments/xyz/title/"}
        assert downloader._extract_media_urls(post) == []


class TestFetchPosts:
    @patch("requests.Session")
    def test_subreddit_mode(self, mock_session_cls, tmp_path):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        posts = [{"id": "a", "url": "https://i.redd.it/a.jpg"}]
        mock_session.get.return_value = _resp(200, _listing(posts))

        downloader = _downloader(tmp_path, source="EarthPorn", mode="subreddit", sort="hot")
        downloader._session = mock_session
        fetched = downloader._fetch_posts()

        assert fetched == posts
        called_url = mock_session.get.call_args.args[0]
        assert called_url == "https://www.reddit.com/r/EarthPorn/hot.json"

    @patch("requests.Session")
    def test_user_mode_strips_u_prefix(self, mock_session_cls, tmp_path):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = _resp(200, _listing([]))

        downloader = _downloader(tmp_path, source="u/someuser", mode="user", sort="new")
        downloader._session = mock_session
        downloader._fetch_posts()

        called_url = mock_session.get.call_args.args[0]
        assert called_url == "https://www.reddit.com/user/someuser/submitted/new.json"

    @patch("requests.Session")
    def test_post_mode_appends_json_and_takes_first_child(self, mock_session_cls, tmp_path):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        post_data = {"id": "abc", "url": "https://i.redd.it/x.png"}
        mock_session.get.return_value = _resp(
            200, [_listing([post_data]), _listing([])]
        )

        downloader = _downloader(
            tmp_path, source="https://reddit.com/r/EarthPorn/comments/abc/title/", mode="post"
        )
        downloader._session = mock_session
        fetched = downloader._fetch_posts()

        assert fetched == [post_data]
        called_url = mock_session.get.call_args.args[0]
        assert called_url.endswith(".json")


class TestRun:
    @patch("requests.Session")
    def test_run_downloads_files(self, mock_session_cls, tmp_path):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        posts = [
            {"id": "a", "subreddit": "EarthPorn", "url": "https://i.redd.it/a.jpg"},
            {"id": "b", "subreddit": "EarthPorn", "url": "https://i.redd.it/b.png"},
        ]
        mock_session.get.side_effect = [
            _resp(200, _listing(posts)),
            _resp(200),  # download a.jpg
            _resp(200),  # download b.png
        ]

        downloader = _downloader(tmp_path, source="EarthPorn")
        saved = []
        downloader.on_image_saved.connect(saved.append)
        finished = []
        downloader.on_finished.connect(lambda count, msg: finished.append((count, msg)))

        result = downloader.run()

        assert result == 2
        assert finished == [(2, "Finished. Downloaded 2 file(s).")]
        assert len(saved) == 2
        assert (tmp_path / "EarthPorn_a_0.jpg").read_bytes() == b"image-bytes"
        assert (tmp_path / "EarthPorn_b_0.png").read_bytes() == b"image-bytes"

    @patch("requests.Session")
    def test_run_error_emits_signal_and_returns_zero(self, mock_session_cls, tmp_path):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.side_effect = requests.ConnectionError("boom")

        downloader = _downloader(tmp_path, source="EarthPorn")
        errors = []
        downloader.on_error.connect(errors.append)

        result = downloader.run()

        assert result == 0
        assert len(errors) == 1
        assert "boom" in errors[0]

    @patch("requests.Session")
    def test_stop_halts_remaining_posts(self, mock_session_cls, tmp_path):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        posts = [
            {"id": "a", "subreddit": "EarthPorn", "url": "https://i.redd.it/a.jpg"},
        ]
        mock_session.get.return_value = _resp(200, _listing(posts))

        downloader = _downloader(tmp_path, source="EarthPorn")
        downloader.stop()
        result = downloader.run()

        assert result == 0

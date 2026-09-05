"""Reddit media downloader — subreddit/user/single-post images, galleries, and video.

Modeled on the ``RedDownloader`` PyPI package's feature set (single post,
subreddit, and user-profile downloads), implemented against Reddit's public
``.json`` listing endpoints (``https://www.reddit.com/r/<sub>/<sort>.json``,
``.../user/<name>/submitted/<sort>.json``, ``<permalink>.json``) — no OAuth
app registration required for public subreddits/profiles, just a descriptive
``User-Agent`` header (Reddit blocks the default ``python-requests`` UA).

Scope note: ``v.redd.it`` videos are served as separate DASH video/audio
streams. This downloader saves the muxed-video-only ``fallback_url`` stream
(no audio track) rather than shelling out to ffmpeg to remux audio in — the
same trade-off ``RedDownloader`` itself documents as a known limitation.

Uses the synchronous ``requests`` library rather than ``asyncio``/
``aiohttp``/``asyncpraw``. This is deliberate, not a style choice: an
earlier ``asyncpraw``/``aiohttp``-based version of this module (and its
nhentai sibling) crashed the app the first time either ran
(``QSocketNotifier: Socket notifiers cannot be enabled or disabled from
another thread`` followed by a SIGSEGV/heap corruption) -- this app has an
extensively documented crash class (see
``.agent/cache/gallery_crash_deleteorphaned_2026-07-27.md``) where *any*
native library's first-ever use off the main thread, with the JPype JVM
loaded in-process, risks exactly this failure signature. ``asyncio.run()``
inside a ``QThread`` creates a brand-new event loop (and ``aiohttp``'s TLS/
DNS machinery on top of it) that had never been exercised live in this app
before (``subreddit_phash_sweep.py`` uses the same ``asyncpraw``/``aiohttp``
combination but has never actually been wired into a running GUI worker) --
``requests`` (synchronous, no event loop of its own) is the same,
already-proven-safe pattern every other QThread-based web worker in this
codebase uses (``ImageCrawler``, ``WebRequestsLogic``, the MAL sync
workers, ...).
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import List
from urllib.parse import urlparse

from backend.src.constants.web import _DIRECT_HOSTS, DOWNLOADERS__IMAGE_EXTS
from backend.src.core import telemetry
from backend.src.events import Observable
from backend.src.web.downloaders._common import (
    MAX_ATTEMPTS,
    ON_EXISTS_DEFAULT,
    backoff_sleep,
    is_retryable_status,
    resolve_dest_path,
)

log = logging.getLogger(__name__)


@dataclass
class RedditDownloadConfig:
    source: str
    """Subreddit name (``"EarthPorn"``), username (``"u/someone"``), or a
    full submission permalink URL, depending on ``mode``."""
    mode: str = "subreddit"  # "subreddit" | "user" | "post"
    sort: str = "hot"  # "hot" | "new" | "top"
    limit: int = 50
    download_images: bool = True
    download_videos: bool = True
    download_dir: str = "."
    user_agent: str = "image-toolkit/1.0 (media loader)"
    request_timeout: float = 20.0
    filename_template: str = "{subreddit}_{id}_{index}{ext}"
    extra_headers: dict = field(default_factory=dict)
    on_exists: str = ON_EXISTS_DEFAULT


class RedditDownloader:
    """Downloads images/galleries/videos from a subreddit, user, or single post."""

    def __init__(self, config: RedditDownloadConfig | dict):
        # === Events (issue #529: plain Observables, not Qt signals) ===
        self.on_status: Observable[str] = Observable()
        self.on_image_saved: Observable[str] = Observable()
        self.on_finished: Observable[tuple[int, str]] = Observable()
        self.on_error: Observable[str] = Observable()
        self._config = (
            config
            if isinstance(config, RedditDownloadConfig)
            else RedditDownloadConfig(**config)
        )
        self._is_running = True
        self._session = None

    def stop(self) -> None:
        self._is_running = False
        self.on_status.publish("Cancellation pending...")

    def run(self) -> int:
        """Synchronous entry point — safe to call from a plain worker thread."""
        import requests

        telemetry.emit(
            "media-loader", "reddit.run.start",
            source=self._config.source, mode=self._config.mode,
        )
        try:
            os.makedirs(self._config.download_dir, exist_ok=True)
            self._session = requests.Session()
            headers = {"User-Agent": self._config.user_agent}
            headers.update(self._config.extra_headers or {})
            self._session.headers.update(headers)

            saved = 0
            try:
                posts = self._fetch_posts()
                telemetry.emit("media-loader", "reddit.posts_fetched", count=len(posts))
                for post in posts:
                    if not self._is_running:
                        break
                    saved += self._download_post(post)
            finally:
                self._session.close()
                self._session = None

            message = f"Finished. Downloaded {saved} file(s)."
            telemetry.emit("media-loader", "reddit.run.finished", saved=saved)
            self.on_finished.publish((saved, message))
            return saved
        except Exception as exc:
            log.exception("Reddit download failed for %s", self._config.source)
            telemetry.emit(
                "media-loader", "reddit.run.error",
                source=self._config.source, error=repr(exc),
            )
            self.on_error.publish(f"Critical error in Reddit downloader: {exc}")
            return 0

    def _fetch_posts(self) -> List[dict]:
        mode = self._config.mode
        limit = self._config.limit
        sort = self._config.sort or "hot"

        if mode == "post":
            url = self._config.source.rstrip("/")
            if not url.endswith(".json"):
                url = f"{url}.json"
            data = self._get_json(url, params={"raw_json": 1})
            listing = data[0] if isinstance(data, list) else data
            children = listing["data"]["children"]
            return [c["data"] for c in children[:1]]

        if mode == "user":
            username = self._config.source.removeprefix("u/").removeprefix("/u/")
            url = f"https://www.reddit.com/user/{username}/submitted/{sort}.json"
        else:
            url = f"https://www.reddit.com/r/{self._config.source}/{sort}.json"

        data = self._get_json(url, params={"limit": limit, "raw_json": 1})
        children = data["data"]["children"]
        return [c["data"] for c in children[:limit]]

    def _get_json(self, url: str, params: dict):
        with telemetry.span("media-loader", "reddit.http_get", url=url):
            resp = self._session.get(url, params=params, timeout=self._config.request_timeout)
        resp.raise_for_status()
        return resp.json()

    def _download_post(self, post: dict) -> int:
        urls = self._extract_media_urls(post)
        saved = 0
        for index, url in enumerate(urls):
            if not self._is_running:
                break
            ext = self._guess_ext(url)
            filename = self._config.filename_template.format(
                subreddit=post.get("subreddit", "reddit"),
                id=post.get("id", "unknown"),
                index=index,
                ext=ext,
            )
            dest = os.path.join(self._config.download_dir, filename)
            dest = resolve_dest_path(dest, self._config.on_exists)
            if dest is None:
                # on_exists=skip and the file is already present.
                self.on_status.publish(f"Skipped (exists): {filename}")
                continue
            if self._download_file(url, dest):
                saved += 1
                self.on_status.publish(f"Saved: {os.path.basename(dest)}")
                self.on_image_saved.publish(dest)
        return saved

    def _extract_media_urls(self, post: dict) -> List[str]:
        urls: List[str] = []

        # Gallery post: multiple images via media_metadata.
        media_metadata = post.get("media_metadata")
        if media_metadata and self._config.download_images:
            for item in media_metadata.values():
                # Reddit galleries use e="Image" for stills and
                # e="AnimatedImage" for GIFs; both carry s.u.
                if item.get("e") in ("Image", "AnimatedImage"):
                    src = item.get("s", {}).get("u", "").replace("&amp;", "&")
                    if src:
                        urls.append(src)
            if urls:
                return urls

        # v.redd.it hosted video (video-only DASH stream, no audio — see
        # module docstring).
        media = post.get("secure_media") or post.get("media") or {}
        reddit_video = media.get("reddit_video") if isinstance(media, dict) else None
        if reddit_video and self._config.download_videos:
            fallback = reddit_video.get("fallback_url")
            if fallback:
                urls.append(fallback.split("?")[0])
            return urls

        # Direct image/gif link.
        url = post.get("url_overridden_by_dest") or post.get("url") or ""
        if self._config.download_images and (
            url.lower().endswith(DOWNLOADERS__IMAGE_EXTS)
            or urlparse(url).netloc in _DIRECT_HOSTS
        ):
            urls.append(url)

        return urls

    @staticmethod
    def _guess_ext(url: str) -> str:
        path = urlparse(url).path
        match = re.search(r"(\.[A-Za-z0-9]{2,4})$", path)
        return match.group(1) if match else ".jpg"

    def _download_file(self, url: str, dest: str) -> bool:
        """Fetch url and write it to dest, retrying transient failures.

        Transient HTTP statuses (429/5xx) and network exceptions are retried
        with backoff (MAX_ATTEMPTS total) before giving up, so a momentary
        CDN hiccup no longer silently drops a file from the run -- the
        previous behaviour that made re-clicking Download necessary to get
        every image of a gallery.
        """
        data = None
        last_error = ""
        for attempt in range(MAX_ATTEMPTS):
            if not self._is_running:
                return False
            try:
                with telemetry.span("media-loader", "reddit.http_get", url=url):
                    resp = self._session.get(url, timeout=self._config.request_timeout)
                if resp.status_code == 200:
                    data = resp.content
                    break
                last_error = f"HTTP {resp.status_code}"
                if not is_retryable_status(resp.status_code):
                    break
            except Exception as exc:
                log.debug("Download failed for %s: %s", url, exc)
                last_error = str(exc)
            if attempt + 1 < MAX_ATTEMPTS:
                backoff_sleep(attempt)
        if data is None:
            self.on_status.publish(f"Failed to download {url}: {last_error}")
            return False

        try:
            with open(dest, "wb") as fh:
                fh.write(data)
        except OSError as exc:
            log.warning("Cannot write %s: %s", dest, exc)
            return False
        return True


__all__ = ["RedditDownloadConfig", "RedditDownloader"]

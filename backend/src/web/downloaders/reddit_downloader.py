"""Reddit media downloader — subreddit/user/single-post images, galleries, and video.

Modeled on the ``RedDownloader`` PyPI package's feature set (single post,
subreddit, and user-profile downloads) but reimplemented against
``asyncpraw`` so it shares credentials/auth conventions with
``subreddit_phash_sweep.py`` (``REDDIT_CLIENT_ID`` / ``REDDIT_CLIENT_SECRET``
env vars, lazy import so this module and its tests import fine without the
optional dependency present).

Scope note: ``v.redd.it`` videos are served as separate DASH video/audio
streams. This downloader saves the muxed-video-only ``fallback_url`` stream
(no audio track) rather than shelling out to ffmpeg to remux audio in — the
same trade-off ``RedDownloader`` itself documents as a known limitation.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Callable, List, Optional
from urllib.parse import urlparse

from PySide6.QtCore import QObject, Signal

log = logging.getLogger(__name__)

_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".gif")
_DIRECT_HOSTS = ("i.redd.it", "i.imgur.com")


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
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    user_agent: str = "image-toolkit/1.0 (media loader)"
    request_timeout: float = 20.0
    filename_template: str = "{subreddit}_{id}_{index}{ext}"
    extra_headers: dict = field(default_factory=dict)


class RedditDownloader(QObject):
    """Downloads images/galleries/videos from a subreddit, user, or single post."""

    on_status = Signal(str)
    on_image_saved = Signal(str)
    on_finished = Signal(int, str)
    on_error = Signal(str)

    def __init__(self, config: RedditDownloadConfig | dict):
        super().__init__()
        self._config = (
            config
            if isinstance(config, RedditDownloadConfig)
            else RedditDownloadConfig(**config)
        )
        self._is_running = True
        self._reddit = None
        self._http = None

    def stop(self) -> None:
        self._is_running = False
        self.on_status.emit("Cancellation pending...")

    def run(self) -> int:
        """Synchronous entry point — safe to call from a plain worker thread."""
        try:
            return asyncio.run(self._run_async())
        except Exception as exc:  # pragma: no cover - defensive top-level guard
            self.on_error.emit(f"Critical error in Reddit downloader: {exc}")
            return 0

    async def _run_async(self) -> int:
        os.makedirs(self._config.download_dir, exist_ok=True)
        await self._ensure_clients()
        saved = 0
        try:
            async for submission in self._iter_submissions():
                if not self._is_running:
                    break
                saved += await self._download_submission(submission)
        finally:
            await self._close_clients()

        message = f"Finished. Downloaded {saved} file(s)."
        self.on_finished.emit(saved, message)
        return saved

    async def _ensure_clients(self) -> None:
        import aiohttp

        if self._http is None:
            self._http = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self._config.request_timeout),
                headers=self._config.extra_headers or None,
            )
        if self._reddit is None:
            import asyncpraw  # lazy — optional dependency

            client_id = self._config.client_id or os.environ.get("REDDIT_CLIENT_ID")
            client_secret = self._config.client_secret or os.environ.get(
                "REDDIT_CLIENT_SECRET"
            )
            if not client_id or not client_secret:
                raise EnvironmentError(
                    "Reddit API credentials not found. Set REDDIT_CLIENT_ID and "
                    "REDDIT_CLIENT_SECRET (or pass them in RedditDownloadConfig)."
                )
            self._reddit = asyncpraw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent=self._config.user_agent,
            )

    async def _close_clients(self) -> None:
        if self._http is not None:
            await self._http.close()
            self._http = None
        if self._reddit is not None:
            await self._reddit.close()
            self._reddit = None

    async def _iter_submissions(self):
        mode = self._config.mode
        limit = self._config.limit
        if mode == "post":
            yield await self._reddit.submission(url=self._config.source)
            return

        if mode == "user":
            username = self._config.source.removeprefix("u/").removeprefix("/u/")
            redditor = await self._reddit.redditor(username)
            listing = redditor.submissions
        else:
            subreddit = await self._reddit.subreddit(self._config.source)
            listing = subreddit

        sort = self._config.sort
        if sort == "new":
            stream = listing.new(limit=limit)
        elif sort == "top":
            stream = listing.top(limit=limit)
        else:
            stream = listing.hot(limit=limit)

        count = 0
        async for submission in stream:
            if not self._is_running or count >= limit:
                break
            yield submission
            count += 1

    async def _download_submission(self, submission) -> int:
        urls = self._extract_media_urls(submission)
        saved = 0
        for index, url in enumerate(urls):
            if not self._is_running:
                break
            ext = self._guess_ext(url)
            filename = self._config.filename_template.format(
                subreddit=str(getattr(submission, "subreddit", "reddit")),
                id=submission.id,
                index=index,
                ext=ext,
            )
            dest = os.path.join(self._config.download_dir, filename)
            if await self._download_file(url, dest):
                saved += 1
                self.on_status.emit(f"Saved: {filename}")
                self.on_image_saved.emit(dest)
        return saved

    def _extract_media_urls(self, submission) -> List[str]:
        urls: List[str] = []
        url = getattr(submission, "url", "") or ""

        # Gallery post: multiple images via media_metadata.
        media_metadata = getattr(submission, "media_metadata", None)
        if media_metadata:
            for item in media_metadata.values():
                if item.get("e") == "Image":
                    src = item.get("s", {}).get("u", "").replace("&amp;", "&")
                    if src and self._config.download_images:
                        urls.append(src)
            if urls:
                return urls

        # v.redd.it hosted video (video-only DASH stream, no audio — see
        # module docstring).
        media = getattr(submission, "media", None) or {}
        reddit_video = media.get("reddit_video") if isinstance(media, dict) else None
        if reddit_video and self._config.download_videos:
            fallback = reddit_video.get("fallback_url")
            if fallback:
                urls.append(fallback.split("?")[0])
            return urls

        # Direct image/gif link.
        if self._config.download_images and (
            url.lower().endswith(_IMAGE_EXTS)
            or urlparse(url).netloc in _DIRECT_HOSTS
        ):
            urls.append(url)

        return urls

    @staticmethod
    def _guess_ext(url: str) -> str:
        path = urlparse(url).path
        match = re.search(r"(\.[A-Za-z0-9]{2,4})$", path)
        return match.group(1) if match else ".jpg"

    async def _download_file(self, url: str, dest: str) -> bool:
        try:
            async with self._http.get(url) as resp:
                if resp.status != 200:
                    return False
                data = await resp.read()
        except Exception as exc:
            log.debug("Download failed for %s: %s", url, exc)
            self.on_status.emit(f"Failed to download {url}: {exc}")
            return False

        try:
            with open(dest, "wb") as fh:
                fh.write(data)
        except OSError as exc:
            log.warning("Cannot write %s: %s", dest, exc)
            return False
        return True


__all__ = ["RedditDownloadConfig", "RedditDownloader"]

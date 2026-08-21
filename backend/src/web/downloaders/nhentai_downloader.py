"""nhentai gallery downloader — fetches every page image of a gallery.

Modeled on the ``nhentai-downloader`` PyPI package: given a gallery ID or
full gallery URL, scrape the gallery page for its embedded gallery-data
JSON (media id + a full relative path per page), then build direct image
URLs against nhentai's image CDN and download each page.

nhentai's frontend is a SvelteKit SPA: the server-rendered HTML embeds the
data its own client-side JS would otherwise fetch via
``/api/v2/galleries/<id>`` as a ``<script type="application/json"
data-sveltekit-fetched data-url="/api/v2/galleries/<id>...">`` tag, whose
text content is a JSON envelope (``{"status": 200, ..., "body": "<json
string>"}``) wrapping the actual gallery JSON as a doubly-encoded string.
An older markup convention (``window._gallery = JSON.parse("...")``,
carrying ``images.pages[].t`` type-letter + dimensions instead of a direct
``path``) is tried as a fallback in case of a partial rollout/CDN cache
serving stale markup.

No authentication is required for public galleries. Cloudflare may
occasionally challenge requests from non-browser user agents; this module
sends a browser-like ``User-Agent`` but does not solve JS challenges — a
failure here surfaces as an ``on_error`` signal rather than a silent hang.

Uses the synchronous ``requests`` library rather than ``asyncio``/
``aiohttp``. This is deliberate, not a style choice: an earlier
``aiohttp``-based version of this module crashed the app the first time it
ran (``QSocketNotifier: Socket notifiers cannot be enabled or disabled from
another thread`` followed by a SIGSEGV/heap corruption) -- this app has an
extensively documented crash class (see
``.agent/cache/gallery_crash_deleteorphaned_2026-07-27.md``) where *any*
native library's first-ever use off the main thread, with the JPype JVM
loaded in-process, risks exactly this failure signature. ``asyncio.run()``
inside a ``QThread`` creates a brand-new event loop (and ``aiohttp``'s TLS/
DNS machinery on top of it) that had never been exercised live in this app
before -- ``requests`` (synchronous, no event loop of its own) is the same,
already-proven-safe pattern every other QThread-based web worker in this
codebase uses (``ImageCrawler``, ``WebRequestsLogic``, the MAL sync
workers, ...).
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import List, Optional

from PySide6.QtCore import QObject, Signal

from backend.src.constants.web import (
    _DEFAULT_HEADERS,
    _GALLERY_ID_RE,
    _LEGACY_GALLERY_JSON_RE,
    _PAGE_EXT,
    _SVELTEKIT_JSON_RE,
)
from backend.src.core import telemetry
from backend.src.web.downloaders._common import (
    MAX_ATTEMPTS,
    ON_EXISTS_DEFAULT,
    backoff_sleep,
    is_retryable_status,
    resolve_dest_path,
)

log = logging.getLogger(__name__)

# Current SvelteKit markup: a sveltekit-fetched <script> tag whose text is a
# JSON envelope with the real gallery JSON nested under "body" as a string.
# Legacy markup fallback (pre-SvelteKit rewrite): images.pages[].t type
# letters instead of a direct per-page path.
# Legacy-markup page "type" letters -> file extension.


@dataclass
class NhentaiDownloadConfig:
    gallery: str
    """A bare gallery id (``"177013"``) or a full gallery URL
    (``"https://nhentai.net/g/177013/"``)."""
    download_dir: str = "."
    request_timeout: float = 20.0
    filename_template: str = "{gallery_id}_{page:03d}{ext}"
    on_exists: str = ON_EXISTS_DEFAULT


class NhentaiDownloader(QObject):
    """Downloads every page image of a single nhentai gallery."""

    on_status = Signal(str)
    on_image_saved = Signal(str)
    on_finished = Signal(int, str)
    on_error = Signal(str)

    def __init__(self, config: NhentaiDownloadConfig | dict):
        super().__init__()
        self._config = (
            config
            if isinstance(config, NhentaiDownloadConfig)
            else NhentaiDownloadConfig(**config)
        )
        self._is_running = True
        self._session = None

    def stop(self) -> None:
        self._is_running = False
        self.on_status.emit("Cancellation pending...")

    def run(self) -> int:
        """Synchronous entry point — safe to call from a plain worker thread."""
        import requests

        telemetry.emit("media-loader", "nhentai.run.start", gallery=self._config.gallery)
        try:
            os.makedirs(self._config.download_dir, exist_ok=True)
            gallery_id = self._parse_gallery_id(self._config.gallery)

            self._session = requests.Session()
            self._session.headers.update(_DEFAULT_HEADERS)
            saved = 0
            try:
                page_urls = self._fetch_gallery_metadata(gallery_id)
                self.on_status.emit(f"Gallery {gallery_id}: {len(page_urls)} page(s) found.")
                telemetry.emit(
                    "media-loader", "nhentai.metadata_fetched",
                    gallery=gallery_id, page_count=len(page_urls),
                )
                for page_num, url in enumerate(page_urls, start=1):
                    if not self._is_running:
                        break
                    ext = os.path.splitext(url)[1] or ".jpg"
                    filename = self._config.filename_template.format(
                        gallery_id=gallery_id, page=page_num, ext=ext
                    )
                    dest = os.path.join(self._config.download_dir, filename)
                    dest = resolve_dest_path(dest, self._config.on_exists)
                    if dest is None:
                        # on_exists=skip and the file is already present.
                        self.on_status.emit(f"Skipped (exists): {filename}")
                        continue
                    if self._download_file(url, dest):
                        saved += 1
                        self.on_status.emit(f"Saved: {os.path.basename(dest)}")
                        self.on_image_saved.emit(dest)
            finally:
                self._session.close()
                self._session = None

            message = f"Finished. Downloaded {saved} page(s)."
            telemetry.emit("media-loader", "nhentai.run.finished", gallery=gallery_id, saved=saved)
            self.on_finished.emit(saved, message)
            return saved
        except Exception as exc:
            log.exception("nhentai download failed for %s", self._config.gallery)
            telemetry.emit(
                "media-loader", "nhentai.run.error",
                gallery=self._config.gallery, error=repr(exc),
            )
            self.on_error.emit(f"Critical error in nhentai downloader: {exc}")
            return 0

    @staticmethod
    def _parse_gallery_id(gallery: str) -> str:
        match = _GALLERY_ID_RE.search(gallery)
        if not match:
            raise ValueError(f"Could not parse a gallery id from {gallery!r}")
        return match.group(1)

    def _fetch_gallery_metadata(self, gallery_id: str) -> List[str]:
        url = f"https://nhentai.net/g/{gallery_id}/"
        with telemetry.span("media-loader", "nhentai.http_get", url=url):
            resp = self._session.get(url, timeout=self._config.request_timeout)
        if resp.status_code != 200:
            raise RuntimeError(
                f"Failed to fetch gallery page {url} (HTTP {resp.status_code})"
            )
        html = resp.text

        page_urls = self._parse_sveltekit_pages(html, gallery_id)
        if page_urls is None:
            page_urls = self._parse_legacy_pages(html)
        if page_urls is None:
            raise RuntimeError(
                f"Could not locate gallery metadata on {url} "
                "(page layout changed, or a Cloudflare challenge blocked the request)"
            )
        return page_urls

    @staticmethod
    def _parse_sveltekit_pages(html: str, gallery_id: str) -> Optional[List[str]]:
        """Current markup: an embedded ``/api/v2/galleries/<id>`` JSON
        envelope whose ``body`` (itself a JSON string) has a ``pages`` list
        of ``{"path": "galleries/<media_id>/<n>.<ext>", ...}`` dicts."""
        match = _SVELTEKIT_JSON_RE.search(html)
        if not match:
            return None
        envelope = json.loads(match.group(1))
        body = json.loads(envelope["body"])
        pages = body.get("pages")
        if not pages:
            return None
        return [f"https://i.nhentai.net/{page['path']}" for page in pages]

    @staticmethod
    def _parse_legacy_pages(html: str) -> Optional[List[str]]:
        """Older markup: ``window._gallery = JSON.parse("...")`` carrying
        ``images.pages[].t`` type letters + a separate ``media_id``,
        instead of a direct per-page path."""
        match = _LEGACY_GALLERY_JSON_RE.search(html)
        if not match:
            return None
        # The embedded blob is itself a JSON-escaped string literal, so it
        # must be decoded once as a string before being parsed as JSON again.
        raw = json.loads(f'"{match.group(1)}"')
        data = json.loads(raw)
        media_id = data["media_id"]
        pages = data["images"]["pages"]
        return [
            f"https://i.nhentai.net/galleries/{media_id}/{i}"
            f"{_PAGE_EXT.get(page.get('t', 'j'), '.jpg')}"
            for i, page in enumerate(pages, start=1)
        ]

    def _download_file(self, url: str, dest: str) -> bool:
        """Fetch url and write it to dest, retrying transient failures.

        Transient HTTP statuses (429/5xx) and network exceptions are retried
        with backoff (MAX_ATTEMPTS total) before giving up, so a momentary
        CDN hiccup no longer silently drops a page from the run -- the
        previous behaviour that made re-clicking Download necessary to get
        every image of a gallery.
        """
        data = None
        last_error = ""
        for attempt in range(MAX_ATTEMPTS):
            if not self._is_running:
                return False
            try:
                with telemetry.span("media-loader", "nhentai.http_get", url=url):
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
            self.on_status.emit(f"Failed to download {url}: {last_error}")
            return False

        try:
            with open(dest, "wb") as fh:
                fh.write(data)
        except OSError as exc:
            log.warning("Cannot write %s: %s", dest, exc)
            return False
        return True


__all__ = ["NhentaiDownloadConfig", "NhentaiDownloader"]

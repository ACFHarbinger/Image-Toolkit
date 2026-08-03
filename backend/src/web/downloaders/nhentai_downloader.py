"""nhentai gallery downloader — fetches every page image of a gallery.

Modeled on the ``nhentai-downloader`` PyPI package: given a gallery ID or
full gallery URL, scrape the gallery page for the embedded
``window._gallery = JSON.parse("...")`` blob (media id + per-page type/
dimensions), then build direct image URLs against nhentai's image CDN and
download each page.

No authentication is required for public galleries. Cloudflare may
occasionally challenge requests from non-browser user agents; this module
sends a browser-like ``User-Agent`` but does not solve JS challenges — a
failure here surfaces as an ``on_error`` signal rather than a silent hang.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal

log = logging.getLogger(__name__)

_GALLERY_ID_RE = re.compile(r"(\d+)")
_GALLERY_JSON_RE = re.compile(
    r"window\._gallery\s*=\s*JSON\.parse\(\"(.*?)\"\);", re.DOTALL
)
_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}
# nhentai page "type" letters -> file extension.
_PAGE_EXT = {"j": ".jpg", "p": ".png", "g": ".gif", "w": ".webp"}


@dataclass
class NhentaiDownloadConfig:
    gallery: str
    """A bare gallery id (``"177013"``) or a full gallery URL
    (``"https://nhentai.net/g/177013/"``)."""
    download_dir: str = "."
    request_timeout: float = 20.0
    filename_template: str = "{gallery_id}_{page:03d}{ext}"


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
        self._http = None

    def stop(self) -> None:
        self._is_running = False
        self.on_status.emit("Cancellation pending...")

    def run(self) -> int:
        import asyncio

        try:
            return asyncio.run(self._run_async())
        except Exception as exc:  # pragma: no cover - defensive top-level guard
            self.on_error.emit(f"Critical error in nhentai downloader: {exc}")
            return 0

    async def _run_async(self) -> int:
        import aiohttp

        os.makedirs(self._config.download_dir, exist_ok=True)
        gallery_id = self._parse_gallery_id(self._config.gallery)

        self._http = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self._config.request_timeout),
            headers=_DEFAULT_HEADERS,
        )
        saved = 0
        try:
            media_id, pages = await self._fetch_gallery_metadata(gallery_id)
            self.on_status.emit(
                f"Gallery {gallery_id}: {len(pages)} page(s) found."
            )
            for page_num, page_type in enumerate(pages, start=1):
                if not self._is_running:
                    break
                ext = _PAGE_EXT.get(page_type, ".jpg")
                url = f"https://i.nhentai.net/galleries/{media_id}/{page_num}{ext}"
                filename = self._config.filename_template.format(
                    gallery_id=gallery_id, page=page_num, ext=ext
                )
                dest = os.path.join(self._config.download_dir, filename)
                if await self._download_file(url, dest):
                    saved += 1
                    self.on_status.emit(f"Saved: {filename}")
                    self.on_image_saved.emit(dest)
        finally:
            await self._http.close()
            self._http = None

        message = f"Finished. Downloaded {saved} page(s)."
        self.on_finished.emit(saved, message)
        return saved

    @staticmethod
    def _parse_gallery_id(gallery: str) -> str:
        match = _GALLERY_ID_RE.search(gallery)
        if not match:
            raise ValueError(f"Could not parse a gallery id from {gallery!r}")
        return match.group(1)

    async def _fetch_gallery_metadata(self, gallery_id: str):
        url = f"https://nhentai.net/g/{gallery_id}/"
        async with self._http.get(url) as resp:
            if resp.status != 200:
                raise RuntimeError(
                    f"Failed to fetch gallery page {url} (HTTP {resp.status})"
                )
            html = await resp.text()

        match = _GALLERY_JSON_RE.search(html)
        if not match:
            raise RuntimeError(
                f"Could not locate gallery metadata on {url} "
                "(page layout changed, or a Cloudflare challenge blocked the request)"
            )
        # The embedded blob is itself a JSON-escaped string literal, so it
        # must be decoded once as a string before being parsed as JSON again.
        raw = json.loads(f'"{match.group(1)}"')
        data = json.loads(raw)

        media_id = data["media_id"]
        pages = [p.get("t", "j") for p in data["images"]["pages"]]
        return media_id, pages

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


__all__ = ["NhentaiDownloadConfig", "NhentaiDownloader"]

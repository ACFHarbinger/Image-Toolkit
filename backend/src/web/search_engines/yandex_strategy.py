"""Yandex reverse-image search — real web-scrape implementation.

Yandex has no official visual-search API and the strongest face/person
matching of the mainstream engines. The flow: upload the image to Yandex's
CBIR image-download endpoint to obtain a ``cbir_id`` + hosted URL, then GET the
``rpt=imageview`` results page and parse the "Sites containing" block.

Brittle by nature (Yandex rotates markup and shows CAPTCHAs to datacenter IPs);
fails soft to ``[]`` or raises ``RateLimited`` for the dispatcher to isolate.
"""

import json
import logging
import re
from typing import List, Optional

from backend.src.web.crawlers.reverse_image_search_crawler import ReverseSearchEngine
from backend.src.web.models import ReverseSearchResult

from .common import EngineBlocked, make_session, raise_for_rate_limit

log = logging.getLogger(__name__)

ENGINE_YANDEX = "yandex"
_UPLOAD_URL = "https://yandex.com/images-apphost/image-download"
_SEARCH_URL = "https://yandex.com/images/search"
_CAPTCHA_MARKERS = ("showcaptcha", "SmartCaptcha", "captcha")
_RES_RE = re.compile(r"(\d+)\s*[×x]\s*(\d+)")


class YandexSearchStrategy(ReverseSearchEngine):
    def __init__(
        self,
        timeout: float = 25.0,
        status_callback: Optional[callable] = None,
    ) -> None:
        self._timeout = timeout
        self._status_callback = status_callback
        self._is_running = True
        self._session = None

    def stop(self) -> None:
        self._is_running = False
        self._emit_status("Cancellation pending…")
        if self._session is not None:
            self._session.close()

    def search(self, image_path: str, **kwargs) -> List[ReverseSearchResult]:
        if self._session is None:
            self._session = make_session(self._timeout)

        self._emit_status("Uploading to Yandex…")
        with open(image_path, "rb") as fh:
            files = {"upfile": ("query.jpg", fh, "image/jpeg")}
            up = self._session.post(
                _UPLOAD_URL, params={"cbird": 111, "images_avatars_size": "preview"},
                files=files, timeout=self._timeout,
            )
        up.raise_for_status()
        try:
            payload = up.json()
        except Exception as exc:
            raise EngineBlocked(f"Yandex upload returned non-JSON response: {exc}")
        cbir_id, image_url = self._parse_upload(payload)
        if not cbir_id:
            self._emit_status("Yandex upload returned no CBIR id.")
            return []

        self._emit_status("Fetching Yandex matches…")
        resp = self._session.get(
            _SEARCH_URL,
            params={"rpt": "imageview", "cbir_id": cbir_id, "url": image_url,
                    "cbir_page": "sites"},
            timeout=self._timeout,
        )
        raise_for_rate_limit(resp, ENGINE_YANDEX)
        if any(marker in resp.text for marker in _CAPTCHA_MARKERS):
            raise EngineBlocked("Yandex presented a CAPTCHA challenge")
        resp.raise_for_status()

        results = self._parse_results(resp.text)
        self._emit_status(f"Yandex returned {len(results)} matches.")
        return results

    @staticmethod
    def _parse_upload(payload: dict):
        """Return (cbir_id, image_url) from the upload JSON. Static + testable."""
        payload = payload or {}
        cbir_id = payload.get("cbir_id", "")
        # The hosted preview URL comes back under a few possible keys.
        sizes = payload.get("sizes") or {}
        image_url = ""
        for key in ("preview", "orig"):
            entry = sizes.get(key) or {}
            if entry.get("path"):
                image_url = entry["path"]
                break
        if image_url.startswith("//"):
            image_url = "https:" + image_url
        return cbir_id, image_url

    @staticmethod
    def _parse_results(html: str) -> List[ReverseSearchResult]:
        """Parse the "Sites containing" block. Static + testable.

        Yandex embeds results as JSON in a ``data-state`` attribute on the
        CbirSites container; parse that when present, else fall back to anchor
        scraping.
        """
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        results: List[ReverseSearchResult] = []
        seen = set()

        container = soup.find(attrs={"data-state": True},
                              class_=re.compile("CbirSites|cbir-sites"))
        if container:
            try:
                state = json.loads(container["data-state"])
                for site in state.get("sites", []) or []:
                    url = site.get("url") or site.get("originalUrl") or ""
                    if not url or url in seen:
                        continue
                    seen.add(url)
                    dims = site.get("originalImage", {}) or {}
                    w, h = dims.get("width"), dims.get("height")
                    resolution = f"{w}x{h}" if w and h else "Unknown"
                    results.append(ReverseSearchResult(
                        url=url, engine=ENGINE_YANDEX, score=0.75,
                        resolution=resolution, title=site.get("title"),
                    ))
            except (ValueError, TypeError, KeyError):
                pass

        if not results:  # markup fallback
            for a in soup.select("a.CbirSites-ItemTitle, a.Link_view_default"):
                url = a.get("href", "")
                if not url.startswith("http") or url in seen:
                    continue
                seen.add(url)
                results.append(ReverseSearchResult(
                    url=url, engine=ENGINE_YANDEX, score=0.7,
                    resolution="Unknown", title=a.get_text(strip=True) or None,
                ))
        return results

    def _emit_status(self, msg: str) -> None:
        if self._status_callback:
            self._status_callback(msg)

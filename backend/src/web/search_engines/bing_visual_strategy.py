"""Bing Visual Search — real implementation.

Two paths, auto-selected:

* **Official API** (if a ``BING_API_KEY`` is configured): multipart POST to the
  Visual Search endpoint, parse the ``tags[].actions[]`` structure for
  ``PagesIncluding`` / ``VisualSearch`` action types.
* **Web scrape** (keyless fallback): upload the image to Bing's "search by
  image" (sbi) endpoint and parse the returned results page.

Both fail soft: on block/parse failure the strategy returns ``[]`` (or raises
``RateLimited`` which the dispatcher isolates per engine).
"""

import base64
import logging
import re
from typing import List, Optional

from backend.src.web.crawlers.reverse_image_search_crawler import ReverseSearchEngine
from backend.src.web.models import ReverseSearchResult

from .common import make_session, raise_for_rate_limit, resolve_api_key

log = logging.getLogger(__name__)

ENGINE_BING = "bing"
_API_ENDPOINT = "https://api.bing.microsoft.com/v7.0/images/visualsearch"
_SBI_UPLOAD = "https://www.bing.com/images/search?view=detailv2&iss=sbi&FORM=SBIIRP"
_RES_RE = re.compile(r'"width":(\d+),"height":(\d+)')


class BingVisualSearchStrategy(ReverseSearchEngine):
    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: float = 20.0,
        status_callback: Optional[callable] = None,
    ) -> None:
        self._api_key = resolve_api_key("bing", "BING_API_KEY", api_key)
        self._timeout = timeout
        self._status_callback = status_callback
        self._is_running = True
        self._session = None

    def stop(self) -> None:
        self._is_running = False
        self._emit_status("Cancellation pending…")

    def search(self, image_path: str, **kwargs) -> List[ReverseSearchResult]:
        if self._session is None:
            self._session = make_session(self._timeout)
        if self._api_key:
            return self._search_api(image_path)
        return self._search_scrape(image_path)

    # -- official API -----------------------------------------------------
    def _search_api(self, image_path: str) -> List[ReverseSearchResult]:
        self._emit_status("Bing Visual Search (API)…")
        with open(image_path, "rb") as fh:
            files = {"image": ("query.jpg", fh, "application/octet-stream")}
            resp = self._session.post(
                _API_ENDPOINT, files=files, timeout=self._timeout,
                headers={"Ocp-Apim-Subscription-Key": self._api_key},
            )
        raise_for_rate_limit(resp, ENGINE_BING)
        resp.raise_for_status()
        results = self._parse_api_response(resp.json())
        self._emit_status(f"Bing returned {len(results)} matches.")
        return results

    @staticmethod
    def _parse_api_response(payload: dict) -> List[ReverseSearchResult]:
        """Parse the Bing Visual Search API JSON. Static + testable."""
        results: List[ReverseSearchResult] = []
        seen = set()
        for tag in (payload or {}).get("tags", []) or []:
            for action in tag.get("actions", []) or []:
                if action.get("actionType") not in ("PagesIncluding", "VisualSearch"):
                    continue
                items = ((action.get("data") or {}).get("value")) or []
                for item in items:
                    url = item.get("hostPageUrl") or item.get("webSearchUrl") or ""
                    if not url or url in seen:
                        continue
                    seen.add(url)
                    w, h = item.get("width"), item.get("height")
                    resolution = f"{w}x{h}" if w and h else "Unknown"
                    results.append(ReverseSearchResult(
                        url=url, engine=ENGINE_BING, score=0.85,
                        resolution=resolution, title=item.get("name"),
                    ))
        return results

    # -- keyless scrape ---------------------------------------------------
    def _search_scrape(self, image_path: str) -> List[ReverseSearchResult]:
        self._emit_status("Bing Visual Search (scrape)…")
        with open(image_path, "rb") as fh:
            image_b64 = base64.b64encode(fh.read()).decode("ascii")
        resp = self._session.post(
            _SBI_UPLOAD, data={"imgurl": "", "cbir": "sbi", "imageBin": image_b64},
            timeout=self._timeout,
        )
        raise_for_rate_limit(resp, ENGINE_BING)
        resp.raise_for_status()
        results = self._parse_scrape_response(resp.text)
        self._emit_status(f"Bing returned {len(results)} matches.")
        return results

    @staticmethod
    def _parse_scrape_response(html: str) -> List[ReverseSearchResult]:
        """Parse Bing's sbi results page. Static + testable.

        Result tiles embed a JSON ``m`` attribute with ``purl`` (page URL) and
        ``murl`` (media URL); we pull those out with BeautifulSoup + json.
        """
        import json

        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        results: List[ReverseSearchResult] = []
        seen = set()
        for tile in soup.find_all("a", class_="iusc"):
            raw = tile.get("m")
            if not raw:
                continue
            try:
                meta = json.loads(raw)
            except (ValueError, TypeError):
                continue
            url = meta.get("purl") or meta.get("murl") or ""
            if not url or url in seen:
                continue
            seen.add(url)
            res_match = _RES_RE.search(raw)
            resolution = (
                f"{res_match.group(1)}x{res_match.group(2)}" if res_match else "Unknown"
            )
            results.append(ReverseSearchResult(
                url=url, engine=ENGINE_BING, score=0.7,
                resolution=resolution, title=meta.get("t"),
            ))
        return results

    def _emit_status(self, msg: str) -> None:
        if self._status_callback:
            self._status_callback(msg)

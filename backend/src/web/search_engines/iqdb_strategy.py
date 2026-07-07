"""IQDB reverse-image search — real multi-booru HTML implementation.

IQDB has no JSON API: it's a multipart form POST (``file`` field) returning an
HTML results page. Each match row carries a source-site link and a
"NN% similarity" cell, which we parse with BeautifulSoup.
"""

import logging
import re
from typing import List, Optional
from urllib.parse import urljoin

from backend.src.web.crawlers.reverse_image_search_crawler import ReverseSearchEngine
from backend.src.web.models import ReverseSearchResult

from .common import make_session, raise_for_rate_limit

log = logging.getLogger(__name__)

ENGINE_IQDB = "iqdb"
_SEARCH_URL = "https://iqdb.org/"
_SIM_RE = re.compile(r"(\d+)%\s*similarity", re.IGNORECASE)
_RES_RE = re.compile(r"(\d+)[×x](\d+)")


class IqdbStrategy(ReverseSearchEngine):
    """Reverse image search via IQDB's multi-booru index."""

    def __init__(
        self,
        min_similarity: float = 60.0,
        timeout: float = 20.0,
        status_callback: Optional[callable] = None,
    ) -> None:
        self._min_similarity = min_similarity
        self._timeout = timeout
        self._status_callback = status_callback
        self._is_running = True
        self._session = None

    def stop(self) -> None:
        self._is_running = False

    def search(self, image_path: str, **kwargs) -> List[ReverseSearchResult]:
        self._emit_status("Uploading to IQDB…")
        if self._session is None:
            self._session = make_session(self._timeout)

        with open(image_path, "rb") as fh:
            files = {"file": ("query.jpg", fh, "application/octet-stream")}
            resp = self._session.post(_SEARCH_URL, files=files, timeout=self._timeout)
        raise_for_rate_limit(resp, ENGINE_IQDB)
        resp.raise_for_status()

        results = self._parse_response(resp.text, self._min_similarity, _SEARCH_URL)
        self._emit_status(f"IQDB returned {len(results)} matches.")
        return results

    @staticmethod
    def _parse_response(
        html: str, min_similarity: float, base_url: str = _SEARCH_URL
    ) -> List[ReverseSearchResult]:
        """Parse the IQDB HTML results page. Static + isolated for testing."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        results: List[ReverseSearchResult] = []

        # Each match is a <div> containing a table with rows: match label,
        # thumbnail (link to source), dimensions+rating, similarity.
        for table in soup.find_all("table"):
            text = table.get_text(" ", strip=True)
            sim_match = _SIM_RE.search(text)
            if not sim_match:
                continue
            similarity = float(sim_match.group(1))
            if similarity < min_similarity:
                continue

            # First anchor pointing at a source booru (skip the local thumb).
            anchor = None
            for a in table.find_all("a", href=True):
                href = a["href"]
                if href.startswith("#") or "iqdb.org" in href:
                    continue
                anchor = a
                break
            if anchor is None:
                continue
            url = anchor["href"]
            if url.startswith("//"):
                url = "https:" + url
            elif url.startswith("/"):
                url = urljoin(base_url, url)

            res_match = _RES_RE.search(text)
            resolution = (
                f"{res_match.group(1)}x{res_match.group(2)}" if res_match else "Unknown"
            )
            results.append(ReverseSearchResult(
                url=url,
                engine=ENGINE_IQDB,
                score=max(0.0, min(1.0, similarity / 100.0)),
                resolution=resolution,
                title=None,
            ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results

    def _emit_status(self, msg: str) -> None:
        if self._status_callback:
            self._status_callback(msg)

"""SauceNao reverse-image search — real REST implementation.

SauceNao exposes a documented JSON API (``output_type=2``). The public tier
works keyless at a low rate; an API key raises the limit and unlocks more DBs.
Highest precision for anime/illustration sources, so the dispatcher weights it
accordingly.
"""

import logging
from typing import List, Optional

from backend.src.web.crawlers.reverse_image_search_crawler import ReverseSearchEngine
from backend.src.web.models import ReverseSearchResult

from .common import make_session, raise_for_rate_limit, resolve_api_key

log = logging.getLogger(__name__)

ENGINE_SAUCENAO = "saucenao"
_API_BASE = "https://saucenao.com/search.php"


class SauceNaoStrategy(ReverseSearchEngine):
    """Reverse image search via the SauceNao JSON API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        min_similarity: float = 60.0,
        timeout: float = 20.0,
        status_callback: Optional[callable] = None,
    ) -> None:
        self._api_key = resolve_api_key("saucenao", "SAUCENAO_API_KEY", api_key)
        self._min_similarity = min_similarity
        self._timeout = timeout
        self._status_callback = status_callback
        self._is_running = True
        self._session = None

    def stop(self) -> None:
        self._is_running = False

    def search(self, image_path: str, **kwargs) -> List[ReverseSearchResult]:
        self._emit_status("Uploading to SauceNao…")
        if self._session is None:
            self._session = make_session(self._timeout)

        params = {
            "output_type": 2,     # JSON
            "numres": kwargs.get("numres", 16),
            "db": kwargs.get("db", 999),   # all databases
        }
        if self._api_key:
            params["api_key"] = self._api_key

        with open(image_path, "rb") as fh:
            files = {"file": ("query.jpg", fh, "application/octet-stream")}
            resp = self._session.post(
                _API_BASE, params=params, files=files, timeout=self._timeout
            )
        raise_for_rate_limit(resp, ENGINE_SAUCENAO)
        resp.raise_for_status()
        payload = resp.json()

        results = self._parse_response(payload, self._min_similarity)
        self._emit_status(f"SauceNao returned {len(results)} matches.")
        return results

    @staticmethod
    def _parse_response(payload: dict, min_similarity: float) -> List[ReverseSearchResult]:
        """Parse the SauceNao JSON body into normalized results.

        Isolated + static so it can be unit-tested against captured payloads
        without any network access.
        """
        results: List[ReverseSearchResult] = []
        for entry in (payload or {}).get("results", []) or []:
            header = entry.get("header", {}) or {}
            data = entry.get("data", {}) or {}
            try:
                similarity = float(header.get("similarity", 0.0))
            except (TypeError, ValueError):
                similarity = 0.0
            if similarity < min_similarity:
                continue
            urls = data.get("ext_urls") or []
            if not urls:
                continue
            title = (
                data.get("title")
                or data.get("source")
                or data.get("author_name")
                or header.get("index_name")
            )
            for url in urls:
                results.append(ReverseSearchResult(
                    url=url,
                    engine=ENGINE_SAUCENAO,
                    score=max(0.0, min(1.0, similarity / 100.0)),
                    resolution="Unknown",
                    title=title,
                ))
        results.sort(key=lambda r: r.score, reverse=True)
        return results

    def _emit_status(self, msg: str) -> None:
        if self._status_callback:
            self._status_callback(msg)

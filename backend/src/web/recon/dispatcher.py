"""Reverse-search dispatch with SQLite caching and per-engine rate limiting.

The dispatcher is *privacy-gated*: with ``privacy_mode`` on it never touches the
network and returns cached results only. Every request is keyed by the C++
``base.recon.cutout_hash`` of the alpha cutout, so re-querying the same subject
is served from cache — preventing IP bans / API throttling.
"""

import contextlib
import json
import logging
import os
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from urllib.parse import urlparse

from .config import ReconConfig

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS provenance_cache (
    cutout_hash TEXT NOT NULL,
    engine      TEXT NOT NULL,
    fetched_at  REAL NOT NULL,
    results     TEXT NOT NULL,
    PRIMARY KEY (cutout_hash, engine)
);
"""


@dataclass
class WebHit:
    url: str
    title: str = ""
    snippet: str = ""
    engine: str = ""

    @property
    def domain(self) -> str:
        try:
            return urlparse(self.url).netloc.replace("www.", "")
        except Exception:
            return ""

    def to_dict(self) -> dict:
        return {"url": self.url, "title": self.title, "snippet": self.snippet,
                "engine": self.engine, "domain": self.domain}


class RateLimiter:
    """Per-key minimum-interval limiter (thread-safe)."""

    def __init__(self, min_interval: float):
        self.min_interval = min_interval
        self._last: Dict[str, float] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        """Non-blocking: True if enough time has elapsed (and records the hit)."""
        with self._lock:
            now = time.monotonic()
            last = self._last.get(key, 0.0)
            if now - last >= self.min_interval:
                self._last[key] = now
                return True
            return False

    def wait(self, key: str):
        """Blocking throttle to honour the min interval."""
        with self._lock:
            now = time.monotonic()
            last = self._last.get(key, 0.0)
            delay = self.min_interval - (now - last)
            if delay > 0:
                time.sleep(delay)
            self._last[key] = time.monotonic()


class ProvenanceCache:
    def __init__(self, db_path: str):
        self.db_path = db_path
        if db_path != ":memory:":
            os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._local = threading.local()
        with self._conn() as con:
            con.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        con = getattr(self._local, "con", None)
        if con is None:
            con = sqlite3.connect(self.db_path)
            con.row_factory = sqlite3.Row
            self._local.con = con
        return con

    def get(self, cutout_hash: str, engine: str) -> Optional[List[WebHit]]:
        row = self._conn().execute(
            "SELECT results FROM provenance_cache WHERE cutout_hash=? AND engine=?",
            (cutout_hash, engine),
        ).fetchone()
        if row is None:
            return None
        return [WebHit(**h) for h in json.loads(row["results"])]

    def put(self, cutout_hash: str, engine: str, hits: List[WebHit]):
        payload = json.dumps([
            {k: v for k, v in h.to_dict().items() if k != "domain"} for h in hits
        ])
        con = self._conn()
        with con:
            con.execute(
                "INSERT OR REPLACE INTO provenance_cache "
                "(cutout_hash, engine, fetched_at, results) VALUES (?,?,?,?)",
                (cutout_hash, engine, time.time(), payload),
            )

    def close(self):
        con = getattr(self._local, "con", None)
        if con is not None:
            con.close()
            self._local.con = None


@dataclass
class DispatchResult:
    cutout_hash: str = ""
    hits: List[WebHit] = field(default_factory=list)
    from_cache: Dict[str, bool] = field(default_factory=dict)
    skipped_privacy: bool = False


class ReverseSearchDispatcher:
    """Fans an alpha-cutout out to reverse-image engines (cache + rate limited).

    Actual HTTP scraping is delegated to ``_query_engine`` which returns a list
    of WebHit; it is intentionally isolated (and stubbed to [] here) so the
    dispatcher's caching/rate-limit/privacy logic is fully testable offline and
    real engine adapters can be dropped in without touching this orchestration.
    """

    def __init__(self, config: ReconConfig, cache: Optional[ProvenanceCache] = None):
        self.config = config
        self.cache = cache or ProvenanceCache(config.cache_path)
        self.limiter = RateLimiter(config.min_request_interval)

    def cutout_hash(self, cutout_png: bytes) -> str:
        import base

        return base.recon.cutout_hash(cutout_png)

    def dispatch(self, cutout_png: bytes) -> DispatchResult:
        result = DispatchResult(cutout_hash=self.cutout_hash(cutout_png))

        if self.config.privacy_mode:
            # Air-gapped: serve only what is already cached, never hit network.
            result.skipped_privacy = True
            for engine in self.config.reverse_engines:
                cached = self.cache.get(result.cutout_hash, engine)
                if cached:
                    result.hits.extend(cached)
                    result.from_cache[engine] = True
            return result

        for engine in self.config.reverse_engines:
            cached = self.cache.get(result.cutout_hash, engine)
            if cached is not None:
                result.hits.extend(cached)
                result.from_cache[engine] = True
                continue
            self.limiter.wait(engine)
            try:
                hits = self._query_engine(engine, cutout_png)
                self.cache.put(result.cutout_hash, engine, hits)
                result.from_cache[engine] = False
            except Exception as e:
                logger.warning("Reverse search on %s failed: %s", engine, e)
                hits = []
            result.hits.extend(hits)
        return result

    def _query_engine(self, engine: str, cutout_png: bytes) -> List[WebHit]:
        """Dispatch to a concrete reverse-search scraper for *engine*.

        Writes the alpha cutout to a temp file (the strategies take a path),
        runs the matching scraper and maps its ``ReverseSearchResult`` list to
        ``WebHit``. Kept out of the caching/rate-limit path so those remain
        independently testable; failures propagate to ``dispatch`` which
        isolates them per engine.
        """
        strategy = self._build_strategy(engine)
        if strategy is None:
            return []

        import os
        import tempfile

        fd, tmp = tempfile.mkstemp(suffix=".png", prefix="recon-cutout-")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(cutout_png)
            results = strategy.search(tmp)
        finally:
            with contextlib.suppress(OSError):
                os.unlink(tmp)

        return [
            WebHit(url=r.url, title=r.title or "", snippet="", engine=engine)
            for r in results if r.url
        ]

    @staticmethod
    def _build_strategy(engine: str):
        """Construct a reverse-search strategy for an Entity-Recon engine name.

        Maps the recon engine ids to the shared search-engine strategies; the
        actual web-scraping / API logic lives there so it is not duplicated.
        """
        try:
            from backend.src.web.search_engines import (
                BingVisualSearchStrategy,
                IqdbStrategy,
                SauceNaoStrategy,
                YandexSearchStrategy,
            )
        except Exception as exc:  # optional deps (requests/bs4) missing
            logger.info("Reverse-search strategies unavailable: %s", exc)
            return None

        builders = {
            "yandex": YandexSearchStrategy,
            "bing": BingVisualSearchStrategy,
            "saucenao": SauceNaoStrategy,
            "iqdb": IqdbStrategy,
        }
        # Google Lens uses the existing C++ browser-driver strategy.
        if engine in ("google_lens", "google"):
            try:
                from backend.src.web.crawlers.reverse_image_search_crawler import (
                    GoogleSearchStrategy,
                )

                return GoogleSearchStrategy(headless=True)
            except Exception as exc:
                logger.info("Google Lens strategy unavailable: %s", exc)
                return None
        factory = builders.get(engine)
        return factory() if factory else None

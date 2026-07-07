"""Meta-crawling dispatcher: fan out a single query image to every
configured reverse-search engine in parallel, normalize their results, and
boost confidence for URLs that multiple independent engines agree on.

This sits one layer above ReverseImageSearchManager: where that class
picks *one* strategy per call, MetaSearchDispatcher runs *all* of them
concurrently and merges the output.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional
from urllib.parse import urlparse

from backend.src.web.crawlers.reverse_image_search_crawler import (
    ApiSearchStrategy,
    GoogleSearchStrategy,
    ReverseSearchEngine,
)
from backend.src.web.models import ReverseSearchResult
from backend.src.web.search_engines.bing_visual_strategy import BingVisualSearchStrategy
from backend.src.web.search_engines.iqdb_strategy import IqdbStrategy
from backend.src.web.search_engines.saucenao_strategy import SauceNaoStrategy
from backend.src.web.search_engines.yandex_strategy import YandexSearchStrategy

log = logging.getLogger(__name__)


@dataclass
class EngineOutcome:
    """Result (or failure) of one engine's search, before consensus merging.

    Attributes:
        engine: Engine name (e.g. "google", "saucenao").
        results: Results returned, empty on failure.
        error: Populated if the engine raised/timed out/rate-limited.
        elapsed_seconds: How long this engine took, for surfacing slow
            engines to the user or auto-tuning per-engine timeouts later.
    """
    engine: str
    results: List[ReverseSearchResult] = field(default_factory=list)
    error: Optional[str] = None
    elapsed_seconds: float = 0.0


@dataclass
class ConsensusResult:
    """A single merged result after cross-engine consensus scoring.

    Attributes:
        url: Canonical URL (first-seen form; engines may report trivially
            different URLs for the same resource, see `_canonical_key`).
        engines: Names of every engine that reported this URL.
        best_score: Highest individual-engine confidence score seen.
        consensus_score: `best_score` boosted by agreement count — the
            value results should actually be ranked by.
        resolution: Best (largest) resolution reported across engines.
        title: First non-empty title reported.
    """
    url: str
    engines: List[str]
    best_score: float
    consensus_score: float
    resolution: str
    title: Optional[str]


class MetaSearchDispatcher:
    """Fans a query image out to every enabled engine and merges the results.

    Args:
        enabled_engines: Which engine names to query, e.g.
            ["google", "tineye", "saucenao", "iqdb", "bing", "yandex"].
            Defaults to all engines this dispatcher knows how to build.
        per_engine_timeout: Seconds to wait for any single engine before
            treating it as failed and continuing with the others.
        consensus_boost_per_engine: Multiplicative boost applied to
            `best_score` for each *additional* engine that agrees on a URL
            (see `_compute_consensus` for the exact formula).
        status_callback: Optional callable(str) for status updates,
            forwarded from whichever engine emits them.
        engine_factory_overrides: Optional dict of engine_name -> zero-arg
            callable returning a configured ReverseSearchEngine, for tests
            or swapping in engine variants without subclassing.
    """

    DEFAULT_ENGINES = ("google", "tineye", "saucenao", "iqdb", "bing", "yandex")

    def __init__(
        self,
        enabled_engines: Optional[List[str]] = None,
        per_engine_timeout: float = 25.0,
        consensus_boost_per_engine: float = 0.15,
        status_callback: Optional[Callable[[str], None]] = None,
        engine_factory_overrides: Optional[Dict[str, Callable[[], ReverseSearchEngine]]] = None,
    ) -> None:
        self._enabled_engines = list(enabled_engines or self.DEFAULT_ENGINES)
        self._per_engine_timeout = per_engine_timeout
        self._consensus_boost_per_engine = consensus_boost_per_engine
        self._status_callback = status_callback
        self._engine_factory_overrides = engine_factory_overrides or {}
        self._active_engines: List[ReverseSearchEngine] = []
        self._is_running = True

    def stop(self) -> None:
        """Propagate cancellation to every currently-running engine."""
        self._is_running = False
        for engine in self._active_engines:
            engine.stop()

    async def search_all(
        self,
        image_path: str,
        engine_kwargs: Optional[Dict[str, dict]] = None,
    ) -> List[ConsensusResult]:
        """Run every enabled engine concurrently and return consensus-ranked results.

        Args:
            image_path: Path to the query image.
            engine_kwargs: Optional per-engine kwargs, e.g.
                {"saucenao": {"min_similarity": 70}}.

        Returns:
            Consensus results sorted by `consensus_score` descending.
        """
        engine_kwargs = engine_kwargs or {}
        tasks = [
            self._run_one_engine(name, image_path, engine_kwargs.get(name, {}))
            for name in self._enabled_engines
        ]
        outcomes: List[EngineOutcome] = await asyncio.gather(*tasks)

        for outcome in outcomes:
            if outcome.error:
                self._emit_status(f"{outcome.engine}: {outcome.error}")
            else:
                self._emit_status(
                    f"{outcome.engine}: {len(outcome.results)} results "
                    f"({outcome.elapsed_seconds:.1f}s)"
                )

        return self._compute_consensus(outcomes)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _run_one_engine(
        self,
        engine_name: str,
        image_path: str,
        kwargs: dict,
    ) -> EngineOutcome:
        """Run a single engine with a timeout, isolating its failures.

        Existing strategies (GoogleSearchStrategy, ApiSearchStrategy, etc.)
        expose a synchronous `.search()`; run each in a worker thread via
        `asyncio.to_thread` so a slow/blocking engine doesn't stall the
        others.
        """
        engine = self._build_engine(engine_name)
        self._active_engines.append(engine)
        loop = asyncio.get_event_loop()
        start = loop.time()

        try:
            results = await asyncio.wait_for(
                asyncio.to_thread(engine.search, image_path, **kwargs),
                timeout=self._per_engine_timeout,
            )
            return EngineOutcome(
                engine=engine_name,
                results=results,
                elapsed_seconds=loop.time() - start,
            )
        except asyncio.TimeoutError:
            engine.stop()
            return EngineOutcome(
                engine=engine_name,
                error=f"timed out after {self._per_engine_timeout}s",
                elapsed_seconds=self._per_engine_timeout,
            )
        except Exception as exc:
            log.warning("%s engine failed: %s", engine_name, exc)
            return EngineOutcome(
                engine=engine_name,
                error=str(exc),
                elapsed_seconds=loop.time() - start,
            )
        finally:
            if engine in self._active_engines:
                self._active_engines.remove(engine)

    def _build_engine(self, engine_name: str) -> ReverseSearchEngine:
        """Construct a configured strategy instance for `engine_name`.

        Honors `engine_factory_overrides` first, then falls back to the
        built-in defaults below.
        """
        if engine_name in self._engine_factory_overrides:
            return self._engine_factory_overrides[engine_name]()

        cb = self._status_callback
        builders: Dict[str, Callable[[], ReverseSearchEngine]] = {
            "google": lambda: GoogleSearchStrategy(status_callback=cb),
            "tineye": lambda: ApiSearchStrategy(status_callback=cb),
            "bing": lambda: BingVisualSearchStrategy(status_callback=cb),
            "yandex": lambda: YandexSearchStrategy(status_callback=cb),
            "saucenao": lambda: SauceNaoStrategy(status_callback=cb),
            "iqdb": lambda: IqdbStrategy(status_callback=cb),
        }
        if engine_name not in builders:
            raise ValueError(f"Unknown engine_name {engine_name!r}")
        return builders[engine_name]()

    def _compute_consensus(self, outcomes: List[EngineOutcome]) -> List[ConsensusResult]:
        """Merge per-engine results into consensus-ranked results.

        Grouping key is `_canonical_key(url)` rather than the raw URL, so
        trivial differences (http vs https, trailing slash, query-string
        cache-busters) don't split what's really the same source.

        Consensus formula: consensus_score = best_score * (1 +
        consensus_boost_per_engine * (num_agreeing_engines - 1)), capped at
        1.0. This rewards agreement without letting a mediocre match from
        many engines outrank a near-perfect single-engine match — tune the
        boost constant and cap based on real result distributions once
        engines are live.
        """
        grouped: Dict[str, ConsensusResult] = {}

        for outcome in outcomes:
            for result in outcome.results:
                key = self._canonical_key(result.url)
                if key not in grouped:
                    grouped[key] = ConsensusResult(
                        url=result.url,
                        engines=[outcome.engine],
                        best_score=result.score,
                        consensus_score=result.score,
                        resolution=result.resolution,
                        title=result.title,
                    )
                    continue

                existing = grouped[key]
                if outcome.engine not in existing.engines:
                    existing.engines.append(outcome.engine)
                existing.best_score = max(existing.best_score, result.score)
                existing.resolution = self._better_resolution(
                    existing.resolution, result.resolution
                )
                existing.title = existing.title or result.title

        for consensus in grouped.values():
            agreeing = len(consensus.engines)
            boosted = consensus.best_score * (
                1 + self._consensus_boost_per_engine * (agreeing - 1)
            )
            consensus.consensus_score = min(1.0, boosted)

        return sorted(grouped.values(), key=lambda c: c.consensus_score, reverse=True)

    @staticmethod
    def _canonical_key(url: str) -> str:
        """Normalize a URL for cross-engine dedup: lowercase host, strip
        scheme/query/trailing-slash. Not a perfect content-identity check
        (that would need a pixel/pHash comparison), but enough to catch the
        common case of the same image URL reported with minor variations.
        """
        parsed = urlparse(url.lower())
        path = parsed.path.rstrip("/")
        return f"{parsed.netloc}{path}"

    @staticmethod
    def _better_resolution(a: str, b: str) -> str:
        """Pick the larger of two 'WxH' resolution strings; falls back
        gracefully if either is 'Unknown' or unparsable."""
        def area(res: str) -> int:
            try:
                w, h = res.lower().split("x")
                return int(w) * int(h)
            except (ValueError, AttributeError):
                return -1

        return a if area(a) >= area(b) else b

    def _emit_status(self, msg: str) -> None:
        if self._status_callback:
            self._status_callback(msg)

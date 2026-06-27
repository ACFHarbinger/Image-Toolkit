"""Reverse image search — Strategy Pattern implementation.

Three concrete strategies are provided:

* ``GoogleSearchStrategy``  — scrapes Google Lens via the existing Rust extension.
* ``ApiSearchStrategy``     — delegates to :class:`~backend.src.web.clients.tineye_client.TinEyeClient`.
* ``LocalCBIRStrategy``     — queries the local CLIP + FAISS index.

All strategies share the ``ReverseSearchEngine`` ABC and return
``List[ReverseSearchResult]``.

The ``ReverseImageSearchManager`` selects a strategy at call-time via the
``engine_type`` parameter so that upstream code (workers, tests) never needs to
instantiate strategy objects directly.

``ReverseImageSearchCrawler`` is kept as a thin alias for
``GoogleSearchStrategy`` to avoid breaking existing import sites.
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import List, Optional

from PySide6.QtCore import QObject, Signal

import base  # Native Rust extension  # noqa: E402

from backend.src.web.models import ReverseSearchResult

log = logging.getLogger(__name__)

# ── Engine type literals ──────────────────────────────────────────────────────
ENGINE_GOOGLE = "google"
ENGINE_TINEYE = "tineye"
ENGINE_LOCAL_CBIR = "local_cbir"

SUPPORTED_ENGINES = (ENGINE_GOOGLE, ENGINE_TINEYE, ENGINE_LOCAL_CBIR)


# ── Base interface ────────────────────────────────────────────────────────────

class ReverseSearchEngine(ABC):
    """Abstract base class that all search engine strategies must implement."""

    @abstractmethod
    def search(
        self,
        image_path: str,
        **kwargs,
    ) -> List[ReverseSearchResult]:
        """Run a reverse image search for *image_path*.

        Args:
            image_path: Absolute path to the query image.
            **kwargs: Engine-specific parameters (e.g. ``search_mode``,
                ``min_width``).

        Returns:
            Ordered list of :class:`~backend.src.web.models.ReverseSearchResult`,
            highest relevance first.
        """

    def stop(self) -> None:
        """Signal the engine to abort an in-progress search (best-effort)."""


# ── Concrete strategy: Google Lens via Rust ──────────────────────────────────

class GoogleSearchStrategy(ReverseSearchEngine):
    """Reverse image search via Google Lens using the native Rust browser driver.

    Args:
        headless: Run the browser headlessly.
        browser: Browser binary to use (``"brave"``, ``"chrome"``, etc.).
        status_callback: Optional callable receiving status strings, e.g. for
            forwarding to a Qt signal.
    """

    def __init__(
        self,
        headless: bool = False,
        browser: str = "brave",
        status_callback=None,
    ) -> None:
        self._headless = headless
        self._browser = browser
        self._status_callback = status_callback
        self._is_running = True

    def stop(self) -> None:
        self._is_running = False
        self._emit_status("Cancellation pending…")

    def search(
        self,
        image_path: str,
        search_mode: str = "All",
        min_width: int = 0,
        min_height: int = 0,
        keep_open: bool = False,
        **kwargs,
    ) -> List[ReverseSearchResult]:
        """Delegate to ``base.run_reverse_image_search`` (Rust implementation).

        Args:
            image_path: Path to the query image.
            search_mode: Google Lens scrape mode — ``"All"``,
                ``"Visual matches"``, or ``"Exact matches"``.
            min_width: Minimum result width filter (applied post-scrape).
            min_height: Minimum result height filter (applied post-scrape).
            keep_open: Whether the Rust layer should keep the browser open
                after the search.
        """
        self._emit_status("Initialising browser…")

        # The Rust extension accepts a JSON config blob and an optional Python
        # object that it calls back via the ``on_status_emitted`` method.
        config = {
            "headless": self._headless,
            "image_path": image_path,
            "search_mode": search_mode,
            "browser": self._browser,
        }

        try:
            # _ProxyQObject is used so Rust can call on_status_emitted without
            # the strategy itself needing to inherit from QObject.
            proxy = _StatusProxy(self._emit_status)
            results_json: str = base.run_reverse_image_search(json.dumps(config), proxy)
            raw: List[dict] = json.loads(results_json)
        except Exception as exc:
            log.error("Rust reverse image search failed: %s", exc)
            self._emit_status(f"Error: {exc}")
            return []

        results = [
            ReverseSearchResult(
                url=r.get("url", ""),
                engine=ENGINE_GOOGLE,
                score=1.0,
                resolution=r.get("resolution", "Unknown"),
                title=r.get("title"),
            )
            for r in raw
            if r.get("url")
        ]
        return results

    def _emit_status(self, msg: str) -> None:
        if self._status_callback:
            self._status_callback(msg)


class _StatusProxy:
    """Minimal duck-type used by the Rust extension to emit status messages."""

    def __init__(self, callback) -> None:
        self._cb = callback

    def on_status_emitted(self, msg: str) -> None:
        if self._cb:
            self._cb(msg)


# ── Concrete strategy: TinEye API ───────────────────────────────────────────

class ApiSearchStrategy(ReverseSearchEngine):
    """Reverse image search via the TinEye commercial REST API.

    API credentials are resolved by :class:`~backend.src.web.clients.tineye_client.TinEyeClient`
    from environment variables or ``backend/config/api_keys.yaml``.

    Args:
        status_callback: Optional callable for forwarding status strings.
    """

    def __init__(self, status_callback=None) -> None:
        self._status_callback = status_callback
        self._client = None

    def search(
        self,
        image_path: str,
        limit: int = 20,
        **kwargs,
    ) -> List[ReverseSearchResult]:
        """Search TinEye by uploading the image file.

        Args:
            image_path: Absolute path to the query image.
            limit: Maximum number of results to request from TinEye.
        """
        from backend.src.web.clients.tineye_client import TinEyeClient

        self._emit_status("Connecting to TinEye API…")
        try:
            if self._client is None:
                self._client = TinEyeClient()
            self._emit_status("Uploading image to TinEye…")
            results = self._client.search_by_file(image_path, limit=limit)
            self._emit_status(f"TinEye returned {len(results)} matches.")
            return results
        except EnvironmentError as exc:
            log.error("TinEye credentials missing: %s", exc)
            self._emit_status("TinEye credentials not configured.")
            raise
        except Exception as exc:
            log.error("TinEye search failed: %s", exc)
            self._emit_status(f"TinEye error: {exc}")
            raise

    def _emit_status(self, msg: str) -> None:
        if self._status_callback:
            self._status_callback(msg)


# ── Concrete strategy: Local CBIR (CLIP + FAISS) ─────────────────────────────

class LocalCBIRStrategy(ReverseSearchEngine):
    """Reverse image search against the user's locally indexed CLIP vector database.

    Uses :class:`~backend.src.core.cbir_search.LocalCBIRSearch` under the hood.

    Args:
        top_k: Number of nearest neighbours to retrieve.
        status_callback: Optional callable for forwarding status strings.
    """

    def __init__(
        self,
        top_k: int = 20,
        status_callback=None,
    ) -> None:
        self._top_k = top_k
        self._status_callback = status_callback
        self._searcher = None

    def search(
        self,
        image_path: str,
        top_k: Optional[int] = None,
        **kwargs,
    ) -> List[ReverseSearchResult]:
        """Retrieve similar images from the local CLIP + FAISS index.

        Args:
            image_path: Absolute path to the query image.
            top_k: Override the default number of results to return.
        """
        from backend.src.core.cbir_search import LocalCBIRSearch

        self._emit_status("Loading CLIP model and FAISS index…")
        try:
            if self._searcher is None:
                self._searcher = LocalCBIRSearch(top_k=self._top_k)
            self._emit_status("Encoding query image…")
            k = top_k if top_k is not None else self._top_k
            results = self._searcher.search(image_path, top_k=k)
            self._emit_status(f"Local search found {len(results)} similar images.")
            return results
        except (FileNotFoundError, ImportError) as exc:
            log.error("Local CBIR unavailable: %s", exc)
            self._emit_status(f"Local index error: {exc}")
            raise
        except Exception as exc:
            log.error("Local CBIR search failed: %s", exc)
            self._emit_status(f"CBIR error: {exc}")
            raise

    def _emit_status(self, msg: str) -> None:
        if self._status_callback:
            self._status_callback(msg)


# ── Manager ──────────────────────────────────────────────────────────────────

class ReverseImageSearchManager(QObject):
    """Selects and runs the appropriate :class:`ReverseSearchEngine` strategy.

    This is the single entry-point used by GUI workers; they never instantiate
    strategy objects directly.

    Signals:
        on_status (str): Emitted for status / progress updates.

    Args:
        headless: Passed to :class:`GoogleSearchStrategy`.
        browser: Passed to :class:`GoogleSearchStrategy`.
    """

    on_status = Signal(str)

    def __init__(
        self,
        headless: bool = False,
        browser: str = "brave",
    ) -> None:
        super().__init__()
        self._headless = headless
        self._browser = browser
        self._active_strategy: Optional[ReverseSearchEngine] = None

    def stop(self) -> None:
        """Delegate a stop request to the currently active strategy."""
        if self._active_strategy:
            self._active_strategy.stop()
        self.on_status.emit("Cancellation pending…")

    def perform_reverse_search(
        self,
        image_path: str,
        engine_type: str = ENGINE_GOOGLE,
        **kwargs,
    ) -> List[dict]:
        """Run a reverse image search and return serialisable result dicts.

        Args:
            image_path: Absolute path to the query image.
            engine_type: One of ``"google"``, ``"tineye"``, ``"local_cbir"``.
            **kwargs: Forwarded to the selected strategy's ``search()`` method
                (e.g. ``search_mode``, ``min_width``, ``limit``, ``top_k``).

        Returns:
            List of dicts compatible with the GUI's ``Signal(list)`` format.
            Each dict has ``url``, ``resolution``, ``score``, ``engine``,
            ``title`` keys.

        Raises:
            ValueError: For unrecognised ``engine_type`` values.
        """
        if engine_type not in SUPPORTED_ENGINES:
            raise ValueError(
                f"Unknown engine_type {engine_type!r}. "
                f"Choose from {SUPPORTED_ENGINES}."
            )

        strategy = self._build_strategy(engine_type)
        self._active_strategy = strategy

        try:
            results = strategy.search(image_path, **kwargs)
        finally:
            self._active_strategy = None

        return [r.to_dict() for r in results]

    def _build_strategy(self, engine_type: str) -> ReverseSearchEngine:
        cb = self.on_status.emit
        if engine_type == ENGINE_GOOGLE:
            return GoogleSearchStrategy(
                headless=self._headless,
                browser=self._browser,
                status_callback=cb,
            )
        if engine_type == ENGINE_TINEYE:
            return ApiSearchStrategy(status_callback=cb)
        if engine_type == ENGINE_LOCAL_CBIR:
            return LocalCBIRStrategy(status_callback=cb)
        raise ValueError(f"Unhandled engine_type: {engine_type!r}")  # pragma: no cover


# ── Backward-compatibility alias ─────────────────────────────────────────────

class ReverseImageSearchCrawler(QObject):
    """Retained for backward compatibility.  New code should use
    :class:`ReverseImageSearchManager` with ``engine_type="google"``.
    """

    on_status = Signal(str)

    def __init__(
        self,
        headless: bool = True,
        download_dir=None,
        screenshot_dir=None,
        browser: str = "brave",
    ) -> None:
        super().__init__()
        self._manager = ReverseImageSearchManager(headless=headless, browser=browser)
        self._manager.on_status.connect(self.on_status)

    def stop(self) -> None:
        self._manager.stop()

    def on_status_emitted(self, msg: str) -> None:
        self.on_status.emit(msg)

    def perform_reverse_search(
        self,
        image_path: str,
        min_width: int = 0,
        min_height: int = 0,
        search_mode: str = "All",
    ) -> List[dict]:
        return self._manager.perform_reverse_search(
            image_path,
            engine_type=ENGINE_GOOGLE,
            search_mode=search_mode,
            min_width=min_width,
            min_height=min_height,
        )

    def close(self) -> None:
        pass

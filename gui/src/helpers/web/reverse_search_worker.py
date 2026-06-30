"""QRunnable worker that drives a reverse image search off the main thread.

The worker accepts an ``engine_type`` string (``"google"``, ``"tineye"``, or
``"local_cbir"``) and routes the request to the appropriate strategy via
:class:`~backend.src.web.ReverseImageSearchManager`.

All three engines return the same ``List[dict]`` payload through the
``finished`` signal, keeping downstream result-display code engine-agnostic.
"""

from typing import Optional

from PySide6.QtCore import Signal, QObject, QRunnable

from backend.src.web import (
    ReverseImageSearchManager,
    ENGINE_GOOGLE,
    ENGINE_TINEYE,
    ENGINE_LOCAL_CBIR,
)


class _ReverseSearchWorkerSignals(QObject):
    """Signals emitted by :class:`ReverseSearchWorker`."""

    finished = Signal(list)
    """Emitted with a list of result dicts (keys: url, resolution, score, engine, title)."""

    error = Signal(str)
    """Emitted with an error message string on unhandled exceptions."""

    status = Signal(str)
    """Emitted with a progress/status string during the search."""


class ReverseSearchWorker(QRunnable):
    """Thread-pool worker that runs a reverse image search without blocking the GUI.

    Args:
        image_path: Absolute path to the query image.
        engine_type: Which backend to use — ``"google"``, ``"tineye"``, or
            ``"local_cbir"``.
        min_width: Minimum result width (Google engine only; 0 = no filter).
        min_height: Minimum result height (Google engine only; 0 = no filter).
        browser: Browser to drive (Google engine only).
        search_mode: Google Lens scrape mode — ``"All"``, ``"Visual matches"``,
            or ``"Exact matches"``.
        keep_open: Keep the browser open after search (Google engine only).
        top_k: Maximum results for ``"local_cbir"`` and ``"tineye"`` engines.
    """

    def __init__(
        self,
        image_path: str,
        engine_type: str = ENGINE_GOOGLE,
        min_width: int = 0,
        min_height: int = 0,
        browser: str = "brave",
        search_mode: str = "All",
        keep_open: bool = False,
        top_k: int = 20,
    ) -> None:
        super().__init__()
        self.image_path = image_path
        self.engine_type = engine_type
        self.min_width = min_width
        self.min_height = min_height
        self.browser = browser
        self.search_mode = search_mode
        self.keep_open = keep_open
        self.top_k = top_k
        self.signals = _ReverseSearchWorkerSignals()

        self._manager: Optional[ReverseImageSearchManager] = None

    def cancel(self) -> None:
        """Request early termination of the in-progress search."""
        if self._manager:
            self._manager.stop()

    def run(self) -> None:
        """Execute the search on a QThreadPool worker thread."""
        try:
            self._manager = ReverseImageSearchManager(
                headless=False,
                browser=self.browser,
            )
            self._manager.on_status.connect(self.signals.status)

            engine_label = {
                ENGINE_GOOGLE: "Google Lens",
                ENGINE_TINEYE: "TinEye",
                ENGINE_LOCAL_CBIR: "Local AI Search",
            }.get(self.engine_type, self.engine_type)

            self.signals.status.emit(f"Starting {engine_label} search…")

            results = self._manager.perform_reverse_search(
                image_path=self.image_path,
                engine_type=self.engine_type,
                # Google-specific
                search_mode=self.search_mode,
                min_width=self.min_width,
                min_height=self.min_height,
                keep_open=self.keep_open,
                # TinEye / CBIR
                limit=self.top_k,
                top_k=self.top_k,
            )
            self.signals.finished.emit(results)

        except Exception as exc:
            self.signals.error.emit(str(exc))
        finally:
            self._manager = None

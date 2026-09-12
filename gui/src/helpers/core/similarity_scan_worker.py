"""Background worker driving :class:`SimilarityEngine` off the UI thread.

The worker is a ``QThread`` *subclass* that overrides ``run()`` (the same
pattern as :class:`DeletionWorker`). This is deliberate: a plain ``QThread`` +
``moveToThread`` would start the default per-thread event loop (``exec()``),
which on Linux/glib creates an event dispatcher with socket notifiers in a
secondary thread. With the JPype JVM loaded in-process that collides fatally
("QSocketNotifier: ... from another thread" → SIGSEGV in libQt6Core). Overriding
``run()`` means no event loop is ever started in the worker thread.

All heavy compute happens either in C++ with the GIL released (hashing,
VP-tree, HNSW, SSIM/ORB/SIFT) or inside torch forward passes (embeddings);
progress/cancellation flow through Qt signals (queued to the GUI thread).
"""
import logging

from backend.src.core.similarity import SimilarityConfig, SimilarityEngine
from backend.src.core.similarity.engine import ScanCancelled
from PySide6.QtCore import Signal

from gui.src.helpers.base import BaseQThreadWorker

logger = logging.getLogger(__name__)

class SimilarityScanWorker(BaseQThreadWorker):
    finished = Signal(object)        # SimilarityReport, None on failure/cancel
    status = Signal(str)
    progress = Signal(int, int)      # done, total (0,0 = indeterminate)

    def __init__(self, config: SimilarityConfig):
        super().__init__()
        self.config = config

    def _on_progress(self, stage: str, done: int, total: int):
        self.status.emit(stage if total == 0 else f"{stage} ({done}/{total})")
        self.progress.emit(done, total)

    def _execute(self) -> object:
        try:
            engine = SimilarityEngine(
                self.config,
                progress_cb=self._on_progress,
                cancel_cb=self.isInterruptionRequested,
            )
            report = engine.scan()
            if self.isInterruptionRequested():
                return None
            return report
        except ScanCancelled:
            return None
        finally:
            # Free any embedding model VRAM once the scan ends.
            try:
                from backend.src.core.similarity.embedder import unload_all

                unload_all()
            except Exception:
                logger.debug("Suppressed Exception in SimilarityScanWorker.run", exc_info=True)

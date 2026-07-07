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
from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)


class SimilarityScanWorker(QThread):
    # NOTE: these custom signals intentionally shadow QThread's built-in
    # ``finished``/``started`` — callers must use these, not QThread.finished.
    finished = Signal(object)        # SimilarityReport
    error = Signal(str)
    status = Signal(str)
    progress = Signal(int, int)      # done, total (0,0 = indeterminate)
    cancelled = Signal()

    def __init__(self, config: SimilarityConfig):
        super().__init__()
        self.config = config

    def _on_progress(self, stage: str, done: int, total: int):
        self.status.emit(stage if total == 0 else f"{stage} ({done}/{total})")
        self.progress.emit(done, total)

    def _is_cancelled(self) -> bool:
        return self.isInterruptionRequested()

    def run(self):
        try:
            engine = SimilarityEngine(
                self.config,
                progress_cb=self._on_progress,
                cancel_cb=self._is_cancelled,
            )
            report = engine.scan()
            if self.isInterruptionRequested():
                self.cancelled.emit()
            else:
                self.finished.emit(report)
        except ScanCancelled:
            self.cancelled.emit()
        except Exception as e:  # surface everything — worker thread has no UI
            logger.exception("Similarity scan failed")
            self.error.emit(str(e))
        finally:
            # Free any embedding model VRAM once the scan ends.
            try:
                from backend.src.core.similarity.embedder import unload_all

                unload_all()
            except Exception:
                pass

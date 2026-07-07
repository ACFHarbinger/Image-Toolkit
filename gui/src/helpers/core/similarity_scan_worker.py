"""Background worker driving :class:`SimilarityEngine` off the UI thread.

The worker lives in a dedicated QThread (created by SimilarityTab). All heavy
compute happens either in C++ with the GIL released (hashing, VP-tree, HNSW,
SSIM/ORB/SIFT) or inside torch forward passes (embeddings), so the GUI event
loop stays responsive; progress/cancellation flow through Qt signals.
"""

import logging

from backend.src.core.similarity import SimilarityConfig, SimilarityEngine
from backend.src.core.similarity.engine import ScanCancelled
from PySide6.QtCore import QObject, QThread, Signal, Slot

logger = logging.getLogger(__name__)


class SimilarityScanWorker(QObject):
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

    @staticmethod
    def _is_cancelled() -> bool:
        thread = QThread.currentThread()
        return bool(thread and thread.isInterruptionRequested())

    @Slot()
    def run(self):
        try:
            engine = SimilarityEngine(
                self.config,
                progress_cb=self._on_progress,
                cancel_cb=self._is_cancelled,
            )
            report = engine.scan()
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

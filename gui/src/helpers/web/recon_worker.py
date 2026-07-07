"""Background workers for the Entity Recon tab.

All heavy work (dataset indexing, SAM segmentation, embedding + resolution)
runs off the UI thread. C++ HNSW and torch forward passes release the GIL, so
the Qt event loop stays responsive.
"""

import logging
from typing import List

import numpy as np
from backend.src.web.recon import DatasetIndexer, ReconConfig, ReconEngine
from PySide6.QtCore import QObject, QThread, Signal, Slot

logger = logging.getLogger(__name__)


class IndexBuildWorker(QObject):
    """Builds the local identity HNSW index from a dataset root."""

    finished = Signal(object, dict)   # DatasetIndexer, stats
    error = Signal(str)
    status = Signal(str)
    progress = Signal(int, int)

    def __init__(self, config: ReconConfig):
        super().__init__()
        self.config = config

    @staticmethod
    def _cancelled() -> bool:
        t = QThread.currentThread()
        return bool(t and t.isInterruptionRequested())

    @Slot()
    def run(self):
        try:
            indexer = DatasetIndexer(
                self.config,
                progress_cb=lambda stage, d, t: (
                    self.status.emit(stage), self.progress.emit(d, t)),
                cancel_cb=self._cancelled,
            )
            indexer.build()
            self.finished.emit(indexer, indexer.stats)
        except Exception as e:
            logger.exception("Index build failed")
            self.error.emit(str(e))


class ResolveWorker(QObject):
    """Segments (optional), embeds and resolves a subject cutout."""

    finished = Signal(object)   # IdentityResolution
    error = Signal(str)
    status = Signal(str)

    def __init__(self, engine: ReconEngine, cutout_rgb: np.ndarray, cutout_png: bytes):
        super().__init__()
        self.engine = engine
        self.cutout_rgb = cutout_rgb
        self.cutout_png = cutout_png

    @Slot()
    def run(self):
        try:
            self.status.emit("Resolving identity...")
            res = self.engine.resolve(self.cutout_rgb, self.cutout_png)
            self.finished.emit(res)
        except Exception as e:
            logger.exception("Resolve failed")
            self.error.emit(str(e))


class BatchSuggestWorker(QObject):
    """Runs identity resolution over a dropped batch of images."""

    finished = Signal(list)     # list[dict]
    error = Signal(str)
    status = Signal(str)

    def __init__(self, engine: ReconEngine, paths: List[str]):
        super().__init__()
        self.engine = engine
        self.paths = paths

    @Slot()
    def run(self):
        try:
            self.status.emit(f"Analyzing {len(self.paths)} images...")
            suggestions = self.engine.suggest_batch(self.paths)
            self.finished.emit(suggestions)
        except Exception as e:
            logger.exception("Batch suggest failed")
            self.error.emit(str(e))

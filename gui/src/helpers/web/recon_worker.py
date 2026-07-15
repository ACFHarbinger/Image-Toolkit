"""Background workers for the Entity Recon tab.

All heavy work (dataset indexing, SAM segmentation, embedding + resolution)
runs off the UI thread. The workers are ``QThread`` *subclasses* that override
``run()`` — NOT QObjects moved onto a plain QThread. A plain QThread runs the
default event loop (``exec()``), which on Linux/glib creates a socket-notifier
event dispatcher in a secondary thread; with the JPype JVM loaded in-process
that collides fatally ("QSocketNotifier: ... from another thread" → SIGSEGV).
Overriding ``run()`` guarantees no event loop is started in the worker thread.

C++ HNSW and torch forward passes release the GIL; progress/results flow to
the GUI thread through queued Qt signals.
"""

import logging
from typing import List

import numpy as np
from backend.src.web.recon import DatasetIndexer, ReconConfig, ReconEngine
from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)


class IndexBuildWorker(QThread):
    """Builds the local identity HNSW index from a dataset root."""

    sig_finished = Signal(object, dict)  # DatasetIndexer, stats
    error = Signal(str)
    status = Signal(str)
    progress = Signal(int, int)

    def __init__(self, config: ReconConfig):
        super().__init__()
        self.config = config

    def _cancelled(self) -> bool:
        return self.isInterruptionRequested()

    def run(self):
        try:
            def progress_callback(stage: str, d: int, t: int) -> None:
                self.status.emit(stage)
                self.progress.emit(d, t)

            indexer = DatasetIndexer(
                self.config,
                progress_cb=progress_callback,
                cancel_cb=self._cancelled,
            )
            indexer.build()
            self.sig_finished.emit(indexer, indexer.stats)
        except Exception as e:
            logger.exception("Index build failed")
            self.error.emit(str(e))


class ResolveWorker(QThread):
    """Segments (optional), embeds and resolves a subject cutout."""

    sig_finished = Signal(object)  # IdentityResolution
    error = Signal(str)
    status = Signal(str)

    def __init__(self, engine: ReconEngine, cutout_rgb: np.ndarray, cutout_png: bytes):
        super().__init__()
        self.engine = engine
        self.cutout_rgb = cutout_rgb
        self.cutout_png = cutout_png

    def run(self):
        try:
            self.status.emit("Resolving identity...")
            res = self.engine.resolve(self.cutout_rgb, self.cutout_png)
            self.sig_finished.emit(res)
        except Exception as e:
            logger.exception("Resolve failed")
            self.error.emit(str(e))


class BatchSuggestWorker(QThread):
    """Runs identity resolution over a dropped batch of images."""

    sig_finished = Signal(list)  # list[dict]
    error = Signal(str)
    status = Signal(str)

    def __init__(self, engine: ReconEngine, paths: List[str]):
        super().__init__()
        self.engine = engine
        self.paths = paths

    def run(self):
        try:
            self.status.emit(f"Analyzing {len(self.paths)} images...")
            suggestions = self.engine.suggest_batch(self.paths)
            self.sig_finished.emit(suggestions)
        except Exception as e:
            logger.exception("Batch suggest failed")
            self.error.emit(str(e))

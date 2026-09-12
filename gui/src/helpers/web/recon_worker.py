"""Background workers for the Entity Recon tab.

All heavy work (dataset indexing, SAM segmentation, embedding + resolution)
runs off the UI thread. The workers subclass ``BaseQThreadWorker`` (R1.1),
whose ``run()`` override — NOT a QObject moved onto a plain QThread —
guarantees no event loop is started in the worker thread. A plain QThread
runs the default event loop (``exec()``), which on Linux/glib creates a
socket-notifier event dispatcher in a secondary thread; with the JPype JVM
loaded in-process that collides fatally ("QSocketNotifier: ... from another
thread" → SIGSEGV).

C++ HNSW and torch forward passes release the GIL; progress/results flow to
the GUI thread through queued Qt signals.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    import numpy as np

from backend.src.web.recon import DatasetIndexer, ReconConfig, ReconEngine
from PySide6.QtCore import Signal

from gui.src.helpers.base import BaseQThreadWorker

logger = logging.getLogger(__name__)


class IndexBuildWorker(BaseQThreadWorker):
    """Builds the local identity HNSW index from a dataset root."""

    finished = Signal(tuple)  # (DatasetIndexer, stats)
    status = Signal(str)
    progress = Signal(int, int)

    def __init__(self, config: ReconConfig):
        super().__init__()
        self.config = config

    def _execute(self) -> object:
        def progress_callback(stage: str, d: int, t: int) -> None:
            self.status.emit(stage)
            self.progress.emit(d, t)

        indexer = DatasetIndexer(
            self.config,
            progress_cb=progress_callback,
            cancel_cb=self.isInterruptionRequested,
        )
        indexer.build()
        return (indexer, indexer.stats)


class ResolveWorker(BaseQThreadWorker):
    """Segments (optional), embeds and resolves a subject cutout."""

    finished = Signal(object)  # IdentityResolution, None on failure/cancel
    status = Signal(str)

    def __init__(self, engine: ReconEngine, cutout_rgb: np.ndarray, cutout_png: bytes):
        super().__init__()
        self.engine = engine
        self.cutout_rgb = cutout_rgb
        self.cutout_png = cutout_png

    def _execute(self) -> object:
        self.status.emit("Resolving identity...")
        return self.engine.resolve(self.cutout_rgb, self.cutout_png)


class BatchSuggestWorker(BaseQThreadWorker):
    """Runs identity resolution over a dropped batch of images."""

    finished = Signal(list)  # list[dict], None on failure/cancel
    status = Signal(str)

    def __init__(self, engine: ReconEngine, paths: List[str]):
        super().__init__()
        self.engine = engine
        self.paths = paths

    def _execute(self) -> object:
        self.status.emit(f"Analyzing {len(self.paths)} images...")
        return self.engine.suggest_batch(self.paths)

"""Background worker for Scan & Tag's per-image metadata upsert (DB.6 P3b).

``QThread`` *subclass* overriding ``run()`` — the same pattern as
:class:`MergeWorker`/:class:`SimilarityScanWorker`, not ``QObject`` +
``moveToThread``. A plain ``moveToThread`` worker starts the default
per-thread event loop, which collides with the JPype JVM loaded in-process
(SIGSEGV — see project notes on this class of bug). Overriding ``run()``
means no event loop starts in the worker thread.

Only the per-image decode (width/height via ``QImage``, thread-safe — never
``QPixmap``, which is not) happens in this background thread. All database
writes are deferred back to the main thread (see ``ScanMetadataTab``'s
``finished`` handler), wrapped in one transaction instead of one
implicit commit per image — this, not the decode itself, was the dominant
cost on large batches.
"""
import logging
from typing import Any, Dict, List

from PySide6.QtCore import Signal
from PySide6.QtGui import QImage

from gui.src.helpers.base import BaseQThreadWorker

logger = logging.getLogger(__name__)

class UpsertWorker(BaseQThreadWorker):
    finished = Signal(list)  # prepared entries, ready for a single DB transaction

    def __init__(self, entries: List[Dict[str, Any]]):
        super().__init__()
        self.entries = entries

    def _execute(self) -> object:
        total = len(self.entries)
        prepared: List[Dict[str, Any]] = []
        for i, entry in enumerate(self.entries):
            if self._cancelled:
                return None
            path = entry["path"]
            width, height = None, None
            try:
                q_img = QImage(path)
                if not q_img.isNull():
                    width = q_img.width()
                    height = q_img.height()
            except Exception:
                logger.debug("Suppressed Exception in UpsertWorker._execute", exc_info=True)
            prepared.append(
                {
                    "path": path,
                    "group_name": entry.get("group_name"),
                    "subgroup_name": entry.get("subgroup_name"),
                    "tags": entry.get("tags"),
                    "width": width,
                    "height": height,
                }
            )
            self.progress.emit(i + 1, total)
        return prepared

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

from typing import Any, Dict, List

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from gui.src.helpers.gc_safe import gc_disabled_run


class UpsertWorker(QThread):
    progress = Signal(int, int)  # (current, total)
    sig_finished = Signal(list)  # prepared entries, ready for a single DB transaction
    error = Signal(str)

    def __init__(self, entries: List[Dict[str, Any]]):
        super().__init__()
        self.entries = entries
        self._should_stop = False

    def cancel(self) -> None:
        self._should_stop = True

    @gc_disabled_run
    def run(self):
        try:
            total = len(self.entries)
            prepared: List[Dict[str, Any]] = []
            for i, entry in enumerate(self.entries):
                if self._should_stop:
                    return
                path = entry["path"]
                width, height = None, None
                try:
                    q_img = QImage(path)
                    if not q_img.isNull():
                        width = q_img.width()
                        height = q_img.height()
                except Exception:
                    pass
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
            self.sig_finished.emit(prepared)
        except Exception as exc:
            self.error.emit(str(exc))

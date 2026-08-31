"""Background worker for DB.7's semantic-embedding backfill.

``QThread`` subclass overriding ``run()`` -- the same pattern as
:class:`UpsertWorker`/:class:`MergeWorker`/:class:`SimilarityScanWorker`,
not ``QObject`` + ``moveToThread`` (see ``upsert_worker.py``'s docstring
for why: a default per-thread event loop collides with the JPype JVM
loaded in-process).

Only embedding *computation* (``backend.src.core.similarity.embedder``,
torch releases the GIL during the forward pass) happens on this
background thread. The database write is deferred back to the main
thread via ``sig_finished`` -- the keyed ``base.database.Database``
handle is not safe to share across threads (DB.2's risk register: "repos
never share statements across threads").
"""

from typing import List, Tuple

from PySide6.QtCore import QThread, Signal

from gui.src.helpers.gc_safe import gc_disabled_run


class ImageEmbeddingWorker(QThread):
    progress = Signal(int, int)  # (current, total)
    sig_finished = Signal(list)  # [(image_id, model, vector), ...], ready for one transaction
    error = Signal(str)

    def __init__(self, items: List[Tuple[int, str]], model: str = "openclip"):
        """*items*: [(image_id, file_path), ...] -- e.g. from
        ``ImageRepo.list_unembedded()``."""
        super().__init__()
        self.items = items
        self.model = model
        self._should_stop = False

    def cancel(self) -> None:
        self._should_stop = True

    @gc_disabled_run
    def run(self):
        try:
            from backend.src.core.similarity.embedder import get_embedder

            embedder = get_embedder(self.model)
            if embedder is None:
                self.error.emit(
                    "No embedding backend available (open_clip/torch not "
                    "installed) -- semantic search backfill skipped."
                )
                return

            total = len(self.items)
            results: List[Tuple[int, str, object]] = []
            batch_size = 16
            id_by_path = {}
            for i in range(0, total, batch_size):
                if self._should_stop:
                    return
                chunk = self.items[i:i + batch_size]
                id_by_path.update({path: image_id for image_id, path in chunk})
                vectors = embedder.embed_batch([path for _, path in chunk])
                for path, vector in vectors.items():
                    results.append((id_by_path[path], embedder.name, vector))
                self.progress.emit(min(i + batch_size, total), total)

            self.sig_finished.emit(results)
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            try:
                from backend.src.core.similarity.embedder import unload_all

                unload_all()
            except Exception:
                pass

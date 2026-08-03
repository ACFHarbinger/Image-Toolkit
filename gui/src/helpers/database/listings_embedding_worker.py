"""Background worker for DB.7's listings semantic-embedding backfill
(media_items/entities), mirroring ``embedding_worker.py``'s
``ImageEmbeddingWorker`` exactly -- ``QThread`` subclass overriding
``run()``, not ``QObject`` + ``moveToThread`` (JPype-JVM-safe pattern).

Reuses the BGE-M3 ``Embedder`` already built and tested for the standalone
``Recommendation-Engine`` sub-project (``submodules/Recommendation-Engine/
src/data/embedder.py``) instead of loading a second copy of the model or
inventing a new embedding pathway -- same principle DB.7's image side used
(reusing the Similarity tab's existing open_clip embedder).
"""

from typing import List, Tuple

from PySide6.QtCore import QThread, Signal

from ...constants import RECOMMENDATION_ENGINE_DIR


def _ensure_re_on_path() -> None:
    import sys

    path = str(RECOMMENDATION_ENGINE_DIR)
    if path not in sys.path:
        sys.path.insert(0, path)


class ListingsEmbeddingWorker(QThread):
    """*owner_type*: "media_item" or "entity" -- selects which text-building
    function is used; *items*: [(id, text), ...], already composed by the
    caller (e.g. "{title}. {type}. {genres}. {review}" for a media item)."""

    progress = Signal(int, int)  # (current, total)
    sig_finished = Signal(list)  # [(owner_id, model, vector), ...], ready for one transaction
    error = Signal(str)

    MODEL = "bge-m3"

    def __init__(self, items: List[Tuple[str, str]]):
        super().__init__()
        self.items = items
        self._should_stop = False

    def cancel(self) -> None:
        self._should_stop = True

    def run(self):
        try:
            _ensure_re_on_path()
            try:
                from src.data.embedder import Embedder  # pyrefly: ignore [missing-import]
            except ImportError as exc:
                self.error.emit(
                    "BGE-M3 embedder unavailable (FlagEmbedding not "
                    f"installed, or Recommendation-Engine not present): {exc}"
                )
                return

            embedder = Embedder()
            total = len(self.items)
            results: List[Tuple[str, str, object]] = []
            for i, (owner_id, text) in enumerate(self.items):
                if self._should_stop:
                    return
                if text and text.strip():
                    vector = embedder.embed_dense(text)
                    results.append((owner_id, self.MODEL, vector))
                self.progress.emit(i + 1, total)

            self.sig_finished.emit(results)
        except Exception as exc:
            self.error.emit(str(exc))

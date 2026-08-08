"""Background worker for DB.7 listings semantic (BGE-M3) search --
text->media_item / text->entity. Mirrors ``semantic_search_worker.py``'s
``SemanticSearchWorker`` exactly (a short ``QRunnable`` on the global
``QThreadPool``, embed+query both happening off the GUI thread), but
against ``SearchRepo`` directly rather than the image-domain facade --
listings GUI code already constructs ``MediaRepo(db)``/``EntityRepo(db)``
directly (see e.g. ``series_listings_subtab``/``entity_listings_subtab``),
not through a facade, so this follows that same convention.
"""

from typing import List, Literal, Optional, Tuple

from gui.src.helpers.base import BaseQRunnableWorker

from ...constants import RECOMMENDATION_ENGINE_DIR


def _ensure_re_on_path() -> None:
    import sys

    path = str(RECOMMENDATION_ENGINE_DIR)
    if path not in sys.path:
        sys.path.insert(0, path)


class ListingsSemanticSearchWorker(BaseQRunnableWorker):
    MODEL = "bge-m3"

    def __init__(
        self,
        db,
        domain: Literal["media", "entity"],
        text: str,
        top_k: int = 50,
        type_filter: Optional[str] = None,
    ):
        super().__init__()
        self.db = db
        self.domain = domain
        self.text = text
        self.top_k = top_k
        self.type_filter = type_filter

    def _execute(self) -> None:
        _ensure_re_on_path()
        try:
            from src.data.embedder import Embedder  # pyrefly: ignore [missing-import]
        except ImportError as exc:
            self.signals.error.emit(
                "BGE-M3 embedder unavailable (FlagEmbedding not "
                f"installed, or CRE not present): {exc}"
            )
            return

        vector = Embedder().embed_dense(self.text)

        if self._cancelled:
            self.signals.cancelled.emit()
            return

        from backend.src.database.unified.search_repo import SearchRepo

        search = SearchRepo(self.db)
        hits: List[Tuple[str, float, str]]
        if self.domain == "media":
            hits = search.semantic_media_search(
                vector, top_k=self.top_k, model=self.MODEL,
                type_filter=self.type_filter,
            )
        else:
            hits = search.semantic_entity_search(
                vector, top_k=self.top_k, model=self.MODEL,
                type_filter=self.type_filter,
            )
        self.signals.finished.emit(hits)

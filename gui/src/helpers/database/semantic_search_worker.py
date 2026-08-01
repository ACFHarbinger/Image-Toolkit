"""Background worker for DB.7 semantic (CLIP) search -- text->image and
find-similar. Mirrors SearchWorker's own structured-search pattern exactly
(a short QRunnable dispatched on the global QThreadPool, embed+query both
happening off the GUI thread) rather than introducing a second pattern.

Note: the actual model used is whatever ``get_embedder()`` resolves to in
this process (graceful fallback mobileclip -> openclip -> resnet18) --
the same resolution the embedding-backfill worker
(``embedding_worker.py``, ``EMBED_MODEL = "openclip"``) goes through, so
within one environment the two stay consistent with each other even if
open_clip isn't installed and both silently fall back to resnet18 (no
text tower -- text search errors out cleanly in that case; find-similar
still works, just at lower embedding quality).
"""

from typing import List, Optional, Sequence, Tuple

from gui.src.helpers.base import BaseQRunnableWorker


class SemanticSearchWorker(BaseQRunnableWorker):
    def __init__(
        self,
        db,
        model: str = "openclip",
        text: Optional[str] = None,
        image_path: Optional[str] = None,
        top_k: int = 50,
        group_name: Optional[str] = None,
        subgroup_name: Optional[str] = None,
        tags: Optional[Sequence[str]] = None,
        input_formats: Optional[Sequence[str]] = None,
        exclude_image_id: Optional[int] = None,
    ):
        """Exactly one of *text*/*image_path* should be given -- text for
        a natural-language query, image_path for "find similar" (querying
        by that image's own embedding)."""
        super().__init__()
        self.db = db
        self.model = model
        self.text = text
        self.image_path = image_path
        self.top_k = top_k
        self.group_name = group_name
        self.subgroup_name = subgroup_name
        self.tags = tags
        self.input_formats = input_formats
        self.exclude_image_id = exclude_image_id

    def _execute(self) -> None:
        from backend.src.core.similarity.embedder import get_embedder

        embedder = get_embedder(self.model)
        if embedder is None:
            self.signals.error.emit(
                "No embedding backend available (open_clip/torch not "
                "installed) -- semantic search is unavailable."
            )
            return

        if self.text is not None:
            if not hasattr(embedder, "embed_text"):
                self.signals.error.emit(
                    f"'{embedder.name}' has no text tower -- semantic text "
                    "search is unavailable in this environment."
                )
                return
            vector = embedder.embed_text(self.text)
        else:
            vectors = embedder.embed_batch([self.image_path])
            vector = vectors.get(self.image_path)
            if vector is None:
                self.signals.error.emit(f"Could not embed {self.image_path}.")
                return

        if self._cancelled:
            self.signals.cancelled.emit()
            return

        fetch_k = self.top_k + (1 if self.exclude_image_id is not None else 0)
        hits: List[Tuple[int, float, str]] = self.db.semantic_image_search(
            vector, top_k=fetch_k, model=embedder.name,
            group_name=self.group_name, subgroup_name=self.subgroup_name,
            tags=self.tags, input_formats=self.input_formats,
        )
        if self.exclude_image_id is not None:
            hits = [h for h in hits if h[0] != self.exclude_image_id]
        self.signals.finished.emit(hits[: self.top_k])

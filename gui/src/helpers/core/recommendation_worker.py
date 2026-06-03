"""
QThread worker for content recommendations via BGE-M3 dense embeddings and local SQLCipher + sqlite-vec.
"""
import logging
from typing import Any, Dict, List, Tuple

from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)


class RecommendationWorker(QThread):
    """
    Generates recommendations using BGE-M3 dense embeddings and SQLCipher + sqlite-vec search.

    *inputs* dict keys (all optional):
      prompt   : str  – Natural language description for dense encoding
      type     : str  – Listing type for payload filter
      genres   : str  – Comma-separated genres for sparse encoding
      tags     : str  – Comma-separated tags for sparse encoding
      entities : str  – Comma-separated entity names for sparse encoding

    Emits ``finished`` with ``List[Tuple[str, float]]`` (UUID, score),
    ordered by descending relevance (higher score is more relevant).
    """

    finished = Signal(list)   # List[Tuple[str, float]]
    error = Signal(str)
    status = Signal(str)
    progress = Signal(int, int)  # current, total steps

    def __init__(
        self,
        db_path: str,
        password: str,
        salt: str,
        inputs: Dict[str, Any],
        top_k: int = 50,
        parent=None,
    ):
        super().__init__(parent)
        self._db_path = db_path
        self._password = password
        self._salt = salt
        self._inputs = inputs
        self._top_k = top_k

    def run(self) -> None:
        try:
            self.status.emit("Loading embedding model…")
            from backend.src.pipeline.vector_ingestion import get_or_load_model

            model = get_or_load_model()

            prompt = (self._inputs.get("prompt") or "").strip()
            type_filter = (self._inputs.get("type") or "").strip()
            genres_text = (self._inputs.get("genres") or "").strip()
            tags_text = (self._inputs.get("tags") or "").strip()
            entities_text = (self._inputs.get("entities") or "").strip()

            # Construct keyword text from structured fields
            kw_parts: List[str] = []
            if genres_text:
                kw_parts.append(f"Genres: {genres_text}")
            if tags_text:
                kw_parts.append(f"Tags: {tags_text}")
            if entities_text:
                kw_parts.append(f"Featuring: {entities_text}")
            keyword_text = ". ".join(kw_parts)

            has_prompt = bool(prompt)
            has_keywords = bool(keyword_text)

            if not has_prompt and not has_keywords:
                self.error.emit(
                    "Please enter a natural language prompt or at least one "
                    "keyword field (genres, tags, or entities)."
                )
                return

            self.status.emit("Generating query embeddings…")
            self.progress.emit(1, 3)

            # Standardize on dense embedding (since we use sqlite-vec which supports dense k-NN search)
            # Combine prompt and keyword text if both are present
            if has_prompt and has_keywords:
                search_text = f"{prompt}. {keyword_text}"
            elif has_prompt:
                search_text = prompt
            else:
                search_text = keyword_text

            dense_out = model.encode(
                [search_text],
                max_length=512,
                return_dense=True,
                return_sparse=False,
                return_colbert_vecs=False,
            )
            dense_vec: List[float] = dense_out["dense_vecs"][0].tolist()

            self.status.emit("Querying secure database…")
            self.progress.emit(2, 3)

            import base
            rows = base.hybrid_search_secure(
                self._db_path,
                self._password,
                self._salt,
                dense_vec,
                type_filter,
                self._top_k
            )

            # Map the rows from secure DB to results list: (id, score)
            # Normalize distance to a similarity score (higher is better)
            results = []
            for row in rows:
                id_, title, category, metadata, distance = row
                score = 1.0 / (1.0 + distance)
                results.append((id_, score))

            # Sort descending by score
            results.sort(key=lambda x: x[1], reverse=True)

            self.status.emit(f"Done — {len(results)} recommendations found.")
            self.progress.emit(3, 3)
            self.finished.emit(results)

        except Exception as exc:
            logger.exception("[RecommendationWorker] %s", exc)
            self.error.emit(str(exc))

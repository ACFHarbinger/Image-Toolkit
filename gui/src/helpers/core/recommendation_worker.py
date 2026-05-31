"""
QThread worker for content recommendations via BGE-M3 dense + sparse + RRF.

Search strategy:
  - Natural language prompt only   → dense k-NN
  - Keyword fields only            → sparse k-NN
  - Both present                   → dense + sparse with Reciprocal Rank Fusion
"""
import logging
from typing import Any, Dict, List, Tuple

from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)


class RecommendationWorker(QThread):
    """
    Generates recommendations using BGE-M3 embeddings and Qdrant search.

    *inputs* dict keys (all optional):
      prompt   : str  – Natural language description for dense encoding
      type     : str  – Listing type for payload filter
      genres   : str  – Comma-separated genres for sparse encoding
      tags     : str  – Comma-separated tags for sparse encoding
      entities : str  – Comma-separated entity names for sparse encoding

    Emits ``finished`` with ``List[Tuple[str, float]]`` (UUID, score),
    ordered by descending relevance.
    """

    finished = Signal(list)   # List[Tuple[str, float]]
    error = Signal(str)
    status = Signal(str)
    progress = Signal(int, int)  # current, total steps

    def __init__(
        self,
        qdrant_manager,
        inputs: Dict[str, Any],
        top_k: int = 50,
        parent=None,
    ):
        super().__init__(parent)
        self._qdrant = qdrant_manager
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

            # Construct keyword text for sparse encoding from structured fields
            kw_parts: List[str] = []
            if genres_text:
                kw_parts.append(f"Genres: {genres_text}")
            if tags_text:
                kw_parts.append(f"Tags: {tags_text}")
            if entities_text:
                kw_parts.append(f"Featuring: {entities_text}")
            keyword_text = ". ".join(kw_parts)

            # Qdrant filter from type dropdown
            criteria: Dict[str, Any] = {}
            if type_filter and type_filter not in ("All", "All Types", ""):
                criteria["type"] = type_filter
            filt = self._qdrant.build_filter(criteria) if criteria else None

            has_prompt = bool(prompt)
            has_keywords = bool(keyword_text)

            if not has_prompt and not has_keywords:
                self.error.emit(
                    "Please enter a natural language prompt or at least one "
                    "keyword field (genres, tags, or entities)."
                )
                return

            results: List[Tuple[str, float]] = []

            if has_prompt and has_keywords:
                # Hybrid: dense semantic + sparse lexical, fused with RRF
                self.status.emit("Embedding prompt…")
                self.progress.emit(1, 4)
                dense_out = model.encode(
                    [prompt],
                    max_length=512,
                    return_dense=True,
                    return_sparse=False,
                    return_colbert_vecs=False,
                )
                dense_vec: List[float] = dense_out["dense_vecs"][0].tolist()

                self.status.emit("Embedding keywords…")
                self.progress.emit(2, 4)
                sparse_out = model.encode(
                    [keyword_text],
                    max_length=256,
                    return_dense=False,
                    return_sparse=True,
                    return_colbert_vecs=False,
                )
                sw = sparse_out["lexical_weights"][0]
                indices = [int(k) for k in sw.keys()]
                values = [float(v) for v in sw.values()]

                self.status.emit("Running hybrid search (RRF)…")
                self.progress.emit(3, 4)
                results = self._qdrant.hybrid_search_rrf(
                    dense_vec, indices, values, filt=filt, limit=self._top_k
                )

            elif has_prompt:
                # Dense-only semantic search
                self.status.emit("Embedding prompt…")
                self.progress.emit(1, 2)
                dense_out = model.encode(
                    [prompt],
                    max_length=512,
                    return_dense=True,
                    return_sparse=False,
                    return_colbert_vecs=False,
                )
                dense_vec = dense_out["dense_vecs"][0].tolist()

                self.status.emit("Running semantic search…")
                self.progress.emit(2, 2)
                results = self._qdrant.search_dense(
                    dense_vec, filt=filt, limit=self._top_k
                )

            else:
                # Sparse-only keyword search
                self.status.emit("Embedding keywords…")
                self.progress.emit(1, 2)
                sparse_out = model.encode(
                    [keyword_text],
                    max_length=256,
                    return_dense=False,
                    return_sparse=True,
                    return_colbert_vecs=False,
                )
                sw = sparse_out["lexical_weights"][0]
                indices = [int(k) for k in sw.keys()]
                values = [float(v) for v in sw.values()]

                self.status.emit("Running keyword search…")
                self.progress.emit(2, 2)
                results = self._qdrant.search_sparse(
                    indices, values, filt=filt, limit=self._top_k
                )

            self.status.emit(f"Done — {len(results)} recommendations found.")
            self.progress.emit(4, 4)
            self.finished.emit(results)

        except Exception as exc:
            logger.exception("[RecommendationWorker] %s", exc)
            self.error.emit(str(exc))

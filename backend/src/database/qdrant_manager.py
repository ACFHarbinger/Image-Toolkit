"""
Local Qdrant vector store manager for listings search and recommendations.
Supports BGE-M3 dense (semantic) and sparse (lexical) multi-vector search.
"""

import logging
import time
from typing import Any, Dict, List, Optional, Tuple
from backend.src.constants import COLLECTION_NAME, DENSE_DIM

logger = logging.getLogger(__name__)


class QdrantManager:
    """
    Wraps a local Qdrant instance with multi-vector support (dense + sparse).

    Collections use two named vectors:
      "dense"  – 1024-dim cosine for semantic search
      "sparse" – BGE-M3 lexical weights for keyword search

    Call connect() before any search or upsert operation.
    """

    def __init__(self, storage_path: Optional[str] = None):
        self._storage_path = storage_path
        self._client = None
        self._ready = False

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def connect(self) -> bool:
        """Connect to Qdrant and ensure the listings collection exists."""
        try:
            from qdrant_client import QdrantClient
        except ImportError:
            logger.error(
                "[QdrantManager] qdrant-client not installed. "
                "Run: pip install 'qdrant-client>=1.9.0'"
            )
            return False

        try:
            t0 = time.perf_counter()
            if self._storage_path:
                self._client = QdrantClient(path=self._storage_path)
            else:
                self._client = QdrantClient(":memory:")
            elapsed = time.perf_counter() - t0
            logger.info(
                "[QdrantManager] Connected in %.2fs (storage=%r)",
                elapsed,
                self._storage_path,
            )
            self._ensure_collection()
            self._ready = True
            return True
        except Exception as exc:
            logger.error("[QdrantManager] Connection failed: %s", exc)
            return False

    @property
    def is_ready(self) -> bool:
        return self._ready and self._client is not None

    def collection_count(self) -> int:
        if not self.is_ready:
            return 0
        try:
            info = self._client.get_collection(COLLECTION_NAME)
            return info.points_count or 0
        except Exception:
            return 0

    def _ensure_collection(self) -> None:
        from qdrant_client.models import (
            Distance,
            SparseIndexParams,
            SparseVectorParams,
            VectorParams,
        )

        existing = {c.name for c in self._client.get_collections().collections}
        if COLLECTION_NAME not in existing:
            self._client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config={
                    "dense": VectorParams(size=DENSE_DIM, distance=Distance.COSINE)
                },
                sparse_vectors_config={
                    "sparse": SparseVectorParams(index=SparseIndexParams(on_disk=False))
                },
            )
            logger.info("[QdrantManager] Created collection '%s'", COLLECTION_NAME)

    # ------------------------------------------------------------------
    # Upsertion
    # ------------------------------------------------------------------

    def upsert_batch(self, points: List[Dict[str, Any]]) -> bool:
        """
        Upsert a batch of points.

        Each dict must contain:
          id              : str (UUID of listing)
          dense           : List[float]  (1024-dim dense vector)
          sparse_indices  : List[int]
          sparse_values   : List[float]
          payload         : Dict[str, Any]  (listing metadata for filtering)
        """
        if not self.is_ready:
            return False
        try:
            from qdrant_client.models import PointStruct, SparseVector

            structs = [
                PointStruct(
                    id=p["id"],
                    vector={
                        "dense": p["dense"],
                        "sparse": SparseVector(
                            indices=p["sparse_indices"],
                            values=p["sparse_values"],
                        ),
                    },
                    payload=p["payload"],
                )
                for p in points
            ]
            self._client.upsert(collection_name=COLLECTION_NAME, points=structs)
            logger.debug("[QdrantManager] Upserted %d points", len(structs))
            return True
        except Exception as exc:
            logger.error("[QdrantManager] Upsert failed: %s", exc)
            return False

    def delete_point(self, listing_id: str) -> bool:
        """Remove a single point by listing UUID."""
        if not self.is_ready:
            return False
        try:
            from qdrant_client.models import PointIdsList

            self._client.delete(
                collection_name=COLLECTION_NAME,
                points_selector=PointIdsList(points=[listing_id]),
            )
            return True
        except Exception as exc:
            logger.error("[QdrantManager] Delete failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search_sparse(
        self,
        indices: List[int],
        values: List[float],
        filt=None,
        limit: int = 100,
    ) -> List[Tuple[str, float]]:
        """Lexical (sparse) search using BGE-M3 token weights."""
        if not self.is_ready:
            return []
        try:
            from qdrant_client.models import NamedSparseVector, SparseVector

            results = self._client.search(
                collection_name=COLLECTION_NAME,
                query_vector=NamedSparseVector(
                    name="sparse",
                    vector=SparseVector(indices=indices, values=values),
                ),
                query_filter=filt,
                limit=limit,
                with_payload=True,
            )
            return [(str(r.payload.get("id", r.id)), r.score) for r in results]
        except Exception as exc:
            logger.error("[QdrantManager] Sparse search failed: %s", exc)
            return []

    def search_dense(
        self,
        dense_vec: List[float],
        filt=None,
        limit: int = 50,
    ) -> List[Tuple[str, float]]:
        """Semantic (dense) search using BGE-M3 dense embeddings."""
        if not self.is_ready:
            return []
        try:
            from qdrant_client.models import NamedVector

            results = self._client.search(
                collection_name=COLLECTION_NAME,
                query_vector=NamedVector(name="dense", vector=dense_vec),
                query_filter=filt,
                limit=limit,
                with_payload=True,
            )
            return [(str(r.payload.get("id", r.id)), r.score) for r in results]
        except Exception as exc:
            logger.error("[QdrantManager] Dense search failed: %s", exc)
            return []

    def hybrid_search_rrf(
        self,
        dense_vec: List[float],
        sparse_indices: List[int],
        sparse_values: List[float],
        filt=None,
        limit: int = 50,
        rrf_k: int = 60,
    ) -> List[Tuple[str, float]]:
        """
        Dense + sparse search fused with Reciprocal Rank Fusion (RRF).

        Fetches limit×3 candidates from each branch, then scores with:
            rrf_score(rank) = 1 / (rrf_k + rank + 1)
        and returns the top-limit entries by combined score.
        """
        fetch = min(limit * 3, 200)
        dense_hits = self.search_dense(dense_vec, filt, fetch)
        sparse_hits = self.search_sparse(sparse_indices, sparse_values, filt, fetch)

        scores: Dict[str, float] = {}
        for rank, (uid, _) in enumerate(dense_hits):
            scores[uid] = scores.get(uid, 0.0) + 1.0 / (rrf_k + rank + 1)
        for rank, (uid, _) in enumerate(sparse_hits):
            scores[uid] = scores.get(uid, 0.0) + 1.0 / (rrf_k + rank + 1)

        fused = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return fused[:limit]

    # ------------------------------------------------------------------
    # Filter Builder
    # ------------------------------------------------------------------

    def build_filter(self, criteria: Dict[str, Any]):
        """
        Build a Qdrant Filter from a criteria dict.

        Recognised keys:
          type   : str  → exact match on payload["type"]
          status : str  → exact match on payload["watch_status"]
          year   : int  → range filter on payload["year_released"]
        """
        from qdrant_client.models import FieldCondition, Filter, MatchValue, Range

        must: List[Any] = []

        type_val = criteria.get("type", "")
        if type_val and type_val not in ("All", "All Types", ""):
            must.append(FieldCondition(key="type", match=MatchValue(value=type_val)))

        status_val = criteria.get("status", "")
        if status_val and status_val not in ("All", "All Status", ""):
            must.append(
                FieldCondition(key="watch_status", match=MatchValue(value=status_val))
            )

        year_val = criteria.get("year")
        if year_val:
            try:
                yr = int(year_val)
                must.append(
                    FieldCondition(
                        key="year_released",
                        range=Range(gte=yr, lte=yr),
                    )
                )
            except (ValueError, TypeError):
                pass

        return Filter(must=must) if must else None

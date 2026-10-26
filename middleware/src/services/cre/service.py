"""Content Recommendation Engine (CRE) service implementation.

Canonical service home for CRE hybrid retrieval, ranking, and recommendations
(W0-03 Phase C, #867).
"""

from __future__ import annotations

import time
from typing import Any

from middleware.src.services.base import CommandValidationError
from middleware.src.services.cre.commands import (
    IndexMediaItemCommand,
    IndexMediaItemResult,
    RecommendationItem,
    RecommendCommand,
    RecommendResult,
)
from middleware.src.services.cre.protocols import CreServiceProtocol


class CreService(CreServiceProtocol):
    """Canonical domain service for content recommendation and hybrid search."""

    def __init__(self, pipeline: Any = None, store: Any = None) -> None:
        """Initialize CreService with optional pipeline or store delegate."""
        self._pipeline = pipeline
        self._store = store

    def _get_pipeline(self) -> Any:
        if self._pipeline is not None:
            return self._pipeline
        try:
            from middleware.src.cre.search.pipeline import RecommendationPipeline

            self._pipeline = RecommendationPipeline(top_k=10, use_reranker=False, explain=False)
            return self._pipeline
        except (ImportError, Exception):
            return None

    def recommend(self, command: RecommendCommand) -> RecommendResult:
        """Execute recommendation query using hybrid retrieval and scoring."""
        t0 = time.monotonic()
        if not command.query.strip():
            raise CommandValidationError("Query string must not be empty", field="query")

        try:
            pipeline = self._get_pipeline()
            items: list[RecommendationItem] = []

            if pipeline is not None and hasattr(pipeline, "run"):
                raw_results = pipeline.run(
                    query=command.query,
                    user_id=command.user_id,
                )
                for res in (raw_results or [])[: command.top_k]:
                    item_id = getattr(res, "item_id", "") or str(getattr(res, "id", ""))
                    title = getattr(res, "title", "") or "Untitled"
                    media_type = getattr(res, "media_type", "other")
                    score = float(getattr(res, "score", 0.0) or 0.0)
                    explanation = getattr(res, "explanation", None)
                    items.append(
                        RecommendationItem(
                            item_id=item_id,
                            title=title,
                            media_type=str(media_type),
                            score=score,
                            explanation=explanation,
                        )
                    )

            elapsed = round(time.monotonic() - t0, 4)
            return RecommendResult(
                success=True,
                items=tuple(items),
                total_found=len(items),
                elapsed_seconds=elapsed,
            )
        except Exception as exc:
            return RecommendResult(
                success=False,
                elapsed_seconds=round(time.monotonic() - t0, 4),
                error=str(exc),
            )

    def index_item(self, command: IndexMediaItemCommand) -> IndexMediaItemResult:
        """Index a media item into the vector and metadata store."""
        if not command.item_id.strip():
            raise CommandValidationError("item_id must not be empty", field="item_id")
        if not command.title.strip():
            raise CommandValidationError("title must not be empty", field="title")

        try:
            if self._store is not None and hasattr(self._store, "insert_item"):
                self._store.insert_item(
                    item_id=command.item_id,
                    title=command.title,
                    media_type=command.media_type,
                    description=command.description,
                    tags=command.tags,
                )
            return IndexMediaItemResult(
                success=True,
                item_id=command.item_id,
            )
        except Exception as exc:
            return IndexMediaItemResult(
                success=False,
                item_id=command.item_id,
                error=str(exc),
            )

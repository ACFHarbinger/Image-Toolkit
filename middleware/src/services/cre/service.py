"""Content Recommendation Engine (CRE) service implementation.

Canonical service home for CRE hybrid retrieval, ranking, and recommendations
(W0-03 Phase C, #867).
"""

from __future__ import annotations

import hashlib
import os
import sys
import time
from pathlib import Path
from typing import Any

from middleware.src.services._submodule_loader import ensure_submodules_registered
from middleware.src.services.base import CommandValidationError
from middleware.src.services.cre.commands import (
    IndexMediaItemCommand,
    IndexMediaItemResult,
    RecommendationItem,
    RecommendCommand,
    RecommendResult,
)
from middleware.src.services.cre.protocols import CreServiceProtocol

_CRE_SYMBOLS: tuple[Any, Any, Any, Any] | None = None


def _local_embedding(title: str, description: str) -> tuple[list[float], list[int], list[float]]:
    """Hash title and description locally so indexing never loads the CRE embedder."""
    digest = hashlib.sha256(f"{title}\0{description}".encode()).digest()
    dense = [byte / 255.0 for byte in digest[:16]]
    sparse_indices = [int(byte) for byte in digest[16:24]]
    sparse_values = [byte / 255.0 for byte in digest[24:32]]
    return dense, sparse_indices, sparse_values


def _cre_repo_src() -> Path:
    return Path(__file__).resolve().parents[4] / "submodules" / "CRE" / "src"


def _cre_store_symbols() -> tuple[Any, Any, Any, Any]:
    """Import CRE Settings, MediaItem, EmbeddedItem, and SQLiteStore.

    Pytest binds ``src`` to ``middleware/src``. CRE lives on that package's
    ``__path__`` so ``src.data`` and ``src.core.config`` still resolve.
    """
    global _CRE_SYMBOLS
    if _CRE_SYMBOLS is not None:
        return _CRE_SYMBOLS

    cre_src = _cre_repo_src()
    if not cre_src.is_dir():
        raise ImportError("CRE source unavailable")

    if "src" not in sys.modules:
        sys.path.insert(0, str(cre_src.parent))

    import src

    cre_src_text = str(cre_src)
    if cre_src_text not in src.__path__:
        src.__path__.append(cre_src_text)

    import src.core as core

    cre_core = str(cre_src / "core")
    if cre_core not in core.__path__:
        core.__path__.append(cre_core)

    from src.core.config import Settings
    from src.core.schema import EmbeddedItem, MediaItem
    from src.data.store import SQLiteStore

    _CRE_SYMBOLS = (Settings, MediaItem, EmbeddedItem, SQLiteStore)
    return _CRE_SYMBOLS


def _row_has_id(row: Any, item_id: str) -> bool:
    if row == item_id:
        return True
    if isinstance(row, dict):
        return row.get("id") == item_id
    try:
        return row["id"] == item_id
    except (KeyError, TypeError, IndexError):
        return False


class CreService(CreServiceProtocol):
    """Canonical domain service for content recommendation and hybrid search."""

    def __init__(self, pipeline: Any = None, store: Any = None) -> None:
        """Initialize CreService with optional pipeline or store delegate."""
        self._pipeline = pipeline
        self._store = store
        ensure_submodules_registered()

    def _get_pipeline(self) -> Any:
        if self._pipeline is not None:
            return self._pipeline
        try:
            from src.search.pipeline import RecommendationPipeline

            self._pipeline = RecommendationPipeline(top_k=10, use_reranker=False, explain=False)
            return self._pipeline
        except Exception:
            return None

    def _open_store(self) -> Any:
        settings_cls, _media_item, _embedded_item, store_cls = _cre_store_symbols()
        sqlite_path = os.environ.get("SQLITE_PATH")
        if not sqlite_path:
            from middleware.src.constants.paths import IMAGE_TOOLKIT_DIR

            sqlite_path = str(Path(IMAGE_TOOLKIT_DIR) / "cre" / "rec_engine.db")
        store = store_cls(settings_cls(sqlite_path=sqlite_path))
        store.create_collection()
        self._store = store
        return store

    def recommend(self, command: RecommendCommand) -> RecommendResult:
        """Execute recommendation query using hybrid retrieval and scoring."""
        t0 = time.monotonic()
        if not command.query.strip():
            raise CommandValidationError("Query string must not be empty", field="query")

        try:
            pipeline = self._get_pipeline()
            if pipeline is None:
                return RecommendResult(
                    success=False,
                    elapsed_seconds=round(time.monotonic() - t0, 4),
                    error="recommendation pipeline unavailable",
                )

            raw_results = pipeline.run(command.query)
            items: list[RecommendationItem] = []
            for res in list(raw_results)[: command.top_k]:
                item = res.item
                score = float(res.recommendation_value)
                reasons = res.reasons
                if isinstance(reasons, list) and reasons:
                    explanation: str | None = "; ".join(reasons)
                else:
                    explanation = None
                items.append(
                    RecommendationItem(
                        item_id=item.id,
                        title=item.title,
                        media_type=str(item.type or "other"),
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
            store = self._store
            if store is None:
                try:
                    store = self._open_store()
                except Exception as exc:
                    return IndexMediaItemResult(
                        success=False,
                        item_id=command.item_id,
                        error=f"recommendation store unavailable: {exc}",
                    )

            try:
                upsert = store.upsert
                fetch_all = store.fetch_all
            except AttributeError:
                return IndexMediaItemResult(
                    success=False,
                    item_id=command.item_id,
                    error="recommendation store upsert unavailable",
                )
            if not callable(upsert) or not callable(fetch_all):
                return IndexMediaItemResult(
                    success=False,
                    item_id=command.item_id,
                    error="recommendation store upsert unavailable",
                )

            _settings, media_cls, embedded_cls, _store_cls = _cre_store_symbols()
            dense, sparse_indices, sparse_values = _local_embedding(command.title, command.description)
            embedded = embedded_cls(
                item=media_cls(
                    id=command.item_id,
                    title=command.title,
                    type=command.media_type,
                    tags=list(command.tags),
                    review_notes=command.description or None,
                ),
                dense_vector=dense,
                sparse_indices=sparse_indices,
                sparse_values=sparse_values,
            )
            count = upsert([embedded])
            if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
                return IndexMediaItemResult(
                    success=False,
                    item_id=command.item_id,
                    error="upsert did not persist the item",
                )
            rows = fetch_all("id = ?", [command.item_id])
            if not rows or not any(_row_has_id(row, command.item_id) for row in rows):
                return IndexMediaItemResult(
                    success=False,
                    item_id=command.item_id,
                    error="indexed item was not returned by fetch",
                )
            return IndexMediaItemResult(success=True, item_id=command.item_id)
        except Exception as exc:
            return IndexMediaItemResult(
                success=False,
                item_id=command.item_id,
                error=str(exc),
            )

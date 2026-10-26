"""Commands and results for the Content Recommendation Engine (CRE) service.

Defines immutable frozen dataclasses for recommendation search and item
indexing operations (W0-03 Phase C, #867).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from middleware.src.services.base import Command, Result


@dataclass(frozen=True)
class RecommendationItem:
    """A scored and optionally explained recommendation result item."""

    item_id: str
    title: str
    media_type: str
    score: float
    explanation: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RecommendCommand(Command):
    """Command to execute a semantic hybrid recommendation query."""

    query: str
    user_id: str | None = None
    top_k: int = 10
    media_types: tuple[str, ...] = ()
    explain: bool = False
    use_reranker: bool = False


@dataclass(frozen=True)
class RecommendResult(Result):
    """Result of a recommendation query."""

    success: bool
    items: tuple[RecommendationItem, ...] = ()
    total_found: int = 0
    elapsed_seconds: float = 0.0
    error: str | None = None


@dataclass(frozen=True)
class IndexMediaItemCommand(Command):
    """Command to index a media item into the recommendation store."""

    item_id: str
    title: str
    media_type: str = "other"
    description: str = ""
    tags: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IndexMediaItemResult(Result):
    """Result of indexing a media item."""

    success: bool
    item_id: str
    error: str | None = None

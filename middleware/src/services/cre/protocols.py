"""Protocols for the Content Recommendation Engine (CRE) service.

Runtime-checkable protocol defining the boundary for media recommendation
and search indexing (W0-03 Phase C, #867).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from middleware.src.services.base import ServiceProtocol
from middleware.src.services.cre.commands import (
    IndexMediaItemCommand,
    IndexMediaItemResult,
    RecommendCommand,
    RecommendResult,
)


@runtime_checkable
class CreServiceProtocol(ServiceProtocol, Protocol):
    """Protocol for semantic recommendation and retrieval services."""

    def recommend(self, command: RecommendCommand) -> RecommendResult:
        """Execute recommendation query using hybrid retrieval and scoring."""
        ...

    def index_item(self, command: IndexMediaItemCommand) -> IndexMediaItemResult:
        """Index a media item into the vector and metadata store."""
        ...

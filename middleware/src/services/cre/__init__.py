"""Content Recommendation Engine (CRE) domain service package (W0-03 Phase C, #867)."""

from __future__ import annotations

from middleware.src.services.cre.commands import (
    IndexMediaItemCommand,
    IndexMediaItemResult,
    RecommendationItem,
    RecommendCommand,
    RecommendResult,
)
from middleware.src.services.cre.protocols import CreServiceProtocol
from middleware.src.services.cre.service import CreService

__all__ = [
    "CreService",
    "CreServiceProtocol",
    "IndexMediaItemCommand",
    "IndexMediaItemResult",
    "RecommendCommand",
    "RecommendResult",
    "RecommendationItem",
]

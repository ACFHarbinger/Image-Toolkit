"""Anime Stitch Pipeline (ASP) domain service package (W0-03 Phase C, #867)."""

from __future__ import annotations

from middleware.src.services.asp.commands import (
    MatchFramesCommand,
    MatchFramesResult,
    RenderCanvasCommand,
    RenderCanvasResult,
    StitchCommand,
    StitchResult,
)
from middleware.src.services.asp.handoff import (
    HANDOFF_KIND,
    AspHybridHandoff,
    HandoffContractError,
    PairHomography,
    build_hybrid_handoff,
    handoff_from_session,
    handoff_summary,
    hybrid_handoff_payload,
)
from middleware.src.services.asp.protocols import StitchServiceProtocol
from middleware.src.services.asp.service import StitchService

__all__ = [
    "HANDOFF_KIND",
    "AspHybridHandoff",
    "HandoffContractError",
    "MatchFramesCommand",
    "MatchFramesResult",
    "PairHomography",
    "RenderCanvasCommand",
    "RenderCanvasResult",
    "StitchCommand",
    "StitchResult",
    "StitchService",
    "StitchServiceProtocol",
    "build_hybrid_handoff",
    "handoff_from_session",
    "handoff_summary",
    "hybrid_handoff_payload",
]

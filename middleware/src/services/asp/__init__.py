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
from middleware.src.services.asp.protocols import StitchServiceProtocol
from middleware.src.services.asp.service import StitchService

__all__ = [
    "MatchFramesCommand",
    "MatchFramesResult",
    "RenderCanvasCommand",
    "RenderCanvasResult",
    "StitchCommand",
    "StitchResult",
    "StitchService",
    "StitchServiceProtocol",
]

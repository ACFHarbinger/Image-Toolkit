"""Protocols for the Anime Stitch Pipeline (ASP) service.

Runtime-checkable protocol defining the boundary for stitching operations
(W0-03 Phase C, #867).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from middleware.src.services.asp.commands import (
    MatchFramesCommand,
    MatchFramesResult,
    RenderCanvasCommand,
    RenderCanvasResult,
    StitchCommand,
    StitchResult,
)
from middleware.src.services.base import ServiceProtocol


@runtime_checkable
class StitchServiceProtocol(ServiceProtocol, Protocol):
    """Protocol for image sequence stitching and frame alignment services."""

    def stitch(self, command: StitchCommand) -> StitchResult:
        """Execute full anime stitching pipeline across frame sequence."""
        ...

    def match_frames(self, command: MatchFramesCommand) -> MatchFramesResult:
        """Match two frames and compute alignment transform."""
        ...

    def render_canvas(self, command: RenderCanvasCommand) -> RenderCanvasResult:
        """Render aligned frames onto a composited canvas."""
        ...

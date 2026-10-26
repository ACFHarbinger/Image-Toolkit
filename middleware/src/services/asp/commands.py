"""Commands and results for the Anime Stitch Pipeline (ASP) service.

Defines immutable frozen dataclasses for stitching, frame matching,
and canvas rendering operations (W0-03 Phase C, #867).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from middleware.src.services.base import Command, Result


@dataclass(frozen=True)
class StitchCommand(Command):
    """Command to execute an end-to-end multi-frame stitch pipeline."""

    image_paths: tuple[str, ...]
    output_path: str | None = None
    motion_model: str = "affine"
    renderer: str = "multiband"
    matcher: str = "auto"
    crop_output: bool = True
    photometric_correction: bool = True
    composite_foreground: bool = False


@dataclass(frozen=True)
class StitchResult(Result):
    """Result of an end-to-end stitch operation."""

    success: bool
    output_path: str | None = None
    canvas_width: int = 0
    canvas_height: int = 0
    num_frames: int = 0
    seam_count: int = 0
    elapsed_seconds: float = 0.0
    metrics: dict[str, float] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class MatchFramesCommand(Command):
    """Command to match two frames and determine pairwise alignment."""

    image_path_1: str
    image_path_2: str
    matcher: str = "auto"


@dataclass(frozen=True)
class MatchFramesResult(Result):
    """Pairwise frame matching and transform alignment result."""

    success: bool
    inlier_count: int = 0
    transform_matrix: tuple[tuple[float, ...], ...] | None = None
    confidence: float = 0.0
    elapsed_seconds: float = 0.0
    error: str | None = None


@dataclass(frozen=True)
class RenderCanvasCommand(Command):
    """Command to render/composite aligned frames onto a destination canvas."""

    image_paths: tuple[str, ...]
    transforms: tuple[tuple[tuple[float, ...], ...], ...] = ()
    renderer: str = "multiband"
    output_path: str | None = None


@dataclass(frozen=True)
class RenderCanvasResult(Result):
    """Result of canvas rendering/compositing operation."""

    success: bool
    output_path: str | None = None
    canvas_width: int = 0
    canvas_height: int = 0
    elapsed_seconds: float = 0.0
    error: str | None = None

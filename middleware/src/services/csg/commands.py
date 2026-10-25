"""Commands and results for the Cel-Shaded Generator (CSG) service.

Defines immutable frozen dataclasses for colorization, ARAP puppeteering,
and temporal animation propagation operations (W0-03 Phase C, #867).
"""

from __future__ import annotations

from dataclasses import dataclass

from middleware.src.services.base import Command, Result


@dataclass(frozen=True)
class ColorizeScribbleCommand(Command):
    """Command to colorize lineart given user color scribbles."""

    lineart_path: str
    scribble_path: str
    output_path: str | None = None
    intensity: float = 1.0
    use_screentone: bool = False


@dataclass(frozen=True)
class ColorizeScribbleResult(Result):
    """Result of scribble-based colorization."""

    success: bool
    output_path: str | None = None
    width: int = 0
    height: int = 0
    elapsed_seconds: float = 0.0
    error: str | None = None


@dataclass(frozen=True)
class ColorizeReferenceCommand(Command):
    """Command to transfer color from a reference style image to lineart."""

    lineart_path: str
    reference_path: str
    output_path: str | None = None
    epsilon: float = 0.01
    max_iter: int = 100


@dataclass(frozen=True)
class ColorizeReferenceResult(Result):
    """Result of reference-based color transfer."""

    success: bool
    output_path: str | None = None
    width: int = 0
    height: int = 0
    elapsed_seconds: float = 0.0
    error: str | None = None


@dataclass(frozen=True)
class ArapDeformCommand(Command):
    """Command to deform a 2D character sprite using ARAP mesh rigging."""

    image_path: str
    control_points: tuple[tuple[float, float], ...]
    target_points: tuple[tuple[float, float], ...]
    output_path: str | None = None
    mesh_resolution: int = 32


@dataclass(frozen=True)
class ArapDeformResult(Result):
    """Result of ARAP deformation operation."""

    success: bool
    output_path: str | None = None
    num_vertices: int = 0
    num_triangles: int = 0
    elapsed_seconds: float = 0.0
    error: str | None = None


@dataclass(frozen=True)
class TemporalPropagateCommand(Command):
    """Command to propagate colorization temporally across animation frames."""

    frame_paths: tuple[str, ...]
    keyframe_index: int = 0
    keyframe_color_path: str = ""
    output_dir: str | None = None


@dataclass(frozen=True)
class TemporalPropagateResult(Result):
    """Result of temporal animation color propagation."""

    success: bool
    output_paths: tuple[str, ...] = ()
    frames_processed: int = 0
    elapsed_seconds: float = 0.0
    error: str | None = None

"""Stitch service implementation conforming to StitchServiceProtocol.

Canonical service home for Anime Stitch Pipeline (ASP) orchestration
(W0-03 Phase C, #867). Unblocks Wave 8 editor #914 E-01.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import numpy as np

from middleware.src.services._submodule_loader import ensure_submodules_registered
from middleware.src.services.asp.commands import (
    MatchFramesCommand,
    MatchFramesResult,
    RenderCanvasCommand,
    RenderCanvasResult,
    StitchCommand,
    StitchResult,
)
from middleware.src.services.asp.protocols import StitchServiceProtocol
from middleware.src.services.base import CommandValidationError

_IDENTITY_AFFINE = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0))


def _elapsed(t0: float) -> float:
    return round(time.monotonic() - t0, 4)


def _affine_2x3(transform: Any) -> np.ndarray:
    """Copy a caller-supplied transform into a 2×3 float64 affine."""
    import numpy as np

    matrix = np.asarray(transform, dtype=np.float64)
    if matrix.shape != (2, 3):
        raise ValueError(f"affine transform must be 2x3, got shape {matrix.shape}")
    return np.ascontiguousarray(matrix, dtype=np.float64)


def _overlap_count(img1: np.ndarray, img2: np.ndarray, matrix: np.ndarray) -> int:
    """Count img1 pixels that land on img2 after the pairwise warp."""
    import cv2
    import numpy as np

    height, width = img2.shape[:2]
    warped = cv2.warpAffine(img1, np.ascontiguousarray(matrix, dtype=np.float64), (width, height))
    if warped.ndim == 3:
        return int(np.count_nonzero(np.any(warped != 0, axis=-1)))
    return int(np.count_nonzero(warped))


class StitchService(StitchServiceProtocol):
    """Canonical domain service for anime frame stitching and alignment."""

    def __init__(self, pipeline_factory: Any = None) -> None:
        """Initialize StitchService with optional pipeline factory or delegate."""
        self._pipeline_factory = pipeline_factory
        ensure_submodules_registered()

    def _get_pipeline(self, **kwargs: Any) -> Any:
        if self._pipeline_factory is not None:
            return self._pipeline_factory(**kwargs)
        try:
            from asp_backend import AnimeStitchPipeline

            return AnimeStitchPipeline(**kwargs)
        except (ImportError, Exception):
            return None

    def stitch(self, command: StitchCommand) -> StitchResult:
        """Execute stitching pipeline across image sequence."""
        t0 = time.monotonic()
        if not command.image_paths or len(command.image_paths) < 2:
            raise CommandValidationError(
                "Stitching requires at least two image paths", field="image_paths"
            )

        for p in command.image_paths:
            if not os.path.isfile(p):
                return StitchResult(
                    success=False,
                    num_frames=len(command.image_paths),
                    elapsed_seconds=round(time.monotonic() - t0, 4),
                    error=f"Image file does not exist: {p}",
                )

        try:
            pipeline = self._get_pipeline(
                motion_model=command.motion_model,
                renderer=command.renderer,
                crop_output=command.crop_output,
                composite_fg=command.composite_foreground,
            )
            if pipeline is None:
                return StitchResult(
                    success=False,
                    num_frames=len(command.image_paths),
                    elapsed_seconds=round(time.monotonic() - t0, 4),
                    error="AnimeStitchPipeline backend is unavailable",
                )

            # Delegate execution to the pipeline
            if hasattr(pipeline, "run"):
                res = pipeline.run(
                    list(command.image_paths),
                    output_path=command.output_path,
                )
                width = getattr(res, "width", 0) if res else 0
                height = getattr(res, "height", 0) if res else 0
                metrics = getattr(res, "metrics", {}) if res else {}
            else:
                return StitchResult(
                    success=False,
                    num_frames=len(command.image_paths),
                    elapsed_seconds=_elapsed(t0),
                    error="ASP pipeline run operation is unavailable",
                )

            elapsed = round(time.monotonic() - t0, 4)
            return StitchResult(
                success=True,
                output_path=command.output_path,
                canvas_width=width,
                canvas_height=height,
                num_frames=len(command.image_paths),
                elapsed_seconds=elapsed,
                metrics=metrics,
            )
        except Exception as exc:
            return StitchResult(
                success=False,
                num_frames=len(command.image_paths),
                elapsed_seconds=round(time.monotonic() - t0, 4),
                error=str(exc),
            )

    def match_frames(self, command: MatchFramesCommand) -> MatchFramesResult:
        """Match two frames and compute pairwise alignment transform."""
        import cv2

        t0 = time.monotonic()
        if not os.path.isfile(command.image_path_1):
            raise CommandValidationError(
                f"First image path does not exist: {command.image_path_1}",
                field="image_path_1",
            )
        if not os.path.isfile(command.image_path_2):
            raise CommandValidationError(
                f"Second image path does not exist: {command.image_path_2}",
                field="image_path_2",
            )

        img1 = cv2.imread(command.image_path_1)
        if img1 is None:
            return MatchFramesResult(
                success=False,
                elapsed_seconds=_elapsed(t0),
                error=f"Image file is unreadable: {command.image_path_1}",
            )
        img2 = cv2.imread(command.image_path_2)
        if img2 is None:
            return MatchFramesResult(
                success=False,
                elapsed_seconds=_elapsed(t0),
                error=f"Image file is unreadable: {command.image_path_2}",
            )

        try:
            from asp_backend.alignment.matching._matcher_plugins import TemplateMatcher
        except ImportError as exc:
            return MatchFramesResult(
                success=False,
                elapsed_seconds=_elapsed(t0),
                error=f"ASP template matcher unavailable: {exc}",
            )

        try:
            matcher = TemplateMatcher()
            matrix, confidence = matcher.match(img1, img2)
            if matrix is None:
                return MatchFramesResult(
                    success=False,
                    elapsed_seconds=_elapsed(t0),
                    error="Matcher produced no transform",
                )
            affine = _affine_2x3(matrix)
            transform = tuple(tuple(float(value) for value in row) for row in affine)
            return MatchFramesResult(
                success=True,
                inlier_count=_overlap_count(img1, img2, affine),
                transform_matrix=transform,
                confidence=float(confidence),
                elapsed_seconds=_elapsed(t0),
            )
        except Exception as exc:
            return MatchFramesResult(
                success=False,
                elapsed_seconds=_elapsed(t0),
                error=str(exc),
            )

    def render_canvas(self, command: RenderCanvasCommand) -> RenderCanvasResult:
        """Render aligned frames onto a composited canvas."""
        import cv2
        import numpy as np

        t0 = time.monotonic()
        if not command.image_paths:
            raise CommandValidationError(
                "Render canvas requires at least one image path", field="image_paths"
            )

        for p in command.image_paths:
            if not os.path.isfile(p):
                return RenderCanvasResult(
                    success=False,
                    elapsed_seconds=_elapsed(t0),
                    error=f"Image file does not exist: {p}",
                )

        frames: list[np.ndarray] = []
        for path in command.image_paths:
            frame = cv2.imread(path)
            if frame is None:
                return RenderCanvasResult(
                    success=False,
                    elapsed_seconds=_elapsed(t0),
                    error=f"Image file is unreadable: {path}",
                )
            frames.append(frame)

        try:
            from asp_backend.alignment.canvas import _compute_canvas
            from asp_backend.rendering.rendering.first import _render_first
        except ImportError as exc:
            return RenderCanvasResult(
                success=False,
                elapsed_seconds=_elapsed(t0),
                error=f"ASP canvas renderer unavailable: {exc}",
            )

        try:
            if len(command.transforms) == len(frames):
                affines = [_affine_2x3(transform) for transform in command.transforms]
            else:
                affines = [np.array(_IDENTITY_AFFINE, copy=True) for _ in frames]

            canvas_h, canvas_w, translation = _compute_canvas(frames, affines)
            offset = np.asarray(translation, dtype=np.float64).reshape(-1)
            for affine in affines:
                affine[0, 2] = float(affine[0, 2]) + float(offset[0])
                affine[1, 2] = float(affine[1, 2]) + float(offset[1])

            rendered, _mask = _render_first(frames, affines, int(canvas_h), int(canvas_w))
            if rendered is None or rendered.size == 0:
                return RenderCanvasResult(
                    success=False,
                    elapsed_seconds=_elapsed(t0),
                    error="Renderer produced an empty canvas",
                )

            output_path = command.output_path
            if output_path:
                destination = Path(output_path)
                destination.parent.mkdir(parents=True, exist_ok=True)
                if not cv2.imwrite(output_path, rendered):
                    return RenderCanvasResult(
                        success=False,
                        elapsed_seconds=_elapsed(t0),
                        error=f"Failed to write canvas: {output_path}",
                    )
                if not destination.is_file() or destination.stat().st_size == 0:
                    return RenderCanvasResult(
                        success=False,
                        elapsed_seconds=_elapsed(t0),
                        error=f"Canvas file is empty: {output_path}",
                    )
                saved = cv2.imread(output_path)
                if saved is None or saved.size == 0:
                    return RenderCanvasResult(
                        success=False,
                        elapsed_seconds=_elapsed(t0),
                        error=f"Wrote canvas but could not read it back: {output_path}",
                    )
                height, width = saved.shape[:2]
            else:
                height, width = rendered.shape[:2]

            return RenderCanvasResult(
                success=True,
                output_path=output_path,
                canvas_width=int(width),
                canvas_height=int(height),
                elapsed_seconds=_elapsed(t0),
            )
        except Exception as exc:
            return RenderCanvasResult(
                success=False,
                elapsed_seconds=_elapsed(t0),
                error=str(exc),
            )

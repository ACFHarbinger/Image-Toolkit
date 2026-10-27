"""Cel-Shaded Generator (CSG) service implementation.

Canonical service home for CSG colorization, puppeteering, and animation
propagation (W0-03 Phase C, #867). Unblocks Wave 8 editor #916 E-03.
"""

from __future__ import annotations

import os
import time
from typing import Any

from middleware.src.services.base import CommandValidationError
from middleware.src.services.csg.commands import (
    ArapDeformCommand,
    ArapDeformResult,
    ColorizeReferenceCommand,
    ColorizeReferenceResult,
    ColorizeScribbleCommand,
    ColorizeScribbleResult,
    TemporalPropagateCommand,
    TemporalPropagateResult,
)
from middleware.src.services.csg.protocols import CsgServiceProtocol

_SOLVER_UNAVAILABLE = "CSG solver is unavailable"


class CsgService(CsgServiceProtocol):
    """Canonical domain service for cel-shaded colorization and puppeteering."""

    def __init__(self, csg_delegate: Any = None) -> None:
        """Initialize CsgService with optional delegate."""
        self._delegate = csg_delegate

    def colorize_scribble(self, command: ColorizeScribbleCommand) -> ColorizeScribbleResult:
        """Colorize lineart using scribble guidance."""
        t0 = time.monotonic()
        if not os.path.isfile(command.lineart_path):
            raise CommandValidationError(f"Lineart path does not exist: {command.lineart_path}", field="lineart_path")
        if not os.path.isfile(command.scribble_path):
            raise CommandValidationError(
                f"Scribble path does not exist: {command.scribble_path}", field="scribble_path"
            )

        try:
            if self._delegate is None or not hasattr(self._delegate, "colorize_scribble"):
                return ColorizeScribbleResult(
                    success=False,
                    elapsed_seconds=round(time.monotonic() - t0, 4),
                    error=_SOLVER_UNAVAILABLE,
                )
            return self._delegate.colorize_scribble(command)
        except Exception as exc:
            return ColorizeScribbleResult(
                success=False,
                elapsed_seconds=round(time.monotonic() - t0, 4),
                error=str(exc),
            )

    def colorize_reference(self, command: ColorizeReferenceCommand) -> ColorizeReferenceResult:
        """Transfer colors from style reference onto target lineart."""
        t0 = time.monotonic()
        if not os.path.isfile(command.lineart_path):
            raise CommandValidationError(f"Lineart path does not exist: {command.lineart_path}", field="lineart_path")
        if not os.path.isfile(command.reference_path):
            raise CommandValidationError(
                f"Reference path does not exist: {command.reference_path}", field="reference_path"
            )

        try:
            if self._delegate is None or not hasattr(self._delegate, "colorize_reference"):
                return ColorizeReferenceResult(
                    success=False,
                    elapsed_seconds=round(time.monotonic() - t0, 4),
                    error=_SOLVER_UNAVAILABLE,
                )
            return self._delegate.colorize_reference(command)
        except Exception as exc:
            return ColorizeReferenceResult(
                success=False,
                elapsed_seconds=round(time.monotonic() - t0, 4),
                error=str(exc),
            )

    def arap_deform(self, command: ArapDeformCommand) -> ArapDeformResult:
        """Perform As-Rigid-As-Possible 2D mesh deformation."""
        t0 = time.monotonic()
        if not os.path.isfile(command.image_path):
            raise CommandValidationError(f"Image path does not exist: {command.image_path}", field="image_path")
        if len(command.control_points) != len(command.target_points):
            raise CommandValidationError(
                "Control points and target points must have identical lengths",
                field="control_points",
            )

        try:
            if self._delegate is None or not hasattr(self._delegate, "arap_deform"):
                return ArapDeformResult(
                    success=False,
                    elapsed_seconds=round(time.monotonic() - t0, 4),
                    error=_SOLVER_UNAVAILABLE,
                )
            return self._delegate.arap_deform(command)
        except Exception as exc:
            return ArapDeformResult(
                success=False,
                elapsed_seconds=round(time.monotonic() - t0, 4),
                error=str(exc),
            )

    def propagate_sequence(self, command: TemporalPropagateCommand) -> TemporalPropagateResult:
        """Propagate colorization temporally across a sequence of animation frames."""
        t0 = time.monotonic()
        if not command.frame_paths:
            raise CommandValidationError("Temporal propagation requires at least one frame path", field="frame_paths")

        for p in command.frame_paths:
            if not os.path.isfile(p):
                return TemporalPropagateResult(
                    success=False,
                    frames_processed=0,
                    elapsed_seconds=round(time.monotonic() - t0, 4),
                    error=f"Frame file does not exist: {p}",
                )

        try:
            if self._delegate is None or not hasattr(self._delegate, "propagate_sequence"):
                return TemporalPropagateResult(
                    success=False,
                    frames_processed=0,
                    elapsed_seconds=round(time.monotonic() - t0, 4),
                    error=_SOLVER_UNAVAILABLE,
                )
            return self._delegate.propagate_sequence(command)
        except Exception as exc:
            return TemporalPropagateResult(
                success=False,
                frames_processed=0,
                elapsed_seconds=round(time.monotonic() - t0, 4),
                error=str(exc),
            )

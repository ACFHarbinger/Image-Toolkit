"""Protocols for the Cel-Shaded Generator (CSG) service.

Runtime-checkable protocol defining the boundary for colorization, puppeteering,
and manga animation propagation (W0-03 Phase C, #867).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from middleware.src.services.base import ServiceProtocol
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


@runtime_checkable
class CsgServiceProtocol(ServiceProtocol, Protocol):
    """Protocol for manga colorization, animation propagation, and ARAP puppeteering."""

    def colorize_scribble(self, command: ColorizeScribbleCommand) -> ColorizeScribbleResult:
        """Colorize lineart using scribble guidance."""
        ...

    def colorize_reference(self, command: ColorizeReferenceCommand) -> ColorizeReferenceResult:
        """Transfer colors from style reference onto target lineart."""
        ...

    def arap_deform(self, command: ArapDeformCommand) -> ArapDeformResult:
        """Perform As-Rigid-As-Possible 2D mesh deformation."""
        ...

    def propagate_sequence(self, command: TemporalPropagateCommand) -> TemporalPropagateResult:
        """Propagate colorization temporally across a sequence of animation frames."""
        ...

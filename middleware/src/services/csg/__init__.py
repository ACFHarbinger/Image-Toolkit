"""Cel-Shaded Generator (CSG) domain service package (W0-03 Phase C, #867)."""

from __future__ import annotations

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
from middleware.src.services.csg.service import CsgService

__all__ = [
    "ArapDeformCommand",
    "ArapDeformResult",
    "ColorizeReferenceCommand",
    "ColorizeReferenceResult",
    "ColorizeScribbleCommand",
    "ColorizeScribbleResult",
    "CsgService",
    "CsgServiceProtocol",
    "TemporalPropagateCommand",
    "TemporalPropagateResult",
]

"""
backend/src/exceptions.py
==========================
Application-wide exception hierarchy.

All application-specific exceptions derive from ``ImageToolkitError`` so
callers can catch them as a group or individually.

Hierarchy
---------
ImageToolkitError
├── PipelineError          — base for all pipeline-stage failures
│   ├── AlignmentFailedError   — BA / affine-validation failure
│   ├── CanvasError            — canvas construction / rendering failure
│   └── FallbackExhaustedError — all registered fallbacks have been tried
├── ModelLoadError         — ML model weights could not be loaded / found
└── ConfigError            — configuration validation failure

Usage
-----
Raise the most specific subclass; catch the base when handling groups::

    from backend.src.exceptions import AlignmentFailedError

    raise AlignmentFailedError(f"ratio={ratio:.2f} < 0.5 after Retry 5")

    # In a QThread worker:
    except AlignmentFailedError as exc:
        logger.warning("Alignment failed — falling back: %s", exc)
        self.error.emit(str(exc))
"""

from __future__ import annotations


class ImageToolkitError(Exception):
    """Base class for all Image Toolkit application errors."""


# ── Pipeline ──────────────────────────────────────────────────────────────────


class PipelineError(ImageToolkitError):
    """Raised when any stage of the stitching / processing pipeline fails."""


class AlignmentFailedError(PipelineError):
    """Raised when bundle-adjustment or affine-validation cannot converge.

    The pipeline typically catches this and attempts a fallback stitcher
    (PANORAMA → SCANS) before surfacing it to the GUI.
    """


class CanvasError(PipelineError):
    """Raised when canvas construction or rendering produces an unusable result.

    Examples: zero-area canvas, degenerate affine placement, SCANS returning a
    non-OK status code.
    """


class FallbackExhaustedError(PipelineError):
    """Raised when every registered fallback path has been attempted and failed.

    Carries a ``fallbacks`` attribute listing the names of attempted fallbacks.
    """

    def __init__(self, message: str, fallbacks: list[str] | None = None) -> None:
        super().__init__(message)
        self.fallbacks: list[str] = fallbacks or []


# ── ML Models ─────────────────────────────────────────────────────────────────


class ModelLoadError(ImageToolkitError):
    """Raised when an ML model's weights cannot be loaded or a required library
    is missing.

    Distinct from ``PipelineError`` because model-load failures are recoverable
    at the *model-selection* level (try a lighter alternative) rather than at
    the pipeline stage level.
    """


# ── Configuration ─────────────────────────────────────────────────────────────


class ConfigError(ImageToolkitError):
    """Raised when a configuration value is invalid or out of range.

    Used by ``validate_asp_config()`` in strict mode and by the TOML config
    loader when a required key is absent.
    """


__all__ = [
    "ImageToolkitError",
    "PipelineError",
    "AlignmentFailedError",
    "CanvasError",
    "FallbackExhaustedError",
    "ModelLoadError",
    "ConfigError",
]

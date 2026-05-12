"""
anime_stitch_pipeline.py — backward-compatibility shim.

The implementation has moved to the :mod:`backend.src.core.anim` package.
This module re-exports the public API so existing imports keep working:

    from backend.src.core.anime_stitch_pipeline import AnimeStitchPipeline

For new code, prefer:

    from backend.src.core.anim import AnimeStitchPipeline
    from backend.src.core.anim.mfsr import run_mfsr, pso_register, de_seam
"""

from __future__ import annotations

from backend.src.core.anim import (
    AnimeStitchPipeline,
    de_seam,
    pso_register,
    run_mfsr,
)
from backend.src.core.anim.bundle_adjust import _bundle_adjust_affine
from backend.src.core.anim.constants import (
    _CANVAS_MAX_DIM,
    _ECC_EPS,
    _ECC_MAX_ITER,
    _ECC_PYRAMID_LEVELS,
    _FOREGROUND_DILATION,
    _FOREGROUND_EROSION,
    _LAPLACIAN_BANDS,
    _MATCH_EDGE_CROP,
    _MAX_DX_DRIFT_RATIO,
    _MEDIAN_MIN_SAMPLES,
    _MIN_LOFTR_INLIERS,
    _MIN_TEMPLATE_SCORE,
    _PC_CONF_THRESHOLD,
    _SMOOTHSTEP_BLEND_PX,
)
from backend.src.core.anim.stateless import (
    _highpass,
    _laplacian_blend,
    _largest_valid_rect,
    _luma,
    _seam_dp,
    _trim_dark_border,
)

__all__ = [
    "AnimeStitchPipeline",
    "run_mfsr",
    "pso_register",
    "de_seam",
    # Legacy helper exports
    "_bundle_adjust_affine",
    "_luma",
    "_highpass",
    "_trim_dark_border",
    "_laplacian_blend",
    "_seam_dp",
    "_largest_valid_rect",
    # Legacy constants
    "_LAPLACIAN_BANDS",
    "_ECC_MAX_ITER",
    "_ECC_EPS",
    "_ECC_PYRAMID_LEVELS",
    "_MIN_LOFTR_INLIERS",
    "_MAX_DX_DRIFT_RATIO",
    "_MATCH_EDGE_CROP",
    "_MIN_TEMPLATE_SCORE",
    "_PC_CONF_THRESHOLD",
    "_CANVAS_MAX_DIM",
    "_MEDIAN_MIN_SAMPLES",
    "_FOREGROUND_DILATION",
    "_FOREGROUND_EROSION",
    "_SMOOTHSTEP_BLEND_PX",
]

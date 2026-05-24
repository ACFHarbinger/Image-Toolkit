"""
Affine matrix validation — post-bundle-adjustment health checks.

Checks the output of Stage 7 (bundle adjustment) for pathological patterns
that would cascade into catastrophic Stage 9 ghosting.  When validation fails,
the pipeline should fall back to OpenCV SCANS stitch.

Issue categories covered:
  C — Alignment failure: frame clustering (min_gap=0), high ratio (>3×).
  D/G — Affine rotation/scale mismatch (test18: good ty/tx, bad rotation).
"""

from __future__ import annotations

from typing import List, NamedTuple

import numpy as np


class AffineHealth(NamedTuple):
    """Result of affine matrix validation."""

    valid: bool
    ratio: float
    min_gap: float
    max_rotation: float
    max_scale_dev: float
    reason: str


def _validate_affines(
    affines: List[np.ndarray],
    min_step: float = 50.0,
    max_ratio: float = 3.0,
    max_rotation: float = 0.1,
    max_scale_dev: float = 0.1,
) -> AffineHealth:
    """
    Full affine health check — determines whether bundle-adjusted affines are
    safe to use for canvas construction and rendering.

    A frame set is considered INVALID if ANY of the following hold:
      1. max_gap / median_gap > max_ratio  (uneven spacing / clustering)
      2. min_gap < min_step                (co-located frames)
      3. any off-diagonal element > max_rotation  (rotation mismatch — test18)
      4. any diagonal element deviates from 1.0 by > max_scale_dev (scale drift)

    Parameters
    ----------
    affines : list of (2, 3) float32 affine matrices.
    min_step : minimum expected ty gap between consecutive frames (px).
    max_ratio : maximum allowed max_gap / median_gap ratio.
    max_rotation : maximum allowed off-diagonal (rotation) element magnitude.
    max_scale_dev : maximum allowed deviation of diagonal elements from 1.0.

    Returns
    -------
    AffineHealth named tuple with validation result and diagnostic metrics.
    """
    N = len(affines)
    if N < 2:
        return AffineHealth(True, 1.0, 0.0, 0.0, 0.0, "single frame")

    from .canvas import _detect_scroll_axis
    scroll_axis = _detect_scroll_axis(affines)

    txs = np.array([float(a[0, 2]) for a in affines])
    tys = np.array([float(a[1, 2]) for a in affines])

    if scroll_axis == "horizontal":
        vals = txs
    elif scroll_axis == "diagonal":
        # For diagonal, use Euclidean distance from the first frame as the 1D sorting axis
        vals = np.sqrt((txs - txs[0])**2 + (tys - tys[0])**2)
    else:
        vals = tys

    sorted_vals = np.sort(vals)
    gaps = np.diff(sorted_vals)

    if len(gaps) == 0:
        return AffineHealth(
            False, float("inf"), 0.0, 0.0, 0.0, "all frames at same position"
        )

    median_gap = float(np.median(gaps))
    max_gap = float(gaps.max())
    min_gap = float(gaps.min())
    ratio = max_gap / max(median_gap, 1.0)

    # Rotation: magnitude of off-diagonal elements in the 2×2 rotation block
    max_rot = max(
        max(abs(float(a[0, 1])), abs(float(a[1, 0]))) for a in affines
    )
    # Scale: deviation of diagonal elements from identity (1.0)
    max_sc = max(
        max(abs(float(a[0, 0]) - 1.0), abs(float(a[1, 1]) - 1.0))
        for a in affines
    )

    if ratio > max_ratio:
        return AffineHealth(
            False,
            ratio,
            min_gap,
            max_rot,
            max_sc,
            f"ratio={ratio:.1f} > {max_ratio}",
        )
    if min_gap < min_step:
        return AffineHealth(
            False,
            ratio,
            min_gap,
            max_rot,
            max_sc,
            f"min_gap={min_gap:.1f}px < {min_step}px",
        )
    if max_rot > max_rotation:
        return AffineHealth(
            False,
            ratio,
            min_gap,
            max_rot,
            max_sc,
            f"rotation={max_rot:.3f} > {max_rotation}",
        )
    if max_sc > max_scale_dev:
        return AffineHealth(
            False,
            ratio,
            min_gap,
            max_rot,
            max_sc,
            f"scale_dev={max_sc:.3f} > {max_scale_dev}",
        )

    return AffineHealth(True, ratio, min_gap, max_rot, max_sc, "ok")


__all__ = ["AffineHealth", "_validate_affines"]

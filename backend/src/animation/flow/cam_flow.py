"""
Background-masked camera displacement estimation.
Replaces whole-frame phase correlation with background-only correlation,
decoupling camera motion from character animation.
§3.5B — CamFlow foreground masking
"""
from __future__ import annotations

import cv2
import numpy as np
from typing import Optional, Tuple

__all__ = [
    "bg_masked_phase_correlate",
    "CamFlowEstimator",
    "CAM_FLOW_MIN_BG_PIXELS",
]

CAM_FLOW_MIN_BG_PIXELS = 500  # Fall back to whole-frame if fewer bg pixels available

try:
    from backend.src.animation import base as _batch
    _HAS_BATCH: bool = True
except ImportError:
    _batch = None  # type: ignore[assignment]
    _HAS_BATCH: bool = False


def bg_masked_phase_correlate(
    frame_a: np.ndarray,
    frame_b: np.ndarray,
    bg_mask_a: Optional[np.ndarray] = None,
    bg_mask_b: Optional[np.ndarray] = None,
    min_bg_pixels: int = CAM_FLOW_MIN_BG_PIXELS,
) -> Tuple[float, float, float]:
    """
    Estimate camera (dx, dy) using only background pixels.

    bg_mask_a/b: bool arrays where True=background, False=foreground.
    Returns (dx, dy, response). Falls back to whole-frame if bg area too small.
    """
    gray_a = cv2.cvtColor(frame_a, cv2.COLOR_BGR2GRAY) if frame_a.ndim == 3 else frame_a.copy()
    gray_b = cv2.cvtColor(frame_b, cv2.COLOR_BGR2GRAY) if frame_b.ndim == 3 else frame_b.copy()

    if _HAS_BATCH:
        # C++ fast path — convert bool masks to uint8 (nonzero = background)
        ma = (bg_mask_a.astype(np.uint8) * 255) if bg_mask_a is not None else None
        mb = (bg_mask_b.astype(np.uint8) * 255) if bg_mask_b is not None else None
        result = _batch.matching.phase_correlate_masked(
            np.ascontiguousarray(gray_a),
            np.ascontiguousarray(gray_b),
            ma, mb,
        )
        return float(result["dx"]), float(result["dy"]), float(result["response"])

    # Python fallback
    if bg_mask_a is None or bg_mask_b is None:
        (dx, dy), response = cv2.phaseCorrelate(
            gray_a.astype(np.float32), gray_b.astype(np.float32)
        )
        return float(dx), float(dy), float(response)

    combined_bg = bg_mask_a.astype(bool) & bg_mask_b.astype(bool)
    n_bg = int(combined_bg.sum())

    if n_bg < min_bg_pixels:
        (dx, dy), response = cv2.phaseCorrelate(
            gray_a.astype(np.float32), gray_b.astype(np.float32)
        )
        return float(dx), float(dy), float(response)

    masked_a = gray_a.astype(np.float32)
    masked_b = gray_b.astype(np.float32)
    fg = ~combined_bg
    masked_a[fg] = 0.0
    masked_b[fg] = 0.0

    (dx, dy), response = cv2.phaseCorrelate(masked_a, masked_b)
    return float(dx), float(dy), float(response)


class CamFlowEstimator:
    """Stateless wrapper around bg_masked_phase_correlate."""

    def __init__(self, min_bg_pixels: int = CAM_FLOW_MIN_BG_PIXELS):
        self.min_bg_pixels = min_bg_pixels

    def estimate(
        self,
        frame_a: np.ndarray,
        frame_b: np.ndarray,
        bg_mask_a: Optional[np.ndarray] = None,
        bg_mask_b: Optional[np.ndarray] = None,
    ) -> Tuple[float, float, float]:
        return bg_masked_phase_correlate(
            frame_a, frame_b, bg_mask_a, bg_mask_b, self.min_bg_pixels
        )

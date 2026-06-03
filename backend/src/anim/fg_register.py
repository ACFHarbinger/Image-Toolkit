"""
backend/src/anim/fg_register.py
===============================
Foreground pose registration (Stage 8.5) — the core fix for strip-seam
character misalignment.

Problem
-------
The ASP camera model is translation-only.  It aligns the *background* across
frames perfectly, but the character is *animating* between the frames being
stitched (300–800 ms apart), so its body parts land in two different poses on
either side of every strip seam → the torn / doubled edges visible in test09.

Approach (see reports/ASP_Foreground_Assembly_Research.md §5)
------------------------------------------------------------
Both frames are first warped into the same canvas coordinate system by the
existing affines, so the *background* is already aligned.  Any optical flow
that remains on the *foreground* between the two canvas-aligned frames is the
pure animation residual ``A_animation`` (the camera component ``T_camera`` is
removed by the alignment-aware warping — it does not need to be subtracted
explicitly).

We then re-pose both frames' foreground toward the *midpoint* pose
(StabStitch++ bidirectional principle: halves the maximum per-frame
distortion).  The warp magnitude is tapered to zero away from the seam so the
correction is localised to the boundary where it matters (SC-AOF blend-band
principle) and never disturbs canvas regions a single frame owns outright.

Flow engine
-----------
Default is OpenCV ``DISOpticalFlow`` (fast, no extra dependency).  A SEA-RAFT
engine can be slotted in later via ``flow_engine="searaft"`` (requires
``ptlflow``); the rest of the module is engine-agnostic.

This module is import-safe for headless use (no Qt, no torch import at module
load) and has no side effects.
"""

from __future__ import annotations

import os
from typing import Optional, Tuple

import cv2
import numpy as np

from backend.src.constants import (
    FG_REG_TAPER_PX,
    FG_REG_MAX_RESIDUAL as _FG_REG_MAX_RESIDUAL_DEFAULT,
    FG_REG_MIN_FG_PIXELS,
    FG_REG_SMOOTH_SIGMA,
)

# Allow benchmark sweeps to tune the warp-vs-single-pose threshold without an
# edit/rebuild cycle.  Lower → more seams take the single-pose fallback (one
# coherent character pose, no blend) instead of an imperfect re-pose+blend that
# can leave faint edge doubling.
try:
    FG_REG_MAX_RESIDUAL = float(
        os.environ.get("ASP_FG_MAX_RESIDUAL", _FG_REG_MAX_RESIDUAL_DEFAULT)
    )
except ValueError:
    FG_REG_MAX_RESIDUAL = _FG_REG_MAX_RESIDUAL_DEFAULT


# ---------------------------------------------------------------------------
# Flow engine
# ---------------------------------------------------------------------------

_DIS_SINGLETON = None


def _get_dis():
    """Lazily construct a reusable DISOpticalFlow instance (MEDIUM preset)."""
    global _DIS_SINGLETON
    if _DIS_SINGLETON is None:
        _DIS_SINGLETON = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
        # Slightly larger patch + denser grid → smoother flow on flat cel regions
        try:
            _DIS_SINGLETON.setUseSpatialPropagation(True)
        except Exception:
            pass
    return _DIS_SINGLETON


def _dense_flow(prev_bgr: np.ndarray, next_bgr: np.ndarray) -> np.ndarray:
    """
    Dense optical flow ``prev → next`` using DISOpticalFlow.

    Returns an (H, W, 2) float32 array ``flow`` where
    ``prev[y, x]`` corresponds to ``next[y + flow[y,x,1], x + flow[y,x,0]]``.
    """
    prev_gray = cv2.cvtColor(prev_bgr, cv2.COLOR_BGR2GRAY)
    next_gray = cv2.cvtColor(next_bgr, cv2.COLOR_BGR2GRAY)
    dis = _get_dis()
    flow = dis.calc(prev_gray, next_gray, None)
    return flow.astype(np.float32)


def _seam_taper(
    h: int,
    w: int,
    seam_pos: int,
    taper_px: float,
    axis: int = 0,
) -> np.ndarray:
    """
    (h, w) float32 taper weight, 1.0 at ``seam_pos`` decaying linearly to 0.0
    at ``±taper_px``.  ``axis=0`` → taper along rows (vertical scroll seam);
    ``axis=1`` → taper along columns (horizontal scroll seam).
    """
    if axis == 0:
        coord = np.arange(h, dtype=np.float32)[:, None]
        dist = np.abs(coord - float(seam_pos))
        w_line = np.clip(1.0 - dist / max(taper_px, 1.0), 0.0, 1.0)  # (h,1)
        return np.broadcast_to(w_line, (h, w)).copy()
    else:
        coord = np.arange(w, dtype=np.float32)[None, :]
        dist = np.abs(coord - float(seam_pos))
        w_line = np.clip(1.0 - dist / max(taper_px, 1.0), 0.0, 1.0)  # (1,w)
        return np.broadcast_to(w_line, (h, w)).copy()


def _remap_by_displacement(img: np.ndarray, disp: np.ndarray) -> np.ndarray:
    """
    Resample ``img`` at position ``(x + disp_x, y + disp_y)`` per pixel.

    ``disp`` is an (H, W, 2) field (dx, dy).  Pixels whose source maps outside
    the image retain their original value (BORDER_TRANSPARENT fallback) to
    avoid the BORDER_REPLICATE edge-smear artefact that creates corrupted
    corner regions in the composite when the warp shifts pixels off-canvas.
    """
    h, w = img.shape[:2]
    grid_x, grid_y = np.meshgrid(
        np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32)
    )
    map_x = grid_x + disp[:, :, 0]
    map_y = grid_y + disp[:, :, 1]
    remapped = cv2.remap(
        img,
        map_x,
        map_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    # Restore original pixels wherever the source coordinate mapped outside
    # the valid frame bounds — those remap to black (0) which is also content
    # in some scenes, so we use the source validity mask instead.
    out_of_bounds = (
        (map_x < 0) | (map_x >= w) | (map_y < 0) | (map_y >= h)
    )
    if out_of_bounds.any():
        out3 = np.stack([out_of_bounds] * 3, axis=2) if img.ndim == 3 else out_of_bounds
        remapped[out3] = img[out3]
    return remapped


def register_foreground_at_seam(
    warped_a: np.ndarray,
    warped_b: np.ndarray,
    fg_a: np.ndarray,
    fg_b: np.ndarray,
    seam_pos: int,
    axis: int = 0,
    taper_px: float = FG_REG_TAPER_PX,
    max_residual: float = FG_REG_MAX_RESIDUAL,
    smooth_sigma: float = FG_REG_SMOOTH_SIGMA,
) -> Tuple[np.ndarray, np.ndarray, dict]:
    """
    Re-pose the foreground of two canvas-aligned frames toward their midpoint
    pose in a tapered band around the seam, so character body parts line up
    across the strip boundary.

    Parameters
    ----------
    warped_a, warped_b : (H, W, 3) uint8
        The two adjacent frames already warped into canvas coordinates (so the
        background is aligned).  ``a`` owns the canvas on one side of
        ``seam_pos``; ``b`` owns the other.
    fg_a, fg_b : (H, W) bool or uint8
        Foreground masks for each warped frame (True / >127 = foreground
        character pixel).  Flow / warp is applied to foreground only.
    seam_pos : int
        Canvas row (axis=0) or column (axis=1) of the ownership boundary.
    axis : int
        0 = vertical scroll (horizontal seam), 1 = horizontal scroll.
    taper_px : float
        Half-width of the seam band over which the warp magnitude tapers to 0.
    max_residual : float
        If the median foreground residual exceeds this, the animation gap is too
        large to warp safely → return inputs unchanged and signal ``warped=False``
        so the caller can fall back to single-pose-per-component (Eden-2006).
    smooth_sigma : float
        Gaussian sigma to smooth the residual flow before warping (suppresses
        per-pixel flow noise that would tear flat cel regions).

    Returns
    -------
    (adj_a, adj_b, info) where ``adj_a``/``adj_b`` are the re-posed frames and
    ``info`` carries diagnostics (``warped`` bool, ``residual`` median px,
    ``fg_pixels`` in the seam band).
    """
    h, w = warped_a.shape[:2]
    fa = (fg_a > 127) if fg_a.dtype != bool else fg_a
    fb = (fg_b > 127) if fg_b.dtype != bool else fg_b

    # Seam band: only the region within taper_px of the seam matters.
    taper = _seam_taper(h, w, seam_pos, taper_px, axis=axis)  # (h,w) in [0,1]
    band = taper > 0.0
    fa_band = fa & band
    fb_band = fb & band
    fg_union = fa_band | fb_band
    n_fg = int(fg_union.sum())

    # Dominant frame in the band = the one carrying the more complete character
    # instance (more foreground pixels).  Used by the single-pose fallback (A6).
    n_a = int(fa_band.sum())
    n_b = int(fb_band.sum())
    dominant = "a" if n_a >= n_b else "b"

    info = {
        "warped": False,
        "fallback": False,
        "residual": 0.0,
        "fg_pixels": n_fg,
        "dominant": dominant,
    }

    if n_fg < FG_REG_MIN_FG_PIXELS:
        # No meaningful character content crosses this seam — nothing to fix.
        return warped_a, warped_b, info

    # Dense flow a → b (camera already removed by canvas alignment ⇒ residual
    # foreground flow is the animation motion).
    flow = _dense_flow(warped_a, warped_b)  # (h,w,2)

    # Smooth the flow to suppress per-pixel noise on flat cel regions.
    if smooth_sigma > 0:
        flow[:, :, 0] = cv2.GaussianBlur(flow[:, :, 0], (0, 0), smooth_sigma)
        flow[:, :, 1] = cv2.GaussianBlur(flow[:, :, 1], (0, 0), smooth_sigma)

    # Magnitude of the residual on foreground pixels in the band.
    mag = np.sqrt(flow[:, :, 0] ** 2 + flow[:, :, 1] ** 2)
    fg_mag = mag[fg_union]
    med_residual = float(np.median(fg_mag)) if fg_mag.size else 0.0
    info["residual"] = round(med_residual, 2)

    if med_residual > max_residual:
        # Animation gap too large for a safe warp — signal the single-pose
        # fallback (A6): the caller should take the foreground in this seam band
        # from the dominant frame only, avoiding a two-pose double image.
        info["fallback"] = True
        return warped_a, warped_b, info

    if med_residual < 0.5:
        # Already aligned (near-static foreground at this seam) — skip.
        info["warped"] = False
        return warped_a, warped_b, info

    # Per-pixel warp weight: taper × foreground membership (warp fg only).
    w_a = (taper * fa.astype(np.float32))[:, :, None]   # (h,w,1)
    w_b = (taper * fb.astype(np.float32))[:, :, None]

    # Midpoint re-posing:
    #   a moves +0.5·flow toward b  → sample a at (x − 0.5·flow)
    #   b moves −0.5·flow toward a  → sample b at (x + 0.5·flow)
    disp_a = -0.5 * flow * w_a
    disp_b = +0.5 * flow * w_b

    # Valid-content masks: positions where the warped canvas has actual pixels.
    valid_a = warped_a.max(axis=2) > 0
    valid_b = warped_b.max(axis=2) > 0

    adj_a = _remap_by_displacement(warped_a, disp_a)
    adj_b = _remap_by_displacement(warped_b, disp_b)

    # Keep background untouched: restore original where the pixel was not warped
    # foreground (so only the character is re-posed, never the aligned bg).
    keep_a = ~(fa & band)
    keep_b = ~(fb & band)
    adj_a[keep_a] = warped_a[keep_a]
    adj_b[keep_b] = warped_b[keep_b]

    # Never introduce content where the original had none — the warp must not
    # extend canvas pixels into previously-empty boundary regions.
    adj_a[~valid_a] = 0
    adj_b[~valid_b] = 0

    info["warped"] = True
    return adj_a, adj_b, info


__all__ = ["register_foreground_at_seam", "_dense_flow", "_seam_taper"]

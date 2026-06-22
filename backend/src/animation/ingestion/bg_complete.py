"""
backend/src/animation/bg_complete.py
================================
Background zero-coverage fill for the Anime Stitch Pipeline (§5A/C).

After Stage 10 (temporal median), canvas pixels that appear in zero
background samples have their value set to black — the character covered
that canvas region in EVERY selected frame.  When this happens in a
significant number of canvas rows, strip boundaries show visible bands.

This module fills those uncovered regions using one of two strategies:

**Nearest-neighbour column fill (§5C, default)**
    For each column, propagates the nearest known pixel value upward/downward
    into the zero-coverage gap.  Zero compute cost.  Works well for scenes
    with a uniform or slowly-varying background (plain walls, lockers).

**ProPainter video inpainting (§5A, optional)**
    Uses ProPainter (ICCV 2023) — a flow-guided recurrent network — to
    generate temporally coherent fills for large zero-coverage zones.
    Requires ``pip install propainter``.  Falls back to NN fill silently
    when ProPainter is unavailable.

Configuration
-------------
``ASP_BG_COMPLETE`` (env, default "0"):
    0 = disabled (skip bg completion entirely)
    1 = nearest-neighbour fill (fast, no new dependencies)
    2 = ProPainter when available, NN fill as fallback
``ASP_BG_COMPLETE_MIN_ROWS`` (env, default "20"):
    Minimum number of zero-coverage rows before completion runs.  Avoids
    overhead for canvases where the character barely covers any bg.
"""

from __future__ import annotations

# --- Relocated Nested Imports ---
try:
    import torch  # noqa: F401  # required by ProPainterInference when available
except ImportError:
    pass
try:
    from propainter.inference_propainter import (  # type: ignore
        ProPainterInference,
    )
except ImportError:
    ProPainterInference = None
# --------------------------------


import os
from typing import List, Optional

import cv2
import numpy as np

__all__ = [
    "_nn_fill_zero_bg",
    "_linear_interp_zero_bg",
    "_masked_median_bg",
    "_propainter_fill",
    "_propainter_complete_frames",
    "complete_background",
]

_BG_COMPLETE: int = int(os.environ.get("ASP_BG_COMPLETE", "0"))
_BG_COMPLETE_MIN_ROWS: int = int(os.environ.get("ASP_BG_COMPLETE_MIN_ROWS", "20"))

# §1.42 — Linear interpolation bg fill.
# When enabled, replaces the hard nearest-neighbour copy in _nn_fill_zero_bg with a
# per-channel linear blend between the known pixel above and the known pixel below
# each gap.  Boundary gaps (only one side known) still fall back to NN copy so no
# pixel is ever left unfilled.  Produces visually smooth transitions across large
# zero-coverage zones (character covering many rows) at negligible extra cost.
# Default OFF.  Enable: ASP_INTERP_BG_FILL=1.
_INTERP_BG_FILL: bool = os.environ.get("ASP_INTERP_BG_FILL", "0") != "0"


# ---------------------------------------------------------------------------
# §1.87 — Masked-Median Background Plate (Overmix AnimRender approach)
# ---------------------------------------------------------------------------


def _masked_median_bg(
    stack: np.ndarray,
    fg_stack: np.ndarray,
    min_agree_frac: float = 0.4,
) -> np.ndarray:
    """Exclude fg pixels from median entirely rather than zero-filling them.

    Implements the Overmix AnimRender principle: instead of zeroing foreground
    pixels before taking the median (which pulls rows toward zero when the
    character covers >50% of frames), we mask them out so the median is only
    computed from background-only samples.  Where every frame has fg (all_fg),
    falls back to a stability vote: the median across all frames ignoring the
    fg constraint, which is better than a ghost-average of different poses.

    Args:
        stack:    (N, H, W, C) float32 [0, 255] — warped frames.
        fg_stack: (N, H, W) bool — True = foreground pixel in that frame.
        min_agree_frac: unused; reserved for future cross-frame stability tuning.

    Returns:
        (H, W, C) float32 background plate.
    """
    N, H, W, C = stack.shape
    result = np.zeros((H, W, C), dtype=np.float32)

    # Build the masked array once per channel to avoid looping over N.
    # np.ma.median excludes masked (fg) entries; when ALL entries are masked,
    # the result is np.ma.masked (fill_value applied → 0).
    fg_broadcast = fg_stack[:, :, :, np.newaxis]  # (N, H, W, 1)
    masked = np.ma.array(stack, mask=np.broadcast_to(fg_broadcast, stack.shape))
    med = np.ma.median(masked, axis=0)  # (H, W, C) masked array

    # Pixels where median is valid (at least one bg sample).
    if hasattr(med, "mask") and med.mask is not np.ma.nomask:
        valid = ~med.mask[:, :, 0]  # (H, W) bool — any channel tells us
    else:
        valid = np.ones((H, W), dtype=bool)

    result[valid] = med.filled(0.0)[valid]

    # Stability-vote fallback for pixels where ALL frames had fg.
    # Use unconstrained median (fg included) — at minimum gives the dominant
    # midpoint pose rather than a ghost average of extreme poses.
    all_fg = ~valid  # (H, W)
    if all_fg.any():
        unconstrained_med = np.median(stack, axis=0)  # (H, W, C)
        result[all_fg] = unconstrained_med[all_fg]

    return result


# ---------------------------------------------------------------------------
# Nearest-neighbour column fill (§5C)
# ---------------------------------------------------------------------------


def _nn_fill_zero_bg(
    canvas: np.ndarray,
    zero_mask: np.ndarray,
) -> np.ndarray:
    """Fill zero-coverage canvas pixels using nearest-neighbour column propagation.

    For each column, finds the nearest non-zero row above and below each gap
    and fills linearly (hard-copy nearest, no interpolation).  Operates
    in-place on a copy.

    Parameters
    ----------
    canvas : (H, W, 3) uint8 BGR canvas from the temporal renderer.
    zero_mask : (H, W) bool or uint8 array — True/non-zero where the pixel
        is uncovered (no background sample available in any frame).

    Returns
    -------
    (H, W, 3) uint8 filled canvas.
    """
    out = canvas.copy()
    H, W = canvas.shape[:2]
    mask = zero_mask.astype(bool) if zero_mask.dtype != bool else zero_mask

    for col in range(W):
        col_mask = mask[:, col]
        if not col_mask.any():
            continue
        known_rows = np.where(~col_mask)[0]
        if len(known_rows) == 0:
            continue
        unknown_rows = np.where(col_mask)[0]
        # For each unknown row, find the nearest known row
        nearest_known = known_rows[
            np.searchsorted(known_rows, unknown_rows, side="left").clip(
                0, len(known_rows) - 1
            )
        ]
        # Clamp: also compare with the row before the insertion point
        idx_before = (np.searchsorted(known_rows, unknown_rows, side="left") - 1).clip(
            0, len(known_rows) - 1
        )
        nn_before = known_rows[idx_before]
        dist_after = np.abs(unknown_rows - nearest_known)
        dist_before = np.abs(unknown_rows - nn_before)
        best = np.where(dist_before < dist_after, nn_before, nearest_known)
        out[unknown_rows, col] = canvas[best, col]

    return out


def _linear_interp_zero_bg(
    canvas: np.ndarray,
    zero_mask: np.ndarray,
) -> np.ndarray:
    """§1.42: Fill zero-coverage pixels with per-channel linear interpolation.

    For each column, each contiguous gap of zero-coverage rows is filled by
    linearly blending between the nearest known pixel *above* and the nearest
    known pixel *below* the gap.  When only one boundary is available (top or
    bottom edge gaps), falls back to the nearest-neighbour copy so every pixel
    receives a value.

    Produces smooth colour gradients across large zero-coverage zones (e.g.,
    a character covering most rows of a column) instead of the discrete step
    that ``_nn_fill_zero_bg`` produces at the midpoint between two different
    background tones.

    Parameters
    ----------
    canvas   : (H, W, 3) uint8 BGR canvas from the temporal renderer.
    zero_mask : (H, W) bool or uint8 — True/non-zero where the pixel is
        uncovered.

    Returns
    -------
    (H, W, 3) uint8 filled canvas (independent copy).
    """
    out = canvas.copy().astype(np.float32)
    H, W = canvas.shape[:2]
    mask = (zero_mask > 0) if zero_mask.dtype != bool else zero_mask

    for col in range(W):
        col_mask = mask[:, col]
        if not col_mask.any():
            continue
        known_rows = np.where(~col_mask)[0]
        if len(known_rows) == 0:
            continue
        unknown_rows = np.where(col_mask)[0]

        for r in unknown_rows:
            # Find nearest known row above
            above_idx = np.searchsorted(known_rows, r, side="left") - 1
            below_idx = np.searchsorted(known_rows, r, side="right")

            has_above = above_idx >= 0
            has_below = below_idx < len(known_rows)

            if has_above and has_below:
                r_above = known_rows[above_idx]
                r_below = known_rows[below_idx]
                span = float(r_below - r_above)
                t = (r - r_above) / span
                out[r, col] = (1.0 - t) * canvas[r_above, col] + t * canvas[
                    r_below, col
                ]
            elif has_above:
                out[r, col] = canvas[known_rows[above_idx], col]
            else:
                out[r, col] = canvas[known_rows[below_idx], col]

    return np.clip(out, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------------------
# ProPainter fill (§5A, optional)
# ---------------------------------------------------------------------------


def _propainter_fill(
    canvas: np.ndarray,
    zero_mask: np.ndarray,
    frames: Optional[List[np.ndarray]] = None,
    device: str = "cpu",
) -> np.ndarray:
    """Fill zero-coverage canvas pixels using ProPainter video inpainting.

    Requires ``pip install propainter``.  Falls back to ``_nn_fill_zero_bg``
    when ProPainter is unavailable or inference fails.

    ProPainter expects a sequence of video frames with a per-frame binary
    mask marking the region to inpaint.  Here the canvas acts as a
    single-frame "video" and the zero_mask marks the missing pixels.

    Parameters
    ----------
    canvas : (H, W, 3) uint8 BGR canvas.
    zero_mask : (H, W) bool/uint8 — uncovered pixels to fill.
    frames : optional list of source frames for flow guidance.  When None,
        ProPainter runs in single-frame mode (no optical flow guidance).
    device : torch device string (default "cpu").
    """
    if ProPainterInference is None:
        return _nn_fill_zero_bg(canvas, zero_mask)
    try:
        model = ProPainterInference(device=device)
        mask_uint8 = (
            (zero_mask > 0).astype(np.uint8) * 255
            if zero_mask.dtype != bool
            else zero_mask.astype(np.uint8) * 255
        )
        result = model.inpaint(
            frames=[cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)],
            masks=[mask_uint8],
        )
        if result and isinstance(result[0], np.ndarray):
            return cv2.cvtColor(result[0], cv2.COLOR_RGB2BGR)
    except Exception as _e:
        print(f"[BgComplete] ProPainter unavailable ({_e}); using NN fill.")
    return _nn_fill_zero_bg(canvas, zero_mask)


# ---------------------------------------------------------------------------
# Multi-frame ProPainter completion (§3.13)
# ---------------------------------------------------------------------------


def _propainter_complete_frames(
    frames: List[np.ndarray],
    bg_masks: "List[Optional[np.ndarray]]",
    device: str = "cpu",
) -> List[np.ndarray]:
    """§3.13: Background-complete all selected frames using ProPainter.

    Runs ProPainter on the full sequence so that every foreground-masked pixel
    in every frame is replaced by a temporally coherent background estimate.
    The completed frames feed Stage 5 (phase correlation) and Stage 10
    (temporal median) to eliminate ghost strips from character-dominated rows.

    Requires ``pip install propainter``.  Falls back to per-frame NN fill when
    ProPainter is unavailable or inference fails.

    Parameters
    ----------
    frames : list of (H, W, 3) uint8 BGR frames (selected, normalised).
    bg_masks : per-frame bg mask — uint8, non-zero = background.  None = all bg.
    device : torch device string passed to ``ProPainterInference``.

    Returns
    -------
    List of (H, W, 3) uint8 BGR frames with foreground pixels inpainted.
    """

    def _nn_fallback() -> List[np.ndarray]:
        out: List[np.ndarray] = []
        for frame, mask in zip(frames, bg_masks):
            if mask is None:
                out.append(frame)
                continue
            fg = (mask <= 127).astype(np.uint8)
            if not fg.any():
                out.append(frame)
                continue
            out.append(_nn_fill_zero_bg(frame, fg))
        return out

    if ProPainterInference is None:
        return _nn_fallback()

    try:
        model = ProPainterInference(device=device)
        rgb_frames = [cv2.cvtColor(f, cv2.COLOR_BGR2RGB) for f in frames]
        h0, w0 = frames[0].shape[:2]
        masks_uint8: List[np.ndarray] = []
        for mask in bg_masks:
            if mask is None:
                masks_uint8.append(np.zeros((h0, w0), dtype=np.uint8))
            else:
                fg = (mask <= 127).astype(np.uint8) * 255
                masks_uint8.append(fg)

        result = model.inpaint(frames=rgb_frames, masks=masks_uint8)
        if result and len(result) == len(frames):
            return [cv2.cvtColor(r, cv2.COLOR_RGB2BGR) for r in result]
    except Exception as _e:
        print(
            f"[BgComplete] §3.13 ProPainter multi-frame failed ({_e}); using NN fill."
        )

    return _nn_fallback()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def complete_background(
    canvas: np.ndarray,
    valid_mask: np.ndarray,
    *,
    use_propainter: bool = False,
    min_rows: Optional[int] = None,
) -> np.ndarray:
    """Fill uncovered background pixels in the stitch canvas.

    Called after Stage 10 (temporal median) in ``pipeline.py`` when
    ``ASP_BG_COMPLETE`` is enabled.

    Parameters
    ----------
    canvas : (H, W, 3) uint8 BGR canvas from ``_render()``.
    valid_mask : (H, W) uint8 mask returned by ``_render()`` —
        255 = at least one frame covered this pixel; 0 = no coverage.
    use_propainter : if True, attempt ProPainter before NN fill.
    min_rows : minimum zero-coverage rows before running.  Defaults to
        ``ASP_BG_COMPLETE_MIN_ROWS`` (env, default 20).

    Returns
    -------
    (H, W, 3) uint8 canvas with zero-coverage regions filled.
    """
    _min = min_rows if min_rows is not None else _BG_COMPLETE_MIN_ROWS
    zero_mask = valid_mask == 0
    n_zero_rows = int(zero_mask.any(axis=1).sum())
    if n_zero_rows < _min:
        return canvas

    if use_propainter:
        return _propainter_fill(canvas, zero_mask)
    if _INTERP_BG_FILL:
        return _linear_interp_zero_bg(canvas, zero_mask)
    return _nn_fill_zero_bg(canvas, zero_mask)

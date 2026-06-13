"""
Laplacian-pyramid composite for animated vertical-scroll stitches.

For each canvas row the frame whose strip-centre is nearest supplies all
pixels (hard partition).  At ownership boundaries a Laplacian pyramid blend
routes the seam through flat cel-shaded regions via a DP energy path.
No photometric gain corrections are applied — the temporal median (Stage 9)
already ghost-removes frames and the pyramid blend is immune to the
brightness-banding artefacts produced by the earlier per-boundary LS gain
machinery.

Optimal boundary placement: for each adjacent frame pair the boundary is
moved (within ±SEARCH_RANGE rows of the midpoint) to the y-position where the
two warped frames are most photometrically similar, guided by background pixels
when available.

Adaptive feathering: the Laplacian blend half-width is scaled from the
photometric similarity score at the boundary, then capped by the natural
overlap between the two adjacent frames.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
from scipy.ndimage import minimum_filter1d as _min_filt1d

from backend.src.constants import (
    FEATHER_MAX,
    FEATHER_MIN,
    MULTISCALE_GAIN_SIGMA,
    SEARCH_RANGE,
    SEARCH_SLAB,
    FEATHER_TABLE,
    LUMINANCE_WEIGHTS,
)

# Stage 8.5 foreground pose registration toggle (see fg_register.py).
# Enabled by default; set ASP_FG_REGISTER=0 to disable for A/B comparison.
_FG_REGISTER_ENABLED = os.environ.get("ASP_FG_REGISTER", "1") != "0"

# ToonCrafter seam synthesis (§3.6B): when a seam escalates to single-pose
# fallback (post_warp_diff > 22 lum), synthesize a coherent intermediate frame
# using ToonCrafter (or cross-dissolve fallback) to eliminate the hard boundary.
# Enabled via ASP_TOONCRAFTER_SEAM=1 (default OFF — adds inference overhead).
# When enabled, synthesis is applied only to the single worst seam per run
# (highest post_warp_diff) to keep overhead bounded.
_TOONCRAFTER_SEAM = os.environ.get("ASP_TOONCRAFTER_SEAM", "0") != "0"

# §1.6C — Gradient-domain Poisson seam blend (S21).
# Replaces Laplacian blend with cv2.seamlessClone(NORMAL_CLONE) in a
# ±_POISSON_BAND_PX band around the DP seam path for normal (non-single-pose)
# seams.  Eliminates the brightness step at hard cuts without ghosting.
# Enabled via ASP_POISSON_SEAM=1 (default OFF — adds ~1–3 s per seam on CPU).
_POISSON_SEAM: bool = os.environ.get("ASP_POISSON_SEAM", "0") != "0"
_POISSON_BAND_PX: int = 20

# §1.4D — Multi-scale spatially-varying gain normalisation (S46).
# When enabled, replaces the single-scalar bg gain with a Gaussian-blur-derived
# per-pixel gain map so that non-uniform panel lighting (darker at top, lighter
# at bottom) is corrected per-region rather than by a global scalar.
# Enable via ASP_MULTISCALE_GAIN=1 (default OFF — scalar path is faster).
_MULTISCALE_GAIN: bool = os.environ.get("ASP_MULTISCALE_GAIN", "0") != "0"

# §1.4E — Background CDF histogram matching normalisation (S49).
# Replaces the per-frame scalar gain with a full tonal-distribution match:
# for each frame, a 256-entry CDF-matching LUT is derived from the background
# pixels of the frame vs the canvas reference and applied per-channel to the
# background region.  Handles exposure differences that a global scalar cannot
# correct (e.g. vignetting, panel-edge brightening).
# Enable via ASP_HISTOGRAM_MATCH=1 (default OFF; _MULTISCALE_GAIN takes priority).
_HISTOGRAM_MATCH: bool = os.environ.get("ASP_HISTOGRAM_MATCH", "0") != "0"

# §1.4F — Per-frame exposure outlier rejection (S50).
# Frames whose background median luminance deviates from the global median by
# more than _EXPOSURE_OUTLIER_THRESH luma units are excluded from gain
# normalisation (skipped in the same way as coherence-gate rejects).  The frame
# still contributes warped pixel content to the canvas; only the gain correction
# is suppressed to prevent extreme correction artefacts.
# Default 0.0 = disabled.  Recommended starting value: 60.0.
_EXPOSURE_OUTLIER_THRESH: float = float(
    os.environ.get("ASP_EXPOSURE_OUTLIER_THRESH", "0.0")
)
_SEAM_COLOR_GATE: float = float(
    os.environ.get("ASP_SEAM_COLOR_GATE", "0.0")
)
# §1.14C — Per-channel BGR Bhattacharyya seam gate (S59).
# When enabled, _check_seam_color_gate uses per-channel (B,G,R) histograms
# and returns min(score_B, score_G, score_R) rather than the greyscale score.
# Catches hue-shifted banding where B/G/R differ sharply but luminance is flat.
# Enable via ASP_SEAM_COLOR_GATE_BGR=1 (default OFF — greyscale path is faster).
_SEAM_COLOR_GATE_BGR: bool = os.environ.get("ASP_SEAM_COLOR_GATE_BGR", "0") != "0"

# §1.18 — Adaptive single-pose escalation threshold (S62).
# When enabled, the single-pose ghost-prevention threshold scales DOWN for wide
# feathers so that moderate post_warp_diff values (15–22 lum) still trigger
# escalation when the blend zone would be ≥ 300 px wide.
# Enable via ASP_ADAPTIVE_SP_THRESH=1 (default OFF — legacy fixed-threshold path).
_ADAPTIVE_SP_THRESH: bool = os.environ.get("ASP_ADAPTIVE_SP_THRESH", "0") != "0"

# §1.19 — Foreground-density-aware feather cap (S63).
# When the seam blend zone (±feather band around boundary) is dominated by fg
# pixels in either adjacent frame, a wide feather blends two different animation
# poses → double-image ghost.  Cap the feather to cap_px when fg fraction > threshold.
# Enable via ASP_FG_FEATHER_CAP=60 (px cap value; 0=off, the default).
_FG_FEATHER_CAP: int = int(os.environ.get("ASP_FG_FEATHER_CAP", "0"))
_FG_FEATHER_THRESH: float = float(os.environ.get("ASP_FG_FEATHER_THRESH", "0.60"))

# §1.20 — Tight-step preemptive single-pose escalation (S64).
# When the dominant-axis camera step between two adjacent frames is smaller than
# this threshold (px), skip ARAP registration entirely and immediately escalate
# to single-pose.  At tiny steps, the character occupies nearly the same rows in
# both frames but may be in a completely different animation pose — ARAP cannot
# reconcile that and the blend creates an unavoidable double-image.
# Enable via ASP_TIGHT_STEP_PX=30 (0=off, the default).
_TIGHT_STEP_PX: int = int(os.environ.get("ASP_TIGHT_STEP_PX", "0"))

# §1.21 — Post-composite seam luminance equalisation (S65).
# After all blending is complete, samples mean luminance above and below each
# seam boundary and applies a linear additive ramp over band_px rows to smooth
# visible luminance steps.  Targets the seam_coherence (SC) metric.
# Enable via ASP_SEAM_LUM_EQ=1 (default OFF).
_SEAM_LUM_EQ: bool = os.environ.get("ASP_SEAM_LUM_EQ", "0") != "0"

# §1.22 — Adaptive single-pose soft-edge width (S66).
# §1.15 (S15) always uses a fixed ±6px soft edge at single-pose seams regardless
# of the original feather width.  When a 300px feather is escalated to single-pose
# the jump from expected-300px-blend to 6px-soft-edge creates a visible step.
# When enabled, the soft-edge half-width scales up with the feather width, capped
# at max_px.  For feather ≤ ref_px the baseline 6px is returned unchanged.
# Enable via ASP_ADAPTIVE_SP_SOFT=1 (default OFF).
_ADAPTIVE_SP_SOFT: bool = os.environ.get("ASP_ADAPTIVE_SP_SOFT", "0") != "0"

# §1.23 — SemanticStitch hard corridor barrier (S67).
# S33 (§3.15A) raised fg-dominated columns to cost=2.0 (soft barrier).  A
# cost-2.0 column is 2× more expensive than a cost-1.0 fg-interior column, so
# the DP is *discouraged* but not *prevented* from routing through it.  When a
# background corridor exists (at least one non-fg-dominated column), setting the
# barrier to a very large finite value (default 1e6) makes the DP 1e6× more
# expensive than a clean bg path → effectively forces background-only seams.
# Falls back to cost=2.0 (S33 behaviour) when no corridor exists.
# Enable via ASP_SEAM_HARD_BARRIER=1 (default OFF).
_SEAM_HARD_BARRIER: bool = os.environ.get("ASP_SEAM_HARD_BARRIER", "0") != "0"
_SEAM_HARD_BARRIER_COST: float = float(os.environ.get("ASP_SEAM_HARD_BARRIER_COST", "1e6"))

# §1.25: Seam path smoothing — median-filter the DP traceback to remove column jitter.
# Raw argmin traceback can produce single-pixel sideways jumps that create diagonal
# aliasing bands at the seam boundary.  A 1-D median filter removes these without
# altering the overall routing.  Window must be odd; 0 or 1 disables smoothing.
# Enable via ASP_SEAM_SMOOTH_WINDOW=5 (default 0 = off).
_SEAM_SMOOTH_WINDOW: int = int(os.environ.get("ASP_SEAM_SMOOTH_WINDOW", "0"))

# §1.26: Seam path boundary clamp — keep the seam at least `margin` rows from zone
# top/bottom edges.  When the seam is at y=0 or y=zone_h-1, the feather blend has no
# room to ramp and creates a hard edge artefact at the zone boundary.  Clamping to
# [margin, zone_h-1-margin] prevents this.  margin=0 disables the clamp.
# Enable via ASP_SEAM_MARGIN=3 (default 0 = off).
_SEAM_MARGIN: int = int(os.environ.get("ASP_SEAM_MARGIN", "0"))

# §1.27: Background pixel coverage minimum for normalisation.  The normalisation loop
# already guards with `len(bg_px) >= 200` before applying gain correction.  This flag
# makes that 200-pixel floor configurable — useful when the character fills most of the
# frame (sparse-bg scenes) and a tighter or looser threshold is needed.
# Default 0 → falls back to the built-in 200-pixel floor.
_BG_NORM_MIN_PX: int = int(os.environ.get("ASP_BG_NORM_MIN_PX", "0"))

# §1.28: Seam path instability escalation.  After the DP seam path is computed, measure
# the standard deviation of path column values.  High std indicates a chaotic path where
# many columns have nearly equal energy — blending such a seam produces zigzag artefacts
# even after §1.25 smoothing.  When std > threshold, escalate the boundary to single-pose.
# Default 0.0 = off.  Recommend 20.0 (paths with 20px std are visibly unstable).
_SEAM_INSTABILITY_THRESH: float = float(os.environ.get("ASP_SEAM_INSTABILITY_THRESH", "0.0"))

# §1.31: Seam foreground-penetration escalation.  After the DP seam path is resolved,
# sample the pixel at each column of the path.  When the fraction of columns where the
# seam cuts through foreground (any-channel > 0 in either frame's zone) exceeds this
# threshold, escalate to single-pose.  Complements §1.23/§3.15 (cost barriers that
# prevent fg routing) by catching cases where the DP routes through fg anyway (e.g.,
# when the entire overlap region is foreground and no background corridor exists).
# Default 0.0 = off.  Recommend 0.7 (>70% fg penetration → character seam, escalate).
_SEAM_FG_PENETRATION_MAX: float = float(os.environ.get("ASP_SEAM_FG_PENETRATION_MAX", "0.0"))

# §1.30: Minimum zone height guard.  When a blend zone is shorter than this many
# rows the boundary clamp (§1.26) leaves at most one valid seam row, the feather
# blend has no headroom, and the DP adds ~1ms overhead for no quality benefit.
# Setting the flag > 0 escalates the boundary directly to single-pose before the
# DP runs.  Default 0 = off.  Recommend 20 (matches the typical S15/S16 soft-edge
# band width; anything narrower cannot be blended cleanly regardless of DP).
_ZONE_MIN_HEIGHT: int = int(os.environ.get("ASP_ZONE_MIN_HEIGHT", "0"))


def _zone_is_degenerate(zone_h: int, min_height: int = 20) -> bool:
    """§1.30: Return True when *zone_h* is too small for a meaningful DP seam cut.

    Below *min_height* the §1.26 boundary clamp collapses the valid seam range to
    a single row, the DSFN feather has no headroom, and the DP cost surface is
    so compressed that it produces a constant-row path regardless of content.
    Escalating to single-pose avoids the DP entirely and lets §1.15 soft-edge
    handle the residual step.

    Parameters
    ----------
    zone_h:
        Height of the blend zone in pixels (rows).
    min_height:
        Minimum row count below which the zone is considered degenerate.
        0 disables the check.

    Returns
    -------
    bool
        True iff the zone is degenerate (too short for blending).
    """
    if min_height <= 0:
        return False
    return zone_h < min_height


def _seam_corridor_exists(cost: np.ndarray, fg_thresh: float = 0.5) -> bool:
    """§1.23: True iff the cost map has both dominated and non-dominated columns.

    A 'corridor' exists when at least one column is fg-dominated AND at least one
    column is not — meaning the DP can be steered into the non-dominated columns
    without becoming infeasible.  Returns False when all columns are dominated
    (no corridor) or when no columns are dominated (no need for a barrier).
    """
    fg_col_frac = (cost >= 1.0).mean(axis=0)
    dominated = fg_col_frac > fg_thresh
    return bool(dominated.any() and not dominated.all())


def _smooth_seam_path(path: np.ndarray, window: int = 5) -> np.ndarray:
    """§1.25: Remove column jitter from a DP seam-cut path via 1-D median filtering.

    The argmin traceback in ``_seam_cut()`` can produce single-pixel sideways
    jumps — each step is locally optimal but consecutive steps may oscillate
    between adjacent columns, creating a fine diagonal aliasing band at the
    seam boundary.  A 1-D median filter of odd window *window* removes these
    short-range oscillations without changing the long-range seam routing.

    Parameters
    ----------
    path:
        1-D int32 array of length W; ``path[x]`` is the y-offset for column x.
    window:
        Median filter half-window (total kernel size = window, must be ≥ 1).
        Window ≤ 1 returns the path unchanged (no-op).  Even windows are
        incremented by 1 so the kernel is always symmetric.

    Returns
    -------
    np.ndarray
        Smoothed path, same dtype and shape as *path*.
    """
    if window <= 1 or len(path) == 0:
        return path
    w = window if window % 2 == 1 else window + 1
    from scipy.ndimage import median_filter as _mf
    return _mf(path.astype(np.float32), size=w).astype(np.int32)


def _clamp_seam_path(path: np.ndarray, zone_h: int, margin: int = 3) -> np.ndarray:
    """§1.26: Clamp a DP seam path to stay within [margin, zone_h-1-margin].

    When the seam arrives at y=0 or y=zone_h-1, the feather blend has no rows
    left to ramp and degenerates into a hard cut at the zone boundary — a
    different artefact from the one §1.25 targets.  Clamping keeps the seam
    inside the zone interior so the feather always has at least *margin* rows
    of valid blending headroom on both sides of the cut.

    Parameters
    ----------
    path:
        1-D int32 array of length W; ``path[x]`` is the y-offset for column x.
    zone_h:
        Height of the composite zone (must be > 2 * margin for clamping to
        be meaningful).
    margin:
        Minimum distance (rows) between the seam and the top/bottom zone
        boundary.  margin ≤ 0 returns the path unchanged.

    Returns
    -------
    np.ndarray
        Clamped path (same dtype as *path*).  When ``zone_h <= 2 * margin``
        the path is returned unchanged to avoid inverting the clamp bounds.
    """
    if margin <= 0 or len(path) == 0:
        return path
    lo = margin
    hi = zone_h - 1 - margin
    if lo > hi:
        return path
    return np.clip(path, lo, hi).astype(path.dtype)


def _has_sufficient_bg(
    bg_sel: np.ndarray,
    min_px: int = 200,
) -> bool:
    """§1.27: Return True iff the background mask has at least *min_px* True pixels.

    The normalisation loop requires enough background pixels to compute a
    reliable mean luminance for gain estimation.  Below *min_px* the sample
    is too sparse and the estimated gain is noisy — particularly when the
    character fills most of the frame (portrait shots, tight cropping).

    Parameters
    ----------
    bg_sel:
        Boolean or uint8 mask; True/nonzero = background pixel.
    min_px:
        Minimum number of background pixels required for reliable estimation.
        Defaults to 200 (the historical hardcoded floor).

    Returns
    -------
    bool
        True when the background coverage is sufficient for normalisation.
    """
    if bg_sel is None:
        return False
    count = int(np.count_nonzero(bg_sel))
    return count >= max(1, min_px)


def _seam_path_std(path: np.ndarray) -> float:
    """§1.28: Return the standard deviation of a seam path's column values.

    A high standard deviation indicates that the DP seam oscillates widely
    across the zone height — signalling that no stable low-cost path exists
    and that the blend will produce visible diagonal banding.  A stable seam
    (routing along a consistent row) has std near zero; a chaotic seam that
    spans the full zone height has std approaching ``zone_h / 3``.

    Parameters
    ----------
    path:
        1-D numeric array; ``path[x]`` is the y-offset for column x.

    Returns
    -------
    float
        Standard deviation of the path values.  Returns 0.0 for empty paths.
    """
    if len(path) == 0:
        return 0.0
    return float(np.std(path))


def _seam_fg_penetration(
    path: np.ndarray,
    fa_zone: np.ndarray,
    fb_zone: np.ndarray,
) -> float:
    """§1.31: Fraction of seam columns where the path cuts through foreground.

    For each column x, the seam pixel is at row ``path[x]``.  A pixel is
    foreground if *any* channel is > 0.  The function returns the fraction
    of columns where the seam pixel is foreground in at least one of the two
    zones.

    Parameters
    ----------
    path:
        1-D int array of shape (W,); ``path[x]`` = zone row at column *x*.
    fa_zone:
        (zone_h, W, C) uint8 array for frame A's zone.
    fb_zone:
        (zone_h, W, C) uint8 array for frame B's zone.

    Returns
    -------
    float
        Fraction in [0, 1].  0.0 for empty path or zero-width zones.
    """
    if len(path) == 0 or fa_zone.shape[1] == 0:
        return 0.0
    W = len(path)
    zone_h = fa_zone.shape[0]
    cols = np.arange(W)
    rows = np.clip(path, 0, zone_h - 1)
    in_fg_a = fa_zone[rows, cols].max(axis=1) > 0
    in_fg_b = fb_zone[rows, cols].max(axis=1) > 0
    return float((in_fg_a | in_fg_b).sum()) / W


def _adaptive_sp_soft_px(
    feather_width: int,
    base_px: int = 6,
    max_px: int = 30,
    ref_px: int = 80,
) -> int:
    """§1.22: Adaptive single-pose soft-edge half-width scaled by original feather.

    Returns *base_px* for feathers at or below *ref_px*, scaling up linearly for
    wider feathers and capping at *max_px*.  Ensures the feather floor (base_px)
    is always returned for degenerate inputs (feather_width ≤ 0).
    """
    return min(max_px, max(base_px, base_px * max(feather_width, 0) // max(ref_px, 1)))


def _fg_density_feather_cap(
    feathers: np.ndarray,
    boundaries: "List[float]",
    warped_bg: "List[Optional[np.ndarray]]",
    order: "List[int]",
    cap_px: int,
    fg_thresh: float = 0.60,
) -> np.ndarray:
    """§1.19: Cap feather in fg-dominated seam zones (S63).

    For each boundary k, checks the fg pixel fraction in the ±feather[k] row
    band around boundaries[k] in canvas space for both adjacent frames.  When
    the maximum fg fraction across the two frames exceeds *fg_thresh*, the
    feather is reduced to *cap_px*.  Masks of None (no BiRefNet mask available)
    are treated as all-background (fg_frac=0.0) so the cap never fires without
    a mask.

    feathers is returned as a copy (input not mutated).
    """
    feathers = feathers.copy()
    n_b = len(boundaries)
    for k in range(n_b):
        fw = int(feathers[k])
        if fw <= cap_px:
            continue  # already narrow — skip
        by = int(boundaries[k])
        fi_a = int(order[k])
        fi_b = int(order[k + 1])
        fg_frac = 0.0
        for fi in (fi_a, fi_b):
            if fi >= len(warped_bg) or warped_bg[fi] is None:
                continue
            H_canvas = warped_bg[fi].shape[0]
            y0 = max(0, by - fw)
            y1 = min(H_canvas, by + fw)
            band = warped_bg[fi][y0:y1]
            if band.size == 0:
                continue
            fg_frac = max(fg_frac, 1.0 - float(band.mean()))
        if fg_frac > fg_thresh:
            feathers[k] = cap_px
    return feathers


def _compute_seam_step_size(
    fi_a: int,
    fi_b: int,
    affines: "List[np.ndarray]",
) -> float:
    """§1.20: Dominant-axis camera step between two frame positions (S64).

    Returns ``max(|ty_b − ty_a|, |tx_b − tx_a|)`` — the dominant-axis pixel
    displacement between the two frames' canvas positions.  Returns
    ``float("inf")`` when either frame index is out of range.
    """
    if fi_a >= len(affines) or fi_b >= len(affines):
        return float("inf")
    dy = abs(float(affines[fi_b][1, 2]) - float(affines[fi_a][1, 2]))
    dx = abs(float(affines[fi_b][0, 2]) - float(affines[fi_a][0, 2]))
    return max(dy, dx)


def _seam_lum_equalize(
    canvas: np.ndarray,
    boundaries: "List[float]",
    band_px: int = 20,
    min_step: float = 5.0,
) -> np.ndarray:
    """§1.21: Post-composite seam luminance equalisation (S65).

    For each seam boundary, samples mean greyscale luminance in *band_px*-row
    reference windows above and below the boundary (with a 3-row guard to
    avoid artefacts at the seam itself).  When ``|below_mean − above_mean|``
    exceeds *min_step* lum units, applies a linear additive ramp over
    *band_px* rows starting at the boundary, subtracting the step from the
    below zone so it gradually blends into the above zone.  All BGR channels
    are shifted equally (luminance correction, chrominance unchanged).

    Returns a uint8 copy of *canvas*.
    """
    out = canvas.astype(np.float32)
    H = canvas.shape[0]
    luma = cv2.cvtColor(canvas, cv2.COLOR_BGR2GRAY).astype(np.float32)
    guard = 3
    for by_f in boundaries:
        by = int(by_f)
        a0 = max(0, by - band_px - guard)
        a1 = max(0, by - guard)
        b0 = min(H, by + guard)
        b1 = min(H, by + band_px + guard)
        if a1 <= a0 or b1 <= b0:
            continue
        above_mean = float(luma[a0:a1].mean())
        below_mean = float(luma[b0:b1].mean())
        step = below_mean - above_mean
        if abs(step) < min_step:
            continue
        ry0, ry1 = by, min(H, by + band_px)
        rlen = ry1 - ry0
        if rlen <= 0:
            continue
        t = np.linspace(0.0, 1.0, rlen, dtype=np.float32)
        corr = (-step * (1.0 - t)).reshape(-1, 1, 1)
        out[ry0:ry1] = np.clip(out[ry0:ry1] + corr, 0.0, 255.0)
    return out.astype(np.uint8)


def _adaptive_sp_threshold(
    feather_width: int,
    base_threshold: float = 22.0,
    min_threshold: float = 12.0,
    feather_reference: int = 80,
) -> float:
    """§1.18: Adaptive single-pose escalation threshold (S62).

    Scales the post_warp_diff escalation threshold down for wide feathers so
    that moderate luminance discrepancies still trigger single-pose mode when
    the blend zone would produce a long double-image ghost.

    feather=80  → 22.0 (unchanged, same as hardcoded baseline)
    feather=146 → 12.0 (floor reached)
    feather=300 → 12.0 (floor)
    """
    return max(min_threshold, base_threshold * (feather_reference / max(feather_width, 1)))


def _seam_color_similarity(
    img: np.ndarray,
    k: int,
    n_strips: int,
    band_px: int = 50,
) -> float:
    """§1.14B: Bhattacharyya colour similarity across seam boundary k.

    Splits *img* into *n_strips* equal-height zones.  Seam k is the boundary
    between zone k and zone k+1 (0-indexed).  Returns ``1 - HISTCMP_BHATTACHARYYA``
    between normalised greyscale histograms of the *band_px*-row windows
    immediately above and below the boundary: 1.0 = identical distributions,
    0.0 = completely disjoint.  Returns 1.0 when the band is too small (<10 rows)
    so trivially thin boundaries never trigger the gate.
    """
    H = img.shape[0]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    zone_h = H / n_strips
    boundary_y = int(round(zone_h * (k + 1)))
    top = gray[max(0, boundary_y - band_px):boundary_y]
    bot = gray[boundary_y:min(H, boundary_y + band_px)]
    if top.shape[0] < 10 or bot.shape[0] < 10:
        return 1.0
    h_top = cv2.calcHist([top], [0], None, [256], [0, 256])
    h_bot = cv2.calcHist([bot], [0], None, [256], [0, 256])
    cv2.normalize(h_top, h_top)
    cv2.normalize(h_bot, h_bot)
    dist = float(cv2.compareHist(h_top, h_bot, cv2.HISTCMP_BHATTACHARYYA))
    return float(np.clip(1.0 - dist, 0.0, 1.0))


def _seam_color_similarity_bgr(
    img: np.ndarray,
    k: int,
    n_strips: int,
    band_px: int = 50,
) -> float:
    """§1.14C: Per-channel Bhattacharyya similarity across seam boundary k.

    Like ``_seam_color_similarity`` but computes separate normalised histograms
    for each of the B, G and R channels and returns ``min(score_B, score_G,
    score_R)``.  Any single channel with a severe distribution mismatch drives
    the score down even when the luminance distribution is identical — catches
    warm-orange vs cool-blue banding that greyscale Bhattacharyya misses.

    Returns 1.0 when the band is too small (<10 rows) or the input has no
    colour channels.
    """
    H = img.shape[0]
    if img.ndim < 3:
        return _seam_color_similarity(img, k, n_strips, band_px=band_px)
    zone_h = H / n_strips
    boundary_y = int(round(zone_h * (k + 1)))
    top = img[max(0, boundary_y - band_px):boundary_y]
    bot = img[boundary_y:min(H, boundary_y + band_px)]
    if top.shape[0] < 10 or bot.shape[0] < 10:
        return 1.0
    min_score = 1.0
    for ch in range(3):
        h_top = cv2.calcHist([top], [ch], None, [256], [0, 256])
        h_bot = cv2.calcHist([bot], [ch], None, [256], [0, 256])
        cv2.normalize(h_top, h_top)
        cv2.normalize(h_bot, h_bot)
        dist = float(cv2.compareHist(h_top, h_bot, cv2.HISTCMP_BHATTACHARYYA))
        min_score = min(min_score, float(np.clip(1.0 - dist, 0.0, 1.0)))
    return min_score


def _check_seam_color_gate(
    img: np.ndarray,
    n_strips: int,
    thresh: float = _SEAM_COLOR_GATE,
    band_px: int = 50,
    use_bgr: bool = False,
) -> "Optional[int]":
    """§1.14B/C: Returns index of the worst seam below *thresh*, or None.

    Evaluates per-seam colour similarity for every inter-strip seam.  When
    *use_bgr* is True uses ``_seam_color_similarity_bgr`` (per-channel B/G/R
    minimum); otherwise uses the greyscale ``_seam_color_similarity``.
    Returns the 0-indexed seam with the lowest score if it falls below *thresh*,
    or ``None`` when *n_strips* ≤ 1, *thresh* ≤ 0, or all seams pass.
    """
    if n_strips <= 1 or thresh <= 0.0:
        return None
    sim_fn = _seam_color_similarity_bgr if use_bgr else _seam_color_similarity
    worst_k: Optional[int] = None
    worst_score = thresh
    for k in range(n_strips - 1):
        score = sim_fn(img, k, n_strips, band_px=band_px)
        if score < worst_score:
            worst_score = score
            worst_k = k
    return worst_k


def _multiscale_gain_map(
    frame: np.ndarray,
    reference: np.ndarray,
    bg_mask: np.ndarray,
    sigma: float = MULTISCALE_GAIN_SIGMA,
    gain_min: float = 0.5,
    gain_max: float = 2.0,
) -> np.ndarray:
    """§1.4D: Spatially-varying gain map from low-frequency luminance ratio.

    Computes per-pixel gain = ref_lum_low / frame_lum_low where both are
    Gaussian-blurred with *sigma* px.  Only background pixels (``bg_mask``)
    are used as sources; the blur propagates bg gains into fg regions so the
    full gain map covers the entire frame.

    Parameters
    ----------
    frame, reference : uint8 (H, W, 3) BGR arrays of equal shape.
    bg_mask          : bool (H, W), True = background pixel.
    sigma            : Gaussian σ in pixels.
    gain_min, gain_max : output clamp bounds.

    Returns
    -------
    float32 (H, W) gain map, clamped to [gain_min, gain_max].
    """
    frame_lum = frame.astype(np.float32).dot(LUMINANCE_WEIGHTS)
    ref_lum = reference.astype(np.float32).dot(LUMINANCE_WEIGHTS)

    # Zero-out fg so the Gaussian spreads only bg information
    frame_bg = np.where(bg_mask, frame_lum, 0.0).astype(np.float32)
    ref_bg = np.where(bg_mask, ref_lum, 0.0).astype(np.float32)

    frame_blurred = cv2.GaussianBlur(frame_bg, (0, 0), sigma)
    ref_blurred = cv2.GaussianBlur(ref_bg, (0, 0), sigma)

    gain = np.where(frame_blurred > 1.0, ref_blurred / (frame_blurred + 1e-3), 1.0)
    return np.clip(gain, gain_min, gain_max).astype(np.float32)


def _diff_to_feather(diff: float) -> int:
    for threshold, feather in FEATHER_TABLE:
        if diff <= threshold:
            return feather
    return FEATHER_MIN


def _gain_to_min_feather(gain_diff: float) -> int:
    """§1.6B: Minimum feather width from luminance gain difference (S22).

    When adjacent frames required significantly different gain corrections the
    normalization residual leaves a brightness step proportional to
    |gain_A − gain_B|.  Returns a floor feather wide enough to blend it:
    max(40, int(gain_diff × 300)), capped at 120 px.
    """
    return min(120, max(40, int(gain_diff * 300)))


def _find_optimal_boundaries(
    warped_list: List[np.ndarray],
    order: np.ndarray,
    initial_boundaries: np.ndarray,
    H: int,
    W: int,
    bg_masks: Optional[List[Optional[np.ndarray]]] = None,
    affines: Optional[List[np.ndarray]] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Move each boundary to the y-position (within ±SEARCH_RANGE of the midpoint)
    where the two adjacent warped frames are most photometrically similar.

    When bg_masks and affines are provided the score is computed over background
    pixels (static, unaffected by character pose).  Falls back to all-pixel diff
    when background pixel count is insufficient.

    Returns (optimised_boundaries, diff_scores), both shape (N-1,).
    """
    len(order)
    optimised = initial_boundaries.copy()
    diffs = np.full(len(initial_boundaries), float("inf"))

    # S17: Adaptive boundary search range.  For pure vertical-scroll sequences
    # (horizontal tx spread < 5 px) the optimal boundary is always very close
    # to the midpoint — a ±100 px window finds it safely and cuts 60 % of the
    # candidate evaluations for sparse sequences.  For diagonal/2D motion the
    # full ±SEARCH_RANGE is needed to reach the similarity minimum.
    _effective_range = SEARCH_RANGE
    if affines is not None and len(order) >= 2:
        _txs = np.array(
            [float(affines[int(order[i])][0, 2]) for i in range(len(order))],
            dtype=np.float32,
        )
        if float(np.ptp(_txs)) < 5.0:
            _effective_range = 100

    warped_bgs: List[Optional[np.ndarray]] = [None] * (max(order) + 1)
    if bg_masks is not None and affines is not None:
        for i in range(len(order)):
            fi = int(order[i])
            if bg_masks[fi] is not None:
                warped_bgs[fi] = (
                    cv2.warpAffine(
                        bg_masks[fi].astype(np.uint8),
                        affines[fi],
                        (W, H),
                        flags=cv2.INTER_NEAREST,
                        borderMode=cv2.BORDER_CONSTANT,
                        borderValue=0,
                    )
                    > 127
                )

    for k, by in enumerate(initial_boundaries):
        fi_a = int(order[k])
        fi_b = int(order[k + 1])

        lo_limit = int(optimised[k - 1]) + 2 * SEARCH_SLAB + 1 if k > 0 else SEARCH_SLAB
        hi_limit = (
            int(initial_boundaries[k + 1]) - 2 * SEARCH_SLAB - 1
            if k < len(initial_boundaries) - 1
            else H - SEARCH_SLAB - SEARCH_SLAB
        )

        y_lo = max(lo_limit, int(by) - _effective_range)
        y_hi = min(hi_limit, int(by) + _effective_range)

        best_y = int(by)
        best_diff = float("inf")
        best_score = float("inf")

        bg_a = warped_bgs[fi_a]
        bg_b = warped_bgs[fi_b]

        for y_cand in range(y_lo, min(y_hi, H - SEARCH_SLAB)):
            slab_a = warped_list[fi_a][y_cand : y_cand + SEARCH_SLAB].astype(np.float32)
            slab_b = warped_list[fi_b][y_cand : y_cand + SEARCH_SLAB].astype(np.float32)
            all_valid = (slab_a.max(axis=2) > 0) & (slab_b.max(axis=2) > 0)
            if all_valid.sum() < 50:
                continue

            all_d = float(np.abs(slab_a - slab_b).mean(axis=2)[all_valid].mean())

            bg_d = None
            if bg_a is not None and bg_b is not None:
                bg_cand = (
                    bg_a[y_cand : y_cand + SEARCH_SLAB]
                    & bg_b[y_cand : y_cand + SEARCH_SLAB]
                    & all_valid
                )
                if bg_cand.sum() >= 50:
                    bg_d = float(np.abs(slab_a - slab_b).mean(axis=2)[bg_cand].mean())

            score = (0.4 * bg_d + 0.6 * all_d) if bg_d is not None else all_d

            if score < best_score:
                best_score = score
                best_diff = bg_d if bg_d is not None else all_d
                best_y = y_cand + SEARCH_SLAB // 2

        half = SEARCH_SLAB // 2
        y0_f = max(0, best_y - half)
        y1_f = min(H - 1, best_y + half)
        sa = warped_list[fi_a][y0_f:y1_f].astype(np.float32)
        sb = warped_list[fi_b][y0_f:y1_f].astype(np.float32)
        av = (sa.max(axis=2) > 0) & (sb.max(axis=2) > 0)
        total_diff = (
            float(np.abs(sa - sb).mean(axis=2)[av].mean())
            if av.sum() >= 10
            else best_diff
        )
        feather_metric = (
            best_diff if (best_diff < 20.0 and total_diff < 20.0) else total_diff
        )

        optimised[k] = float(best_y)
        diffs[k] = feather_metric
        feather = _diff_to_feather(feather_metric)
        moved = best_y - int(by)
        print(
            f"[Stitch]     Boundary {k} (frames {fi_a}/{fi_b}): "
            f"{int(by)} → {best_y} (Δ={moved:+d}, bg_diff={best_diff:.1f}, "
            f"total_diff={total_diff:.1f}, feather={feather}px)"
        )

    return optimised, diffs


def _seam_cut(
    img1: np.ndarray,
    img2: np.ndarray,
    edge_weight: float = 15.0,
    sem_cost: Optional[np.ndarray] = None,
    sem_weight: float = 200.0,
) -> np.ndarray:
    """
    DP seam cut that strongly avoids outlines in *either* frame.

    Energy = diff(img1,img2) + grad(diff) + edge_weight*(edges_in_img1 + edges_in_img2)
             + sem_weight * sem_cost   (P2.4 — character boundary avoidance)

    Returns path[x] = y-offset in [0, h-1] for the minimum-energy horizontal
    cut running left→right across the (h × W × 3) slices.
    """
    diff = cv2.absdiff(img1, img2).astype(np.float32).mean(axis=2)
    gx_d = cv2.Sobel(diff, cv2.CV_32F, 1, 0, ksize=3)
    gy_d = cv2.Sobel(diff, cv2.CV_32F, 0, 1, ksize=3)
    energy = diff + 0.5 * (np.abs(gx_d) + np.abs(gy_d))

    for img in (img1, img2):
        gray = img.astype(np.float32).mean(axis=2)
        gx_i = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy_i = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        energy += edge_weight * (np.abs(gx_i) + np.abs(gy_i))

    # P2.4 — Semantic character boundary avoidance
    if sem_cost is not None and sem_cost.shape == energy.shape:
        energy += sem_weight * sem_cost

    # Transpose (h, W) → (W, h) so DP runs left→right; path[x] = y-offset
    E = energy.T.copy()
    W_e, h_e = E.shape

    # §1.5A: Vectorized DP forward pass.
    # minimum_filter1d(row, size=3) computes min(row[j-1], row[j], row[j+1])
    # at every j with cval=inf boundaries — equivalent to the previous
    # per-iteration left/right array allocations but runs as a compiled C kernel.
    for i in range(1, W_e):
        E[i] += _min_filt1d(E[i - 1], size=3, mode="constant", cval=np.inf)

    # Traceback: avoid per-step Python list allocation by using slice argmin.
    path = np.empty(W_e, dtype=np.int32)
    j = int(E[W_e - 1].argmin())
    path[W_e - 1] = j
    for i in range(W_e - 2, -1, -1):
        j_lo = max(0, j - 1)
        j_hi = min(h_e, j + 2)  # exclusive
        j = j_lo + int(E[i, j_lo:j_hi].argmin())
        path[i] = j
    # §1.25: smooth jitter when flag is enabled
    if _SEAM_SMOOTH_WINDOW > 1:
        path = _smooth_seam_path(path, _SEAM_SMOOTH_WINDOW)
    # §1.26: clamp seam away from zone top/bottom edges
    if _SEAM_MARGIN > 0:
        path = _clamp_seam_path(path, h_e, _SEAM_MARGIN)
    return path  # path[x] in [0, zone_h-1]


def _soft_seam_weight(
    fa_zone: np.ndarray,
    fb_zone: np.ndarray,
    path_local: np.ndarray,
    zone_h: int,
    W: int,
    sigma: float = 15.0,
    diffuse_sigma: float = 20.0,
    bg_mask_a: Optional[np.ndarray] = None,
    bg_mask_b: Optional[np.ndarray] = None,
) -> np.ndarray:
    """
    P2.5 / S17+S20 — Spatially-adaptive seam blend weight (DSFN technique).

    Returns (zone_h, W) float32 weight in [0, 1]:
      1.0 → fa_zone,  0.0 → fb_zone.

    S17: blend radius is now *per-pixel* rather than per-column-average.
    Each pixel gets a blend ramp proportional to its own local photometric
    similarity: background pixels (high similarity) get a wide, smooth
    transition; foreground pixels (low similarity at character edges) get a
    narrow cut automatically, without any separate fg-mask branch.  This is
    strictly more adaptive than the previous per-column mean — a column
    containing background rows at top and a character edge at the bottom row
    now gives those rows independently-sized ramps instead of the same average.

    S20: when *bg_mask_a* and *bg_mask_b* are provided, fg-vs-fg overlap pixels
    have their diffused similarity zeroed **after** the Gaussian diffusion step.
    This prevents background similarity from bleeding into character-vs-character
    overlap regions through the blur kernel.  Background pixels near the fg
    boundary still receive blended similarity from their neighbours, preserving
    the smooth background→edge gradient; only pixels where BOTH frames classify
    the pixel as foreground are forced to the narrow ramp (min_ramp_bg).
    """
    # Per-pixel L1 distance, mean over channels → (zone_h, W)
    diff = np.abs(fa_zone.astype(np.float32) - fb_zone.astype(np.float32)).mean(axis=2)
    # Similarity field: 1 where frames agree, 0 where they differ strongly
    similarity = np.exp(-diff / max(sigma, 1.0))
    # Anisotropic diffusion: Gaussian blur propagates similarity from flat areas
    sim_diffused = cv2.GaussianBlur(
        similarity, (0, 0), sigmaX=diffuse_sigma, sigmaY=diffuse_sigma
    )
    # S20: zero-out fg-vs-fg pixels *after* diffusion so that background
    # similarity cannot diffuse into character-vs-character overlap regions.
    # bg_mask: True = background pixel.  Only modifies pixels where BOTH frames
    # classify the pixel as foreground; bg-side edge pixels are untouched.
    if bg_mask_a is not None and bg_mask_b is not None:
        both_fg = (~bg_mask_a.astype(bool)) & (~bg_mask_b.astype(bool))
        if both_fg.any():
            sim_diffused[both_fg] = 0.0

    # S17: per-pixel blend ramp — each pixel drives its own transition width.
    # min_ramp_bg (10px) for low-similarity pixels; zone_h * 0.35 for high.
    min_ramp_bg = 10.0
    max_ramp_bg = max(min_ramp_bg + 1.0, zone_h * 0.35)
    ramp = (min_ramp_bg + sim_diffused * (max_ramp_bg - min_ramp_bg)).astype(
        np.float32
    )  # (zone_h, W) — was (1, W) via per-column mean before S17

    ys = np.arange(zone_h, dtype=np.float32)[:, np.newaxis]  # (zone_h, 1)
    seam_y = path_local[np.newaxis, :].astype(np.float32)    # (1, W)
    dist = ys - seam_y                                         # (zone_h, W)
    weight = np.clip(0.5 - dist / (2.0 * ramp), 0.0, 1.0).astype(np.float32)
    return weight


def _build_seam_cost_map(
    canvas_zone: np.ndarray,
    bg_mask_a: Optional[np.ndarray],
    bg_mask_b: Optional[np.ndarray],
    dilate_px: int = 15,
    barrier_cost: Optional[float] = None,
    exclusion_masks: Optional[List[np.ndarray]] = None,
) -> np.ndarray:
    """
    P2.4 — Per-pixel seam cost map using character boundary avoidance (§1.6A S19).

    Issue 10A3 — exclusion_masks: list of uint8 (H_zone, W) masks (255=exclude).
    Each mask pixel where value > 127 gets cost=1e6 (hard barrier), forcing the
    DP seam to route around the named region. Generated by
    ``_detect_exclusion_mask(frame, "right arm")`` in grounding.py and injected
    after natural-language seam routing in the HITL MaskReviewDialog.

    Generates high cost near foreground character edges (where BiRefNet says
    the pixel belongs to a character) so the DP seam is routed around them.

    Tiered cost structure — creates a gradient that pulls the DP toward
    background corridors (§1.6A):
      Tier 1 — fg interior: cost = 1.0.  With sem_weight=200 in
      ``_seam_cut()``, every fg-interior pixel costs ≈ 200 energy units vs
      background pixels at ≈ 10–50.  Strongly deters the seam from
      bisecting the character body.
      Tier 2 — dilated fg edge buffer: cost = 0.5 (half of interior).
      Background pixels within ``dilate_px`` of any fg edge pay 100 energy —
      less than interior but more than clean background.  This gradient
      steers the DP THROUGH the edge-buffer zone toward background corridors,
      rather than treating the buffer identically to the body interior.

    Before S19, Tier 2 also used cost=1.0 (same as interior), so the DP had
    no incentive to route through the edge buffer on its way to background.

    If the character fills the full width and there is no all-background path,
    the DP gracefully degrades: it finds the minimum-cost path through the
    character body at its thinnest point.

    Parameters
    ----------
    canvas_zone : (H_zone, W, 3) uint8 slice from the overlap zone.
    bg_mask_a/b : uint8 (H, W) background masks (255=background) for the two frames,
                  already warped to canvas space, sliced to the zone rows.
    dilate_px   : avoidance radius in pixels around foreground edges.
    barrier_cost: cost applied to fg-dominated columns when a background corridor
                  exists (§1.23). *None* → uses module-level `_SEAM_HARD_BARRIER`
                  flag to choose between 2.0 (soft, S33 default) and
                  `_SEAM_HARD_BARRIER_COST` (1e6 hard barrier, S67).

    Returns
    -------
    cost : (H_zone, W) float32 — 0=bg seam-friendly, 0.5=fg edge buffer,
           1.0=fg interior, 2.0=fg-dominated column barrier (§3.15A).
           The column barrier fires only when background-corridor columns exist;
           when every column is fg-dominated the cost stays in {0, 0.5, 1.0}.
    """
    zone_h, zone_w = canvas_zone.shape[:2]
    cost = np.zeros((zone_h, zone_w), dtype=np.float32)

    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (2 * dilate_px + 1, 2 * dilate_px + 1)
    )
    for bm in (bg_mask_a, bg_mask_b):
        if bm is None:
            continue
        fg = (bm < 127).astype(np.uint8) * 255  # foreground pixels

        # Tier 1 — fg interior: cost=1.0.
        cost = np.maximum(cost, (fg > 0).astype(np.float32))

        # Tier 2 — dilated fg edge buffer: cost=0.5 (§1.6A).
        # np.maximum preserves Tier 1 at 1.0 for fg pixels; only pure-background
        # pixels near fg edges are raised from 0 → 0.5.
        edge = cv2.morphologyEx(
            fg, cv2.MORPH_GRADIENT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        )
        dilated = cv2.dilate(edge, kernel)
        cost = np.maximum(cost, (dilated > 0).astype(np.float32) * 0.5)

    # §3.15A SemanticStitch column barrier (S33) + §1.23 hard barrier upgrade (S67).
    # When a background corridor exists (some but not all columns are fg-dominated),
    # raise the dominated columns to `_barrier` so the DP is steered into the
    # corridor.  Soft mode (S33 default): 2.0 — discourages but does not block.
    # Hard mode (§1.23, ASP_SEAM_HARD_BARRIER=1): 1e6 — forces background-only seam.
    # Fallback: when all columns are fg-dominated there is no corridor — skip the
    # filter so the DP finds the minimum-cost through-character path instead.
    _barrier = (
        barrier_cost
        if barrier_cost is not None
        else (_SEAM_HARD_BARRIER_COST if _SEAM_HARD_BARRIER else 2.0)
    )
    fg_col_frac = (cost >= 1.0).mean(axis=0)
    dominated = fg_col_frac > 0.5
    if dominated.any() and not dominated.all():
        cost[:, dominated] = np.maximum(cost[:, dominated], _barrier)

    # Issue 10A3 — NL seam routing: inject hard-barrier exclusion masks.
    # Each mask pixel > 127 receives cost=1e6 so the DP cannot route through it.
    if exclusion_masks:
        for em in exclusion_masks:
            if em is None:
                continue
            em_zone = em
            if em.shape != (zone_h, zone_w):
                em_zone = cv2.resize(em, (zone_w, zone_h), interpolation=cv2.INTER_NEAREST)
            cost[em_zone > 127] = 1e6

    return cost


def _seam_color_match(
    dom_zone: np.ndarray,
    oth_zone: np.ndarray,
    path_local: np.ndarray,
    band_px: int,
) -> np.ndarray:
    """Shift *oth_zone* channel means to match *dom_zone* inside the seam band (S16).

    Computes per-channel mean luminance of content pixels within `band_px` rows
    of the seam path in each zone, then adds the per-channel delta to oth_zone's
    band pixels.  Pixels outside the band are returned unchanged.

    This reduces the color step at the seam centre from `post_warp_diff` lum
    units toward zero before the S15 linear ramp blend is applied, making the
    composite transition far less perceptible.  Safe to call even when
    `band_px == sp_soft_px` because the blend ramp weight approaches 0 at the
    band edge — the shift is smoothed away by the blend itself.

    Returns a (zone_h, W, C) uint8 copy of oth_zone with the band shifted.
    Unchanged copy returned when fewer than 10 content pixels exist in either
    zone's band (degenerate zone).
    """
    if band_px <= 0:
        return oth_zone.copy()
    zone_h, W = oth_zone.shape[:2]
    _row_idx = np.arange(zone_h, dtype=np.float32)[:, np.newaxis]
    _path_row = path_local[np.newaxis, :].astype(np.float32)
    _in_band = np.abs(_row_idx - _path_row) < band_px     # (zone_h, W) bool

    dom_content_mask = (dom_zone.max(axis=2) > 0) & _in_band
    oth_content_mask = (oth_zone.max(axis=2) > 0) & _in_band

    if dom_content_mask.sum() < 10 or oth_content_mask.sum() < 10:
        return oth_zone.copy()

    dom_mean = dom_zone[dom_content_mask].astype(np.float32).mean(axis=0)  # (C,)
    oth_mean = oth_zone[oth_content_mask].astype(np.float32).mean(axis=0)  # (C,)
    delta = dom_mean - oth_mean                                              # (C,)

    out = oth_zone.copy()
    shifted = oth_zone[_in_band].astype(np.float32) + delta
    out[_in_band] = np.clip(shifted, 0, 255).astype(np.uint8)
    return out


def _single_pose_soft_edge(
    dom_zone: np.ndarray,
    oth_zone: np.ndarray,
    path_local: np.ndarray,
    apply_mask: np.ndarray,
    sp_soft_px: int,
) -> np.ndarray:
    """Narrow path-guided blend at a single-pose seam boundary (S15).

    Applies a linear feather of half-width *sp_soft_px* centred on
    *path_local* to smooth the hard color step between the dominant frame
    and the fill frame.  The zone is intentionally narrow (≤ 12 px at the
    default of 6) so pose-gap ghosts are not perceptible.

    Only pixels where BOTH frames have foreground content (non-zero) AND
    *apply_mask* is True AND distance to *path_local* < *sp_soft_px* are
    modified.  All other pixels are returned unchanged.

    Returns a (zone_h, W, C) uint8 copy of dom_zone with the blend applied.
    """
    zone_h, W = dom_zone.shape[:2]
    out = dom_zone.copy()
    if sp_soft_px <= 0:
        return out
    both_have = (dom_zone.max(axis=2) > 0) & (oth_zone.max(axis=2) > 0) & apply_mask
    if not both_have.any():
        return out
    _row_idx = np.arange(zone_h, dtype=np.float32)[:, np.newaxis]
    _path_row = path_local[np.newaxis, :].astype(np.float32)
    _dist = np.abs(_row_idx - _path_row)          # (zone_h, W)
    _in_band = (_dist < sp_soft_px) & both_have
    if not _in_band.any():
        return out
    _w_oth = (np.clip(1.0 - _dist / sp_soft_px, 0.0, 1.0) * 0.5)[:, :, np.newaxis]
    _blended = np.clip(
        dom_zone.astype(np.float32) * (1.0 - _w_oth)
        + oth_zone.astype(np.float32) * _w_oth,
        0,
        255,
    ).astype(np.uint8)
    out[_in_band] = _blended[_in_band]
    return out


def _adaptive_gain_clamp(ref_lum: float, frame_lum: float) -> float:
    """Scalar luminance gain with §1.4B continuous adaptive clip (S24).

    Clamp width linearly interpolates between ±26 % (pure-black scene) and
    ±14 % (pure-white scene): ``clamp_width = 0.26 - 0.12 × (ref_lum / 255)``.
    This removes the discontinuity at the S18 ref_lum=80 threshold while
    keeping the same endpoints ([0.86, 1.14] at ref=255).  Scalar (not
    per-channel) to avoid hue shift.
    """
    clamp_width = 0.26 - 0.12 * (ref_lum / 255.0)
    lo = 1.0 - clamp_width
    hi = 1.0 + clamp_width
    return float(np.clip(ref_lum / max(frame_lum, 1.0), lo, hi))


def _bg_gain_unclamped(
    ref_lum: float,
    frame_lum: float,
    override_threshold: float = 0.20,
) -> float:
    """§1.4C — Background-only gain that lifts the clamp when needed.

    When ``_adaptive_gain_clamp`` would reduce the ideal correction by more
    than ``override_threshold`` (default 20%), return the raw ideal gain so
    that background pixels receive the full correction.  For small deviations
    (clamp cut ≤ 20%) the clamped value is returned unchanged.

    Background pixels tolerate aggressive correction because:
    1. They are large uniform regions — clipping is less visible.
    2. Character skin tones (which motivated the clamp) are already excluded
       from the bg-only application site.

    Parameters
    ----------
    ref_lum : float
        Reference median background luminance (scene median, [0, 255]).
    frame_lum : float
        This frame's median background luminance.
    override_threshold : float
        Fraction of the ideal correction that the clamp may cut before we
        bypass it.  0.20 means the clamp may reduce the ideal by at most 20 %.
    """
    if frame_lum <= 0.0:
        return 1.0
    ideal = float(ref_lum) / float(frame_lum)
    clamped = _adaptive_gain_clamp(ref_lum, frame_lum)
    if ideal == 0.0:
        return clamped
    cut = abs(ideal - clamped) / abs(ideal)
    return ideal if cut > override_threshold else clamped


def _bg_histogram_lut(
    src_pixels: np.ndarray,
    ref_pixels: np.ndarray,
) -> np.ndarray:
    """§1.4E: Build a 256-entry CDF-matching LUT for background luminance normalisation.

    Given 1-D arrays of uint8 luminance (or channel) values from the source frame
    background and the reference background, returns a float32 LUT of shape (256,)
    that maps source intensities to their reference-matched equivalents.

    Algorithm: standard histogram specification via CDF matching —
    ``lut[v] = argmin_u |CDF_ref(u) − CDF_src(v)|``, implemented with
    ``np.searchsorted`` for O(256 log 256) vectorised lookup.

    Falls back to the identity LUT when either input has fewer than 10 pixels
    (degenerate background mask).
    """
    if len(src_pixels) < 10 or len(ref_pixels) < 10:
        return np.arange(256, dtype=np.float32)

    src_lum = src_pixels.ravel().astype(np.uint8)
    ref_lum = ref_pixels.ravel().astype(np.uint8)

    src_hist, _ = np.histogram(src_lum, bins=256, range=(0, 256))
    ref_hist, _ = np.histogram(ref_lum, bins=256, range=(0, 256))

    src_cdf = (src_hist.cumsum() / max(float(src_hist.sum()), 1.0)).astype(np.float64)
    ref_cdf = (ref_hist.cumsum() / max(float(ref_hist.sum()), 1.0)).astype(np.float64)

    # lut[v] = smallest u s.t. CDF_ref(u) >= CDF_src(v)
    lut = np.searchsorted(ref_cdf, src_cdf, side="left").clip(0, 255).astype(np.float32)
    return lut


def _apply_bg_histogram_match(
    frame: np.ndarray,
    reference: np.ndarray,
    bg_mask: np.ndarray,
) -> np.ndarray:
    """§1.4E: Apply per-channel CDF histogram matching to background pixels.

    For each channel, derives a ``_bg_histogram_lut`` from the *bg_mask* region
    of *frame* vs *reference*, then applies that LUT to the background channel
    values.  Foreground pixels are copied unchanged.

    Returns a uint8 (H, W, 3) array.
    """
    result = frame.copy()
    bg_sel = bg_mask.astype(bool)
    if not bg_sel.any():
        return result

    for ch in range(min(frame.shape[2], 3)):
        src_ch = frame[..., ch]
        ref_ch = reference[..., ch]
        lut = _bg_histogram_lut(src_ch[bg_sel], ref_ch[bg_sel])
        mapped = lut[src_ch.clip(0, 255).astype(np.uint8)]
        result[bg_sel, ch] = np.clip(mapped[bg_sel], 0, 255).astype(np.uint8)

    return result


def _reject_exposure_outliers(
    frame_lums: "List[Optional[float]]",
    max_deviation_lum: float = 60.0,
) -> "List[bool]":
    """§1.4F: Per-frame skip mask for absolute luminance outliers (S50).

    Computes the median background luminance across all frames that have a
    valid lum value, then returns *True* for any frame whose background lum
    deviates from that median by more than *max_deviation_lum* luma units.

    Frames with ``None`` lum (too few bg pixels to compute a value) are never
    rejected — they are already excluded from gain normalisation by the caller's
    ``frame_lums`` guard.

    Falls back to all-False when fewer than 3 valid luminance values are
    available; the sample median is unreliable below that count.
    """
    n = len(frame_lums)
    result = [False] * n

    valid = [float(l) for l in frame_lums if l is not None]
    if len(valid) < 3:
        return result

    median_lum = float(np.median(valid))
    for i, lum in enumerate(frame_lums):
        if lum is not None and abs(float(lum) - median_lum) > max_deviation_lum:
            result[i] = True

    return result


def _coherence_skip_mask(
    order: np.ndarray,
    frame_lums: "List[Optional[float]]",
    coherence_limit: float = 20.0,
) -> "List[bool]":
    """Per-frame normalization-skip mask from adjacent-strip coherence check (S18).

    Marks both frames in an adjacent pair as skip-normalization when their
    background luminance differs by more than *coherence_limit*.  Only the
    bad pair's frames are excluded — other frames proceed normally.  This
    replaces the former global-skip approach that penalised every frame when
    a single scene-change pair exceeded the limit.

    Returns a list of bool, one entry per frame index (not per order slot).
    """
    N = len(order)
    skip: "List[bool]" = [False] * N
    lum_by_order = [frame_lums[int(order[k])] for k in range(N)]
    for k in range(N - 1):
        la, lb = lum_by_order[k], lum_by_order[k + 1]
        if la is not None and lb is not None and abs(la - lb) > coherence_limit:
            skip[int(order[k])] = True
            skip[int(order[k + 1])] = True
    return skip


def _poisson_seam_blend(
    fa_zone: np.ndarray,
    fb_zone: np.ndarray,
    path_local: np.ndarray,
    apply_mask: np.ndarray,
) -> np.ndarray:
    """§1.6C: Gradient-domain seam blend via cv2.seamlessClone (S21).

    Builds a hard-partition zone (fa above path, fb below) then applies Poisson
    blending in ±_POISSON_BAND_PX rows around the DP seam path.  The gradient
    solver finds intensities that match fb gradients in the band while satisfying
    the hard-partition boundary conditions — eliminating the brightness step
    without ghosting.

    The seam band is clipped to [1, zone_h-2] × [1, W-2] so it never touches
    the destination image border (cv2.seamlessClone requirement).

    Falls back to the hard partition on cv2 errors or degenerate input.
    """
    zone_h, W = fa_zone.shape[:2]

    # Hard partition: A pixels above seam path, B pixels below.
    hard = fa_zone.copy()
    for col in range(W):
        r = min(int(path_local[col]), zone_h - 1)
        hard[r:, col] = fb_zone[r:, col]

    if not apply_mask.any():
        return hard

    # Seam band — must not touch any border pixel (cv2 Poisson requirement).
    seam_mask = np.zeros((zone_h, W), dtype=np.uint8)
    for col in range(1, W - 1):
        r = min(int(path_local[col]), zone_h - 1)
        r0 = max(1, r - _POISSON_BAND_PX)
        r1 = min(zone_h - 1, r + _POISSON_BAND_PX + 1)
        if r1 > r0:
            seam_mask[r0:r1, col] = 255

    if seam_mask.max() == 0:
        return hard

    ys, xs = np.argwhere(seam_mask > 0).T
    cy = max(1, min(zone_h - 2, int(ys.mean())))
    cx = max(1, min(W - 2, int(xs.mean())))

    try:
        cloned = cv2.seamlessClone(
            fb_zone.copy(),
            hard.copy(),
            seam_mask,
            (cx, cy),
            cv2.NORMAL_CLONE,
        )
    except cv2.error:
        return hard

    out = hard.copy()
    out[(seam_mask > 0) & apply_mask] = cloned[(seam_mask > 0) & apply_mask]
    return out


def _get_seam_cost_flags() -> Tuple:
    """§1.5D: Snapshot of module-level flags that affect seam cost computation."""
    return (_POISSON_SEAM, _TOONCRAFTER_SEAM)


def _make_seam_cache_key(
    frame_keys: Optional[Tuple[str, ...]],
    k: int,
    cost_flags: Tuple,
) -> Optional[Tuple]:
    """§1.5D: Hashable cache key for seam boundary *k*.

    Returns *None* when *frame_keys* is None, disabling cache lookup/insertion.
    The key encodes frame identity, boundary index, and active cost flags so
    that changing a flag (e.g. enabling Poisson) correctly bypasses the cache.
    """
    if frame_keys is None:
        return None
    return (frame_keys, k, cost_flags)


def _compute_initial_boundaries(
    affines: List[np.ndarray],
    frames: List[np.ndarray],
) -> np.ndarray:
    """Return midpoint y-coordinates between adjacent frame strip centres.

    Used by HITL checkpoint 3.5 to pre-compute boundary candidates for the
    boundary editor dialog before `_composite_foreground` is called.
    """
    N = len(frames)
    strip_center_ys = np.array(
        [float(affines[i][1, 2]) + frames[i].shape[0] / 2.0 for i in range(N)],
        dtype=np.float64,
    )
    order = np.argsort(strip_center_ys)
    sorted_centers = strip_center_ys[order]
    return (sorted_centers[:-1] + sorted_centers[1:]) / 2.0


def _composite_foreground(
    warped_corr: List[np.ndarray],
    warped_fgs: List[np.ndarray],
    canvas: np.ndarray,
    H: int,
    W: int,
    frames: List[np.ndarray],
    affines: List[np.ndarray],
    bg_masks: List[Optional[np.ndarray]],
    frame_keys: Optional[Tuple[str, ...]] = None,
    seam_path_cache: Optional[Dict] = None,
    exclusion_masks: Optional[List[np.ndarray]] = None,
    preset_boundaries: Optional[np.ndarray] = None,
    paint_mask: Optional[np.ndarray] = None,
) -> np.ndarray:
    """
    Deghost the temporal-median canvas by replacing animated foreground pixels
    with single-frame content.

    paint_mask: optional uint8 (H_canvas, W_canvas) mask painted by the user
    in HITL checkpoint 4.5.  Pixels >127 are treated as hard seam barriers
    (cost=1e6), forcing the DP to route seams around the painted region.
    Appended to *exclusion_masks* so it is sliced per-zone identically.

    Background pixels are always kept from the temporal median (photometrically
    consistent across the whole canvas).  Only foreground character pixels are
    replaced with the single best owning frame, eliminating ghosting without
    introducing zone-level brightness discontinuities in the background.

    At ownership boundaries a Laplacian pyramid blend with a DP seam path is
    applied to foreground pixels only, providing a seamless character transition.
    """
    from .stateless import _laplacian_blend

    N = len(frames)
    print("[Stitch]   Laplacian-blend composite (foreground-only deghost)...")

    # For horizontal scrolls the strip_center_ys are all equal → all N-1 boundaries
    # pile up at canvas_h/2 → repeated overlapping Laplacian blends at the same row
    # produce a bright artefact band.  Temporal median is already correct for
    # horizontal scrolls (each pixel is covered by ≤2 frames so ghosting is minimal).
    tys = np.array([float(affines[i][1, 2]) for i in range(N)])
    txs = np.array([float(affines[i][0, 2]) for i in range(N)])
    ty_range = float(tys.max() - tys.min())
    tx_range = float(txs.max() - txs.min())
    if tx_range > 0 and ty_range / max(tx_range, 1.0) < 0.1:
        print(
            "[Stitch]   Horizontal scroll — temporal median is already optimal, skipping zone composite."
        )
        return canvas.copy()

    # Strip centres and ownership ordering
    strip_center_ys = np.array(
        [float(affines[i][1, 2]) + frames[i].shape[0] / 2.0 for i in range(N)],
        dtype=np.float64,
    )
    order = np.argsort(strip_center_ys)
    sorted_centers = strip_center_ys[order]
    initial_boundaries = (sorted_centers[:-1] + sorted_centers[1:]) / 2.0
    if preset_boundaries is not None and len(preset_boundaries) == N - 1:
        initial_boundaries = np.asarray(preset_boundaries, dtype=np.float64)

    # Warp every frame to the full canvas.
    # INTER_LINEAR is intentional here: INTER_LANCZOS4's negative side-lobes produce
    # dark halos at sharp silhouette edges (character outline against black) that are
    # incorrectly classified as foreground content, creating staircase artifacts.
    warped_list: List[np.ndarray] = []
    for i in range(N):
        wf = cv2.warpAffine(
            frames[i],
            affines[i],
            (W, H),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )
        warped_list.append(wf)

    # Warp bg_masks to canvas space (True = background pixel).
    # Uncovered canvas positions default to background so they are never overwritten.
    warped_bg: List[Optional[np.ndarray]] = []
    for i in range(N):
        if bg_masks[i] is not None:
            wm = cv2.warpAffine(
                bg_masks[i].astype(np.uint8),
                affines[i],
                (W, H),
                flags=cv2.INTER_NEAREST,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=255,
            )
            warped_bg.append(wm > 127)
        else:
            warped_bg.append(None)

    # Normalise every warped frame to a GLOBAL photometric reference computed from
    # the temporal median across all background pixels from all frames.
    #
    # Using the same absolute reference for every frame is critical: if each frame
    # normalised to "its own zone of the temporal median" independently, adjacent
    # zones could end up at different absolute brightness levels (because the median
    # itself may vary spatially if different-brightness frames dominate different
    # parts of the canvas).  A shared global reference guarantees all frames end up
    # on the same scale → no colour/brightness step at seam boundaries.
    #
    # Scalar luminance gain (not per-channel): corrects exposure without shifting hue.
    # Per-channel gain was introducing warm/red casts when backgrounds are dominated
    # by a strong hue (reddish dirt, orange firelight) — the skewed ref_mean would
    # over-boost the red channel and under-boost blue, altering the output colour.
    # BT.601 luminance weights for BGR: B=0.114, G=0.587, R=0.299.
    print("[Stitch]   Normalising warped frames to global temporal-median reference...")
    union_bg = np.zeros((H, W), dtype=bool)
    for wb in warped_bg:
        if wb is not None:
            union_bg |= wb

    global_ref_lum: Optional[float] = None
    ref_px = canvas[union_bg & (canvas.max(axis=2) > 10)]
    if len(ref_px) >= 500:
        global_ref_lum = float(ref_px.astype(np.float32).dot(LUMINANCE_WEIGHTS).mean())

    # Compute per-frame background luminance for coherence check
    frame_lums: List[Optional[float]] = []
    for i in range(N):
        if warped_bg[i] is not None:
            bg_sel = warped_bg[i] & (warped_list[i].max(axis=2) > 10)
            bg_px = warped_list[i][bg_sel]
            if len(bg_px) >= 200:
                frame_lums.append(
                    float(bg_px.astype(np.float32).dot(LUMINANCE_WEIGHTS).mean())
                )
                continue
        frame_lums.append(None)

    # Inter-strip color coherence guard (S18: per-pair instead of global skip).
    # Frames in adjacent pairs whose background luminance differs by more than
    # _COHERENCE_LIMIT are excluded from normalization; other frames proceed
    # normally.  This avoids penalising every frame when a single scene-change
    # pair exceeds the limit.
    _COHERENCE_LIMIT = 20.0
    valid_lums = [l for l in frame_lums if l is not None]
    _skip_norm: List[bool] = _coherence_skip_mask(order, frame_lums, _COHERENCE_LIMIT)
    # §1.4F: OR in exposure-outlier skips (absolute lum deviation from global median)
    if _EXPOSURE_OUTLIER_THRESH > 0.0:
        _exp_skip = _reject_exposure_outliers(frame_lums, _EXPOSURE_OUTLIER_THRESH)
        _n_exp_skipped = sum(_exp_skip)
        if _n_exp_skipped:
            print(
                f"[Stitch]   Exposure outlier gate: {_n_exp_skipped}/{N} frames excluded"
                f" (|lum - median| > {_EXPOSURE_OUTLIER_THRESH:.1f})."
            )
        _skip_norm = [a or b for a, b in zip(_skip_norm, _exp_skip)]
    if len(valid_lums) >= 2:
        lum_by_order = [frame_lums[int(order[k])] for k in range(N)]
        adj_diffs = [
            abs(lum_by_order[k + 1] - lum_by_order[k])
            for k in range(len(lum_by_order) - 1)
            if lum_by_order[k] is not None and lum_by_order[k + 1] is not None
        ]
        _max_adj_diff = float(max(adj_diffs)) if adj_diffs else 0.0
        _n_skipped = sum(_skip_norm)
        if _n_skipped:
            print(
                f"[Stitch]   Color coherence gate (per-pair): max adj diff={_max_adj_diff:.1f}"
                f" → skipping normalization for {_n_skipped}/{N} frames in bad pairs."
            )
        else:
            print(
                f"[Stitch]   Color coherence OK (max adj diff={_max_adj_diff:.1f}). Applying normalization."
            )

    # §1.6B: track per-frame applied gain so the feather-width pass can widen
    # boundaries where adjacent frames needed significantly different corrections.
    frame_gains: List[float] = [1.0] * N
    warped_norm: List[np.ndarray] = []
    for i in range(N):
        if (
            not _skip_norm[i]
            and global_ref_lum is not None
            and warped_bg[i] is not None
        ):
            bg_sel = warped_bg[i] & (warped_list[i].max(axis=2) > 10)
            bg_px = warped_list[i][bg_sel]
            _bg_min = _BG_NORM_MIN_PX if _BG_NORM_MIN_PX > 0 else 200
            if _has_sufficient_bg(bg_sel, _bg_min) and frame_lums[i] is not None:
                f32 = warped_list[i].astype(np.float32)
                if _MULTISCALE_GAIN:
                    # §1.4D: spatially-varying gain map (bg-only, fg untouched).
                    # _multiscale_gain_map uses bg_sel as the source mask; the
                    # Gaussian blur propagates bg gains into fg regions so the
                    # full (H,W) map covers all pixels without fg-colour shift.
                    gain_map = _multiscale_gain_map(
                        warped_list[i], canvas, bg_sel
                    )
                    f32[bg_sel] = np.clip(
                        f32[bg_sel] * gain_map[bg_sel, np.newaxis], 0, 255
                    )
                    # Representative scalar for §1.6B feather widening
                    gain = float(np.median(gain_map[bg_sel]))
                    print(
                        f"[Stitch]     Frame {i}: multiscale_gain median={gain:.3f} (bg-only)"
                    )
                elif _HISTOGRAM_MATCH:
                    # §1.4E: CDF histogram match — tonal distribution equalisation
                    matched = _apply_bg_histogram_match(warped_list[i], canvas, bg_sel)
                    f32 = matched.astype(np.float32)
                    # Compute representative scalar for §1.6B feather widening
                    src_lum_vals = (
                        warped_list[i][bg_sel].astype(np.float32).dot(LUMINANCE_WEIGHTS)
                    )
                    out_lum_vals = (
                        matched[bg_sel].astype(np.float32).dot(LUMINANCE_WEIGHTS)
                    )
                    ratios = np.where(
                        src_lum_vals > 0.5,
                        out_lum_vals / (src_lum_vals + 1e-3),
                        1.0,
                    )
                    gain = float(np.median(ratios.clip(0.5, 2.0)))
                    print(
                        f"[Stitch]     Frame {i}: histogram_match median_gain={gain:.3f} (bg-only)"
                    )
                else:
                    # §1.4C: scalar bg gain (default path)
                    gain = _bg_gain_unclamped(global_ref_lum, frame_lums[i])
                    f32[bg_sel] = np.clip(f32[bg_sel] * gain, 0, 255)
                    print(f"[Stitch]     Frame {i}: lum_gain={gain:.3f} (bg-only)")
                frame_gains[i] = gain
                warped_norm.append(f32.astype(np.uint8))
                continue
        warped_norm.append(warped_list[i])

    # Single-pass boundary placement — use normalised frames for accurate diff scores
    print("[Stitch]   Optimising boundary placement...")
    boundaries, diff_scores = _find_optimal_boundaries(
        warped_norm,
        order,
        initial_boundaries,
        H,
        W,
        bg_masks=bg_masks,
        affines=affines,
    )
    feathers = np.array([_diff_to_feather(d) for d in diff_scores], dtype=np.int64)

    # Cap feathers by natural frame overlap so they never extend past real content
    n_b = len(boundaries)
    max_feathers: List[int] = []
    for k in range(n_b):
        fi_a = int(order[k])
        fi_b = int(order[k + 1])
        ty_a = float(affines[fi_a][1, 2])
        ty_b = float(affines[fi_b][1, 2])
        H_a = frames[fi_a].shape[0]
        H_b = frames[fi_b].shape[0]
        nat_overlap = max(0, int(min(ty_a + H_a, ty_b + H_b) - max(ty_a, ty_b)))
        max_feather = max(5, min(nat_overlap // 2, FEATHER_MAX))
        max_feathers.append(max_feather)
        if feathers[k] > max_feather:
            feathers[k] = max_feather
    print(
        "[Stitch]   Feathers (overlap-capped): "
        + " ".join(f"B{k}={int(feathers[k])}px" for k in range(n_b))
    )

    # §1.6B: Minimum feather from luminance gain difference at each boundary.
    # When adjacent frames required significantly different gain corrections, the
    # residual step after clamping is proportional to |gain_A − gain_B|.  Widen
    # the feather to fade = max(40, int(gain_diff × 300)), capped at 120 px.
    # The overlap cap is re-applied so the feather never exceeds real content.
    _feather_gain_widened = False
    for k in range(n_b):
        fi_a = int(order[k])
        fi_b = int(order[k + 1])
        gain_diff = abs(frame_gains[fi_a] - frame_gains[fi_b])
        min_fk = _gain_to_min_feather(gain_diff)
        if feathers[k] < min_fk:
            feathers[k] = min(int(min_fk), max_feathers[k])
            _feather_gain_widened = True
    if _feather_gain_widened:
        print(
            "[Stitch]   Feathers (§1.6B gain-adjusted): "
            + " ".join(f"B{k}={int(feathers[k])}px" for k in range(n_b))
        )

    # §1.19: Fg-density-aware feather cap.  When the seam blend zone is dominated
    # by fg pixels, cap the feather to prevent long double-image ghost bands.
    if _FG_FEATHER_CAP > 0:
        feathers = _fg_density_feather_cap(
            feathers, boundaries, warped_bg, order,
            cap_px=_FG_FEATHER_CAP,
            fg_thresh=_FG_FEATHER_THRESH,
        )
        print(
            "[Stitch]   Feathers (§1.19 fg-density-capped): "
            + " ".join(f"B{k}={int(feathers[k])}px" for k in range(n_b))
        )

    # ── Stage 8.5: Foreground pose registration — global reference strategy ──
    # The camera model is translation-only, so the BACKGROUND is aligned in
    # warped_norm but the animating CHARACTER lands in two different poses on
    # either side of each ownership boundary → torn/doubled edges at the seam.
    #
    # Strategy: global reference pose (vs. pairwise midpoint).
    # We pick the temporally-central strip as the reference pose.  Every other
    # frame's foreground is warped TOWARD the reference at its seam boundary.
    # The warp fraction α decays with temporal distance from the reference so
    # the reference frame is never warped, nearby frames are warped a little,
    # and distant frames are warped more.  This prevents the drift accumulation
    # that pairwise midpoint warps accumulate across long strip chains.
    #
    # Fallback (A6): when the residual exceeds max_residual, take the seam-zone
    # foreground from the dominant pose frame only — no blending.
    seam_single_pose: dict = {}
    seam_post_diffs: dict = {}   # k → post-warp diff score (residual if fallback)
    seam_synthesized: dict = {}  # k → synthesized seam-band crop (ToonCrafter §3.6)
    if _FG_REGISTER_ENABLED and N >= 2:
        try:
            from .fg_register import register_foreground_at_seam

            scroll_is_h = tx_range > 0 and ty_range / max(tx_range, 1.0) < 0.1
            reg_axis = 1 if scroll_is_h else 0

            # Reference index: the temporally-central frame in the sorted order.
            ref_idx_in_order = len(order) // 2
            ref_fi = int(order[ref_idx_in_order])

            n_warped = 0
            n_fallback = 0
            for k, by in enumerate(boundaries):
                fi_a = int(order[k])
                fi_b = int(order[k + 1])
                if warped_bg[fi_a] is None or warped_bg[fi_b] is None:
                    continue
                fg_a = ~warped_bg[fi_a]
                fg_b = ~warped_bg[fi_b]

                # §1.20: Preemptive single-pose for tiny-step seams.
                # When the camera barely moved, the character occupies nearly
                # the same rows in both frames but may be in a different
                # animation pose — ARAP cannot reconcile this.
                if _TIGHT_STEP_PX > 0:
                    _step_sz = _compute_seam_step_size(fi_a, fi_b, affines)
                    if _step_sz < _TIGHT_STEP_PX:
                        _by_int = int(by)
                        _half = min(20, int(feathers[k]))
                        _y0 = max(0, _by_int - _half)
                        _y1 = min(H, _by_int + _half)
                        _fg_a_cnt = int(fg_a[_y0:_y1].sum())
                        _fg_b_cnt = int(fg_b[_y0:_y1].sum())
                        _dom = fi_a if _fg_a_cnt >= _fg_b_cnt else fi_b
                        seam_single_pose[k] = _dom
                        seam_post_diffs[k] = _step_sz
                        n_fallback += 1
                        print(
                            f"[Stitch]     FG-register B{k} (frames {fi_a}/{fi_b}): "
                            f"step={_step_sz:.1f}px < {_TIGHT_STEP_PX}px "
                            f"→ preemptive single-pose (frame {_dom})"
                        )
                        continue

                # Symmetric midpoint: both frames move halfway toward each other.
                # The global-reference approach (asymmetric alpha based on
                # distance from reference) amplifies noisy flow estimates for
                # frames far from the reference, causing regressions. Symmetric
                # midpoint is the safe default; the reference tracking is still
                # used for the ref= reporting/diagnostics.
                alpha_a = 0.5
                alpha_b = 0.5

                adj_a, adj_b, info = register_foreground_at_seam(
                    warped_norm[fi_a],
                    warped_norm[fi_b],
                    fg_a,
                    fg_b,
                    seam_pos=int(by),
                    axis=reg_axis,
                    alpha_a=alpha_a,
                    alpha_b=alpha_b,
                )
                if info["warped"]:
                    warped_norm[fi_a] = adj_a
                    warped_norm[fi_b] = adj_b
                    n_warped += 1
                    # Post-warp verification: if the foreground colour discrepancy
                    # at the seam is still large after ARAP warping, the two poses
                    # are too different to blend cleanly — escalate to single-pose
                    # so the blend zone doesn't create a double-image ghost.
                    post_diff = info.get("post_warp_diff", 0.0)
                    seam_post_diffs[k] = post_diff
                    _sp_thresh = (
                        _adaptive_sp_threshold(int(feathers[k]))
                        if _ADAPTIVE_SP_THRESH
                        else 22.0
                    )
                    if post_diff > _sp_thresh:
                        dom = fi_a if info["dominant"] == "a" else fi_b
                        seam_single_pose[k] = dom
                        n_fallback += 1
                        print(
                            f"[Stitch]     FG-register B{k} (frames {fi_a}/{fi_b}): "
                            f"residual={info['residual']:.1f}px post_diff={post_diff:.1f} "
                            f"→ re-posed BUT escalated to single-pose (ghost prevention)"
                        )
                    else:
                        print(
                            f"[Stitch]     FG-register B{k} (frames {fi_a}/{fi_b}): "
                            f"residual={info['residual']:.1f}px α=({alpha_a:.2f},{alpha_b:.2f}) "
                            f"post_diff={post_diff:.1f} fg_px={info['fg_pixels']} → re-posed"
                        )
                elif info.get("fallback"):
                    dom = fi_a if info["dominant"] == "a" else fi_b
                    seam_single_pose[k] = dom
                    seam_post_diffs[k] = float(info.get("residual", 0.0))
                    n_fallback += 1
                    print(
                        f"[Stitch]     FG-register B{k} (frames {fi_a}/{fi_b}): "
                        f"residual={info['residual']:.1f}px too large → "
                        f"single-pose fallback (frame {dom})"
                    )
            print(
                f"[Stitch]   FG pose registration: {n_warped}/{n_b} re-posed, "
                f"{n_fallback}/{n_b} single-pose fallback. ref={ref_fi}"
            )

            # ToonCrafter seam synthesis (§3.6B) — applied to single-pose
            # escalated seams when ASP_TOONCRAFTER_SEAM=1.  Synthesizes a
            # coherent intermediate pose that replaces the hard-partition
            # boundary.  Only the worst seam (highest post_warp_diff) per run
            # is synthesized to keep inference overhead bounded (~24s on A100).
            if _TOONCRAFTER_SEAM and seam_single_pose:
                try:
                    from .anim_fill import _generate_canonical_cel
                    import torch as _tc_torch

                    _tc_device = "cuda" if _tc_torch.cuda.is_available() else "cpu"
                    canvas_h_tc, canvas_w_tc = warped_norm[0].shape[:2]
                    _taper_crop = 64  # half-height of the seam-band crop for synthesis

                    # Synthesize only the single worst seam (highest post_diff)
                    # to keep overhead bounded.  Track post_diffs across all seams.
                    _worst_k = max(
                        seam_single_pose.keys(),
                        key=lambda _k: _k,  # fallback: last seam; override if tracked
                    )
                    by = boundaries[_worst_k]
                    fi_a = int(order[_worst_k])
                    fi_b = int(order[_worst_k + 1])

                    if reg_axis == 0:  # vertical scroll seam
                        _sy0 = max(0, int(by) - _taper_crop)
                        _sy1 = min(canvas_h_tc, int(by) + _taper_crop)
                        crop_a_tc = warped_norm[fi_a][_sy0:_sy1, :]
                        crop_b_tc = warped_norm[fi_b][_sy0:_sy1, :]
                    else:  # horizontal scroll seam
                        _sx0 = max(0, int(by) - _taper_crop)
                        _sx1 = min(canvas_w_tc, int(by) + _taper_crop)
                        crop_a_tc = warped_norm[fi_a][:, _sx0:_sx1]
                        crop_b_tc = warped_norm[fi_b][:, _sx0:_sx1]

                    synth = _generate_canonical_cel(crop_a_tc, crop_b_tc, _tc_device)
                    seam_synthesized[_worst_k] = {
                        "synth": synth,
                        "seam_pos": int(by),
                        "crop_half": _taper_crop,
                        "axis": reg_axis,
                    }
                    print(
                        f"[ToonCrafter] Seam synthesis for B{_worst_k}: "
                        f"seam_pos={int(by)}  crop_half={_taper_crop}px"
                    )
                except Exception as _tc_exc:
                    print(f"[ToonCrafter] Seam synthesis skipped ({_tc_exc}).")

        except Exception as _fg_exc:
            print(f"[Stitch]   FG pose registration skipped ({_fg_exc}).")

    # §S12: Adaptive feather refinement based on FG registration quality.
    # post_warp_diff < 8  → excellent alignment: widen feather 1.5× for a
    #                         smoother Laplacian blend (less visible step at seam).
    # post_warp_diff > 16 → poor alignment: narrow feather 0.75× to reduce the
    #                         blend zone where misaligned fg would create ghosting.
    # Seams that became single-pose (post_diff > 22) are skipped — feather still
    # governs the background blend width but fg routing is already single-pose.
    # Re-applies the overlap cap after modification.
    _feather_adapted = False
    for _k, _pdiff in seam_post_diffs.items():
        if _k in seam_single_pose:
            continue
        if _pdiff < 8.0:
            feathers[_k] = min(int(feathers[_k] * 1.5), FEATHER_MAX)
            _feather_adapted = True
        elif _pdiff > 16.0:
            feathers[_k] = max(int(feathers[_k] * 0.75), FEATHER_MIN)
            _feather_adapted = True
    if _feather_adapted:
        # Re-apply natural overlap cap so widened feathers never exceed real content
        for _k in range(n_b):
            _fi_a = int(order[_k])
            _fi_b = int(order[_k + 1])
            _ty_a = float(affines[_fi_a][1, 2])
            _ty_b = float(affines[_fi_b][1, 2])
            _H_a = frames[_fi_a].shape[0]
            _H_b = frames[_fi_b].shape[0]
            _nat_ov = max(0, int(min(_ty_a + _H_a, _ty_b + _H_b) - max(_ty_a, _ty_b)))
            _max_f = max(5, min(_nat_ov // 2, FEATHER_MAX))
            if feathers[_k] > _max_f:
                feathers[_k] = _max_f
        print(
            "[Stitch]   Feathers (post-FG-reg adapted): "
            + " ".join(f"B{_k}={int(feathers[_k])}px" for _k in range(n_b))
        )

    # ToonCrafter seam synthesis (§3.6 / S9): generate a canonical interpolated
    # cel at the single worst post-diff seam so the hard single-pose partition
    # is replaced by a smoothly interpolated character pose.  Only fires when
    # ASP_TOONCRAFTER_SEAM=1 and at least one seam was escalated to single-pose.
    seam_canonical_crops: dict = {}
    if _TOONCRAFTER_SEAM and seam_single_pose:
        try:
            worst_k = max(seam_single_pose, key=lambda _k: seam_post_diffs.get(_k, 0.0))
            fi_a_w = int(order[worst_k])
            fi_b_w = int(order[worst_k + 1])
            by_w = boundaries[worst_k]
            feather_w = int(feathers[worst_k])
            y0_fw = max(0, int(by_w) - feather_w)
            y1_fw = min(H, int(by_w) + feather_w + 1)
            crop_a_tc = warped_norm[fi_a_w][y0_fw:y1_fw]
            crop_b_tc = warped_norm[fi_b_w][y0_fw:y1_fw]
            from .anim_fill import _generate_canonical_cel
            import torch as _tc_torch

            _dev_tc_seam = "cuda" if _tc_torch.cuda.is_available() else "cpu"
            canonical_cel = _generate_canonical_cel(crop_a_tc, crop_b_tc, _dev_tc_seam)
            seam_canonical_crops[worst_k] = canonical_cel
            print(
                f"[Stitch]   ToonCrafter seam synthesis: B{worst_k} "
                f"(frames {fi_a_w}/{fi_b_w}) post_diff={seam_post_diffs.get(worst_k, 0.0):.1f} "
                f"→ canonical cel generated."
            )
        except Exception as _tc_seam_e:
            print(f"[Stitch]   ToonCrafter seam synthesis skipped ({_tc_seam_e}).")

    # Start from temporal median canvas — background pixels stay here permanently
    result = canvas.copy()

    # Hard-partition: write FOREGROUND pixels only from each ownership zone.
    # Background pixels are intentionally left as the temporal median so the
    # static scene elements (walls, floors, props) retain photometric consistency.
    for k in range(N):
        fi = int(order[k])
        y_start = 0 if k == 0 else int(boundaries[k - 1])
        y_end = H if k == N - 1 else int(boundaries[k])
        src = warped_norm[fi][y_start:y_end]
        has_content = src.max(axis=2) > 0
        if warped_bg[fi] is not None:
            is_fg = ~warped_bg[fi][y_start:y_end]  # foreground = not background
            replace = has_content & is_fg
        else:
            replace = has_content
        result[y_start:y_end][replace] = src[replace]

    # §S12: Pre-compute seam DP paths for all boundaries in parallel.
    # _seam_cut() is read-only (reads warped_norm + result snapshot from hard-partition).
    # Since result is fully populated before the blend loop starts, all seam cuts are
    # independent — no write conflicts.  ThreadPoolExecutor releases the GIL for NumPy ops.
    import concurrent.futures as _cf

    def _seam_job(job_args):
        _k, _fa_z, _fb_z, _sem, _W, _zh = job_args
        _both = (_fa_z.max(axis=2) > 0) & (_fb_z.max(axis=2) > 0)
        if int(_both.sum()) > _zh * _W // 20:
            try:
                return _k, _seam_cut(_fa_z, _fb_z, sem_cost=_sem)
            except Exception:
                pass
        return _k, np.full(_W, _zh // 2, dtype=np.int32)

    # §S86: merge painter canvas-space mask into exclusion_masks list.
    # paint_mask is (H_canvas, W_canvas) uint8; sliced per-zone identically to
    # existing exclusion_masks entries so no additional handling is needed.
    _eff_exclusion = list(exclusion_masks or [])
    if paint_mask is not None and paint_mask.shape[0] == H and paint_mask.shape[1] == W:
        _eff_exclusion.append(paint_mask)
    _eff_exclusion = _eff_exclusion or None  # type: ignore[assignment]

    _seam_cost_flags = _get_seam_cost_flags()
    _seam_jobs = []
    _precomp_paths: dict = {}
    for _k, _by in enumerate(boundaries):
        # §1.5D: serve from cache when the same frame set + cost config was seen before
        _ck = _make_seam_cache_key(frame_keys, _k, _seam_cost_flags)
        if _ck is not None and seam_path_cache is not None and _ck in seam_path_cache:
            _precomp_paths[_k] = seam_path_cache[_ck]
            continue
        _fi_a = int(order[_k])
        _fi_b = int(order[_k + 1])
        _f = int(feathers[_k])
        _y0 = max(0, int(_by) - _f)
        _y1 = min(H, int(_by) + _f + 1)
        if _y1 - _y0 < 4:
            continue
        _fa_z = warped_norm[_fi_a][_y0:_y1].copy()
        _fb_z = warped_norm[_fi_b][_y0:_y1].copy()
        _bg_a_z = warped_bg[_fi_a][_y0:_y1] if warped_bg[_fi_a] is not None else None
        _bg_b_z = warped_bg[_fi_b][_y0:_y1] if warped_bg[_fi_b] is not None else None
        _em_zone = [em[_y0:_y1] for em in (_eff_exclusion or []) if em is not None and em.shape[0] >= _y1]
        _sem = _build_seam_cost_map(
            result[_y0:_y1].copy(),
            ((_bg_a_z.astype(np.uint8) * 255) if _bg_a_z is not None else None),
            ((_bg_b_z.astype(np.uint8) * 255) if _bg_b_z is not None else None),
            exclusion_masks=_em_zone or None,
        )
        _seam_jobs.append((_k, _fa_z, _fb_z, _sem, W, _y1 - _y0))

    if len(_seam_jobs) > 1:
        with _cf.ThreadPoolExecutor(max_workers=min(len(_seam_jobs), 4)) as _pool:
            for _k, _path in _pool.map(_seam_job, _seam_jobs):
                _precomp_paths[_k] = _path
    elif _seam_jobs:
        _k, _path = _seam_job(_seam_jobs[0])
        _precomp_paths[_k] = _path

    # §1.5D: populate cache with all newly computed paths
    if frame_keys is not None and seam_path_cache is not None:
        for _k, _path in _precomp_paths.items():
            _ck = _make_seam_cache_key(frame_keys, _k, _seam_cost_flags)
            if _ck not in seam_path_cache:
                seam_path_cache[_ck] = _path

    # Laplacian blend at each boundary seam zone (foreground pixels only)
    for k, by in enumerate(boundaries):
        fi_a = int(order[k])
        fi_b = int(order[k + 1])
        feather = int(feathers[k])

        y0_f = max(0, int(by) - feather)
        y1_f = min(H, int(by) + feather + 1)
        zone_h = y1_f - y0_f
        if zone_h < 4:
            continue

        fa_zone = warped_norm[fi_a][y0_f:y1_f]
        fb_zone = warped_norm[fi_b][y0_f:y1_f]

        # §1.30: degenerate zone guard — escalate to single-pose before DP when
        # zone is too short for a meaningful blend (DP collapses to constant path).
        if (
            _ZONE_MIN_HEIGHT > 0
            and _zone_is_degenerate(zone_h, _ZONE_MIN_HEIGHT)
            and k not in seam_single_pose
        ):
            _fg_a = int((fa_zone.max(axis=2) > 0).sum())
            _fg_b = int((fb_zone.max(axis=2) > 0).sum())
            seam_single_pose[k] = fi_a if _fg_a >= _fg_b else fi_b

        # P2.4 — Semantic seam routing: build a character-boundary cost map so
        # the DP path avoids cutting through foreground outlines.
        _bg_a_zone = warped_bg[fi_a][y0_f:y1_f] if warped_bg[fi_a] is not None else None
        _bg_b_zone = warped_bg[fi_b][y0_f:y1_f] if warped_bg[fi_b] is not None else None

        # Use pre-computed seam path when available (parallel pre-computation above)
        path_local = _precomp_paths.get(k)
        if path_local is None:
            # Fallback: compute inline (zone was skipped in pre-compute or < 4px)
            _em_zone_fb = [em[y0_f:y1_f] for em in (_eff_exclusion or []) if em is not None and em.shape[0] >= y1_f]
            _sem_cost = _build_seam_cost_map(
                result[y0_f:y1_f],
                ((_bg_a_zone.astype(np.uint8) * 255) if _bg_a_zone is not None else None),
                ((_bg_b_zone.astype(np.uint8) * 255) if _bg_b_zone is not None else None),
                exclusion_masks=_em_zone_fb or None,
            )
            both = (fa_zone.max(axis=2) > 0) & (fb_zone.max(axis=2) > 0)
            if int(both.sum()) > zone_h * W // 20:
                try:
                    path_local = _seam_cut(fa_zone, fb_zone, sem_cost=_sem_cost)
                except Exception:
                    path_local = np.full(W, zone_h // 2, dtype=np.int32)
            else:
                path_local = np.full(W, zone_h // 2, dtype=np.int32)

        # P2.5 — Soft-seam diffusion blending (DSFN technique).
        # Instead of a fixed-width linear ramp, compute a spatially-adaptive blend
        # weight from the photometric similarity between the two frames in the zone.
        # High similarity (flat background) → wide, smooth transition.
        # Low similarity (character edge) → narrow, hard cut that preserves outlines.
        # The seam path still anchors the 50% iso-contour of the weight.
        # warped_bg[i] is True=background; pass background masks directly so the
        # seam weight can apply a tight cut at foreground pixels specifically.
        _wbg_a = warped_bg[fi_a][y0_f:y1_f] if warped_bg[fi_a] is not None else None
        _wbg_b = warped_bg[fi_b][y0_f:y1_f] if warped_bg[fi_b] is not None else None
        mask_float = _soft_seam_weight(
            fa_zone,
            fb_zone,
            path_local,
            zone_h,
            W,
            bg_mask_a=_wbg_a,
            bg_mask_b=_wbg_b,
        )

        blended = _laplacian_blend(fa_zone, fb_zone, mask_float)

        # Apply blend only to FOREGROUND pixels so background stays from temporal median.
        # Where both frames agree the pixel is background, leave the temporal median value.
        has_a = fa_zone.max(axis=2) > 0
        has_b = fb_zone.max(axis=2) > 0
        has_any = has_a | has_b

        if warped_bg[fi_a] is not None and warped_bg[fi_b] is not None:
            bg_a_z = warped_bg[fi_a][y0_f:y1_f]
            bg_b_z = warped_bg[fi_b][y0_f:y1_f]
            # Foreground in at least one frame — apply blend
            is_fg = ~(bg_a_z & bg_b_z)
            apply = has_any & is_fg
        else:
            is_fg = None
            apply = has_any

        # §1.28: Instability escalation — if the seam path has high column variance
        # and no prior single-pose decision exists, escalate to single-pose now.
        if (
            _SEAM_INSTABILITY_THRESH > 0.0
            and k not in seam_single_pose
            and _seam_path_std(path_local) > _SEAM_INSTABILITY_THRESH
        ):
            _fg_a = int((fa_zone.max(axis=2) > 0).sum())
            _fg_b = int((fb_zone.max(axis=2) > 0).sum())
            seam_single_pose[k] = fi_a if _fg_a >= _fg_b else fi_b

        # §1.31: FG penetration escalation — if the seam path cuts through
        # foreground pixels in too many columns, the DP has routed through
        # character bodies.  Escalate to single-pose to avoid a bisected character.
        if (
            _SEAM_FG_PENETRATION_MAX > 0.0
            and k not in seam_single_pose
            and _seam_fg_penetration(path_local, fa_zone, fb_zone) > _SEAM_FG_PENETRATION_MAX
        ):
            _fg_a = int((fa_zone.max(axis=2) > 0).sum())
            _fg_b = int((fb_zone.max(axis=2) > 0).sum())
            seam_single_pose[k] = fi_a if _fg_a >= _fg_b else fi_b

        # A6 — single-pose fallback: when the warp was unsafe at this seam, the
        # two frames hold the character in irreconcilable poses.  Blending them
        # produces a double image, so take the FOREGROUND from the dominant frame
        # only (background still blends).  The dominant frame's foreground pixels
        # win; the other frame fills only where the dominant has no content.
        # ToonCrafter upgrade (§3.6): if a canonical cel was synthesised for this
        # seam, use it instead of the hard dominant-frame partition.
        _single = seam_single_pose.get(k)
        _synth_info = seam_synthesized.get(k)
        if _synth_info is not None and is_fg is not None:
            # ToonCrafter synthesized seam (§3.6B): the synthesis covers the
            # band around the seam boundary.  Apply it where both frames have
            # foreground content; fall back to single-pose for the rest.
            synth = _synth_info["synth"]  # crop of the seam zone
            sp = _synth_info["seam_pos"]  # canvas row of the seam
            ch = _synth_info["crop_half"]  # half-height of the crop
            ax = _synth_info["axis"]  # 0=vertical, 1=horizontal

            dom_fi = _single if _single is not None else fi_a
            oth_fi = fi_b if dom_fi == fi_a else fi_a
            dom_zone = warped_norm[dom_fi][y0_f:y1_f]
            oth_zone = warped_norm[oth_fi][y0_f:y1_f]

            # Single-pose baseline (covers entire zone)
            dom_has = dom_zone.max(axis=2) > 0
            result[y0_f:y1_f][apply & dom_has] = dom_zone[apply & dom_has]
            oth_fill = apply & (~dom_has) & (oth_zone.max(axis=2) > 0)
            result[y0_f:y1_f][oth_fill] = oth_zone[oth_fill]

            # Overwrite the synthesis band with the ToonCrafter output
            if ax == 0:
                _syn_y0 = max(y0_f, sp - ch)
                _syn_y1 = min(y1_f, sp + ch)
                if _syn_y0 < _syn_y1 and synth.shape[0] > 0:
                    _rel0 = _syn_y0 - (sp - ch)
                    _rel1 = _rel0 + (_syn_y1 - _syn_y0)
                    if 0 <= _rel0 < synth.shape[0] and _rel1 <= synth.shape[0]:
                        _s = synth[_rel0:_rel1, :]
                        _has_s = _s.max(axis=2) > 0
                        result[_syn_y0:_syn_y1][_has_s] = _s[_has_s]
            print(f"[ToonCrafter] Composite B{k}: synthesis at seam {sp}±{ch}px")
        elif _single is not None and is_fg is not None:
            dom_zone = warped_norm[_single][y0_f:y1_f]
            oth = fi_b if _single == fi_a else fi_a
            oth_zone = warped_norm[oth][y0_f:y1_f]
            dom_has = dom_zone.max(axis=2) > 0
            fg_apply = apply  # foreground pixels in the zone
            take_dom = fg_apply & dom_has
            take_oth = fg_apply & (~dom_has) & (oth_zone.max(axis=2) > 0)
            result[y0_f:y1_f][take_dom] = dom_zone[take_dom]
            result[y0_f:y1_f][take_oth] = oth_zone[take_oth]

            # S15+S16 — color-match oth_zone to dom_zone in the seam band, then
            # apply a narrow soft-edge blend along the seam path.
            # _seam_color_match reduces the channel-mean delta from post_warp_diff
            # lum-units toward zero before the ±sp_soft_px ramp is applied, making
            # the composite transition nearly imperceptible.
            _sp_soft_px_base = int(os.environ.get("ASP_SP_SOFT_PX", "6"))
            _sp_soft_px = (
                _adaptive_sp_soft_px(feather)
                if _ADAPTIVE_SP_SOFT
                else _sp_soft_px_base
            )
            _oth_matched = _seam_color_match(dom_zone, oth_zone, path_local, _sp_soft_px + 4)
            _sp_zone = _single_pose_soft_edge(dom_zone, _oth_matched, path_local, fg_apply, _sp_soft_px)
            _both_for_sp = dom_has & (oth_zone.max(axis=2) > 0) & fg_apply
            if _both_for_sp.any():
                result[y0_f:y1_f][_both_for_sp] = _sp_zone[_both_for_sp]

            print(
                f"[Stitch]   Single-pose B{k} (frame {_single}): "
                f"zone=[{y0_f}–{y1_f}] fg_px={int(fg_apply.sum())} "
                f"soft_px={_sp_soft_px}"
            )
        else:
            # §1.6C — Poisson seam blend (ASP_POISSON_SEAM=1): replace Laplacian
            # blend with gradient-domain cv2.seamlessClone at normal seams.
            if _POISSON_SEAM:
                blended = _poisson_seam_blend(fa_zone, fb_zone, path_local, apply)

            # Apply blend only where BOTH frames have actual content.
            # At canvas boundary positions where only one frame has content, the
            # Laplacian pyramid creates ringing at the content-vs-zero transition.
            # For single-frame positions, take that frame directly.
            both_content = has_a & has_b & apply
            only_a = has_a & (~has_b) & apply
            only_b = (~has_a) & has_b & apply
            if both_content.any():
                result[y0_f:y1_f][both_content] = blended[both_content]
            if only_a.any():
                result[y0_f:y1_f][only_a] = fa_zone[only_a]
            if only_b.any():
                result[y0_f:y1_f][only_b] = fb_zone[only_b]
            _blend_mode = "poisson" if _POISSON_SEAM else "laplacian"
            print(
                f"[Stitch]   Blended B{k} (frames {fi_a}/{fi_b}, {_blend_mode}): "
                f"zone=[{y0_f}–{y1_f}] feather={feather}px "
                f"seam=[{int(path_local.min())}–{int(path_local.max())}]"
            )

    # Fallback: fill remaining black pixels with content from any frame.
    # When frames have different horizontal extents (diagonal scroll), the warped
    # coverage areas create interior gaps not covered by the zone's owning frame.
    # These gaps would show as staircase black edges in the final image.  Any frame
    # that has content at the gap location is used to fill it.
    still_black = result.max(axis=2) == 0
    if still_black.any():
        for wn in warped_norm:
            has_content = (wn.max(axis=2) > 0) & still_black
            if has_content.any():
                result[has_content] = wn[has_content]
                still_black = result.max(axis=2) == 0
                if not still_black.any():
                    break

    # §1.21: Post-composite seam luminance equalisation.
    if _SEAM_LUM_EQ and boundaries:
        result = _seam_lum_equalize(result, boundaries)

    return result


__all__ = [
    "_composite_foreground",
    "_get_seam_cost_flags",
    "_make_seam_cache_key",
    "_multiscale_gain_map",
    "_poisson_seam_blend",
    "_single_pose_soft_edge",
    "_seam_color_match",
    "_soft_seam_weight",
    "_adaptive_gain_clamp",
    "_coherence_skip_mask",
    "_build_seam_cost_map",
    "_gain_to_min_feather",
    "_bg_gain_unclamped",
    "_bg_histogram_lut",
    "_apply_bg_histogram_match",
    "_reject_exposure_outliers",
    "_seam_color_similarity",
    "_seam_color_similarity_bgr",
    "_check_seam_color_gate",
    "_adaptive_sp_threshold",
    "_fg_density_feather_cap",
    "_compute_seam_step_size",
    "_seam_lum_equalize",
    "_adaptive_sp_soft_px",
    "_seam_corridor_exists",
    "_smooth_seam_path",
    "_clamp_seam_path",
    "_has_sufficient_bg",
    "_seam_path_std",
    "_zone_is_degenerate",
    "_seam_fg_penetration",
    "_compute_initial_boundaries",
]

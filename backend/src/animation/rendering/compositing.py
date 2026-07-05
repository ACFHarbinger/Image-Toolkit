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

import concurrent.futures as _cf

from scipy.ndimage import median_filter as _mf
from skimage.metrics import structural_similarity as ssim_fn

from backend.src.animation.alignment.fg_register import register_foreground_at_seam
from backend.src.animation.core.stateless import _laplacian_blend
from backend.src.animation.rendering.anim_fill import _generate_canonical_cel

try:
    import torch as _tc_torch
except ImportError:
    _tc_torch = None  # type: ignore[assignment]

try:
    from backend.src.animation import base as batch
    BATCH_AVAILABLE = True
except ImportError:
    BATCH_AVAILABLE = False

import os
from typing import Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np
from scipy.ndimage import minimum_filter1d as _min_filt1d

from backend.src.constants import (
    FEATHER_MAX,
    FEATHER_MIN,
    FEATHER_TABLE,
    LUMINANCE_WEIGHTS,
    MULTISCALE_GAIN_SIGMA,
    SEAM_CROP_BAND_PX,
    SEAM_OVERLAY_AMBER_THRESH,
    SEAM_OVERLAY_RED_THRESH,
    SEARCH_RANGE,
    SEARCH_SLAB,
)

# §3.11 — Session-level seam ThreadPoolExecutor.  Creating a new pool per
# _composite_foreground call (311 tests × up to 4 workers) causes ~1 200
# pthread_create/join cycles that stall the Linux CFS scheduler.  One shared
# pool, created once on first use, eliminates all thread lifecycle overhead.
_SEAM_POOL: Optional["_cf.ThreadPoolExecutor"] = None


def _get_seam_pool() -> "_cf.ThreadPoolExecutor":
    global _SEAM_POOL
    if _SEAM_POOL is None:
        _SEAM_POOL = _cf.ThreadPoolExecutor(max_workers=4)
    return _SEAM_POOL


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

# §2.10A — Flow HITL callback checkpoint.
# When set, called at single-pose escalation with (seam_k, seam_info).
# If it returns an (H, W, 2) float32 flow array, that flow is used to re-register
# the seam before the normal single-pose decision.  Returning None proceeds normally.
_flow_hitl_callback: Optional[Callable[[int, dict], Optional[np.ndarray]]] = None


def set_flow_hitl_callback(
    cb: Optional[Callable[[int, dict], Optional[np.ndarray]]],
) -> None:
    """Register a callback invoked when a seam escalates to single-pose.

    cb(seam_k, seam_info) -> Optional[np.ndarray[H,W,2 float32]] flow override.
    Returning None lets the normal single-pose escalation proceed.
    """
    global _flow_hitl_callback
    _flow_hitl_callback = cb


# §1.6C — Gradient-domain Poisson seam blend (S21).
# Replaces Laplacian blend with cv2.seamlessClone(NORMAL_CLONE) in a
# ±_POISSON_BAND_PX band around the DP seam path for normal (non-single-pose)
# seams.  Eliminates the brightness step at hard cuts without ghosting.
# Enabled via ASP_POISSON_SEAM=1 (default OFF — adds ~1–3 s per seam on CPU).
_POISSON_SEAM: bool = os.environ.get("ASP_POISSON_SEAM", "0") != "0"
_POISSON_BAND_PX: int = 20

# Phase 4 — cv::detail::GraphCutSeamFinder global multi-image seam.
# Default ON (BATCH_AVAILABLE) — replaces pairwise DP with globally optimal
# multi-image seam; 97-test benchmark showed seam_visibility 6.1× worse with
# pairwise DP as the dominant failure mode.  Set ASP_GRAPHCUT_SEAM=0 to disable.
_GRAPHCUT_SEAM: bool = BATCH_AVAILABLE and os.environ.get("ASP_GRAPHCUT_SEAM", "1") != "0"

# §3.33 — Feather width (px) at GraphCut ownership boundaries.
# A narrow linear alpha ramp eliminates the 1-pixel luminance step at GC transitions.
# Set ASP_GC_FEATHER_PX=0 to disable; default 8px matches half the zone-edge guard width.
_GC_FEATHER_PX: int = int(os.environ.get("ASP_GC_FEATHER_PX", "8"))

# §4.5 — cv::detail::DpSeamFinder canvas-space DP seam.
# Fallback between GraphCut (batch, global) and pairwise DP (local).
# cv2.detail_DpSeamFinder("COLOR_GRAD").find() runs in canvas space across all
# N frames simultaneously, handling 3-way overlaps that pairwise DP misses.
# Enabled via ASP_DP_CANVAS_SEAM=1 (default OFF — only useful when GraphCut
# is disabled; no extra deps beyond opencv-contrib).
_DP_CANVAS_SEAM: bool = os.environ.get("ASP_DP_CANVAS_SEAM", "0") != "0"

# Phase 4 — OpenMP parallel N-1 seam batch via batch.seam.seam_batch
# (ASP_SEAM_BATCH=1, default OFF — replaces ThreadPoolExecutor pre-computation).
_SEAM_BATCH: bool = BATCH_AVAILABLE and os.environ.get("ASP_SEAM_BATCH", "0") != "0"

# Phase 4 — cv::detail::MultiBandBlender global canvas blend
# (ASP_MULTIBAND_BLEND=1, default OFF — adds blender overhead, best for large canvases).
_MULTIBAND_BLEND: bool = BATCH_AVAILABLE and os.environ.get("ASP_MULTIBAND_BLEND", "0") != "0"

# §4.6 — MultiBand confidence-weighted blending. Only takes effect when
# _MULTIBAND_BLEND is also enabled. Replaces the hard 0/255 GraphCut
# ownership mask fed to MultiBandBlender with a smoothly-varying per-frame
# confidence mask (distance-to-seam + bg-mask-edge softening + ECC
# agreement), so the blend pyramid weights uncertain transition pixels more
# gently instead of a binary cut. Default OFF — adds a small amount of
# distance-transform + ECC overhead per composite.
_MULTIBAND_CONF: bool = BATCH_AVAILABLE and os.environ.get("ASP_MULTIBAND_CONF", "0") != "0"
_MULTIBAND_CONF_BAND_PX: int = int(os.environ.get("ASP_MULTIBAND_CONF_BAND_PX", "24"))

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
_SEAM_COLOR_GATE: float = float(os.environ.get("ASP_SEAM_COLOR_GATE", "0.0"))
# §1.14C — Per-channel BGR Bhattacharyya seam gate (S59).
# When enabled, _check_seam_color_gate uses per-channel (B,G,R) histograms
# and returns min(score_B, score_G, score_R) rather than the greyscale score.
# Catches hue-shifted banding where B/G/R differ sharply but luminance is flat.
# Enable via ASP_SEAM_COLOR_GATE_BGR=1 (default OFF — greyscale path is faster).
_SEAM_COLOR_GATE_BGR: bool = os.environ.get("ASP_SEAM_COLOR_GATE_BGR", "0") != "0"

# §1.66 — NCC structural coherence gate (S131).
# After compositing, measures normalised cross-correlation (NCC) between the
# band_px-row windows above and below each seam boundary.  A low NCC (< thresh)
# indicates that the texture *pattern* above and below the boundary is structurally
# discontinuous — different line-art, different character pose — even when the
# Bhattacharyya gate (§1.14B) reports similar colour distributions.
# Complementary to §1.14B (colour histogram) and §1.24 (absolute luma step).
# NCC detects structure/pose mismatch that the other two gates miss.
# Default 0.0 = off.  Recommend ASP_SEAM_NCC_GATE=0.45.
_SEAM_NCC_GATE: float = float(os.environ.get("ASP_SEAM_NCC_GATE", "0.0"))

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

# §1.56 — Post-composite chroma seam correction (S122).
# Complement to §1.21: after luminance equalisation, corrects a/b chroma shift
# across seam boundaries in LAB colour space.  Each strip pair is converted to
# LAB; the mean difference in the 'a' (green↔red) and 'b' (blue↔yellow) channels
# is measured in the reference bands above and below the boundary and a linear
# additive ramp is applied over band_px rows below the boundary.  Targets
# colour-temperature and hue banding that §1.21's luminance-only pass misses.
# Enable via ASP_SEAM_CHROMA_EQ=1 (default OFF).
_SEAM_CHROMA_EQ: bool = os.environ.get("ASP_SEAM_CHROMA_EQ", "0") != "0"

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
_SEAM_HARD_BARRIER_COST: float = float(
    os.environ.get("ASP_SEAM_HARD_BARRIER_COST", "1e6")
)

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
_SEAM_INSTABILITY_THRESH: float = float(
    os.environ.get("ASP_SEAM_INSTABILITY_THRESH", "0.0")
)

# §1.31: Seam foreground-penetration escalation.  After the DP seam path is resolved,
# sample the pixel at each column of the path.  When the fraction of columns where the
# seam cuts through foreground (any-channel > 0 in either frame's zone) exceeds this
# threshold, escalate to single-pose.  Complements §1.23/§3.15 (cost barriers that
# prevent fg routing) by catching cases where the DP routes through fg anyway (e.g.,
# when the entire overlap region is foreground and no background corridor exists).
# Default 0.0 = off.  Recommend 0.7 (>70% fg penetration → character seam, escalate).
_SEAM_FG_PENETRATION_MAX: float = float(
    os.environ.get("ASP_SEAM_FG_PENETRATION_MAX", "0.0")
)

# §1.86 — Zone SSIM pre-gate (S141).
# After ARAP registration and zone extraction, measures SSIM between the two warped
# zone crops.  A score below the threshold means the two strips are structurally
# incompatible — different character poses that ARAP could not reconcile — and
# blending will produce a double-image ghost.  Escalate directly to single-pose.
# Complements §1.60 (fg MAD) and §1.70 (fg coverage) which fire before zone extraction;
# §1.86 fires after ARAP + zone extraction and uses full SSIM rather than pixel L1.
# Default 0.0 = off.  Recommended starting value: ASP_ZONE_PRE_SSIM_THRESH=0.35.
_ZONE_PRE_SSIM_THRESH: float = float(os.environ.get("ASP_ZONE_PRE_SSIM_THRESH", "0.0"))

# §2.4B — Seam overlay annotation (S94).
# When enabled, draws coloured horizontal diagnostic lines on the composite output at
# each seam boundary position: green (post_diff < SEAM_OVERLAY_AMBER_THRESH), amber
# (AMBER_THRESH ≤ diff < RED_THRESH), or red (diff ≥ RED_THRESH or single-pose).
# A short text label (seam index + diff + "SP" flag) is placed at the left edge.
# Enable via ASP_SEAM_OVERLAY=1 (default OFF — zero overhead when disabled).
_SEAM_OVERLAY: bool = os.environ.get("ASP_SEAM_OVERLAY", "0") != "0"

# §1.30: Minimum zone height guard.  When a blend zone is shorter than this many
# rows the boundary clamp (§1.26) leaves at most one valid seam row, the feather
# blend has no headroom, and the DP adds ~1ms overhead for no quality benefit.
# Setting the flag > 0 escalates the boundary directly to single-pose before the
# DP runs.  Default 0 = off.  Recommend 20 (matches the typical S15/S16 soft-edge
# band width; anything narrower cannot be blended cleanly regardless of DP).
_ZONE_MIN_HEIGHT: int = int(os.environ.get("ASP_ZONE_MIN_HEIGHT", "0"))

# §1.34: Seam zone texture-energy pre-escalation.  When the ±30px band around a
# seam boundary has very low Laplacian variance (flat colour — sky, solid fill,
# bare background), ARAP/optical-flow has no gradient to track (aperture problem)
# and reliably produces garbage offsets.  Pre-escalating such seams to single-pose
# avoids the ARAP call entirely at negligible cost.
# Set to 0.0 to disable (default); recommend 5.0 for real sequences.
_SEAM_LOW_TEXTURE_THRESH: float = float(
    os.environ.get("ASP_SEAM_LOW_TEXTURE_THRESH", "0.0")
)

# §1.35: Line-art gradient penalty in seam cost map.
# Additive cost in [0, weight] applied to fg-interior pixels based on normalized
# Laplacian magnitude — steers DP away from character outline pixels.
# Set to 0.0 to disable (default); recommend 1.0 for anime sequences.
_LINE_GRAD_WEIGHT: float = float(os.environ.get("ASP_LINE_GRAD_WEIGHT", "0.0"))

# §1.65 — Foreground mask erosion buffer for seam cost (S130).
# After standard fg/dilated-edge Tier-1 costs are applied, erode the fg mask
# by FG_SEAM_EROSION_PX pixels before assigning cost=1.0.  This shrinks the
# high-cost region by one ring of character-outline pixels, creating a
# transition zone where the cost is 0.5 (edge buffer) instead of 1.0.
# Effect: DP seams are nudged one ring outward from the character silhouette —
# the seam cuts through the character's soft-edge halo rather than the hard
# outline itself, reducing the colour step at single-pixel outline edges.
# Complementary to §1.35 (line-art gradient penalty) which raises outline cost;
# §1.65 lowers the border ring to make it the DP's preferred path.
# Default 0 = off.  Recommend ASP_FG_SEAM_EROSION_PX=2 (one outline ring ≈ 2 px).
_FG_SEAM_EROSION_PX: int = int(os.environ.get("ASP_FG_SEAM_EROSION_PX", "0"))

# §3.15B — OBJ-GSP triangular mesh seam barrier (S144).
# Builds a Delaunay triangulation on the fg contour points and rasterises each
# triangle as a 1e6 hard barrier, preventing the DP seam from routing inside any
# mesh triangle that belongs to the character body.  Complementary to §3.15A
# (column soft-barrier, 2.0) and §1.23 (hard column barrier, 1e6).
# Default OFF.  Enable: ASP_MESH_BARRIER=1.
_MESH_BARRIER: bool = os.environ.get("ASP_MESH_BARRIER", "0") != "0"

# §1.88 — Per-channel ECDF histogram matching in seam blend band (S147).
# More robust than S16 mean-shift: transfers the full luminance distribution
# of oth_zone to match dom_zone inside the blend band, handling cases where
# the two zones have different exposure curves (not just different means).
# Default OFF.  Enable: ASP_HIST_MATCH_SEAM=1.
_HIST_MATCH_SEAM: bool = os.environ.get("ASP_HIST_MATCH_SEAM", "0") != "0"

# §1.89 — Seam processing order by ascending residual (S147).
# Blend loop processes seams from lowest post_warp_diff to highest so that
# the best-quality seams establish the reference quality baseline.
# Default OFF (linear order).  Enable: ASP_SEAM_ORDER=residual.
_SEAM_ORDER_RESIDUAL: bool = os.environ.get("ASP_SEAM_ORDER", "") == "residual"

# §1.90 — Post-composite bilateral seam smoothing pass (S147).
# After all seams are blended, applies a narrow bilateral filter in ±5px
# columns around each seam path to smooth residual 1–3 lum-unit color steps.
# Default OFF.  Enable: ASP_BILATERAL_SEAM=1.
_BILATERAL_SEAM: bool = os.environ.get("ASP_BILATERAL_SEAM", "0") != "0"

# §3.17 — High-frequency column seam cost (S147).
# Adds per-column Laplacian energy as an additive cost term in _build_seam_cost_map,
# routing the DP seam away from high-frequency texture columns.
# Default OFF.  Enable: ASP_HF_SEAM_COST=1.
_HF_SEAM_COST: bool = os.environ.get("ASP_HF_SEAM_COST", "0") != "0"
_HF_SEAM_THRESHOLD: float = float(os.environ.get("ASP_HF_SEAM_THRESHOLD", "50.0"))
_HF_SEAM_BOOST: float = float(os.environ.get("ASP_HF_SEAM_BOOST", "0.5"))

# §1.91 — Iterative seam luminance convergence (S148).
# After _seam_color_match + §1.88 histogram match, measures residual mean delta;
# if > target applies another _seam_color_match pass (max 2 total passes).
# Guarantees the band delta is < ASP_SEAM_LUM_CONVERGE_TARGET lum units.
# Default OFF.  Enable: ASP_SEAM_LUM_CONVERGE=1.
_SEAM_LUM_CONVERGE: bool = os.environ.get("ASP_SEAM_LUM_CONVERGE", "0") != "0"
_SEAM_LUM_CONVERGE_TARGET: float = float(
    os.environ.get("ASP_SEAM_LUM_CONVERGE_TARGET", "5.0")
)

# §1.92 — Gaussian smooth on feather widths between adjacent seams (S148).
# Applies a 1-D Gaussian smooth (σ=1 seam) after the feather computation to
# prevent jarring width transitions between adjacent low/high-residual seams.
# Default OFF.  Enable: ASP_SMOOTH_FEATHER=1.
_SMOOTH_FEATHER: bool = os.environ.get("ASP_SMOOTH_FEATHER", "0") != "0"
_SMOOTH_FEATHER_SIGMA: float = float(os.environ.get("ASP_SMOOTH_FEATHER_SIGMA", "1.0"))

# §1.95 — Fg-zone single-pose threshold scaling (S149).
# When the blend zone has a high fg fraction, lower the post-warp diff threshold
# for single-pose escalation.  Fg-dominated zones produce worse ghosts when
# blended; reducing the threshold escalates them to single-pose earlier.
# Default OFF.  Enable: ASP_SP_THRESH_FG_SCALE=1.
_SP_THRESH_FG_SCALE: bool = os.environ.get("ASP_SP_THRESH_FG_SCALE", "0") != "0"
_SP_THRESH_FG_FACTOR: float = float(os.environ.get("ASP_SP_THRESH_FG_FACTOR", "0.7"))
_SP_FG_FRAC_THRESH: float = float(os.environ.get("ASP_SP_FG_FRAC_THRESH", "0.5"))

# §3.19 — Per-zone pre-blend chroma alignment (S149).
# Globally shifts fb_zone's LAB a/b mean to match fa_zone before Laplacian
# blending, reducing colour-temperature banding at seam boundaries.
# Default OFF.  Enable: ASP_ZONE_CHROMA_ALIGN=1.
_ZONE_CHROMA_ALIGN: bool = os.environ.get("ASP_ZONE_CHROMA_ALIGN", "0") != "0"

# §1.97 — Seam zone entropy asymmetry gate (S149).
# Pre-escalates to single-pose when entropy gap between the two zone crops
# exceeds the threshold (bits).  One near-flat zone + one textured zone means
# ARAP flow has no gradient signal on the flat side → spurious warp vectors.
# Default OFF.  Set to e.g. ASP_ENTROPY_GAP_THRESH=1.5 to enable.
_ENTROPY_GAP_THRESH: float = float(os.environ.get("ASP_ENTROPY_GAP_THRESH", "0.0"))

# §1.98 — Per-frame gain normalization smoothing (S150).
# After computing per-frame bg gain corrections, applies a 1-D Gaussian smooth
# (σ=1 frame) over the frame_gains array and re-applies the ratio correction to
# warped_norm, preventing abrupt inter-strip brightness jumps from isolated
# outlier gain values.
# Default OFF.  Enable: ASP_SMOOTH_GAIN=1.
_SMOOTH_GAIN: bool = os.environ.get("ASP_SMOOTH_GAIN", "0") != "0"
_SMOOTH_GAIN_SIGMA: float = float(os.environ.get("ASP_SMOOTH_GAIN_SIGMA", "1.0"))

# §3.20 — Extra fg-boundary outer dilation cost ring (S150).
# Adds a 0.3-cost outer ring around the existing Tier-2 fg-edge buffer in the
# seam cost map.  Creates a cost gradient 0→0.3→0.5→1.0 from background to
# fg-interior, pushing the DP seam further from character edges.
# Default 0 (OFF).  Set: ASP_EXTRA_FG_DILATION=8 (pixels).
_EXTRA_FG_DILATION: int = int(os.environ.get("ASP_EXTRA_FG_DILATION", "0"))

# §1.99 — Seam endpoint bg-preference (S150).
# In the top/bottom ASP_SEAM_PIN_ROWS rows of each blend zone, amplifies fg
# pixel costs by 10× in the seam cost map, steering the DP seam path to enter
# and exit through background-only columns.
# Default 0 (OFF).  Set: ASP_SEAM_PIN_ROWS=3.
_SEAM_PIN_ROWS: int = int(os.environ.get("ASP_SEAM_PIN_ROWS", "0"))

# §1.101 — Blend-zone full MAD pre-escalation (S151).
# When the mean absolute per-pixel difference between the two warped zone
# crops exceeds ASP_ZONE_MAD_THRESH, escalates to single-pose before the DP.
# Broader than §1.60 (fg-only MAD): catches the case where bg colour differs
# significantly across the two frames in the blend zone.
# Default 0.0 (OFF).  Set: ASP_ZONE_MAD_THRESH=30.0.
_ZONE_MAD_THRESH: float = float(os.environ.get("ASP_ZONE_MAD_THRESH", "0.0"))

# §1.102 — Warp residual momentum damping (S151).
# When the previous seam (k-1) was a single-pose fallback, lower the SP
# threshold for the current seam by ASP_WARP_MOMENTUM_FACTOR.  Adjacent seams
# sharing a frame often share the same pose discontinuity; early pre-escalation
# prevents ARAP from spending compute on unregisterable zones.
# Default OFF.  Enable: ASP_WARP_MOMENTUM_DAMP=1.
_WARP_MOMENTUM_DAMP: bool = os.environ.get("ASP_WARP_MOMENTUM_DAMP", "0") != "0"
_WARP_MOMENTUM_FACTOR: float = float(os.environ.get("ASP_WARP_MOMENTUM_FACTOR", "0.85"))

# §1.103 — Reference-proximity dominant frame selection (S151).
# When escalating to single-pose, chooses the frame temporally closest to the
# reference frame (ref_fi) as the dominant, rather than the frame with more fg
# pixels.  The reference frame has the least accumulated warp drift, making it
# the most geometrically reliable choice.
# Default OFF.  Enable: ASP_SP_REF_PROX=1.
_SP_REF_PROX: bool = os.environ.get("ASP_SP_REF_PROX", "0") != "0"

# §1.104 — Per-zone luminance normalization before blend (S152).
# Equalises the mean luminance of fb_zone background pixels to match fa_zone
# before the Laplacian blend.  Distinct from §1.56 (post-composite strip lum)
# and §3.19 (LAB chroma): targets bg-pixel lum mismatch at the zone level.
# Default OFF.  Enable: ASP_ZONE_LUM_NORM=1.
_ZONE_LUM_NORM: bool = os.environ.get("ASP_ZONE_LUM_NORM", "0") != "0"

# §1.105 — Fg-overlap Laplacian blend weight cap (S152).
# When both zones have foreground content at a pixel, the Laplacian blend can
# produce a double-image ghost even with a well-placed DP seam.  This flag
# caps mask_float at ASP_FG_OVERLAP_BLEND_CAP (0=dominant-only, 0.5=equal)
# for pixels where both zones have fg content AND their lum differs by >10.
# Default 0.0 (OFF — cap disabled).  Set: ASP_FG_OVERLAP_BLEND_CAP=0.3.
_FG_OVERLAP_BLEND_CAP: float = float(os.environ.get("ASP_FG_OVERLAP_BLEND_CAP", "0.0"))

# §1.106 — Post-composite seam luminance step audit (S152).
# After all seams are composited, measures the mean absolute lum step at each
# boundary row in the final output and logs warnings for large steps.
# ASP_POST_SEAM_WARN_THRESH sets the warning threshold (default 8.0 lum units).
# Always runs when boundaries are available (negligible overhead).
_POST_SEAM_WARN_THRESH: float = float(
    os.environ.get("ASP_POST_SEAM_WARN_THRESH", "8.0")
)

# §1.107 — Adaptive seam band width from zone height (S153).
# Replaces the fixed band_px = _sp_soft_px + 4 formula in the single-pose
# colour correction path with a zone-height-aware value: band_px is at least
# base_band but grows with zone height up to max_band=40px.
# Default OFF.  Enable: ASP_ADAPTIVE_SEAM_BAND=1.
_ADAPTIVE_SEAM_BAND: bool = os.environ.get("ASP_ADAPTIVE_SEAM_BAND", "0") != "0"
_ADAPTIVE_SEAM_BAND_MAX: int = int(os.environ.get("ASP_ADAPTIVE_SEAM_BAND_MAX", "40"))

# §1.108 — Laplacian blend alpha schedule (S153).
# Fine Laplacian pyramid levels (high frequency) use a sharpened blend mask
# (mask ** 2) while coarse levels use the original mask.  This reduces high-
# frequency colour bleeding at character edges while keeping smooth transitions
# at low frequencies.
# Default OFF.  Enable: ASP_LAPLACIAN_ALPHA_SCHEDULE=1.
_LAPLACIAN_ALPHA_SCHEDULE: bool = (
    os.environ.get("ASP_LAPLACIAN_ALPHA_SCHEDULE", "0") != "0"
)

# §1.109 — Seam cost map L-inf normalization (S153).
# Normalizes the seam cost map (excluding hard-barrier pixels >= 1e5) to [0, 1]
# before returning, ensuring stable relative cost tiers regardless of additive
# HF column boosts (§3.17) or line-art gradient penalties (§1.35).
# Default OFF.  Enable: ASP_COST_MAP_NORM=1.
_COST_MAP_NORM: bool = os.environ.get("ASP_COST_MAP_NORM", "0") != "0"

# §1.110 — Seam cost map Gaussian blur (S154).
# After computing the seam cost map (and optional §1.109 norm), applies a
# Gaussian blur to the soft-cost region (cost < 1e5) to smooth transitions
# between cost tiers.  DP oscillation occurs when adjacent columns have equal
# or near-equal costs — blurring creates a smooth gradient that guides the DP
# seam toward low-cost background corridors.
# sigma=0.0 → off.  Recommend ASP_COST_MAP_BLUR_SIGMA=2.0.
_COST_MAP_BLUR_SIGMA: float = float(os.environ.get("ASP_COST_MAP_BLUR_SIGMA", "0.0"))

# §1.111 — Zone background saturation normalization (S154).
# After zone lum-norm, matches the mean HSV saturation of background pixels
# in *fb_zone* to those in *fa_zone*.  Corrects chromatic seam banding that
# persists after lum-norm when one frame has a more saturated background
# (e.g. warm sunset vs cool indoor palette shift across a hold transition).
# Default OFF.  Enable: ASP_ZONE_SAT_NORM=1.
_ZONE_SAT_NORM: bool = os.environ.get("ASP_ZONE_SAT_NORM", "0") != "0"

# §1.112 — Seam path vertical drift gate (S154).
# Computes the maximum absolute column-to-column jump in the DP seam path
# (``max(|path[i+1] - path[i]|)``).  A large jump indicates the seam makes
# a sudden discontinuous vertical leap — this produces a kink artifact
# visible as a diagonal slash even after §1.25 smoothing.  When drift exceeds
# the threshold and the seam is not already single-pose-escalated, the blend
# loop escalates it to single-pose (dominant frame by fg pixel count).
# Default OFF (0).  Recommend ASP_SEAM_DRIFT_THRESH=15.
_SEAM_DRIFT_THRESH: float = float(os.environ.get("ASP_SEAM_DRIFT_THRESH", "0.0"))

# §1.113 — Seam cost map column-wise Gaussian smooth (S155).
# Applies scipy.ndimage.gaussian_filter1d along axis=1 (horizontal) on the
# soft-cost region after all tier computations.  Creates lateral cost gradients
# that prevent DP zigzag between adjacent equal-cost columns.
# Default 0.0 (OFF).  Set: ASP_COST_COL_SMOOTH_SIGMA=1.5.
_COST_COL_SMOOTH_SIGMA: float = float(
    os.environ.get("ASP_COST_COL_SMOOTH_SIGMA", "0.0")
)

# §1.114 — Zone RMS contrast equalization before blend (S155).
# Scales fb_zone so its luminance standard deviation over non-black pixels
# matches fa_zone's.  Corrects contrast-wash banding that §1.104 (mean lum)
# cannot fix — two strips may have the same mean but very different contrast.
# Default OFF.  Enable: ASP_ZONE_CONTRAST_EQ=1.
_ZONE_CONTRAST_EQ: bool = os.environ.get("ASP_ZONE_CONTRAST_EQ", "0") != "0"

# §1.115 — Absolute feather jump cap (S155).
# After §1.68 ratio cap, further enforces that adjacent feather values differ
# by at most ASP_FEATHER_JUMP_MAX pixels.  Complements §1.68 (ratio-based) by
# bounding absolute jumps for very wide sequences.
# Default 0 (OFF).  Set: ASP_FEATHER_JUMP_MAX=150.
_FEATHER_JUMP_MAX: int = int(os.environ.get("ASP_FEATHER_JUMP_MAX", "0"))

# §1.116 — Blend zone bg-fraction diagnostic (S156).
# Records the bg fraction of each blend zone (fraction of pixels classified
# as background in the union of the two frame masks) and stores it in the
# debug context as zone_bg_fracs.  Negligible overhead — warped_bg is already
# sliced for §1.70.  Only activates when debug_context is provided.
_ZONE_BG_FRAC_DIAG: bool = os.environ.get("ASP_ZONE_BG_FRAC_DIAG", "0") != "0"

# §1.117 — Fast zone NCC structural pre-gate (S156).
# Thumbnail-based (32×32) NCC between the two warped zone crops.  Much faster
# than §1.86 SSIM while catching the same gross pose mismatches.  Can be used
# standalone (§1.86 disabled) or as a fast pre-filter before expensive SSIM.
# Default 0.0 (OFF).  Set: ASP_ZONE_FAST_NCC_THRESH=0.3.
_ZONE_FAST_NCC_THRESH: float = float(os.environ.get("ASP_ZONE_FAST_NCC_THRESH", "0.0"))

# §1.118 — Post-composite seam sharpness guard (S156).
# After blending all seams, measures Laplacian variance in a ±5px band around
# each boundary.  Logs a "blur warning" when sharpness drops below
# ASP_SEAM_SHARP_MIN.  Stores seam_sharpness/max_seam_blur in debug_context.
# Default 0.0 (OFF — log only, no correction).
_SEAM_SHARP_MIN: float = float(os.environ.get("ASP_SEAM_SHARP_MIN", "0.0"))

# §1.119 — Seam zone width variance gate (S157).
# After boundary optimisation, measures the coefficient of variation (std/mean)
# of adjacent zone widths (boundary[k+1] - boundary[k]).  High CV means the
# boundary search produced an uneven layout — some zones very narrow, others
# very wide — which often correlates with a bad BA outcome.  When CV exceeds
# ASP_ZONE_WIDTH_CV_MAX, the worst (narrowest) seam is pre-escalated to
# single-pose before DP.  Default 0.0 (OFF).
_ZONE_WIDTH_CV_MAX: float = float(os.environ.get("ASP_ZONE_WIDTH_CV_MAX", "0.0"))

# §1.120 — Post-composite saturation step audit (S157).
# Analogous to §1.106 lum audit: measures mean HSV saturation difference in
# ±5px bands at each seam boundary.  High sat-step = colour-saturation seam
# artifact (chroma banding not caught by luminance-only checks).  Logs a warning
# when step exceeds ASP_SEAM_SAT_WARN_THRESH.  Stores seam_sat_steps /
# max_seam_sat_step in seam_meta_out.  Default 0.0 (OFF — no logging).
_SEAM_SAT_WARN_THRESH: float = float(os.environ.get("ASP_SEAM_SAT_WARN_THRESH", "0.0"))

# §1.121 — Zone histogram intersection pre-gate (S157).
# Fast per-zone histogram intersection score between the two warped zone crops
# (mean across 3 channels).  Score in [0, 1]: 1.0 = identical histograms,
# 0.0 = completely disjoint.  When score falls below threshold and the seam is
# not already single-pose, pre-escalates to single-pose before DP cut.
# Complementary to §1.117 NCC (structural) — catches colour-palette shifts that
# NCC misses.  Default 0.0 (OFF).  Set: ASP_ZONE_HIST_THRESH=0.5.
_ZONE_HIST_THRESH: float = float(os.environ.get("ASP_ZONE_HIST_THRESH", "0.0"))

# §1.122 — High seam path cost escalation (S158).
# After the DP seam cut, computes the mean cost value along the selected path.
# When the mean path cost exceeds the threshold (seam could not avoid fg-interior
# pixels), escalates to single-pose before blending.  Complementary to §1.69
# (bg-ratio gate): catches routes that are nominally in background but still
# incur high aggregate cost (e.g. many scattered fg pixels).
# Default 0.0 (OFF).  Recommended: ASP_HIGH_PATH_COST_THRESH=0.6.
_HIGH_PATH_COST_THRESH: float = float(
    os.environ.get("ASP_HIGH_PATH_COST_THRESH", "0.0")
)

# §1.123 — Local scatter penalty in seam cost map (S158).
# Adds a per-pixel local pixel-variance term to the seam cost map before DP.
# High-variance regions (texture edges, noise, scattered fg debris) receive an
# additive penalty proportional to their local variance relative to the zone max.
# Routes the seam toward spatially uniform (smooth background) corridors.
# Enable: ASP_SCATTER_COST=1.  Weight: ASP_SCATTER_COST_WEIGHT (default 0.3).
_SCATTER_COST: bool = os.environ.get("ASP_SCATTER_COST", "0") != "0"
_SCATTER_COST_WEIGHT: float = float(os.environ.get("ASP_SCATTER_COST_WEIGHT", "0.3"))

# §1.124 — Adaptive single-pose soft-edge width from seam residual (S158).
# After the feather-based adaptive width (§1.22), further clips the soft-edge
# pixel count based on the post-warp diff for this seam:
#   diff > 30 lum units (bad warp) → clamp to _ADAPTIVE_SP_SOFT_MIN (narrow)
#   diff < 10 lum units (clean warp) → widen to _ADAPTIVE_SP_SOFT_MAX
# Only active when ASP_ADAPTIVE_SP_SOFT=1 (umbrella flag from §1.22).
# ASP_ADAPTIVE_SP_SOFT_MIN default 3, ASP_ADAPTIVE_SP_SOFT_MAX default 10.
_ADAPTIVE_SP_SOFT_MIN: int = int(os.environ.get("ASP_ADAPTIVE_SP_SOFT_MIN", "3"))
_ADAPTIVE_SP_SOFT_MAX: int = int(os.environ.get("ASP_ADAPTIVE_SP_SOFT_MAX", "10"))

# §1.125 — Seam transition straightness penalty (S159).
# Adds a row-distance-from-midline cost to the energy matrix in _seam_cut,
# creating a mild prior toward straight horizontal seam paths.  High penalty
# pushes the seam toward the zone midline; low penalty preserves natural
# low-energy routing around fg content.  Default 0.0 (off).
# Enable: ASP_SEAM_TRANSITION_PEN=<float> (e.g. 5.0).
_SEAM_TRANSITION_PEN: float = float(os.environ.get("ASP_SEAM_TRANSITION_PEN", "0.0"))

# §1.126 — Fg-majority column floor in seam cost map (S159).
# When the entire blend zone is >60% foreground, raises columns that are >80%
# fg to at least _FG_MAJORITY_FLOOR so the DP seam is pushed toward the
# minority background corridor columns.  Default 0.0 (off).
# Enable: ASP_FG_MAJORITY_FLOOR=<float> (e.g. 1.5).
_FG_MAJORITY_FLOOR: float = float(os.environ.get("ASP_FG_MAJORITY_FLOOR", "0.0"))

# §1.127 — Per-zone HSV hue equalization (S159).
# After §1.114 contrast-eq, shifts the mean hue of fb_zone to match fa_zone
# in the seam band.  Only fires when the mean hue difference exceeds
# ZONE_HUE_EQ_MIN_DIFF_DEG degrees to avoid nudging naturally similar zones.
# Default OFF.  Enable: ASP_ZONE_HUE_EQ=1.
_ZONE_HUE_EQ: bool = os.environ.get("ASP_ZONE_HUE_EQ", "0") != "0"

# §4.1 — Spatial blocks gain compensation (S160).
# After per-frame luminance normalisation, divide the blend zone into 32×32
# blocks and compute a per-block BGR gain ratio (fa/fb).  A bilinear-resized
# gain map (clamped [0.5, 2.0]) is applied to fb_zone before blending.
# Targets strip-level banding that the global scalar gain cannot handle.
# Default ON (§4.10 pre-seam equalization covers GraphCut; DP path also corrects).
_BLOCKS_GAIN_COMP: bool = os.environ.get("ASP_BLOCKS_GAIN_COMP", "1") != "0"

# §4.4 — Per-channel luminance blocks gain compensation (S160).
# Like §4.1 but uses the LAB L-channel ratio as a scalar gain applied to all
# BGR channels — avoids color cast from near-zero individual channel means.
# Default ON — LAB L-channel complement to BGR gain (no colour-cast risk).
_BLOCKS_LUM_COMP: bool = os.environ.get("ASP_BLOCKS_LUM_COMP", "1") != "0"

# §4.10 — Pre-seam global gain equalization (S165).
# Applied to ALL warped frames before GraphCut / DP seam finding.  Sequential
# pairwise _blocks_gain_compensate calls equalize inter-frame luminance to
# reduce strip_banding_score and seam_visibility.  Frame 0 (reference) unchanged.
# Only corrects pixels where BOTH adjacent frames have valid content (non-black).
# Default ON.  Set ASP_GLOBAL_GAIN_COMP=0 to disable.
_GLOBAL_GAIN_COMP: bool = os.environ.get("ASP_GLOBAL_GAIN_COMP", "1") != "0"

# §1.60 — Foreground pose-gap pre-escalation (S124).
# Before the DP seam cut, measures the mean absolute difference (MAD) between
# the two warped frames restricted to their common foreground pixels in the
# blend zone.  A high fg MAD indicates the character is in a substantially
# different animation pose in the two frames — ARAP/flow registration cannot
# bridge a large pose discontinuity, and the resulting Laplacian blend produces
# a double-image ghost regardless of seam path quality.  Pre-escalating to
# single-pose in these cases prevents the DP from routing a well-placed seam
# through incoherent fg content.
# Measured in [0, 255] luminance units.  Default 0.0 = off.
# Recommend ASP_FG_POSE_GAP_THRESH=35.0 (visible pose step threshold).
_FG_POSE_GAP_THRESH: float = float(os.environ.get("ASP_FG_POSE_GAP_THRESH", "0.0"))

# §1.68 — Adjacent feather ratio enforcement (S132).
# After all per-seam feather widths are computed (§1.6B, §1.19), a large
# feather-width jump between adjacent seams creates a visible "rhythm"
# discontinuity: one seam blends over 300 px, the next over 80 px, producing
# an obvious tonal gradient difference.  When max_ratio > 0, iteratively clamp
# each seam's feather so that no two adjacent seams differ by more than max_ratio
# fold.  Two-pass (forward + backward) for chain stability.
# Default 0.0 = off.  Recommend ASP_FEATHER_RATIO_MAX=3.0.
_FEATHER_RATIO_MAX: float = float(os.environ.get("ASP_FEATHER_RATIO_MAX", "0.0"))

# §1.69 — Seam DP background routing ratio (S132).
# After _seam_cut() produces the DP traceback path, sample bg_mask values at
# each (column, path[column]) position.  The fraction of columns where BOTH
# frame masks classify the seam pixel as background measures how well the DP
# found a genuine background corridor.  A low ratio means the seam was forced
# through character pixels despite cost-map steering.  When ratio < threshold
# and no prior single-pose decision exists, escalate to single-pose.
# Default 0.0 = off.  Recommend ASP_SEAM_DP_BG_MIN=0.30.
_SEAM_DP_BG_MIN: float = float(os.environ.get("ASP_SEAM_DP_BG_MIN", "0.0"))

# §1.70 — Blend zone fg coverage pre-escalation (S132).
# Before the DP seam cut, measure the fraction of the blend zone that is
# foreground in EITHER frame (union of both masks).  When the entire zone is
# fg-dominated (e.g., a standing character fills the full overlap between two
# frames), §1.23/§3.15 cost barriers cannot route the seam into background
# because no background exists in the zone.  Pre-escalating to single-pose
# avoids DP on an infeasible cost landscape and prevents the seam from
# bisecting the character at its thinnest accessible point.
# Complementary to §1.31 (which checks fg penetration AFTER the DP runs).
# Default 0.0 = off.  Recommend ASP_SEAM_ZONE_FG_MAX=0.85.
_SEAM_ZONE_FG_MAX: float = float(os.environ.get("ASP_SEAM_ZONE_FG_MAX", "0.0"))


def _fg_zone_pose_gap(fa_zone: np.ndarray, fb_zone: np.ndarray) -> float:
    """§1.60: Mean absolute luminance difference between two blend-zone crops
    restricted to their common foreground pixels (S124).

    Returns the mean absolute difference (MAD) of the grayscale luminance
    values at pixels where BOTH frames have non-zero content.  This is a
    frame-level pose-gap estimator: high MAD → different animation poses;
    low MAD → same (or very similar) pose.

    Parameters
    ----------
    fa_zone, fb_zone : (zone_h, W, 3) uint8 crops of the two warped frames
                       in the blend zone.

    Returns
    -------
    float
        MAD in [0, 255].  Returns 0.0 when fewer than 10 shared fg pixels
        exist (degenerate case — no meaningful comparison possible).
    """
    both_fg = (fa_zone.max(axis=2) > 0) & (fb_zone.max(axis=2) > 0)
    n_shared = int(both_fg.sum())
    if n_shared < 10:
        return 0.0
    lum_a = (
        fa_zone[..., 0].astype(np.float32) * 0.114
        + fa_zone[..., 1].astype(np.float32) * 0.587
        + fa_zone[..., 2].astype(np.float32) * 0.299
    )
    lum_b = (
        fb_zone[..., 0].astype(np.float32) * 0.114
        + fb_zone[..., 1].astype(np.float32) * 0.587
        + fb_zone[..., 2].astype(np.float32) * 0.299
    )
    return float(np.mean(np.abs(lum_a[both_fg] - lum_b[both_fg])))


def _enforce_feather_ratio(feathers: List[int], max_ratio: float = 3.0) -> List[int]:
    """§1.68: Clamp adjacent feather-width jumps to at most *max_ratio*-fold (S132).

    After §1.6B/§1.19 compute per-seam feather widths, adjacent seams can differ
    dramatically (e.g. 80 px next to 300 px).  The 3× blend-zone size difference
    creates a visible tonal rhythm discontinuity independent of seam quality.
    This function enforces a maximum ratio between consecutive feathers via a
    forward pass (left-to-right clamp) followed by a backward pass (right-to-left
    clamp) for chain stability.

    Parameters
    ----------
    feathers:
        List or array of integer feather half-widths (px).
    max_ratio:
        Maximum fold-change between adjacent seams.  0.0 or negative → no-op.

    Returns
    -------
    list[int]
        Adjusted feather widths (new list; input is not modified).
    """
    if max_ratio <= 0.0 or len(feathers) <= 1:
        return list(feathers)
    result = [max(1, f) for f in feathers]
    for k in range(len(result) - 1):
        if result[k + 1] > result[k] * max_ratio:
            result[k + 1] = int(result[k] * max_ratio)
    for k in range(len(result) - 2, -1, -1):
        if result[k] > result[k + 1] * max_ratio:
            result[k] = int(result[k + 1] * max_ratio)
    return result


def _seam_dp_bg_ratio(
    path: np.ndarray,
    bg_mask_a: Optional[np.ndarray],
    bg_mask_b: Optional[np.ndarray],
) -> float:
    """§1.69: Fraction of the seam path that routes through background (S132).

    Samples the background mask values at each ``(x, path[x])`` position along
    the DP traceback.  Returns the fraction of columns where BOTH frame masks
    classify the seam pixel as background (True).  A value near 1.0 means the
    DP found a genuine background corridor; a value near 0.0 means the seam was
    forced through character pixels despite §1.23/§3.15 cost-map steering.

    Parameters
    ----------
    path:
        1-D int32 array of length W; ``path[x]`` is the seam row for column x.
    bg_mask_a, bg_mask_b:
        Boolean arrays (H_zone, W), True = background pixel.  Either may be
        *None* (treated as all-background for its contribution).

    Returns
    -------
    float
        Fraction in [0, 1]; 1.0 when no masks provided (safe default).
    """
    if len(path) == 0:
        return 1.0
    if bg_mask_a is None and bg_mask_b is None:
        return 1.0
    ref = bg_mask_a if bg_mask_a is not None else bg_mask_b
    H = ref.shape[0]
    W = len(path)
    xs = np.arange(W, dtype=np.int32)
    ys = np.clip(path.astype(np.int32), 0, H - 1)

    bg_a = bg_mask_a[ys, xs].astype(bool) if bg_mask_a is not None else np.ones(W, dtype=bool)

    bg_b = bg_mask_b[ys, xs].astype(bool) if bg_mask_b is not None else np.ones(W, dtype=bool)

    both_bg = bg_a & bg_b
    return round(float(both_bg.mean()), 4)


def _fg_fraction_in_zone(
    bg_mask_a: Optional[np.ndarray],
    bg_mask_b: Optional[np.ndarray],
) -> float:
    """§1.70: Fraction of blend-zone pixels classified as fg in either frame (S132).

    Computes the union foreground fraction: pixels where EITHER bg_mask_a or
    bg_mask_b is False (foreground) count toward the result.  When the entire
    overlap zone is character-dominated (fraction → 1.0), no background corridor
    exists for the DP seam to route through — pre-escalating to single-pose is
    more reliable than running the DP on an infeasible cost landscape.

    Parameters
    ----------
    bg_mask_a, bg_mask_b:
        Boolean arrays (H_zone, W), True = background pixel.  Either may be
        *None* (treated as all-background for its contribution, i.e. adds zero
        to the fg union).

    Returns
    -------
    float
        Fraction in [0, 1]; 0.0 when both masks are None (safe default).
    """
    if bg_mask_a is None and bg_mask_b is None:
        return 0.0
    if bg_mask_a is None:
        fg_union = ~bg_mask_b.astype(bool)
    elif bg_mask_b is None:
        fg_union = ~bg_mask_a.astype(bool)
    else:
        fg_union = (~bg_mask_a.astype(bool)) | (~bg_mask_b.astype(bool))
    return float(fg_union.mean())


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


def _zone_pair_ssim(
    fa_zone: np.ndarray,
    fb_zone: np.ndarray,
    small_h: int = 64,
) -> float:
    """§1.86 Zone SSIM pre-gate (S141).

    Measures the Structural Similarity Index (SSIM) between two warped zone
    crops.  Used in the blend loop after §1.70 to detect structurally
    incompatible zones — different character poses that ARAP could not reconcile
    — before the DP seam cut runs.

    A low score indicates that blending will produce a double-image ghost, so
    single-pose escalation is preferred.  Unlike §1.60 (fg MAD, pixel L1) this
    metric combines luminance, contrast, and local structure into a single
    perceptually-motivated score.

    Parameters
    ----------
    fa_zone, fb_zone : Warped BGR uint8 zone crops (H, W, 3).
    small_h : Target height for INTER_AREA resize; reduces SSIM compute time.

    Returns
    -------
    float in [−1, 1]; returns 1.0 (no gate) for degenerate zones.
    """
    h = min(fa_zone.shape[0], fb_zone.shape[0])
    w = min(fa_zone.shape[1], fb_zone.shape[1])
    if h < 4 or w < 8:
        return 1.0
    ratio = small_h / max(h, 1)
    new_h = max(4, small_h)
    new_w = max(8, int(w * ratio))
    a_small = cv2.resize(fa_zone[:h, :w], (new_w, new_h), interpolation=cv2.INTER_AREA)
    b_small = cv2.resize(fb_zone[:h, :w], (new_w, new_h), interpolation=cv2.INTER_AREA)
    a_gray = cv2.cvtColor(a_small, cv2.COLOR_BGR2GRAY) if a_small.ndim == 3 else a_small
    b_gray = cv2.cvtColor(b_small, cv2.COLOR_BGR2GRAY) if b_small.ndim == 3 else b_small
    try:
        return float(ssim_fn(a_gray, b_gray, data_range=255))
    except Exception:
        return 1.0


def _zone_pair_ncc(
    fa_zone: np.ndarray, fb_zone: np.ndarray, thumb_size: int = 32
) -> float:
    """§1.117: Fast thumbnail NCC between two warped zone crops (S156).

    Resizes both zones to *thumb_size*×*thumb_size* grayscale, then computes
    normalized cross-correlation.  Returns value in [-1, 1]; 1.0 = identical,
    near-0 or negative = structurally incompatible.  Returns 1.0 for
    degenerate zones (too small to resize or zero-norm).
    """
    if fa_zone.size == 0 or fb_zone.size == 0:
        return 1.0
    h = min(fa_zone.shape[0], fb_zone.shape[0])
    w = min(fa_zone.shape[1], fb_zone.shape[1])
    if h < 4 or w < 4:
        return 1.0
    a_gray = cv2.cvtColor(fa_zone[:h, :w], cv2.COLOR_BGR2GRAY).astype(np.float32)
    b_gray = cv2.cvtColor(fb_zone[:h, :w], cv2.COLOR_BGR2GRAY).astype(np.float32)
    a_th = cv2.resize(
        a_gray, (thumb_size, thumb_size), interpolation=cv2.INTER_AREA
    ).ravel()
    b_th = cv2.resize(
        b_gray, (thumb_size, thumb_size), interpolation=cv2.INTER_AREA
    ).ravel()
    a_th = a_th - a_th.mean()
    b_th = b_th - b_th.mean()
    denom = float(np.linalg.norm(a_th) * np.linalg.norm(b_th))
    if denom < 1e-6:
        return 1.0
    return float(np.dot(a_th, b_th) / denom)


def _annotate_seams(
    canvas: np.ndarray,
    boundaries: np.ndarray,
    seam_post_diffs: dict,
    seam_single_pose: dict,
    line_thickness: int = 2,
) -> np.ndarray:
    """§2.4B — Draw coloured diagnostic lines on *canvas* at each seam boundary.

    Each horizontal line is coloured by alignment quality:
    - Green  (BGR 0,200,0)   : post_diff < SEAM_OVERLAY_AMBER_THRESH, not single-pose
    - Amber  (BGR 0,165,255) : AMBER_THRESH ≤ post_diff < RED_THRESH, not single-pose
    - Red    (BGR 0,0,220)   : post_diff ≥ RED_THRESH or seam in single-pose fallback

    A short label ``S{k}:{diff:.0f}`` (plus ``SP`` for single-pose seams) is drawn
    at the left edge so the diagnostic overlay is self-documenting.
    """
    if canvas.size == 0 or len(boundaries) == 0:
        return canvas
    out = canvas.copy()
    H, W = out.shape[:2]
    for k, by in enumerate(boundaries):
        y = int(by)
        if y < 0 or y >= H:
            continue
        diff = float(seam_post_diffs.get(k, 0.0))
        is_sp = k in seam_single_pose
        if is_sp or diff >= SEAM_OVERLAY_RED_THRESH:
            colour = (0, 0, 220)
        elif diff >= SEAM_OVERLAY_AMBER_THRESH:
            colour = (0, 165, 255)
        else:
            colour = (0, 200, 0)
        cv2.line(out, (0, y), (W - 1, y), colour, line_thickness)
        label = f"S{k}:{diff:.0f}"
        if is_sp:
            label += " SP"
        cv2.putText(
            out,
            label,
            (4, max(y - 3, 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            colour,
            1,
            cv2.LINE_AA,
        )
    return out


def _extract_seam_crops(
    canvas: np.ndarray,
    boundaries: np.ndarray,
    band_px: int = SEAM_CROP_BAND_PX,
) -> Dict[int, np.ndarray]:
    """§2.4C — Crop ±band_px rows around each seam boundary from *canvas*.

    Returns a dict mapping seam index k → cropped subarray.  The crop is
    clamped to canvas bounds so edge seams produce narrower crops rather than
    raising an error.  Returns an empty dict when *boundaries* is empty or
    *canvas* has zero area.
    """
    result: Dict[int, np.ndarray] = {}
    if canvas.size == 0 or len(boundaries) == 0:
        return result
    H = canvas.shape[0]
    for k, by in enumerate(boundaries):
        y = int(by)
        y0 = max(0, y - band_px)
        y1 = min(H, y + band_px)
        result[k] = canvas[y0:y1].copy()
    return result


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
    # relocated: from scipy.ndimage import median_filter as _mf
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


def _seam_path_drift(path: np.ndarray) -> float:
    """§1.112: Maximum consecutive column-to-column jump in a seam path (S154).

    Returns ``max(|path[i+1] - path[i]|)`` for all consecutive column pairs.
    A large drift indicates a sudden vertical discontinuity in the DP seam,
    which produces a visible kink artefact even after §1.25 median smoothing.

    Parameters
    ----------
    path:
        1-D numeric array; ``path[x]`` is the y-offset for column x.

    Returns
    -------
    float
        Maximum consecutive absolute step.  Returns 0.0 for paths with
        fewer than two entries.
    """
    if len(path) < 2:
        return 0.0
    return float(np.max(np.abs(np.diff(path.astype(np.float32)))))


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


def _zone_entropy(zone: np.ndarray) -> float:
    """§1.97: Shannon entropy of a BGR zone's grayscale histogram (S149)."""
    if zone.size == 0:
        return 0.0
    gray = zone.mean(axis=2).astype(np.uint8)
    hist = np.bincount(gray.ravel(), minlength=256).astype(np.float64)
    hist /= max(hist.sum(), 1.0)
    nonzero = hist[hist > 0]
    return float(-np.dot(nonzero, np.log2(nonzero)))


def _seam_zone_entropy_gap(fa_zone: np.ndarray, fb_zone: np.ndarray) -> float:
    """§1.97: Absolute entropy difference between the two zone crops (S149).

    Returns the abs(H(fa_zone) - H(fb_zone)) in bits.  A large gap means one
    zone is nearly flat (uniform colour, low entropy) while the other is highly
    textured; ARAP optical flow has no signal in the flat zone and produces
    spurious warp vectors that worsen the blend.
    """
    return abs(_zone_entropy(fa_zone) - _zone_entropy(fb_zone))


def _seam_zone_texture_energy(
    fa: np.ndarray,
    fb: np.ndarray,
    boundary: int,
    half_band: int = 30,
) -> float:
    """§1.34: Mean Laplacian variance in the ±half_band rows around a seam boundary.

    Low values indicate flat-colour zones where optical flow / ARAP is unreliable
    (aperture problem) — both frames lack gradient signal near the seam.

    Parameters
    ----------
    fa, fb:
        Full-height BGR uint8 frames (H, W, 3) or grayscale (H, W).
    boundary:
        Row index of the seam boundary in the full canvas.
    half_band:
        Half-width of the evaluation band in rows (default 30).

    Returns
    -------
    float
        Mean Laplacian variance across both frames (uint8 scale, ≥ 0).
        0.0 when the band is empty or frames have no rows.
    """
    if fa.size == 0 or fb.size == 0:
        return 0.0
    H = min(fa.shape[0], fb.shape[0])
    y0 = max(0, boundary - half_band)
    y1 = min(H, boundary + half_band)
    if y1 <= y0:
        return 0.0
    variances: list[float] = []
    for frame in (fa, fb):
        band = frame[y0:y1]
        gray = cv2.cvtColor(band, cv2.COLOR_BGR2GRAY) if band.ndim == 3 else band
        variances.append(float(cv2.Laplacian(gray, cv2.CV_32F).var()))
    return float(np.mean(variances)) if variances else 0.0


def _fg_gradient_cost(
    canvas_zone: np.ndarray,
    weight: float = 1.0,
) -> np.ndarray:
    """§1.35: Per-pixel Laplacian gradient cost for fg-interior seam penalty.

    Anime character outlines are dark, thin, high-gradient lines. A DP seam that
    cuts through an outline pixel creates a visible hairline break in the stroke.
    This returns a (H, W) float32 cost map in [0, weight] so that fg-interior
    pixels near character outlines are more expensive than flat fill regions,
    pushing the seam into low-gradient body fill when no background corridor exists.

    Parameters
    ----------
    canvas_zone : (H, W, 3) uint8 BGR slice from the blend zone canvas.
    weight : additive cost ceiling (default 1.0). Set to 0.0 to disable.

    Returns
    -------
    np.ndarray of shape (H, W), dtype float32, values in [0, weight].
    """
    if canvas_zone.size == 0 or weight <= 0.0:
        return np.zeros(canvas_zone.shape[:2], dtype=np.float32)
    gray = (
        cv2.cvtColor(canvas_zone, cv2.COLOR_BGR2GRAY)
        if canvas_zone.ndim == 3
        else canvas_zone
    )
    lap = np.abs(cv2.Laplacian(gray.astype(np.float32), cv2.CV_32F))
    lap_max = float(lap.max())
    if lap_max < 1e-6:
        return np.zeros(canvas_zone.shape[:2], dtype=np.float32)
    return np.minimum(lap / lap_max, 1.0).astype(np.float32) * weight


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
        fi_a = order[k]
        fi_b = order[k + 1]
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


def _seam_chroma_equalize(
    canvas: np.ndarray,
    boundaries: "List[float]",
    band_px: int = 20,
    min_shift: float = 3.0,
) -> np.ndarray:
    """§1.56: Post-composite chroma seam correction (S122).

    Complement to :func:`_seam_lum_equalize` (§1.21).  Converts strip reference
    bands above and below each seam boundary to CIE LAB colour space and measures
    the mean shift in the 'a' (green↔red) and 'b' (blue↔yellow) channels.  When
    either shift exceeds *min_shift* LAB units, a linear additive ramp is applied
    over *band_px* rows below the boundary to close the gap.  Luminance (L*) is
    not modified here — that is handled by §1.21.

    The correction targets colour-temperature and hue banding between adjacent
    strips that equal-BGR luminance shifts (§1.21) cannot fix.

    Returns a uint8 copy of *canvas*.
    """
    out = canvas.astype(np.float32)
    H = canvas.shape[0]
    guard = 3

    for by_f in boundaries:
        by = int(by_f)
        a0 = max(0, by - band_px - guard)
        a1 = max(0, by - guard)
        b0 = min(H, by + guard)
        b1 = min(H, by + band_px + guard)
        if a1 <= a0 or b1 <= b0:
            continue

        above_bgr = canvas[a0:a1]
        below_bgr = canvas[b0:b1]

        above_lab = cv2.cvtColor(above_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
        below_lab = cv2.cvtColor(below_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)

        # Mean a/b per band (L channel ignored — handled by §1.21)
        above_a = float(above_lab[:, :, 1].mean())
        above_b = float(above_lab[:, :, 2].mean())
        below_a = float(below_lab[:, :, 1].mean())
        below_b = float(below_lab[:, :, 2].mean())

        shift_a = below_a - above_a
        shift_b = below_b - above_b

        if abs(shift_a) < min_shift and abs(shift_b) < min_shift:
            continue

        ry0, ry1 = by, min(H, by + band_px)
        rlen = ry1 - ry0
        if rlen <= 0:
            continue

        # Linear ramp: full correction at boundary, zero at band end
        t = np.linspace(0.0, 1.0, rlen, dtype=np.float32)  # 0→1 moving away from seam

        # Convert ramp zone to LAB, apply correction, convert back
        zone_bgr = np.clip(out[ry0:ry1], 0.0, 255.0).astype(np.uint8)
        zone_lab = cv2.cvtColor(zone_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)

        # Correction at row r: subtract (1-t) * shift so seam gets full correction,
        # band end gets zero correction.
        corr_a = (-shift_a * (1.0 - t)).reshape(-1, 1)
        corr_b = (-shift_b * (1.0 - t)).reshape(-1, 1)

        zone_lab[:, :, 1] = np.clip(zone_lab[:, :, 1] + corr_a, 0.0, 255.0)
        zone_lab[:, :, 2] = np.clip(zone_lab[:, :, 2] + corr_b, 0.0, 255.0)

        zone_corrected = cv2.cvtColor(zone_lab.astype(np.uint8), cv2.COLOR_LAB2BGR)
        out[ry0:ry1] = zone_corrected.astype(np.float32)

    return np.clip(out, 0.0, 255.0).astype(np.uint8)


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
    return max(
        min_threshold, base_threshold * (feather_reference / max(feather_width, 1))
    )


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
    top = gray[max(0, boundary_y - band_px) : boundary_y]
    bot = gray[boundary_y : min(H, boundary_y + band_px)]
    if top.shape[0] < 10 or bot.shape[0] < 10:
        return 1.0
    h_top = cv2.calcHist([top], [0], None, [256], [0, 256])
    h_bot = cv2.calcHist([bot], [0], None, [256], [0, 256])
    cv2.normalize(h_top, h_top)
    cv2.normalize(h_bot, h_bot)
    dist = cv2.compareHist(h_top, h_bot, cv2.HISTCMP_BHATTACHARYYA)
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
    top = img[max(0, boundary_y - band_px) : boundary_y]
    bot = img[boundary_y : min(H, boundary_y + band_px)]
    if top.shape[0] < 10 or bot.shape[0] < 10:
        return 1.0
    min_score = 1.0
    for ch in range(3):
        h_top = cv2.calcHist([top], [ch], None, [256], [0, 256])
        h_bot = cv2.calcHist([bot], [ch], None, [256], [0, 256])
        cv2.normalize(h_top, h_top)
        cv2.normalize(h_bot, h_bot)
        dist = cv2.compareHist(h_top, h_bot, cv2.HISTCMP_BHATTACHARYYA)
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


def _seam_ncc_coherence(
    img: np.ndarray,
    n_strips: int,
    band_px: int = 60,
) -> "List[float]":
    """§1.66: Per-seam NCC structural coherence (S131).

    Measures structural continuity across each seam boundary by computing the
    normalised cross-correlation (NCC) between the *band_px*-row window
    immediately above and the window immediately below each of the
    ``n_strips − 1`` inter-strip seam boundaries.

    NCC score per seam (in [−1, 1], higher = more coherent):

    * ≥ 0.90 : excellent structural match (invisible seam)
    * 0.70–0.90 : good continuity
    * 0.40–0.70 : moderate mismatch (visible structure step)
    * < 0.40   : severe mismatch (hard structure cut or pose gap)

    Returns an empty list when *n_strips* ≤ 1.  Flat bands (σ < 1e-3)
    return 1.0 per seam (no texture = no detectable mismatch).

    Complementary to ``_seam_color_similarity`` (histogram similarity) — two
    strips can have matching colour distributions but completely different
    line-art pattern, which NCC detects while Bhattacharyya misses.
    """
    if n_strips <= 1:
        return []
    H = img.shape[0]
    gray = (
        cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
        if img.ndim == 3
        else img.astype(np.float32)
    )
    zone_h = H / n_strips
    scores: List[float] = []
    for k in range(1, n_strips):
        boundary_y = int(round(zone_h * k))
        top = gray[max(0, boundary_y - band_px) : boundary_y]
        bot = gray[boundary_y : min(H, boundary_y + band_px)]
        if top.size == 0 or bot.size == 0:
            scores.append(0.0)
            continue
        min_rows = min(top.shape[0], bot.shape[0])
        if min_rows < 4:
            scores.append(0.0)
            continue
        if top.shape[0] != min_rows:
            top = cv2.resize(
                top, (top.shape[1], min_rows), interpolation=cv2.INTER_AREA
            )
        if bot.shape[0] != min_rows:
            bot = cv2.resize(
                bot, (bot.shape[1], min_rows), interpolation=cv2.INTER_AREA
            )
        mu_a, mu_b = float(top.mean()), float(bot.mean())
        sig_a = float(top.std())
        sig_b = float(bot.std())
        if sig_a < 1e-3 or sig_b < 1e-3:
            scores.append(1.0)
            continue
        ncc = float(np.mean((top - mu_a) * (bot - mu_b)) / (sig_a * sig_b + 1e-8))
        scores.append(round(float(np.clip(ncc, -1.0, 1.0)), 4))
    return scores


def _check_seam_ncc_gate(
    img: np.ndarray,
    n_strips: int,
    thresh: Optional[float] = None,
    band_px: int = 60,
) -> Optional[int]:
    """§1.66: Return the worst-NCC seam index, or None when all seams pass (S131).

    Calls ``_seam_ncc_coherence`` and returns the index of the seam with the
    *lowest* NCC score when that score falls below *thresh*.  Returns ``None``
    when *n_strips* ≤ 1, *thresh* ≤ 0, or all seams pass.

    Parameters
    ----------
    thresh : gate threshold in [−1, 1].  Seams with NCC < thresh trigger the
             gate.  Defaults to the module-level ``_SEAM_NCC_GATE`` value.
    """
    if thresh is None:
        thresh = _SEAM_NCC_GATE
    if n_strips <= 1 or thresh <= 0.0:
        return None
    scores = _seam_ncc_coherence(img, n_strips, band_px=band_px)
    if not scores:
        return None
    worst_k: Optional[int] = None
    worst_score = thresh
    for k, score in enumerate(scores):
        if score < worst_score:
            worst_score = score
            worst_k = k
    return worst_k


# §1.72 module flag — set ASP_SEAM_ENTROPY_GATE=1.5 to enable.
_SEAM_ENTROPY_GATE: float = float(os.environ.get("ASP_SEAM_ENTROPY_GATE", "0.0"))


def _seam_entropy_asymmetry(
    img: np.ndarray,
    n_strips: int,
    band_px: int = 50,
) -> "List[float]":
    """§1.72: Per-seam Shannon entropy asymmetry between bands above and below each seam.

    Computes the greyscale Shannon entropy of the *band_px*-row window immediately
    above and below each inter-strip seam boundary, then returns the absolute
    difference ``|H_top − H_bot|`` for each of the ``n_strips − 1`` seams.

    High asymmetry indicates that one side of the seam is flat-colour (low entropy
    — solid-colour character clothing, blank wall) while the other has rich texture
    (high entropy — complex background, detailed clothing).  This creates a
    perceptible texture density discontinuity that NCC and Bhattacharyya both miss:
    NCC measures structural coherence (pattern alignment), Bhattacharyya measures
    distribution shape (colour matching), but neither measures the *amount* of
    texture on each side.

    Entropy in [0, log2(256)] ≈ [0, 8.0] bits; asymmetry of 0 = perfectly
    balanced texture on both sides; > 1.5 bits ≈ one side near-flat, the other
    complex.

    Returns an empty list when *n_strips* ≤ 1.  Flat or near-flat bands (< 4
    unique grey values) return 0.0 per seam (no measurable texture density).
    """
    if n_strips <= 1:
        return []
    H_img = img.shape[0]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    zone_h = H_img / n_strips
    scores: List[float] = []
    for k in range(1, n_strips):
        boundary_y = int(round(zone_h * k))
        top = gray[max(0, boundary_y - band_px) : boundary_y]
        bot = gray[boundary_y : min(H_img, boundary_y + band_px)]
        if top.size == 0 or bot.size == 0:
            scores.append(0.0)
            continue

        def _entropy(band: np.ndarray) -> float:
            counts = np.bincount(band.ravel(), minlength=256).astype(np.float64)
            if (counts > 0).sum() < 4:
                return 0.0
            probs = counts / counts.sum()
            probs = probs[probs > 0]
            return float(-np.sum(probs * np.log2(probs)))

        scores.append(round(abs(_entropy(top) - _entropy(bot)), 4))
    return scores


def _check_seam_entropy_gate(
    img: np.ndarray,
    n_strips: int,
    thresh: Optional[float] = None,
    band_px: int = 50,
) -> Optional[int]:
    """§1.72: Return the worst-asymmetry seam index, or None when all pass.

    Calls ``_seam_entropy_asymmetry`` and returns the index of the seam with
    the *highest* entropy asymmetry score when that score exceeds *thresh*.
    Returns ``None`` when *n_strips* ≤ 1, *thresh* ≤ 0, or all seams pass.
    """
    if thresh is None:
        thresh = _SEAM_ENTROPY_GATE
    if thresh <= 0.0 or n_strips <= 1:
        return None
    scores = _seam_entropy_asymmetry(img, n_strips, band_px=band_px)
    if not scores:
        return None
    worst_k: Optional[int] = None
    worst_score = thresh
    for k, score in enumerate(scores):
        if score > worst_score:
            worst_score = score
            worst_k = k
    return worst_k


# §1.76 module flag — set ASP_SEAM_MAX_COL_GATE=40.0 to enable.
# Unlike §1.24 (_measure_max_seam_step) which returns the *mean* band luma,
# §1.76 reports the worst *individual column* step, catching localised hot-spots
# (a single character-edge column crossing the seam) that the mean gate misses.
_SEAM_MAX_COL_GATE: float = float(os.environ.get("ASP_SEAM_MAX_COL_GATE", "0.0"))


def _seam_max_col_luma_step(
    img: np.ndarray,
    n_strips: int,
    band_px: int = 8,
    guard: int = 2,
) -> "List[float]":
    """§1.76: Per-seam maximum column-wise luma step across the seam band (S134).

    For each inter-strip boundary, computes per-column mean luma in *band_px* rows
    above and below (with *guard* rows excluded), then returns ``max_col |above −
    below|`` for that seam.  Unlike §1.24 (mean across band width), this reports
    the worst single-column step — catching localised hot-spots that the mean
    smooths away.

    Parameters
    ----------
    img : BGR uint8 composite.
    n_strips : Number of composited strips.
    band_px : Rows above/below boundary to average for per-column luma.
    guard : Rows immediately adjacent to boundary excluded from averaging.

    Returns
    -------
    List of ``n_strips − 1`` floats, each the worst-column luma step (0–255).
    """
    H, W = img.shape[:2]
    if n_strips <= 1 or 2 * (band_px + guard) > H or W == 0:
        return []
    luma = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    steps: "List[float]" = []
    for k in range(1, n_strips):
        by = H * k // n_strips
        a0 = max(0, by - band_px - guard)
        a1 = max(0, by - guard)
        b0 = min(H, by + guard)
        b1 = min(H, by + band_px + guard)
        if a1 <= a0 or b1 <= b0:
            steps.append(0.0)
            continue
        above_col = luma[a0:a1].mean(axis=0)
        below_col = luma[b0:b1].mean(axis=0)
        steps.append(float(np.abs(below_col - above_col).max()))
    return steps


def _check_seam_max_col_gate(
    img: np.ndarray,
    n_strips: int,
    thresh: "Optional[float]" = None,
    band_px: int = 8,
    guard: int = 2,
) -> "Optional[int]":
    """§1.76: Return worst-column seam index when any per-seam step ≥ thresh.

    Parameters
    ----------
    thresh : Gate threshold in luma units.  Falls back to ``_SEAM_MAX_COL_GATE``.

    Returns
    -------
    Seam index (0-based) of the worst offender, or ``None`` when all pass.
    """
    if thresh is None:
        thresh = _SEAM_MAX_COL_GATE
    if thresh <= 0.0 or n_strips <= 1:
        return None
    scores = _seam_max_col_luma_step(img, n_strips, band_px=band_px, guard=guard)
    if not scores:
        return None
    worst_k: "Optional[int]" = None
    worst_score = thresh
    for k, score in enumerate(scores):
        if score > worst_score:
            worst_score = score
            worst_k = k
    return worst_k


# §1.77 module flag — set ASP_SEAM_SAT_GATE=40.0 to enable.
# Saturation jump detects a colour-vibrancy discontinuity that luma-based gates
# (§1.24, §1.76) and entropy gates (§1.72) both miss: two strips can have
# identical mean brightness and equal texture complexity but completely different
# colour saturation — e.g., a muted pastel background abutting a vividly
# coloured character outfit.  In HSV space the saturation channel is in [0, 255];
# a jump of ≥ 40 at the seam boundary is clearly visible.
_SEAM_SAT_GATE: float = float(os.environ.get("ASP_SEAM_SAT_GATE", "0.0"))


def _seam_saturation_jump(
    img: np.ndarray,
    n_strips: int,
    band_px: int = 30,
) -> "List[float]":
    """§1.77: Per-seam mean HSV saturation jump across the seam boundary (S135).

    For each inter-strip boundary, computes the mean HSV saturation in the
    *band_px*-row window immediately above and below, then returns
    ``|sat_above − sat_below|`` (in [0, 255]).

    High saturation jump indicates a vibrancy discontinuity — e.g., a muted
    background strip adjacent to a vividly coloured character strip — that
    luma, entropy, and Bhattacharyya gates do not specifically target.

    Parameters
    ----------
    img : BGR uint8 composite image.
    n_strips : Number of composited strips.
    band_px : Rows above/below the boundary used for saturation estimation.

    Returns
    -------
    List of ``n_strips − 1`` floats in [0, 255].  Empty when n_strips ≤ 1.
    Single-channel (greyscale) inputs return 0.0 per seam.
    """
    if n_strips <= 1:
        return []
    H = img.shape[0]
    if img.ndim == 2 or img.shape[2] == 1:
        return [0.0] * (n_strips - 1)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1].astype(np.float32)
    zone_h = H / n_strips
    jumps: "List[float]" = []
    for k in range(1, n_strips):
        by = int(round(zone_h * k))
        top = sat[max(0, by - band_px) : by]
        bot = sat[by : min(H, by + band_px)]
        if top.size == 0 or bot.size == 0:
            jumps.append(0.0)
            continue
        jumps.append(round(abs(float(top.mean()) - float(bot.mean())), 4))
    return jumps


def _check_seam_saturation_gate(
    img: np.ndarray,
    n_strips: int,
    thresh: "Optional[float]" = None,
    band_px: int = 30,
) -> "Optional[int]":
    """§1.77: Return worst saturation-jump seam index when any jump ≥ thresh.

    Returns the seam index (0-based) whose ``|sat_above − sat_below|`` is the
    largest and exceeds *thresh*.  Returns ``None`` when *n_strips* ≤ 1,
    *thresh* ≤ 0, or all seams pass.
    """
    if thresh is None:
        thresh = _SEAM_SAT_GATE
    if thresh <= 0.0 or n_strips <= 1:
        return None
    scores = _seam_saturation_jump(img, n_strips, band_px=band_px)
    if not scores:
        return None
    worst_k: "Optional[int]" = None
    worst_score = thresh
    for k, score in enumerate(scores):
        if score > worst_score:
            worst_score = score
            worst_k = k
    return worst_k


# §1.78 module flag — set ASP_SEAM_HUE_GATE=30.0 to enable.
# Hue shift detects a colour-temperature discontinuity that saturation and luma
# gates miss: two strips can have equal brightness and equal saturation yet
# completely different hues — e.g., a warm orange/red background strip abutting
# a cool blue/teal strip.  HSV hue is circular in [0, 180] (OpenCV convention);
# the circular distance is used so that red (hue≈0) and magenta (hue≈170) are
# correctly treated as nearby (distance≈10), not opposite (distance≈170).
_SEAM_HUE_GATE: float = float(os.environ.get("ASP_SEAM_HUE_GATE", "0.0"))

# §1.79 module flag — set ASP_SEAM_SHARP_GATE=3.0 to enable.
# Sharpness mismatch detects a blur/sharpness discontinuity that colour-space
# gates (luma, saturation, hue, entropy) do not capture: two strips can have
# identical colour profiles yet one strip is noticeably blurrier than the other
# due to different source MPEG compression, upscaling, or frame-averaging rates.
# The metric is the log₂ ratio of Laplacian variance in the band above vs. below
# each seam boundary.  |log₂(sharp_top / sharp_bot)| > thresh flags a mismatch.
# A ratio of 3.0 means one side is 8× sharper than the other — clearly visible.
# Default 0.0 = off.  Recommend ASP_SEAM_SHARP_GATE=3.0.
_SEAM_SHARP_GATE: float = float(os.environ.get("ASP_SEAM_SHARP_GATE", "0.0"))

# §1.80 module flag — set ASP_SEAM_GRAD_DIR_GATE=45.0 to enable.
# Gradient direction coherence detects a structural orientation discontinuity
# that all colour-space gates (luma, saturation, hue, sharpness, entropy)
# ignore: two strips can have identical photometric profiles yet different
# dominant edge orientations — e.g., diagonal speed-lines above a horizontal
# cloud-layer below.  The gradient direction is measured using Sobel gx/gy;
# undirected orientation (mod π) circular mean is computed per band using the
# angle-doubling trick.  The score is the circular distance in degrees [0, 90].
# A score of 45° means one side has edges mainly at 45° to the other — clearly
# visible as a texture orientation jump.  Default 0.0 = off.
# Recommend ASP_SEAM_GRAD_DIR_GATE=45.0.
_SEAM_GRAD_DIR_GATE: float = float(os.environ.get("ASP_SEAM_GRAD_DIR_GATE", "0.0"))


def _seam_hue_shift(
    img: np.ndarray,
    n_strips: int,
    band_px: int = 30,
) -> "List[float]":
    """§1.78: Per-seam mean circular hue shift across the seam boundary (S135).

    For each inter-strip boundary, computes the mean HSV hue in the *band_px*-row
    window immediately above and below using the circular (angular) distance to
    handle the red-wraparound at hue=0/180.  Returns the circular distance in
    [0, 90] degrees (OpenCV hue scale: 0–180, so max circular distance = 90).

    High hue shift indicates a colour-temperature discontinuity — e.g., a warm
    orange/sunset background strip abutting a cool blue/sky strip — that luma,
    saturation, entropy, and Bhattacharyya gates do not capture.

    Near-black or near-white pixels have undefined hue and inflate the mean; they
    are excluded via a saturation threshold (sat > 15/255) so only chromatically
    meaningful pixels contribute.

    Parameters
    ----------
    img : BGR uint8 composite image.
    n_strips : Number of composited strips.
    band_px : Rows above/below the boundary used for hue estimation.

    Returns
    -------
    List of ``n_strips − 1`` floats in [0, 90].  Empty when n_strips ≤ 1.
    Greyscale inputs return 0.0 per seam (no hue information).
    """
    if n_strips <= 1:
        return []
    if img.ndim == 2 or (img.ndim == 3 and img.shape[2] == 1):
        return [0.0] * (n_strips - 1)
    H = img.shape[0]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    hue = hsv[:, :, 0].astype(np.float32)
    sat = hsv[:, :, 1].astype(np.float32)
    zone_h = H / n_strips
    shifts: "List[float]" = []
    for k in range(1, n_strips):
        by = int(round(zone_h * k))
        top_h = hue[max(0, by - band_px) : by]
        top_s = sat[max(0, by - band_px) : by]
        bot_h = hue[by : min(H, by + band_px)]
        bot_s = sat[by : min(H, by + band_px)]
        if top_h.size == 0 or bot_h.size == 0:
            shifts.append(0.0)
            continue
        top_mask = top_s > 15.0
        bot_mask = bot_s > 15.0
        if top_mask.sum() < 4 or bot_mask.sum() < 4:
            shifts.append(0.0)
            continue
        mean_top = float(top_h[top_mask].mean())
        mean_bot = float(bot_h[bot_mask].mean())
        # Circular distance on [0, 180] scale; max = 90.
        diff = abs(mean_top - mean_bot)
        if diff > 90.0:
            diff = 180.0 - diff
        shifts.append(round(diff, 4))
    return shifts


def _check_seam_hue_gate(
    img: np.ndarray,
    n_strips: int,
    thresh: "Optional[float]" = None,
    band_px: int = 30,
) -> "Optional[int]":
    """§1.78: Return worst hue-shift seam index when any shift ≥ thresh.

    Returns the seam index (0-based) whose circular hue shift is the largest and
    exceeds *thresh*.  Returns ``None`` when *n_strips* ≤ 1, *thresh* ≤ 0, or
    all seams pass.
    """
    if thresh is None:
        thresh = _SEAM_HUE_GATE
    if thresh <= 0.0 or n_strips <= 1:
        return None
    scores = _seam_hue_shift(img, n_strips, band_px=band_px)
    if not scores:
        return None
    worst_k: "Optional[int]" = None
    worst_score = thresh
    for k, score in enumerate(scores):
        if score > worst_score:
            worst_score = score
            worst_k = k
    return worst_k


def _seam_sharpness_mismatch(
    img: np.ndarray,
    n_strips: int,
    band_px: int = 30,
) -> "List[float]":
    """§1.79: Per-seam log₂ sharpness ratio across the seam boundary (S136).

    For each inter-strip boundary, computes the Laplacian variance in the
    *band_px*-row window immediately above and below.  The Laplacian variance
    (``cv2.Laplacian`` → variance of float response) is a well-established
    blur measure: sharp regions have high variance; blurry regions have low.

    The mismatch score is ``|log₂(sharp_top / sharp_bot)|``, where both values
    are clamped to ≥ 1.0 to prevent log singularities on near-flat regions.
    A score of 0 means equal sharpness; 1.0 means one side is 2× sharper;
    3.0 means one side is 8× sharper — clearly perceptible as a texture jump.

    Input is converted to greyscale before Laplacian to avoid channel artefacts.
    Works on both colour (H, W, 3) and greyscale (H, W) arrays.

    Parameters
    ----------
    img : BGR uint8 composite image.
    n_strips : Number of composited strips.
    band_px : Rows above/below each boundary used for sharpness estimation.

    Returns
    -------
    List of ``n_strips − 1`` non-negative floats.  Empty when n_strips ≤ 1.
    """
    if n_strips <= 1:
        return []
    H = img.shape[0]
    grey = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32) if img.ndim == 3 else img.astype(np.float32)
    lap = cv2.Laplacian(grey, cv2.CV_32F)
    zone_h = H / n_strips
    scores: "List[float]" = []
    for k in range(1, n_strips):
        by = int(round(zone_h * k))
        top_lap = lap[max(0, by - band_px) : by]
        bot_lap = lap[by : min(H, by + band_px)]
        if top_lap.size == 0 or bot_lap.size == 0:
            scores.append(0.0)
            continue
        sharp_top = max(1.0, float(np.var(top_lap)))
        sharp_bot = max(1.0, float(np.var(bot_lap)))
        ratio = np.log2(sharp_top / sharp_bot)
        scores.append(round(abs(ratio), 4))
    return scores


def _check_seam_sharpness_gate(
    img: np.ndarray,
    n_strips: int,
    thresh: "Optional[float]" = None,
    band_px: int = 30,
) -> "Optional[int]":
    """§1.79: Return worst sharpness-mismatch seam index when any score ≥ thresh.

    Returns the seam index (0-based) with the largest |log₂(sharp_top/sharp_bot)|
    that exceeds *thresh*.  Returns ``None`` when *n_strips* ≤ 1, *thresh* ≤ 0,
    or all seams pass.
    """
    if thresh is None:
        thresh = _SEAM_SHARP_GATE
    if thresh <= 0.0 or n_strips <= 1:
        return None
    scores = _seam_sharpness_mismatch(img, n_strips, band_px=band_px)
    if not scores:
        return None
    worst_k: "Optional[int]" = None
    worst_score = thresh
    for k, score in enumerate(scores):
        if score > worst_score:
            worst_score = score
            worst_k = k
    return worst_k


def _seam_grad_direction(
    img: np.ndarray,
    n_strips: int,
    band_px: int = 30,
    mag_thresh: float = 10.0,
) -> "List[float]":
    """§1.80: Per-seam gradient direction coherence score (S137).

    For each inter-strip boundary, computes the mean *undirected* gradient
    orientation in the *band_px*-row window immediately above and below, then
    returns the circular distance between the two means in degrees [0, 90].

    Gradient orientation is measured using 3×3 Sobel operators.  The undirected
    orientation ``θ = arctan2(gy, gx) mod π`` lies in [0, π).  Per-band
    circular mean is derived via the angle-doubling trick:

        mean_angle = 0.5 × arctan2(mean(sin(2θ)), mean(cos(2θ)))

    Only pixels whose Sobel magnitude exceeds *mag_thresh* contribute, so
    flat regions (uniform colour) do not bias the mean.  When fewer than 4
    strong-gradient pixels exist in either band the seam score is 0.0 (no
    information → no gate).

    A score of 0° means the dominant edge direction is the same on both sides
    of the seam (compatible structure).  A score of 45° means one side's edges
    run perpendicular to the other — clearly perceptible as a texture jump.
    A score of 90° is the maximum (horizontal lines above, vertical lines below).

    Parameters
    ----------
    img : BGR uint8 (H, W, 3) or greyscale (H, W) composite image.
    n_strips : Number of composited strips.
    band_px : Rows above/below each boundary used for orientation estimation.
    mag_thresh : Sobel magnitude floor; pixels below are excluded (flat regions).

    Returns
    -------
    List of ``n_strips − 1`` floats in [0, 90].  Empty when n_strips ≤ 1.
    """
    if n_strips <= 1:
        return []
    H = img.shape[0]
    grey = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32) if img.ndim == 3 else img.astype(np.float32)

    gx = cv2.Sobel(grey, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(grey, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.sqrt(gx * gx + gy * gy)
    # Undirected orientation in [0, π): arctan2 ∈ (-π, π] → mod π.
    orientation = np.arctan2(gy, gx) % np.pi

    zone_h = H / n_strips
    scores: "List[float]" = []

    for k in range(1, n_strips):
        by = int(round(zone_h * k))
        t_sl = slice(max(0, by - band_px), by)
        b_sl = slice(by, min(H, by + band_px))

        top_mag = mag[t_sl]
        bot_mag = mag[b_sl]
        if top_mag.size == 0 or bot_mag.size == 0:
            scores.append(0.0)
            continue

        top_mask = top_mag > mag_thresh
        bot_mask = bot_mag > mag_thresh
        if top_mask.sum() < 4 or bot_mask.sum() < 4:
            scores.append(0.0)
            continue

        top_a = orientation[t_sl][top_mask]
        bot_a = orientation[b_sl][bot_mask]

        # Circular mean of undirected orientations via angle-doubling trick.
        # Double to [0, 2π), compute unit-vector mean, halve back.
        phi_top = 2.0 * top_a
        phi_bot = 2.0 * bot_a
        mean_top = 0.5 * np.arctan2(
            float(np.mean(np.sin(phi_top))), float(np.mean(np.cos(phi_top)))
        )
        mean_bot = 0.5 * np.arctan2(
            float(np.mean(np.sin(phi_bot))), float(np.mean(np.cos(phi_bot)))
        )

        # Map both means to [0, π) then compute circular distance in [0, π/2].
        mean_top_pos = mean_top % np.pi
        mean_bot_pos = mean_bot % np.pi
        diff = abs(mean_top_pos - mean_bot_pos)
        if diff > np.pi / 2.0:
            diff = np.pi - diff

        scores.append(round(float(np.degrees(diff)), 4))

    return scores


def _check_seam_grad_direction_gate(
    img: np.ndarray,
    n_strips: int,
    thresh: "Optional[float]" = None,
    band_px: int = 30,
) -> "Optional[int]":
    """§1.80: Return worst-seam index when any gradient-direction score ≥ thresh.

    Returns the 0-based seam index whose circular gradient-direction distance
    is the largest and exceeds *thresh* degrees.  Returns ``None`` when
    *n_strips* ≤ 1, *thresh* ≤ 0, or all seams pass.
    """
    if thresh is None:
        thresh = _SEAM_GRAD_DIR_GATE
    if thresh <= 0.0 or n_strips <= 1:
        return None
    scores = _seam_grad_direction(img, n_strips, band_px=band_px)
    if not scores:
        return None
    worst_k: "Optional[int]" = None
    worst_score = thresh
    for k, score in enumerate(scores):
        if score > worst_score:
            worst_score = score
            worst_k = k
    return worst_k


# §1.81 module flag — set ASP_SEAM_SSIM_GATE=0.85 to enable.
# SSIM directly measures the *perceptual similarity* between the bands above
# and below a seam boundary by jointly evaluating luminance, contrast, and
# structure.  Luma, saturation, hue, sharpness and gradient-direction gates
# (§1.76–§1.80) each measure one photometric dimension independently; SSIM
# fuses all three (luma, contrast, structure) into a single [0,1] score.
# A score of 1.0 = identical bands; 0.0 = totally unrelated content.
# Default 0.0 = off.  Recommend ASP_SEAM_SSIM_GATE=0.85 (fire below 0.85).
# The gate fires when ANY seam's band-SSIM is *below* the threshold (lower
# similarity = worse seam), unlike §1.76–§1.80 which fire when a score
# *exceeds* a threshold.  The returned value is still "worst seam index".
_SEAM_SSIM_GATE: float = float(os.environ.get("ASP_SEAM_SSIM_GATE", "0.0"))

# §1.82 module flag — set ASP_SEAM_FREQ_GATE=0.6 to enable.
# Spatial frequency profile mismatch detects a spectral content discontinuity
# invisible to all previous gates: two strips can have identical mean luma,
# saturation, sharpness, and gradient orientation yet completely different
# dominant spatial frequencies — e.g., a fine-grained noise texture above a
# smooth gradient below.  The metric is 1 − Pearson-r between the two bands'
# 1D column-averaged FFT magnitude spectra (DC-excluded), in [0, 1].
# A score of 0 = identical spectra; 1 = orthogonal spectra.
# Default 0.0 = off.  Recommend ASP_SEAM_FREQ_GATE=0.6.
_SEAM_FREQ_GATE: float = float(os.environ.get("ASP_SEAM_FREQ_GATE", "0.0"))


def _seam_band_ssim(
    img: np.ndarray,
    n_strips: int,
    band_px: int = 30,
) -> "List[float]":
    """§1.81: Per-seam SSIM between bands above and below each seam boundary.

    For each inter-strip boundary, computes the Structural Similarity Index
    (SSIM) between the *band_px*-row window immediately above and below.  The
    two band arrays are resized to the same height (``min(top_h, bot_h)``) when
    one is taller than the other (boundary near image edge).

    SSIM jointly captures luminance, contrast, and structure — it is sensitive
    to all photometric and structural differences simultaneously, making it a
    catch-all complement to the targeted §1.76–§1.80 single-dimension gates.

    The score is in [0, 1]:
    * 1.0 = bands are perceptually identical (seam is invisible).
    * < 0.85 = clear perceptual discontinuity at the seam boundary.
    * 0.0 = bands are completely unrelated.

    The gate fires when a score is *below* the threshold (unlike §1.76–§1.80
    which fire *above* their thresholds) — lower SSIM → worse seam.

    Parameters
    ----------
    img : BGR uint8 (H, W, 3) or greyscale (H, W) composite image.
    n_strips : Number of composited strips.
    band_px : Rows above/below each boundary for SSIM estimation.

    Returns
    -------
    List of ``n_strips − 1`` floats in [0, 1].  Empty when n_strips ≤ 1.
    """
    # relocated: from skimage.metrics import structural_similarity as ssim_fn

    if n_strips <= 1:
        return []
    H = img.shape[0]
    multichannel = img.ndim == 3 and img.shape[2] == 3
    grey = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if multichannel else img if img.ndim == 2 else img[:, :, 0]
    grey = grey.astype(np.float32) / 255.0

    zone_h = H / n_strips
    scores: "List[float]" = []
    for k in range(1, n_strips):
        by = int(round(zone_h * k))
        top = grey[max(0, by - band_px) : by]
        bot = grey[by : min(H, by + band_px)]
        if top.size == 0 or bot.size == 0:
            scores.append(1.0)
            continue
        # Equalise heights so ssim arrays match.
        h = min(top.shape[0], bot.shape[0])
        if h < 7:
            scores.append(1.0)
            continue
        top = top[:h]
        bot = bot[:h]
        try:
            val = float(ssim_fn(top, bot, data_range=1.0))
        except Exception:
            val = 1.0
        scores.append(round(max(0.0, min(1.0, val)), 4))
    return scores


def _check_seam_ssim_gate(
    img: np.ndarray,
    n_strips: int,
    thresh: "Optional[float]" = None,
    band_px: int = 30,
) -> "Optional[int]":
    """§1.81: Return worst-seam index when any band-SSIM is *below* thresh.

    Returns the 0-based seam index whose SSIM score is the lowest and falls
    below *thresh*.  Returns ``None`` when *n_strips* ≤ 1, *thresh* ≤ 0, or
    all seams pass.
    """
    if thresh is None:
        thresh = _SEAM_SSIM_GATE
    if thresh <= 0.0 or n_strips <= 1:
        return None
    scores = _seam_band_ssim(img, n_strips, band_px=band_px)
    if not scores:
        return None
    worst_k: "Optional[int]" = None
    worst_score = thresh
    for k, score in enumerate(scores):
        if score < worst_score:
            worst_score = score
            worst_k = k
    return worst_k


def _seam_freq_profile(
    img: np.ndarray,
    n_strips: int,
    band_px: int = 30,
) -> "List[float]":
    """§1.82: Per-seam spatial-frequency profile mismatch score (1 − Pearson-r).

    For each inter-strip boundary, computes the column-averaged 1D FFT magnitude
    spectrum of the greyscale band above and below (DC bin excluded).  The
    Pearson correlation coefficient *r* between the two spectral vectors
    captures how similar the dominant spatial frequency content is across the
    boundary.  The mismatch score is ``1 − max(0, r)`` in [0, 1]:

    * 0.0 = identical frequency profiles (spectrally compatible strips).
    * 1.0 = orthogonal/anti-correlated spectra (spectral discontinuity).

    This catches cases where two strips look similar in colour and luma yet
    differ in frequency content — e.g., a fine-grained noise texture above a
    smooth low-frequency gradient below — invisible to all §1.76–§1.81 gates.

    Only the positive-frequency half of the one-sided spectrum is used.
    When a band is too narrow (< 4 rows) the score defaults to 0.0 (no info).

    Parameters
    ----------
    img : BGR uint8 (H, W, 3) or greyscale (H, W) composite image.
    n_strips : Number of composited strips.
    band_px : Rows above/below each boundary for spectrum estimation.

    Returns
    -------
    List of ``n_strips − 1`` floats in [0, 1].  Empty when n_strips ≤ 1.
    """
    if n_strips <= 1:
        return []
    H = img.shape[0]
    grey = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32) if img.ndim == 3 else img.astype(np.float32)

    zone_h = H / n_strips
    scores: "List[float]" = []
    for k in range(1, n_strips):
        by = int(round(zone_h * k))
        top = grey[max(0, by - band_px) : by]
        bot = grey[by : min(H, by + band_px)]
        if top.shape[0] < 4 or bot.shape[0] < 4:
            scores.append(0.0)
            continue

        # 1D FFT per column, average magnitude across columns, exclude DC.
        def _col_mean_spectrum(band: np.ndarray) -> np.ndarray:
            spec = np.abs(np.fft.rfft(band, axis=0))  # (freqs, W)
            return spec[1:].mean(axis=1)  # exclude DC, mean over columns

        top_spec = _col_mean_spectrum(top)
        bot_spec = _col_mean_spectrum(bot)
        # Align lengths (edge bands may have different heights).
        n = min(len(top_spec), len(bot_spec))
        if n < 2:
            scores.append(0.0)
            continue
        top_s = top_spec[:n]
        bot_s = bot_spec[:n]
        # Pearson-r between the two spectra.
        top_z = top_s - top_s.mean()
        bot_z = bot_s - bot_s.mean()
        denom = float(np.linalg.norm(top_z) * np.linalg.norm(bot_z))
        if denom < 1e-9:
            scores.append(0.0)
            continue
        r = float(np.dot(top_z, bot_z) / denom)
        scores.append(round(1.0 - max(0.0, r), 4))
    return scores


def _check_seam_freq_gate(
    img: np.ndarray,
    n_strips: int,
    thresh: "Optional[float]" = None,
    band_px: int = 30,
) -> "Optional[int]":
    """§1.82: Return worst-seam index when any frequency-mismatch score ≥ thresh.

    Returns the 0-based seam index whose ``1 − Pearson-r`` spectrum mismatch
    is the largest and exceeds *thresh*.  Returns ``None`` when *n_strips* ≤ 1,
    *thresh* ≤ 0, or all seams pass.
    """
    if thresh is None:
        thresh = _SEAM_FREQ_GATE
    if thresh <= 0.0 or n_strips <= 1:
        return None
    scores = _seam_freq_profile(img, n_strips, band_px=band_px)
    if not scores:
        return None
    worst_k: "Optional[int]" = None
    worst_score = thresh
    for k, score in enumerate(scores):
        if score > worst_score:
            worst_score = score
            worst_k = k
    return worst_k


# §1.83 module flag — set ASP_SEAM_NOISE_GATE=1.0 to enable.
# Noise-level asymmetry detects a codec/exposure discontinuity that all previous
# gates miss: two strips can have identical mean luma, saturation, sharpness, and
# spectral content yet differ in per-pixel noise amplitude (e.g., one strip is a
# heavily JPEG-quantised block while the adjacent strip was captured at a higher
# bitrate).  The metric is the normalised absolute difference of Laplacian-std
# noise estimates (Immerkær 1996): score = |σ_top − σ_bot| / mean(σ_top, σ_bot).
# score in [0, 2]; 0 = identical noise, >1 = substantial mismatch.
# Default 0.0 = off.  Recommend ASP_SEAM_NOISE_GATE=1.0.
_SEAM_NOISE_GATE: float = float(os.environ.get("ASP_SEAM_NOISE_GATE", "0.0"))


def _seam_noise_mismatch(
    img: np.ndarray,
    n_strips: int,
    band_px: int = 30,
) -> "List[float]":
    """§1.83: Per-seam noise-level asymmetry between bands above and below each seam.

    Estimates per-strip noise sigma using the Laplacian-std estimator
    ``σ ≈ std(Laplacian(band)) / 6`` (Immerkær 1996 — standard noise-estimation
    heuristic for natural images).  The score is the normalised absolute
    difference:

        score_k = |σ_top − σ_bot| / max(1e-4, (σ_top + σ_bot) / 2)

    in [0, 2+]; 0 = identical noise levels, >1 = one strip is substantially
    noisier.  Detects codec or exposure-mismatch discontinuities that are
    invisible to luma/chroma/spectral metrics.

    Parameters
    ----------
    img : BGR uint8 (H, W, 3) or greyscale uint8 (H, W) composite image.
    n_strips : Number of composited strips.
    band_px : Rows above/below each boundary for noise estimation.

    Returns
    -------
    List of ``n_strips − 1`` floats ≥ 0.  Empty when n_strips ≤ 1.
    """
    if n_strips <= 1:
        return []
    H = img.shape[0]
    if img.ndim == 3:
        grey = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        grey = img if img.dtype == np.uint8 else img.clip(0, 255).astype(np.uint8)

    zone_h = H / n_strips
    scores: "List[float]" = []
    for k in range(1, n_strips):
        by = int(round(zone_h * k))
        top = grey[max(0, by - band_px) : by]
        bot = grey[by : min(H, by + band_px)]
        if top.shape[0] < 2 or bot.shape[0] < 2:
            scores.append(0.0)
            continue
        top_sigma = float(cv2.Laplacian(top, cv2.CV_32F).std()) / 6.0
        bot_sigma = float(cv2.Laplacian(bot, cv2.CV_32F).std()) / 6.0
        mean_sigma = (top_sigma + bot_sigma) / 2.0
        if mean_sigma < 1e-4:
            scores.append(0.0)
            continue
        scores.append(round(abs(top_sigma - bot_sigma) / mean_sigma, 4))
    return scores


def _check_seam_noise_gate(
    img: np.ndarray,
    n_strips: int,
    thresh: "Optional[float]" = None,
    band_px: int = 30,
) -> "Optional[int]":
    """§1.83: Return worst-seam index when any noise-asymmetry score ≥ thresh.

    Returns the 0-based seam index whose noise-level asymmetry is largest and
    exceeds *thresh*.  Returns ``None`` when *n_strips* ≤ 1, *thresh* ≤ 0, or
    all seams pass.
    """
    if thresh is None:
        thresh = _SEAM_NOISE_GATE
    if thresh <= 0.0 or n_strips <= 1:
        return None
    scores = _seam_noise_mismatch(img, n_strips, band_px=band_px)
    if not scores:
        return None
    worst_k: "Optional[int]" = None
    worst_score = thresh
    for k, score in enumerate(scores):
        if score > worst_score:
            worst_score = score
            worst_k = k
    return worst_k


# §1.84 module flag — set ASP_SEAM_CONTRAST_GATE=4.0 to enable.
# RMS contrast ratio detects broad-range contrast discontinuities invisible to
# §1.79 (sharpness: fine-detail intensity) and §1.82 (spectral profile).
# Two strips can have the same mean luma, saturation, Laplacian variance, and
# frequency content yet completely different contrast range — e.g., a smooth
# low-dynamic-range background zone adjacent to a high-contrast ink-line zone.
# The metric is the coefficient-of-variation ratio:
#   c = std(band) / max(1, mean(band))  →  score = max(c_top, c_bot) / min(c_top, c_bot)
# score in [1, ∞); 1 = identical contrast, >4 = substantial mismatch.
# Default 0.0 = off.  Recommend ASP_SEAM_CONTRAST_GATE=4.0.
_SEAM_CONTRAST_GATE: float = float(os.environ.get("ASP_SEAM_CONTRAST_GATE", "0.0"))


def _seam_rms_contrast_ratio(
    img: np.ndarray,
    n_strips: int,
    band_px: int = 30,
) -> "List[float]":
    """§1.84: Per-seam RMS contrast ratio between bands above and below each seam.

    RMS contrast is the coefficient of variation ``c = std / max(1, mean)``
    of the greyscale band.  The score is the ratio of the larger to the smaller
    per-strip contrast:

        score_k = max(c_top, c_bot) / max(1e-4, min(c_top, c_bot))

    in [1, ∞); 1.0 = identical contrast levels.  Distinct from §1.79 (sharpness
    ratio of Laplacian variance): §1.79 captures fine-detail edge intensity;
    §1.84 captures the broad dynamic range of the strip.

    Parameters
    ----------
    img : BGR uint8 (H, W, 3) or greyscale (H, W) composite image.
    n_strips : Number of composited strips.
    band_px : Rows above/below each boundary for contrast estimation.

    Returns
    -------
    List of ``n_strips − 1`` floats ≥ 1.0.  Empty when n_strips ≤ 1.
    """
    if n_strips <= 1:
        return []
    H = img.shape[0]
    grey = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32) if img.ndim == 3 else img.astype(np.float32)

    zone_h = H / n_strips
    scores: "List[float]" = []
    for k in range(1, n_strips):
        by = int(round(zone_h * k))
        top = grey[max(0, by - band_px) : by]
        bot = grey[by : min(H, by + band_px)]
        if top.size == 0 or bot.size == 0:
            scores.append(1.0)
            continue
        c_top = float(top.std()) / max(1.0, float(top.mean()))
        c_bot = float(bot.std()) / max(1.0, float(bot.mean()))
        c_max = max(c_top, c_bot)
        c_min = min(c_top, c_bot)
        scores.append(round(c_max / max(1e-4, c_min), 4))
    return scores


def _check_seam_rms_contrast_gate(
    img: np.ndarray,
    n_strips: int,
    thresh: "Optional[float]" = None,
    band_px: int = 30,
) -> "Optional[int]":
    """§1.84: Return worst-seam index when any RMS contrast ratio ≥ thresh.

    Returns the 0-based seam index whose RMS contrast ratio is largest and
    exceeds *thresh*.  Returns ``None`` when *n_strips* ≤ 1, *thresh* ≤ 0, or
    all seams pass.
    """
    if thresh is None:
        thresh = _SEAM_CONTRAST_GATE
    if thresh <= 0.0 or n_strips <= 1:
        return None
    scores = _seam_rms_contrast_ratio(img, n_strips, band_px=band_px)
    if not scores:
        return None
    worst_k: "Optional[int]" = None
    worst_score = thresh
    for k, score in enumerate(scores):
        if score > worst_score:
            worst_score = score
            worst_k = k
    return worst_k


# §1.85 module flag — set ASP_SEAM_ENSEMBLE_VOTES=3 to enable (default 0=off).
# The multi-gate ensemble combiner fires when a seam accumulates votes from
# ≥ min_votes active quality gates.  Individual gates have fixed thresholds
# calibrated to fire only on clear failures; the ensemble catches corner cases
# where a seam nearly fails 3-4 gates without exceeding any single gate's
# threshold.  It also catches seam sequences that are systematically degraded
# across all dimensions without being catastrophically bad in any one.
# Each vote uses the same threshold as the individual gate (0.0 = gate excluded
# from voting).  When min_votes=0 the combiner is disabled.
_SEAM_ENSEMBLE_VOTES: int = int(os.environ.get("ASP_SEAM_ENSEMBLE_VOTES", "0"))


def _seam_gate_vote_counts(
    img: np.ndarray,
    n_strips: int,
    *,
    thresh_color: float = 0.0,
    thresh_ncc: float = 0.0,
    thresh_entropy: float = 0.0,
    thresh_col_step: float = 0.0,
    thresh_sat: float = 0.0,
    thresh_hue: float = 0.0,
    thresh_sharp: float = 0.0,
    thresh_grad_dir: float = 0.0,
    thresh_ssim: float = 0.0,
    thresh_freq: float = 0.0,
    thresh_noise: float = 0.0,
    thresh_contrast: float = 0.0,
) -> "List[int]":
    """§1.85: Per-seam vote count from all active quality gates.

    Accumulates one vote per seam for every gate that flags it.  Only gates
    with a positive threshold contribute.  The comparison direction matches
    each gate's definition:

    * *Fires below* (lower = worse): color, NCC, SSIM.
    * *Fires above* (higher = worse): entropy, max-col-step, saturation, hue,
      sharpness, grad-direction, frequency, noise, contrast.

    Parameters
    ----------
    img : BGR uint8 (H, W, 3) composite image.
    n_strips : Number of composited strips.
    thresh_* : Per-gate thresholds.  Pass 0.0 to exclude a gate.

    Returns
    -------
    List of ``n_strips − 1`` non-negative ints.  Empty when n_strips ≤ 1.
    """
    if n_strips <= 1:
        return []
    n_seams = n_strips - 1
    votes = [0] * n_seams

    # ── gates that fire BELOW threshold (lower = worse) ─────────────────────
    if thresh_color > 0.0:
        for k in range(n_seams):
            if _seam_color_similarity(img, k, n_strips, band_px=50) < thresh_color:
                votes[k] += 1

    if thresh_ncc > 0.0:
        for k, s in enumerate(_seam_ncc_coherence(img, n_strips, band_px=60)):
            if s < thresh_ncc:
                votes[k] += 1

    if thresh_ssim > 0.0:
        for k, s in enumerate(_seam_band_ssim(img, n_strips, band_px=30)):
            if s < thresh_ssim:
                votes[k] += 1

    # ── gates that fire ABOVE threshold (higher = worse) ────────────────────
    _above: "List[tuple]" = [
        (thresh_entropy, lambda: _seam_entropy_asymmetry(img, n_strips, band_px=50)),
        (thresh_col_step, lambda: _seam_max_col_luma_step(img, n_strips)),
        (thresh_sat, lambda: _seam_saturation_jump(img, n_strips, band_px=30)),
        (thresh_hue, lambda: _seam_hue_shift(img, n_strips, band_px=30)),
        (thresh_sharp, lambda: _seam_sharpness_mismatch(img, n_strips, band_px=30)),
        (thresh_grad_dir, lambda: _seam_grad_direction(img, n_strips, band_px=30)),
        (thresh_freq, lambda: _seam_freq_profile(img, n_strips, band_px=30)),
        (thresh_noise, lambda: _seam_noise_mismatch(img, n_strips, band_px=30)),
        (thresh_contrast, lambda: _seam_rms_contrast_ratio(img, n_strips, band_px=30)),
    ]
    for thresh, score_fn in _above:
        if thresh <= 0.0:
            continue
        for k, s in enumerate(score_fn()):
            if s > thresh:
                votes[k] += 1

    return votes


def _check_seam_ensemble_gate(
    img: np.ndarray,
    n_strips: int,
    min_votes: "Optional[int]" = None,
    *,
    thresh_color: float = 0.0,
    thresh_ncc: float = 0.0,
    thresh_entropy: float = 0.0,
    thresh_col_step: float = 0.0,
    thresh_sat: float = 0.0,
    thresh_hue: float = 0.0,
    thresh_sharp: float = 0.0,
    thresh_grad_dir: float = 0.0,
    thresh_ssim: float = 0.0,
    thresh_freq: float = 0.0,
    thresh_noise: float = 0.0,
    thresh_contrast: float = 0.0,
) -> "Optional[int]":
    """§1.85: Return worst-seam index when it accumulates ≥ min_votes gate failures.

    Aggregates per-seam vote counts from all active gates (see
    :func:`_seam_gate_vote_counts`) and returns the 0-based index of the seam
    with the highest vote count when it meets or exceeds *min_votes*.
    Returns ``None`` when *n_strips* ≤ 1, *min_votes* ≤ 0, or all seams pass.
    """
    if min_votes is None:
        min_votes = _SEAM_ENSEMBLE_VOTES
    if min_votes <= 0 or n_strips <= 1:
        return None
    votes = _seam_gate_vote_counts(
        img,
        n_strips,
        thresh_color=thresh_color,
        thresh_ncc=thresh_ncc,
        thresh_entropy=thresh_entropy,
        thresh_col_step=thresh_col_step,
        thresh_sat=thresh_sat,
        thresh_hue=thresh_hue,
        thresh_sharp=thresh_sharp,
        thresh_grad_dir=thresh_grad_dir,
        thresh_ssim=thresh_ssim,
        thresh_freq=thresh_freq,
        thresh_noise=thresh_noise,
        thresh_contrast=thresh_contrast,
    )
    if not votes:
        return None
    worst_k = max(range(len(votes)), key=lambda k: votes[k])
    return worst_k if votes[worst_k] >= min_votes else None


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
    # Phase 5d: C++ fast path — GIL-released inner pixel loops, ~10–30× speedup
    if BATCH_AVAILABLE and hasattr(batch, "compositing") and hasattr(
        batch.compositing, "find_optimal_boundaries"
    ):
        try:
            _bg = None
            if bg_masks is not None:
                _bg = [
                    np.asarray(m, dtype=np.uint8) if m is not None else None
                    for m in bg_masks
                ]
            _bounds, _diffs = batch.compositing.find_optimal_boundaries(
                [np.ascontiguousarray(f) for f in warped_list],
                np.asarray(order, dtype=np.int64),
                np.asarray(initial_boundaries, dtype=np.float64),
                H, W,
                SEARCH_RANGE, SEARCH_SLAB,
                _bg, affines,
            )
            return np.asarray(_bounds), np.asarray(_diffs)
        except Exception:
            pass

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
    waypoints: Optional[List[Tuple[int, int]]] = None,
) -> np.ndarray:
    if BATCH_AVAILABLE:
        w_list = []
        if waypoints:
            w_list = [-1] * img1.shape[1]
            for wx, wy in waypoints:
                if 0 <= wx < len(w_list):
                    w_list[wx] = wy
        c_cost = (sem_cost * sem_weight) if sem_cost is not None else None
        return batch.seam.seam_cut(img1, img2, c_cost, w_list, _SEAM_TRANSITION_PEN, edge_weight)
    """
    DP seam cut that strongly avoids outlines in *either* frame.

    Energy = diff(img1,img2) + grad(diff) + edge_weight*(edges_in_img1 + edges_in_img2)
             + sem_weight * sem_cost   (P2.4 — character boundary avoidance)

    Returns path[x] = y-offset in [0, h-1] for the minimum-energy horizontal
    cut running left→right across the (h × W × 3) slices.

    §2.11A: *waypoints* is an optional list of ``(x, y)`` pairs in zone-local
    coordinates (x = column 0..W-1, y = row 0..h-1).  Each waypoint forces the
    seam to pass through that exact pixel by setting all other rows in column x
    to ``+inf`` before the DP forward pass.  The seam then fans out from the
    forced pixel in subsequent columns, so 3-connectivity is preserved.
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

    # §1.125 — Seam transition straightness penalty (S159).
    # Adds a distance-from-midline term scaled by the zone height so the seam
    # has a mild prior toward running horizontally through the zone centre.
    # Row-distance is normalised to [0, 1] so the penalty is scale-invariant.
    if _SEAM_TRANSITION_PEN > 0.0:
        mid_row = energy.shape[0] // 2
        row_dist = np.abs(np.arange(energy.shape[0]) - mid_row).astype(np.float32)
        row_dist_norm = row_dist / max(float(row_dist.max()), 1.0)
        energy = energy + row_dist_norm[:, np.newaxis] * _SEAM_TRANSITION_PEN

    # Transpose (h, W) → (W, h) so DP runs left→right; path[x] = y-offset
    E = energy.T.copy()
    W_e, h_e = E.shape

    # §2.11A: Intelligent Scissors waypoint injection.
    # Setting all rows except y_wp to +inf in column x_wp forces the DP forward
    # pass to route through (x_wp, y_wp): no other row can accumulate finite cost
    # in that column, so the traceback is guaranteed to land on y_wp.  The seam
    # fans out from the forced pixel in subsequent columns at the normal DP rate
    # (±1 per column), preserving 3-connectivity end-to-end.
    if waypoints:
        for x_wp, y_wp in waypoints:
            x_wp, y_wp = x_wp, y_wp
            if 0 <= x_wp < W_e and 0 <= y_wp < h_e:
                col_mask = np.ones(h_e, dtype=bool)
                col_mask[y_wp] = False
                E[x_wp, col_mask] = np.inf

    # §1.5A: Vectorized DP forward pass.
    # minimum_filter1d(row, size=3) computes min(row[j-1], row[j], row[j+1])
    # at every j with cval=inf boundaries — equivalent to the previous
    # per-iteration left/right array allocations but runs as a compiled C kernel.
    for i in range(1, W_e):
        E[i] += _min_filt1d(E[i - 1], size=3, mode="constant", cval=np.inf)

    # §2.11A: build lookup for forced traceback at waypoint columns.
    # The forward-pass inf-injection ensures the seam fans out from y_wp rightward,
    # but the traceback (right→left) may arrive at column x_wp from a row that is
    # outside the ±1 window of y_wp when the seam moved far between x_wp and the
    # end column.  Forcing j = y_wp in the traceback loop at each waypoint column
    # guarantees the path lands exactly on the waypoint regardless of arrival row.
    _wp_force: Dict[int, int] = {}
    if waypoints:
        for _xw, _yw in waypoints:
            _xw, _yw = _xw, _yw
            if 0 <= _xw < W_e and 0 <= _yw < h_e:
                _wp_force[_xw] = _yw

    # Traceback: avoid per-step Python list allocation by using slice argmin.
    path = np.empty(W_e, dtype=np.int32)
    j = _wp_force.get(W_e - 1, int(E[W_e - 1].argmin()))
    path[W_e - 1] = j
    for i in range(W_e - 2, -1, -1):
        if i in _wp_force:
            j = _wp_force[i]  # §2.11A: hard-force seam through waypoint
        else:
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
    # §2.11A: re-apply waypoints after post-processing so smoothing and clamping
    # cannot displace the user-specified seam positions.  Hard constraints win.
    for _x_final, _y_final in _wp_force.items():
        path[_x_final] = _y_final
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
    seam_y = path_local[np.newaxis, :].astype(np.float32)  # (1, W)
    dist = ys - seam_y  # (zone_h, W)
    weight = np.clip(0.5 - dist / (2.0 * ramp), 0.0, 1.0).astype(np.float32)
    return weight


def _build_fg_mesh_barrier(
    apply_mask: np.ndarray,
    min_area_px: int = 100,
) -> np.ndarray:
    """§3.15B — Rasterise a Delaunay triangulation of the fg contour as a 1e6 barrier.

    apply_mask : (H, W) uint8 — foreground mask (255=fg, 0=bg).
    Returns    : (H, W) float32 — 0=background, 1e6=inside a character mesh triangle.
    """
    H, W = apply_mask.shape[:2]
    barrier = np.zeros((H, W), dtype=np.float32)

    contours, _ = cv2.findContours(
        apply_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    if not contours:
        return barrier

    total_area = sum(cv2.contourArea(c) for c in contours)
    if total_area < min_area_px:
        return barrier

    points = np.vstack([c.reshape(-1, 2) for c in contours]).astype(np.float32)
    if len(points) < 4:
        return barrier

    from scipy.spatial import Delaunay  # lazy import

    tri = Delaunay(points)
    for simplex in tri.simplices:
        pts = points[simplex].astype(np.int32)
        cv2.fillConvexPoly(barrier, pts, 1e6)
    return barrier


def _build_seam_cost_map(
    canvas_zone: np.ndarray,
    bg_mask_a: Optional[np.ndarray],
    bg_mask_b: Optional[np.ndarray],
    dilate_px: int = 15,
    barrier_cost: Optional[float] = None,
    exclusion_masks: Optional[List[np.ndarray]] = None,
) -> np.ndarray:
    if (
        BATCH_AVAILABLE
        and barrier_cost is None
        and not exclusion_masks
        and dilate_px == 15              # C++ uses fixed 15px dilate
        and _FG_SEAM_EROSION_PX == 0    # C++ has no erosion stage
        and not _MESH_BARRIER           # C++ has no mesh barrier
        and not _SEAM_HARD_BARRIER      # C++ uses fixed tier ceiling; no hard barrier
        and _COST_MAP_BLUR_SIGMA == 0.0 # C++ has no post-blur step
        and not _COST_MAP_NORM          # C++ normalization is not always equivalent
        and not _SCATTER_COST           # C++ scatter not exposed via flag
    ):
        _all_bg = np.full(canvas_zone.shape[:2], 255, dtype=np.uint8)
        ma = bg_mask_a if bg_mask_a is not None else _all_bg
        mb = bg_mask_b if bg_mask_b is not None else _all_bg
        # cost_map_norm=False: Python fallback never normalizes; keep tiers intact
        return batch.seam.build_seam_cost_map(canvas_zone, ma, mb, cost_map_norm=False)
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

        # §1.65: Erode fg mask before Tier-1 assignment — shrinks the cost=1.0
        # region by _FG_SEAM_EROSION_PX pixels, converting the outermost outline
        # ring from Tier-1 (1.0) to Tier-2 edge-buffer (0.5).  The DP therefore
        # prefers the halo ring over the hard interior, nudging the seam one
        # ring outward from the character outline.
        fg_for_tier1 = fg
        if _FG_SEAM_EROSION_PX > 0:
            erode_k = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE,
                (2 * _FG_SEAM_EROSION_PX + 1, 2 * _FG_SEAM_EROSION_PX + 1),
            )
            fg_for_tier1 = cv2.erode(fg, erode_k)

        # Tier 1 — fg interior: cost=1.0.
        cost = np.maximum(cost, (fg_for_tier1 > 0).astype(np.float32))

        # Tier 2 — dilated fg edge buffer: cost=0.5 (§1.6A).
        # np.maximum preserves Tier 1 at 1.0 for fg pixels; only pure-background
        # pixels near fg edges are raised from 0 → 0.5.
        edge = cv2.morphologyEx(
            fg, cv2.MORPH_GRADIENT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        )
        dilated = cv2.dilate(edge, kernel)
        cost = np.maximum(cost, (dilated > 0).astype(np.float32) * 0.5)

        # §3.20: Extra outer dilation ring — soft 0.3-cost buffer further from
        # fg boundaries; np.maximum preserves higher Tier-1/2 costs.
        if _EXTRA_FG_DILATION > 0:
            _outer_kernel = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE,
                (2 * _EXTRA_FG_DILATION + 1, 2 * _EXTRA_FG_DILATION + 1),
            )
            _outer_dilated = cv2.dilate(fg, _outer_kernel)
            cost = np.maximum(cost, (_outer_dilated > 0).astype(np.float32) * 0.3)

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

    # §3.15B — OBJ-GSP triangular mesh barrier (S144).
    if _MESH_BARRIER:
        combined_fg = np.zeros((zone_h, zone_w), dtype=np.uint8)
        for bm in (bg_mask_a, bg_mask_b):
            if bm is not None:
                fg_bm = (bm < 127).astype(np.uint8) * 255
                if fg_bm.shape != (zone_h, zone_w):
                    fg_bm = cv2.resize(
                        fg_bm, (zone_w, zone_h), interpolation=cv2.INTER_NEAREST
                    )
                combined_fg = np.maximum(combined_fg, fg_bm)
        if combined_fg.any():
            mesh_cost = _build_fg_mesh_barrier(combined_fg)
            cost = np.maximum(cost, mesh_cost)

    # Issue 10A3 — NL seam routing: inject hard-barrier exclusion masks.
    # Each mask pixel > 127 receives cost=1e6 so the DP cannot route through it.
    if exclusion_masks:
        for em in exclusion_masks:
            if em is None:
                continue
            em_zone = em
            if em.shape != (zone_h, zone_w):
                em_zone = cv2.resize(
                    em, (zone_w, zone_h), interpolation=cv2.INTER_NEAREST
                )
            cost[em_zone > 127] = 1e6

    # §1.35: Line-art gradient penalty — fg-interior outline pixels cost more than flat fill.
    # Adds normalized Laplacian magnitude (in [0, _LINE_GRAD_WEIGHT]) only to fg pixels
    # (cost >= 1.0), so character outline pixels become more expensive than the body fill.
    if _LINE_GRAD_WEIGHT > 0.0 and canvas_zone.size > 0:
        grad = _fg_gradient_cost(canvas_zone, _LINE_GRAD_WEIGHT)
        fg_mask = cost >= 1.0
        cost[fg_mask] = cost[fg_mask] + grad[fg_mask]

    # §3.17 — high-frequency column cost: penalise texture-heavy columns.
    if _HF_SEAM_COST:
        cost = cost + _hf_column_cost(
            canvas_zone, canvas_zone, _HF_SEAM_THRESHOLD, _HF_SEAM_BOOST
        )

    # §1.99: Amplify fg cost at seam zone top/bottom to force bg entry/exit.
    if _SEAM_PIN_ROWS > 0 and zone_h > 2 * _SEAM_PIN_ROWS:
        _pin = _SEAM_PIN_ROWS
        _fg_pin = cost >= 1.0
        cost[:_pin] = np.where(_fg_pin[:_pin], cost[:_pin] * 10.0, cost[:_pin])
        cost[-_pin:] = np.where(_fg_pin[-_pin:], cost[-_pin:] * 10.0, cost[-_pin:])

    # §1.109: L-inf normalize non-barrier costs to [0, 1].
    if _COST_MAP_NORM:
        soft_mask = cost < 1e5
        soft_max = float(cost[soft_mask].max()) if soft_mask.any() else 1.0
        if soft_max > 1e-6:
            cost = np.where(soft_mask, cost / soft_max, cost)

    # §1.110: Gaussian blur soft-cost region to smooth tier transitions (S154).
    if _COST_MAP_BLUR_SIGMA > 0.0:
        from scipy.ndimage import gaussian_filter as _gf

        soft_mask = cost < 1e5
        barriers = np.where(soft_mask, 0.0, cost)
        blurred = _gf(
            np.where(soft_mask, cost, 0.0).astype(np.float64),
            sigma=_COST_MAP_BLUR_SIGMA,
        )
        cost = np.where(soft_mask, blurred, barriers)

    # §1.113: Column-wise Gaussian smooth on soft-cost region (S155).
    if _COST_COL_SMOOTH_SIGMA > 0.0:
        from scipy.ndimage import gaussian_filter1d as _gf1d_col

        _soft_col = cost < 1e5
        _cost_soft = np.where(_soft_col, cost, 0.0)
        _cost_soft_smooth = _gf1d_col(
            _cost_soft.astype(np.float64),
            sigma=_COST_COL_SMOOTH_SIGMA,
            axis=1,
            mode="nearest",
        )
        cost = np.where(_soft_col, _cost_soft_smooth.astype(np.float32), cost)

    # §1.123: Local scatter penalty — per-pixel local variance additive term (S158).
    # Penalises high-frequency noise/texture regions, steering DP toward smooth bg.
    if _SCATTER_COST and canvas_zone.size > 0:
        _gray_sc = cv2.cvtColor(canvas_zone, cv2.COLOR_BGR2GRAY).astype(np.float32)
        _mean_sc = cv2.boxFilter(_gray_sc, cv2.CV_32F, (3, 3))
        _mean_sq_sc = cv2.boxFilter((_gray_sc**2), cv2.CV_32F, (3, 3))
        _var_sc = np.maximum(0.0, _mean_sq_sc - _mean_sc**2)
        _soft_sc = cost < 1e5
        _var_max = float(_var_sc[_soft_sc].max()) if _soft_sc.any() else 1.0
        if _var_max > 1e-6:
            _scatter = (_var_sc / _var_max) * _SCATTER_COST_WEIGHT
            cost = np.where(_soft_sc, cost + _scatter.astype(np.float32), cost)

    # §1.126 — Fg-majority column floor (S159).
    # When the zone is >60% fg interior (cost ≥ 1.0), raises columns that are
    # >80% fg to at least _FG_MAJORITY_FLOOR so the DP seam is guided toward
    # the minority background/low-cost corridor columns.
    if _FG_MAJORITY_FLOOR > 0.0:
        _zone_fg_frac_126 = float((cost >= 1.0).mean())
        if _zone_fg_frac_126 > 0.60:
            _col_fg_frac = (cost >= 1.0).mean(axis=0)
            _heavy_cols = _col_fg_frac > 0.80
            if _heavy_cols.any() and not _heavy_cols.all():
                cost[:, _heavy_cols] = np.maximum(
                    cost[:, _heavy_cols], _FG_MAJORITY_FLOOR
                )

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
    _in_band = np.abs(_row_idx - _path_row) < band_px  # (zone_h, W) bool

    dom_content_mask = (dom_zone.max(axis=2) > 0) & _in_band
    oth_content_mask = (oth_zone.max(axis=2) > 0) & _in_band

    if dom_content_mask.sum() < 10 or oth_content_mask.sum() < 10:
        return oth_zone.copy()

    dom_mean = dom_zone[dom_content_mask].astype(np.float32).mean(axis=0)  # (C,)
    oth_mean = oth_zone[oth_content_mask].astype(np.float32).mean(axis=0)  # (C,)
    delta = dom_mean - oth_mean  # (C,)

    out = oth_zone.copy()
    shifted = oth_zone[_in_band].astype(np.float32) + delta
    out[_in_band] = np.clip(shifted, 0, 255).astype(np.uint8)
    return out


def _seam_band_hist_match(
    dom_zone: np.ndarray,
    oth_zone: np.ndarray,
    path_local: np.ndarray,
    band_px: int,
) -> np.ndarray:
    """Per-channel ECDF histogram match of oth_zone to dom_zone in the seam blend band.

    More robust than mean-shift (§1.88, S147) for zones with different luminance
    distributions. Returns a copy of oth_zone with histogram-matched band pixels.
    Falls back to mean-shift when scipy is unavailable or too few band pixels exist.
    """
    if band_px <= 0:
        return oth_zone.copy()

    zone_h, W = dom_zone.shape[:2]
    n_channels = dom_zone.shape[2] if dom_zone.ndim == 3 else 1

    # Build column-based band mask (column distance from seam path < band_px)
    band_mask = np.zeros((zone_h, W), dtype=bool)
    for row in range(min(len(path_local), zone_h)):
        col = int(path_local[row])
        lo = max(0, col - band_px)
        hi = min(W, col + band_px + 1)
        band_mask[row, lo:hi] = True

    n_band = int(band_mask.sum())
    if n_band < 10:
        return oth_zone.copy()

    oth_matched = oth_zone.copy().astype(np.float32)

    try:
        from scipy.interpolate import interp1d as _interp1d
    except ImportError:
        _interp1d = None

    for c in range(n_channels):
        if dom_zone.ndim == 3:
            dom_ch = dom_zone[band_mask, c].astype(np.float32)
            oth_ch = oth_zone[band_mask, c].astype(np.float32)
        else:
            dom_ch = dom_zone[band_mask].astype(np.float32)
            oth_ch = oth_zone[band_mask].astype(np.float32)

        if _interp1d is None or len(oth_ch) < 2:
            # Mean-shift fallback
            delta = dom_ch.mean() - oth_ch.mean()
            if dom_zone.ndim == 3:
                oth_matched[band_mask, c] = np.clip(oth_ch + delta, 0, 255)
            else:
                oth_matched[band_mask] = np.clip(oth_ch + delta, 0, 255)
            continue

        dom_sorted = np.sort(dom_ch)
        oth_sorted = np.sort(oth_ch)

        dom_quantiles = np.linspace(0, 1, len(dom_sorted))
        transfer = _interp1d(
            dom_quantiles,
            dom_sorted,
            bounds_error=False,
            fill_value=(dom_sorted[0], dom_sorted[-1]),
        )

        ranks = np.searchsorted(oth_sorted, oth_ch) / max(len(oth_sorted) - 1, 1)
        ranks = np.clip(ranks, 0, 1)
        mapped = transfer(ranks)

        if dom_zone.ndim == 3:
            oth_matched[band_mask, c] = np.clip(mapped, 0, 255)
        else:
            oth_matched[band_mask] = np.clip(mapped, 0, 255)

    return oth_matched.astype(oth_zone.dtype)


def _seam_lum_converge(
    dom_zone: np.ndarray,
    oth_zone: np.ndarray,
    path_local: np.ndarray,
    band_px: int,
    target_delta: float = 5.0,
    max_iters: int = 2,
) -> np.ndarray:
    """Iteratively call _seam_color_match until band mean-delta < target_delta (§1.91, S148).

    After S16+§1.88, if a residual colour step remains above *target_delta* lum
    units, applies another _seam_color_match pass.  Caps at *max_iters* to avoid
    over-correction on genuinely different-exposure zones.
    """
    if band_px <= 0 or max_iters < 1:
        return oth_zone.copy()

    zone_h, W = oth_zone.shape[:2]
    out = oth_zone.copy()

    for _ in range(max_iters):
        # Measure mean absolute delta in the blend band
        band_mask = np.zeros((zone_h, W), dtype=bool)
        for row in range(min(len(path_local), zone_h)):
            col = int(path_local[row])
            lo = max(0, col - band_px)
            hi = min(W, col + band_px + 1)
            band_mask[row, lo:hi] = True

        n_pix = int(band_mask.sum())
        if n_pix < 10:
            break

        dom_band = dom_zone[band_mask].astype(np.float32)
        oth_band = out[band_mask].astype(np.float32)
        delta = float(np.abs(dom_band.mean(axis=0) - oth_band.mean(axis=0)).mean())

        if delta <= target_delta:
            break
        out = _seam_color_match(dom_zone, out, path_local, band_px)

    return out


def _smooth_feather_array(
    feathers: np.ndarray,
    sigma: float = 1.0,
    feather_min: int = 0,
    feather_max: int = 9999,
) -> np.ndarray:
    """1D Gaussian smooth on feather widths to prevent abrupt adjacent-seam transitions (§1.92, S148).

    Prevents jarring changes between e.g. feather=80px (tight fg seam) and
    feather=300px (wide bg seam).  feather_min/max are re-clamped after smoothing.
    Falls back to identity for sequences of length ≤ 1.
    """
    if len(feathers) <= 1:
        return feathers.copy()
    try:
        from scipy.ndimage import gaussian_filter1d as _gf1d
    except ImportError:
        return feathers.copy()
    smoothed = _gf1d(feathers.astype(float), sigma=sigma)
    return np.clip(np.round(smoothed), feather_min, feather_max).astype(feathers.dtype)


def _zone_chroma_align(
    fa_zone: np.ndarray,
    fb_zone: np.ndarray,
) -> np.ndarray:
    if BATCH_AVAILABLE:
        return batch.compositing.zone_chroma_align(fa_zone, fb_zone, 3.0)
    """§3.19: Global LAB a/b shift of fb_zone to match fa_zone mean chroma (S149).

    Computes the mean LAB a/b values over non-black pixels in each zone and
    applies a global additive shift to fb_zone so its chroma mean matches
    fa_zone.  This corrects colour-temperature drift between adjacent frames
    before the Laplacian blend, reducing the residual visible at seam
    boundaries that §1.56 (post-composite) otherwise must fix.
    """
    mask_a = fa_zone.max(axis=2) > 0
    mask_b = fb_zone.max(axis=2) > 0
    if not mask_a.any() or not mask_b.any():
        return fb_zone.copy()

    lab_a = cv2.cvtColor(fa_zone, cv2.COLOR_BGR2LAB).astype(np.float32)
    lab_b = cv2.cvtColor(fb_zone, cv2.COLOR_BGR2LAB).astype(np.float32)

    mean_a_ch1 = float(lab_a[mask_a, 1].mean())
    mean_a_ch2 = float(lab_a[mask_a, 2].mean())
    mean_b_ch1 = float(lab_b[mask_b, 1].mean())
    mean_b_ch2 = float(lab_b[mask_b, 2].mean())

    delta_ch1 = mean_a_ch1 - mean_b_ch1
    delta_ch2 = mean_a_ch2 - mean_b_ch2

    if abs(delta_ch1) < 2.0 and abs(delta_ch2) < 2.0:
        return fb_zone.copy()

    out_lab = lab_b.copy()
    out_lab[..., 1] = np.clip(out_lab[..., 1] + delta_ch1, 0, 255)
    out_lab[..., 2] = np.clip(out_lab[..., 2] + delta_ch2, 0, 255)
    return cv2.cvtColor(out_lab.astype(np.uint8), cv2.COLOR_LAB2BGR)


def _smooth_gain_array(gains: "List[float]", sigma: float = 1.0) -> np.ndarray:
    """§1.98: Gaussian smooth over per-frame gain values (S150).

    Reduces abrupt brightness jumps between adjacent strips caused by isolated
    outlier gain corrections.  Returns a float64 array of the same length.
    """
    from scipy.ndimage import gaussian_filter1d

    arr = np.array(gains, dtype=np.float64)
    if arr.size < 2:
        return arr
    return gaussian_filter1d(arr, sigma=sigma, mode="nearest")


def _zone_lum_norm(
    fa_zone: np.ndarray,
    fb_zone: np.ndarray,
) -> np.ndarray:
    if BATCH_AVAILABLE:
        return batch.compositing.zone_lum_norm(fa_zone, fb_zone, 2.0)
    """§1.104: Per-zone bg-pixel luminance normalization (S152).

    Computes mean grayscale luminance of non-black pixels in *fa_zone* and
    *fb_zone*.  When the ratio exceeds 1% deviation, applies a scalar gain
    to *fb_zone*'s non-black pixels so its mean luminance matches *fa_zone*.
    Returns a uint8 copy of *fb_zone* with corrected luminance.
    """
    mask_a = fa_zone.max(axis=2) > 0
    mask_b = fb_zone.max(axis=2) > 0
    if not mask_a.any() or not mask_b.any():
        return fb_zone.copy()

    lum_a = float(fa_zone[mask_a].astype(np.float32).mean())
    lum_b = float(fb_zone[mask_b].astype(np.float32).mean())

    if lum_b < 1.0 or abs(lum_a - lum_b) / max(lum_b, 1.0) < 0.01:
        return fb_zone.copy()

    gain = np.clip(lum_a / lum_b, 0.5, 2.0)
    out = fb_zone.astype(np.float32)
    out[mask_b] = np.clip(out[mask_b] * gain, 0, 255)
    return out.astype(np.uint8)


def _zone_sat_norm(
    fa_zone: np.ndarray,
    fb_zone: np.ndarray,
) -> np.ndarray:
    if BATCH_AVAILABLE:
        return batch.compositing.zone_sat_norm(fa_zone, fb_zone, 2.0)
    """§1.111: Per-zone background HSV saturation normalization (S154).

    Converts both zones to HSV, computes mean saturation of background
    (non-black) pixels in each zone, then scales *fb_zone*'s saturation
    channel so its background mean matches *fa_zone*'s.  Fg pixels (all
    channels == 0) are excluded from the saturation estimate and returned
    unchanged.  A gain clamp of [0.5, 2.0] prevents over-saturation on
    near-greyscale frames.  Returns a uint8 copy of *fb_zone*.
    """
    import cv2 as _cv2

    mask_a = fa_zone.max(axis=2) > 0
    mask_b = fb_zone.max(axis=2) > 0
    if not mask_a.any() or not mask_b.any():
        return fb_zone.copy()

    hsv_a = _cv2.cvtColor(fa_zone, _cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv_b = _cv2.cvtColor(fb_zone, _cv2.COLOR_BGR2HSV).astype(np.float32)

    sat_a = float(hsv_a[mask_a, 1].mean())
    sat_b = float(hsv_b[mask_b, 1].mean())

    if sat_b < 1.0 or abs(sat_a - sat_b) / max(sat_b, 1.0) < 0.02:
        return fb_zone.copy()

    gain = np.clip(sat_a / sat_b, 0.5, 2.0)
    hsv_out = hsv_b.copy()
    hsv_out[mask_b, 1] = np.clip(hsv_out[mask_b, 1] * gain, 0, 255)
    out = _cv2.cvtColor(hsv_out.astype(np.uint8), _cv2.COLOR_HSV2BGR)
    return out


def _audit_seam_lum_steps(
    result: np.ndarray,
    boundaries: "List[float]",
    band_px: int = 5,
    warn_thresh: float = 8.0,
) -> "Dict[int, float]":
    """§1.106: Post-composite per-boundary luminance step audit (S152).

    For each boundary, measures mean absolute lum difference in a ±band_px
    row band around the boundary in *result*.  Logs a warning when any step
    exceeds *warn_thresh*.  Returns a dict {boundary_idx: lum_step}.
    """
    H = result.shape[0]
    steps: dict = {}
    for k, by_f in enumerate(boundaries):
        by = int(by_f)
        above_y0 = max(0, by - band_px)
        above_y1 = max(0, by)
        below_y0 = min(H, by)
        below_y1 = min(H, by + band_px)
        if above_y1 <= above_y0 or below_y1 <= below_y0:
            steps[k] = 0.0
            continue
        above_lum = float(
            result[above_y0:above_y1]
            .astype(np.float32)
            .dot(np.array([0.114, 0.587, 0.299], dtype=np.float32))
            .mean()
        )
        below_lum = float(
            result[below_y0:below_y1]
            .astype(np.float32)
            .dot(np.array([0.114, 0.587, 0.299], dtype=np.float32))
            .mean()
        )
        step = abs(above_lum - below_lum)
        steps[k] = step
        if step > warn_thresh:
            print(
                f"[Stitch] §1.106 seam-step WARNING: B{k} lum_step={step:.1f} "
                f"> {warn_thresh:.1f} at y={by}"
            )
    return steps


def _adaptive_seam_band(zone_h: int, base_band: int, max_band: int = 40) -> int:
    """§1.107: Zone-height-aware seam band width (S153).

    Returns ``min(max_band, max(base_band, zone_h // 6))``.  For tall zones
    the band grows so colour-match corrections capture more of the transition
    region; for short zones it falls back to *base_band*.
    """
    return min(max_band, max(base_band, zone_h // 6))


def _zone_contrast_eq(
    fa_zone: np.ndarray,
    fb_zone: np.ndarray,
) -> np.ndarray:
    if BATCH_AVAILABLE:
        return batch.compositing.zone_contrast_eq(fa_zone, fb_zone, 2.0)
    """§1.114: Per-zone RMS contrast (luminance std) equalization (S155).

    Computes luminance standard deviation over non-black pixels in each zone
    and scales *fb_zone* so its contrast matches *fa_zone*.  Scale factor is
    clamped to [0.5, 2.0] to prevent extreme corrections.  Returns a uint8
    copy of *fb_zone* with equalized contrast.
    """
    mask_a = fa_zone.max(axis=2) > 0
    mask_b = fb_zone.max(axis=2) > 0
    if not mask_a.any() or not mask_b.any():
        return fb_zone.copy()

    lum_weights = np.array([0.114, 0.587, 0.299], dtype=np.float32)
    lum_a = fa_zone[mask_a].astype(np.float32).dot(lum_weights)
    lum_b = fb_zone[mask_b].astype(np.float32).dot(lum_weights)

    std_a = float(lum_a.std())
    std_b = float(lum_b.std())

    if std_b < 1.0 or abs(std_a - std_b) / max(std_b, 1.0) < 0.05:
        return fb_zone.copy()

    scale = float(np.clip(std_a / std_b, 0.5, 2.0))
    mean_b = float(lum_b.mean())
    out = fb_zone.astype(np.float32)
    out[mask_b] = np.clip((out[mask_b] - mean_b) * scale + mean_b, 0, 255)
    return out.astype(np.uint8)


def _zone_hue_eq(
    fa_zone: np.ndarray,
    fb_zone: np.ndarray,
) -> np.ndarray:
    if BATCH_AVAILABLE:
        return batch.compositing.zone_hue_eq(fa_zone, fb_zone, 3.0)
    """§1.127: Per-zone HSV hue equalization (S159).

    Converts both zones to HSV and computes the circular mean hue of non-black
    pixels in each zone.  If the mean hue difference exceeds
    ZONE_HUE_EQ_MIN_DIFF_DEG degrees, shifts *fb_zone* hue by the delta so the
    two zones share the same mean hue.  Only hue is modified; saturation and
    value channels are unchanged.  The shift is clamped to [−30°, +30°] to
    prevent extreme corrections from pushing the seam further into a
    non-matching region.  Returns a uint8 copy of fb_zone.
    """
    from backend.src.constants.animation import ZONE_HUE_EQ_MIN_DIFF_DEG

    mask_a = fa_zone.max(axis=2) > 0
    mask_b = fb_zone.max(axis=2) > 0
    if not mask_a.any() or not mask_b.any():
        return fb_zone.copy()

    hsv_a = cv2.cvtColor(fa_zone, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv_b = cv2.cvtColor(fb_zone, cv2.COLOR_BGR2HSV).astype(np.float32)

    # Circular mean hue in [0, 180] (OpenCV convention)
    def _mean_hue(hsv: np.ndarray, mask: np.ndarray) -> float:
        h = hsv[mask, 0] * (np.pi / 90.0)  # → radians [0, 2π]
        return (
            float(np.arctan2(np.sin(h).mean(), np.cos(h).mean()) * (90.0 / np.pi))
            % 180.0
        )

    mean_h_a = _mean_hue(hsv_a, mask_a)
    mean_h_b = _mean_hue(hsv_b, mask_b)

    # Circular difference in [−90, 90] (half the 180-degree hue wheel)
    delta = mean_h_a - mean_h_b
    if delta > 90.0:
        delta -= 180.0
    elif delta < -90.0:
        delta += 180.0

    if abs(delta) < ZONE_HUE_EQ_MIN_DIFF_DEG:
        return fb_zone.copy()

    delta = float(np.clip(delta, -30.0, 30.0))
    out_hsv = hsv_b.copy()
    out_hsv[mask_b, 0] = (out_hsv[mask_b, 0] + delta) % 180.0
    return cv2.cvtColor(out_hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)


def _blocks_gain_compensate(
    fa_zone: np.ndarray,
    fb_zone: np.ndarray,
    block_size: int = 32,
) -> np.ndarray:
    """§4.1: Spatial blocks gain compensation (S160).

    Divides the blend zone into *block_size* × *block_size* blocks and computes
    a per-block per-channel BGR gain ratio ``mean(fa_block) / mean(fb_block)``.
    A bilinear-resized (H, W, 3) gain map is applied to *fb_zone* to correct
    strip-level banding that global scalar gain normalisation cannot handle.
    Gain is clamped to [0.5, 2.0] before application.  Blocks where the
    fb-channel mean is < 1.0 (near-black) use gain=1.0 (safe no-op).

    Returns a uint8 copy of fb_zone with the spatial gain applied.
    """
    if fa_zone.size == 0 or fb_zone.size == 0:
        return fb_zone.copy()
    if BATCH_AVAILABLE and hasattr(batch, "compositing") and hasattr(
        batch.compositing, "blocks_gain_compensate_pair"
    ):
        try:
            return np.asarray(
                batch.compositing.blocks_gain_compensate_pair(fa_zone, fb_zone, block_size)
            )
        except Exception:
            pass
    H, W = fb_zone.shape[:2]
    bs = max(1, block_size)
    n_rows = max(1, (H + bs - 1) // bs)
    n_cols = max(1, (W + bs - 1) // bs)
    gain_grid = np.ones((n_rows, n_cols, 3), dtype=np.float32)
    for ri in range(n_rows):
        r0 = ri * bs
        r1 = min(r0 + bs, H)
        for ci in range(n_cols):
            c0 = ci * bs
            c1 = min(c0 + bs, W)
            fa_b = fa_zone[r0:r1, c0:c1].astype(np.float32)
            fb_b = fb_zone[r0:r1, c0:c1].astype(np.float32)
            for ch in range(3):
                m_fb = fb_b[:, :, ch].mean()
                m_fa = fa_b[:, :, ch].mean()
                gain_grid[ri, ci, ch] = (m_fa / m_fb) if m_fb >= 1.0 else 1.0
    gain_map = cv2.resize(gain_grid, (W, H), interpolation=cv2.INTER_LINEAR)
    gain_map = np.clip(gain_map, 0.5, 2.0)
    result = np.clip(fb_zone.astype(np.float32) * gain_map, 0, 255).astype(np.uint8)
    return result


def _blocks_lum_compensate(
    fa_zone: np.ndarray,
    fb_zone: np.ndarray,
    block_size: int = 32,
) -> np.ndarray:
    """§4.4: LAB L-channel blocks gain compensation (S160).

    Like ``_blocks_gain_compensate`` but uses the LAB L-channel ratio as a
    scalar gain applied uniformly to all BGR channels.  This avoids the colour
    cast that per-channel BGR gain can produce when any channel's mean is near
    zero in a block.  Gain clamped to [0.5, 2.0].

    Returns a uint8 copy of fb_zone with the spatial L-gain applied.
    """
    if fa_zone.size == 0 or fb_zone.size == 0:
        return fb_zone.copy()
    if BATCH_AVAILABLE and hasattr(batch, "compositing") and hasattr(
        batch.compositing, "blocks_lum_compensate_pair"
    ):
        try:
            return np.asarray(
                batch.compositing.blocks_lum_compensate_pair(fa_zone, fb_zone, block_size)
            )
        except Exception:
            pass
    H, W = fb_zone.shape[:2]
    fa_lab = cv2.cvtColor(fa_zone, cv2.COLOR_BGR2LAB).astype(np.float32)
    fb_lab = cv2.cvtColor(fb_zone, cv2.COLOR_BGR2LAB).astype(np.float32)
    bs = max(1, block_size)
    n_rows = max(1, (H + bs - 1) // bs)
    n_cols = max(1, (W + bs - 1) // bs)
    gain_grid = np.ones((n_rows, n_cols), dtype=np.float32)
    for ri in range(n_rows):
        r0 = ri * bs
        r1 = min(r0 + bs, H)
        for ci in range(n_cols):
            c0 = ci * bs
            c1 = min(c0 + bs, W)
            m_fb_l = float(fb_lab[r0:r1, c0:c1, 0].mean())
            m_fa_l = float(fa_lab[r0:r1, c0:c1, 0].mean())
            gain_grid[ri, ci] = m_fa_l / max(1.0, m_fb_l)
    gain_map = cv2.resize(gain_grid, (W, H), interpolation=cv2.INTER_LINEAR)
    gain_map = np.clip(gain_map, 0.5, 2.0)
    result = np.clip(
        fb_zone.astype(np.float32) * gain_map[:, :, np.newaxis], 0, 255
    ).astype(np.uint8)
    return result


def _cap_feather_jumps(feathers: np.ndarray, max_jump: int) -> np.ndarray:
    """§1.115: Two-pass absolute feather jump cap (S155).

    Forward and backward passes: each element is clamped to within *max_jump*
    of its left/right neighbour.  Prevents sudden large jumps between adjacent
    seam feather widths that §1.68 ratio-cap can miss for extreme values.
    """
    if max_jump <= 0 or len(feathers) < 2:
        return feathers
    out = feathers.astype(np.float64).copy()
    for i in range(1, len(out)):
        out[i] = np.clip(out[i], out[i - 1] - max_jump, out[i - 1] + max_jump)
    for i in range(len(out) - 2, -1, -1):
        out[i] = np.clip(out[i], out[i + 1] - max_jump, out[i + 1] + max_jump)
    return out.astype(feathers.dtype)


def _measure_seam_sharpness(
    result: np.ndarray,
    boundaries: "List[float]",
    band_px: int = 5,
) -> "Dict[int, float]":
    """§1.118: Per-boundary Laplacian variance sharpness measurement (S156).

    For each boundary, computes the Laplacian variance of a ±*band_px* row
    band in *result*.  Returns a dict {boundary_idx: laplacian_variance}.
    Low variance indicates blur introduced by the seam blend.
    """
    H = result.shape[0]
    gray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
    sharpness: dict = {}
    for k, by_f in enumerate(boundaries):
        by = int(by_f)
        y0 = max(0, by - band_px)
        y1 = min(H, by + band_px)
        if y1 - y0 < 2:
            sharpness[k] = 0.0
            continue
        band = gray[y0:y1]
        lap = cv2.Laplacian(band, cv2.CV_64F)
        sharpness[k] = float(lap.var())
    return sharpness


def _zone_width_cv(boundaries: "List[float]") -> float:
    """§1.119: Coefficient of variation of seam zone widths (S157).

    Returns std(widths) / mean(widths) for the N-1 inter-boundary gaps.
    Returns 0.0 for fewer than 2 boundaries (no zone widths to measure).
    """
    if len(boundaries) < 2:
        return 0.0
    widths = [boundaries[i + 1] - boundaries[i] for i in range(len(boundaries) - 1)]
    arr = np.array(widths, dtype=np.float64)
    mean = float(arr.mean())
    if mean < 1e-6:
        return 0.0
    return float(arr.std() / mean)


def _audit_seam_sat_steps(
    result: np.ndarray,
    boundaries: "List[float]",
    band_px: int = 5,
    warn_thresh: float = 0.0,
) -> "Dict[int, float]":
    """§1.120: Per-boundary HSV saturation step audit (S157).

    Measures mean HSV saturation difference in ±*band_px* row bands above and
    below each seam boundary.  High values indicate chromatic banding not
    captured by the luminance-only §1.106 lum audit.
    """
    H = result.shape[0]
    hsv = cv2.cvtColor(result, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1].astype(np.float32)
    sat_steps: dict = {}
    for k, by_f in enumerate(boundaries):
        by = int(by_f)
        guard = max(1, band_px // 2)
        y_above_end = max(0, by - guard)
        y_above_start = max(0, y_above_end - band_px)
        y_below_start = min(H, by + guard)
        y_below_end = min(H, y_below_start + band_px)
        above = sat[y_above_start:y_above_end]
        below = sat[y_below_start:y_below_end]
        if above.size == 0 or below.size == 0:
            sat_steps[k] = 0.0
            continue
        step = float(abs(above.mean() - below.mean()))
        sat_steps[k] = step
        if warn_thresh > 0.0 and step > warn_thresh:
            print(
                f"[Stitch] §1.120 sat-step WARNING: B{k} sat_diff={step:.2f}"
                f" > {warn_thresh:.2f}"
            )
    return sat_steps


def _zone_hist_intersection(fa_zone: np.ndarray, fb_zone: np.ndarray) -> float:
    """§1.121: Per-channel histogram intersection between two zone crops (S157).

    Returns the mean per-channel normalised histogram intersection in [0, 1].
    1.0 = identical histograms; 0.0 = no overlap.  Fast compared to full SSIM.
    """
    if fa_zone.size == 0 or fb_zone.size == 0:
        return 1.0
    h = min(fa_zone.shape[0], fb_zone.shape[0])
    w = min(fa_zone.shape[1], fb_zone.shape[1])
    if h < 2 or w < 2:
        return 1.0
    score = 0.0
    for c in range(3):
        ha = cv2.calcHist([fa_zone[:h, :w]], [c], None, [32], [0, 256])
        hb = cv2.calcHist([fb_zone[:h, :w]], [c], None, [32], [0, 256])
        ha = ha.ravel() / (ha.sum() + 1e-6)
        hb = hb.ravel() / (hb.sum() + 1e-6)
        score += float(np.minimum(ha, hb).sum())
    return score / 3.0


def _mean_path_cost(path_local: np.ndarray, cost_map: np.ndarray) -> float:
    """§1.122: Mean seam cost along the selected DP path (S158)."""
    if path_local.size == 0 or cost_map.size == 0:
        return 0.0
    W = len(path_local)
    cols = np.arange(W)
    rows = np.clip(path_local, 0, cost_map.shape[0] - 1)
    return float(cost_map[rows, cols].mean())


def _hf_column_cost(
    zone_a: np.ndarray,
    zone_b: np.ndarray,
    hf_threshold: float = 50.0,
    hf_boost: float = 0.5,
) -> np.ndarray:
    """Per-column high-frequency energy additive cost for seam routing (§3.17, S147).

    Columns with strong Laplacian energy (high-frequency texture) get an
    additional cost so the DP seam prefers low-texture background corridors.
    Returns (zone_h, W) float32 cost map additive to the existing cost map.
    """
    zone_h, zone_w = zone_a.shape[:2]

    def _col_energy(zone: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(zone, cv2.COLOR_BGR2GRAY) if zone.ndim == 3 else zone.copy()
        lap = cv2.Laplacian(gray.astype(np.float32), cv2.CV_32F, ksize=3)
        return np.abs(lap).mean(axis=0)  # (W,)

    energy_a = _col_energy(zone_a)
    energy_b = _col_energy(zone_b)
    col_energy = (energy_a + energy_b) / 2.0

    cost_row = np.where(col_energy > hf_threshold, hf_boost, 0.0).astype(np.float32)
    return np.tile(cost_row, (zone_h, 1))


def _bilateral_seam_smooth(
    canvas: np.ndarray,
    seam_paths: Dict[int, np.ndarray],
    band_px: int = 5,
    sigma_space: float = 3.0,
    sigma_color: float = 20.0,
) -> np.ndarray:
    """Bilateral filter in ±band_px columns around each seam path (§1.90, S147).

    Smooths residual 1–3 lum-unit color steps left after compositing without
    blurring content outside the narrow seam band.
    """
    out = canvas.copy()

    for _k, path in seam_paths.items():
        if path is None or len(path) == 0:
            continue
        zone_h = min(len(path), canvas.shape[0])
        for row in range(zone_h):
            col = int(path[row])
            lo = max(0, col - band_px)
            hi = min(canvas.shape[1], col + band_px + 1)
            if hi - lo < 3:
                continue
            row_lo = max(0, row - 2)
            row_hi = min(canvas.shape[0], row + 3)
            band_crop = out[row_lo:row_hi, lo:hi]
            if band_crop.shape[0] < 1 or band_crop.shape[1] < 3:
                continue
            smoothed = cv2.bilateralFilter(
                band_crop,
                d=0,
                sigmaColor=sigma_color,
                sigmaSpace=sigma_space,
            )
            out[row_lo:row_hi, lo:hi] = smoothed

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
    _dist = np.abs(_row_idx - _path_row)  # (zone_h, W)
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
    ideal = ref_lum / frame_lum
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

    valid = [lum for lum in frame_lums if lum is not None]
    if len(valid) < 3:
        return result

    median_lum = np.median(valid)
    for i, lum in enumerate(frame_lums):
        if lum is not None and abs(lum - median_lum) > max_deviation_lum:
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
    return (_POISSON_SEAM, _TOONCRAFTER_SEAM, _GRAPHCUT_SEAM, _SEAM_BATCH, _MULTIBAND_BLEND, _DP_CANVAS_SEAM)


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


def _canvas_dp_seam_composite(
    warped_norm: List[np.ndarray],
    warped_bg: List,
    canvas: np.ndarray,
    H: int,
    W: int,
    N: int,
) -> Optional[np.ndarray]:
    """§4.5: Canvas-space DP seam composite using cv2.detail_DpSeamFinder.

    Runs a single multi-frame DpSeamFinder("COLOR_GRAD") call in canvas space,
    handling 3-way overlaps that N-1 independent pairwise DPs miss.  Each frame
    contributes a full-canvas coverage mask; the finder partitions ownership into
    N non-overlapping regions and the result is composited pixel-by-pixel.

    Falls back gracefully — callers wrap in try/except.

    Returns the composited canvas (H×W×3 uint8) or None if N<2.
    """
    if N < 2:
        return None

    # Build coverage masks: 255 where this frame has content, 0 otherwise.
    _dp_masks = [
        (warped_norm[i].max(axis=2) > 0).astype(np.uint8) * 255
        for i in range(N)
    ]
    # Corners: all frames are in canvas space → top-left = (0, 0) for each.
    _dp_corners = [(0, 0)] * N

    finder = cv2.detail_DpSeamFinder("COLOR_GRAD")
    # find() modifies masks in-place (partitions ownership).
    finder.find(warped_norm, _dp_corners, _dp_masks)

    result = canvas.copy()
    for i in range(N):
        own = _dp_masks[i] > 127
        src = warped_norm[i]
        has_content = src.max(axis=2) > 0
        apply_px = own & has_content
        if warped_bg[i] is not None:
            apply_px = apply_px & (~warped_bg[i])
        result[apply_px] = src[apply_px]

    # Fill remaining black pixels from any frame that has content there.
    _black = result.max(axis=2) == 0
    if _black.any():
        for _wn in warped_norm:
            _fill = _black & (_wn.max(axis=2) > 0)
            if _fill.any():
                result[_fill] = _wn[_fill]
                _black = result.max(axis=2) == 0
            if not _black.any():
                break

    return result


def _feather_gc_boundaries(
    result: np.ndarray,
    ownership_masks: List[np.ndarray],
    warped_frames: List[np.ndarray],
    feather_px: int = 8,
) -> np.ndarray:
    """§3.33: Narrow feathered blend at GraphCut ownership transitions.

    For each adjacent pair (i, i+1) of ownership masks the per-column boundary
    row (last row owned by frame i) is found and a ±feather_px linear alpha ramp
    is blended between the two source frames.  Only pixels where both frames have
    content (non-black) are blended; all-black pixels are skipped so gap-fill work
    is not undone.
    """
    N = len(ownership_masks)
    if N < 2 or feather_px <= 0:
        return result
    out = result.copy()
    H, W = result.shape[:2]
    rows = np.arange(H, dtype=np.int32)[:, None]  # (H, 1) broadcast column
    for i in range(N - 1):
        own_i = (ownership_masks[i] > 127)
        has_col_i = own_i.any(axis=0)                    # (W,) — columns frame i owns
        last_row_i = (H - 1) - np.argmax(own_i[::-1], axis=0)  # last owned row per col
        boundary = np.where(has_col_i, last_row_i, -1)  # (W,) — -1 for unowned cols

        src_i    = warped_frames[i].astype(np.float32)
        src_next = warped_frames[i + 1].astype(np.float32)
        content_i    = warped_frames[i].max(axis=2) > 0   # (H, W)
        content_next = warped_frames[i + 1].max(axis=2) > 0

        b = boundary[None, :]  # (1, W)
        # alpha=1.0 → fully frame i; alpha=0.0 → fully frame i+1
        alpha = ((b + feather_px - rows) / (2.0 * feather_px)).clip(0.0, 1.0)
        in_band = (rows >= (b - feather_px)) & (rows <= (b + feather_px)) & (b >= 0)
        blend_here = in_band & content_i & content_next
        if not blend_here.any():
            continue
        alpha3 = alpha[:, :, None]
        blended = (alpha3 * src_i + (1.0 - alpha3) * src_next).clip(0, 255).astype(np.uint8)
        out[blend_here] = blended[blend_here]
    return out


def _equalize_warped_gains(
    warped_frames: List[np.ndarray],
    block_size: int = 32,
) -> List[np.ndarray]:
    """§4.10: Equalize inter-frame luminance before seam finding.

    Sequential pairwise gain compensation: frame 0 is the reference; each
    subsequent frame is corrected to match its (already-corrected) predecessor.
    Only pixels where BOTH adjacent frames have valid content (max channel > 0)
    are altered — black/transparent border fill regions are left untouched.
    """
    if len(warped_frames) < 2:
        return [f.copy() for f in warped_frames]
    result: List[np.ndarray] = [warped_frames[0].copy()]
    for i in range(1, len(warped_frames)):
        prev = result[i - 1]
        curr = warped_frames[i]
        has_prev = prev.max(axis=2) > 0
        has_curr = curr.max(axis=2) > 0
        both_valid = has_prev & has_curr
        if not both_valid.any():
            result.append(curr.copy())
            continue
        corrected = _blocks_gain_compensate(prev, curr, block_size=block_size)
        out = curr.copy()
        out[both_valid] = corrected[both_valid]
        result.append(out)
    return result


def _compute_ecc_confidence(
    crop_a: np.ndarray,
    crop_b: np.ndarray,
    mask: Optional[np.ndarray] = None,
) -> float:
    """§4.6 — cv2.computeECC-based agreement score between two same-shape
    crops, mapped from [-1, 1] to a [0, 1] confidence. Higher agreement
    (better photometric/geometric alignment between this frame's content
    and its neighbours' in the overlap band) means higher confidence."""
    if crop_a.size == 0 or crop_a.shape != crop_b.shape:
        return 0.5
    try:
        ga = cv2.cvtColor(crop_a, cv2.COLOR_BGR2GRAY).astype(np.float32)
        gb = cv2.cvtColor(crop_b, cv2.COLOR_BGR2GRAY).astype(np.float32)
        m = mask if mask is None else np.ascontiguousarray(mask.astype(np.uint8))
        cc = cv2.computeECC(ga, gb, m)
        if not np.isfinite(cc):
            return 0.5
        return float(np.clip((cc + 1.0) / 2.0, 0.0, 1.0))
    except cv2.error:
        return 0.5


def _compute_multiband_confidence(
    gc_frames: List[np.ndarray],
    ownership: List[np.ndarray],
    bg_masks: List[Optional[np.ndarray]],
    band_px: int = _MULTIBAND_CONF_BAND_PX,
) -> List[np.ndarray]:
    """§4.6 MultiBand Confidence-Weighted Blending.

    Builds a smoothly-varying per-frame confidence mask (uint8, 0-255) for
    cv::detail::MultiBandBlender.feed(), replacing the hard 0/255 GraphCut
    ownership label. Combines three signals:

      - dist_to_seam: distance-transform softening near the GraphCut
        boundary -- full confidence deep inside a frame's owned region,
        tapering to 0.5 right at the seam, so the blend pyramid weights
        uncertain transition pixels more gently than a binary cut.
      - bg_conf: distance-transform softening near the BiRefNet fg/bg mask
        edge -- least confident right at the character silhouette, most
        confident away from it in either direction.
      - ecc_conf: per-frame agreement (cv2.computeECC) between this frame's
        owned content and the union of all *other* frames' owned content,
        restricted to the seam-adjacent band (cheap -- not a full-frame
        pass). Stands in for the "ECC residual" signal from Stage 8 without
        threading state through the whole pipeline.

    conf = own_binary * dist_to_seam_norm * bg_conf * ecc_conf, scaled to
    [0, 255]. own_binary keeps coverage identical to the hard GraphCut
    ownership (0 stays 0 -- WHICH frame owns a pixel is unchanged); only the
    *weighting* within an owned region is graded.
    """
    n = len(gc_frames)
    confidences: List[np.ndarray] = []

    for i in range(n):
        own = (ownership[i] > 127).astype(np.uint8)
        if own.sum() == 0:
            confidences.append(np.zeros(own.shape, dtype=np.uint8))
            continue

        dist = cv2.distanceTransform(own * 255, cv2.DIST_L2, 5)
        dist_conf = 0.5 + 0.5 * np.clip(dist / max(1, band_px), 0.0, 1.0)

        bg_conf = np.ones_like(dist_conf)
        bmask = bg_masks[i] if i < len(bg_masks) else None
        if bmask is not None:
            fg = (~bmask.astype(bool)).astype(np.uint8)
            fg_dist = cv2.distanceTransform(fg * 255, cv2.DIST_L2, 5)
            bg_dist = cv2.distanceTransform((1 - fg) * 255, cv2.DIST_L2, 5)
            edge_dist = np.minimum(fg_dist, bg_dist)
            bg_conf = 0.6 + 0.4 * np.clip(edge_dist / max(1, band_px), 0.0, 1.0)

        ecc_conf_scalar = 1.0
        band = (dist < band_px) & own.astype(bool)
        if band.sum() > 64:
            others = np.zeros_like(gc_frames[i])
            has_other = np.zeros(own.shape, dtype=bool)
            for j in range(n):
                if j == i:
                    continue
                oj = ownership[j] > 127
                others[oj] = gc_frames[j][oj]
                has_other |= oj
            band = band & has_other
            if band.sum() > 64:
                ys, xs = np.where(band)
                y0, y1 = int(ys.min()), int(ys.max()) + 1
                x0, x1 = int(xs.min()), int(xs.max()) + 1
                ecc_conf_scalar = _compute_ecc_confidence(
                    gc_frames[i][y0:y1, x0:x1],
                    others[y0:y1, x0:x1],
                    band[y0:y1, x0:x1],
                )

        conf = own.astype(np.float32) * dist_conf * bg_conf * ecc_conf_scalar
        confidences.append(np.clip(conf * 255.0, 0, 255).astype(np.uint8))

    return confidences


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
    seam_meta_out: Optional[dict] = None,
    seam_overrides: Optional[dict] = None,
) -> np.ndarray:
    """
    Deghost the temporal-median canvas by replacing animated foreground pixels
    with single-frame content.

    paint_mask: optional uint8 (H_canvas, W_canvas) mask painted by the user
    in HITL checkpoint 4.5.  Pixels >127 are treated as hard seam barriers
    (cost=1e6), forcing the DP to route seams around the painted region.
    Appended to *exclusion_masks* so it is sliced per-zone identically.

    seam_meta_out: optional mutable dict that is populated on return with
    ``{"boundaries": list, "seam_post_diffs": dict, "seam_single_pose": dict}``.
    Used by HITL checkpoint 4.6 to surface per-seam diagnostic data.

    seam_overrides: optional dict mapping seam index k → override options dict.
    Supported keys: ``"force_single_pose"`` (bool) skips ARAP and immediately
    escalates seam k to the dominant-pose frame; ``"force_blend"`` (bool) undoes
    any single-pose escalation for seam k after the registration pass, forcing
    the DSFN blend path regardless of post_warp_diff.

    Background pixels are always kept from the temporal median (photometrically
    consistent across the whole canvas).  Only foreground character pixels are
    replaced with the single best owning frame, eliminating ghosting without
    introducing zone-level brightness discontinuities in the background.

    At ownership boundaries a Laplacian pyramid blend with a DP seam path is
    applied to foreground pixels only, providing a seamless character transition.
    """
    # relocated: from backend.src.animation.core.stateless import _laplacian_blend

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
    valid_lums = [lum for lum in frame_lums if lum is not None]
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
        _skip_norm = [a or b for a, b in zip(_skip_norm, _exp_skip, strict=False)]
    if len(valid_lums) >= 2:
        lum_by_order = [frame_lums[int(order[k])] for k in range(N)]
        adj_diffs = [
            abs(lum_by_order[k + 1] - lum_by_order[k])
            for k in range(len(lum_by_order) - 1)
            if lum_by_order[k] is not None and lum_by_order[k + 1] is not None
        ]
        _max_adj_diff = max(adj_diffs) if adj_diffs else 0.0
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
                    gain_map = _multiscale_gain_map(warped_list[i], canvas, bg_sel)
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

    # §1.98: Smooth per-frame gains to prevent abrupt brightness staircase.
    if _SMOOTH_GAIN and N > 1:
        _smoothed_gains = _smooth_gain_array(frame_gains, sigma=_SMOOTH_GAIN_SIGMA)
        for _sg_i in range(N):
            _sg_ratio = float(_smoothed_gains[_sg_i]) / max(frame_gains[_sg_i], 1e-6)
            if abs(_sg_ratio - 1.0) > 0.005 and warped_bg[_sg_i] is not None:
                _bg_sel_sg = warped_bg[_sg_i] & (warped_norm[_sg_i].max(axis=2) > 10)
                if _bg_sel_sg.any():
                    _f32_sg = warped_norm[_sg_i].astype(np.float32)
                    _f32_sg[_bg_sel_sg] = np.clip(
                        _f32_sg[_bg_sel_sg] * _sg_ratio, 0, 255
                    )
                    warped_norm[_sg_i] = _f32_sg.astype(np.uint8)

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
            feathers[k] = min(min_fk, max_feathers[k])
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
            feathers,
            boundaries,
            warped_bg,
            order,
            cap_px=_FG_FEATHER_CAP,
            fg_thresh=_FG_FEATHER_THRESH,
        )
        print(
            "[Stitch]   Feathers (§1.19 fg-density-capped): "
            + " ".join(f"B{k}={int(feathers[k])}px" for k in range(n_b))
        )

    # §1.68: Adjacent feather ratio enforcement — prevent rhythm discontinuity.
    if _FEATHER_RATIO_MAX > 0.0 and n_b > 1:
        feathers = _enforce_feather_ratio(feathers, max_ratio=_FEATHER_RATIO_MAX)

    # §1.92 — Gaussian smooth on feather widths to reduce abrupt transitions.
    if _SMOOTH_FEATHER and n_b > 1:
        feathers = _smooth_feather_array(
            feathers,
            sigma=_SMOOTH_FEATHER_SIGMA,
            feather_min=int(FEATHER_MIN),
            feather_max=int(FEATHER_MAX),
        )
        print(
            "[Stitch]   Feathers (§1.92 Gaussian-smoothed): "
            + " ".join(f"B{k}={int(feathers[k])}px" for k in range(n_b))
        )

    # §1.115: Absolute feather jump cap.
    if _FEATHER_JUMP_MAX > 0 and n_b > 1:
        feathers = _cap_feather_jumps(feathers, _FEATHER_JUMP_MAX)

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
    seam_post_diffs: dict = {}  # k → post-warp diff score (residual if fallback)
    seam_synthesized: dict = {}  # k → synthesized seam-band crop (ToonCrafter §3.6)
    if _FG_REGISTER_ENABLED and N >= 2:
        try:
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

                # §2.4A: User seam override — force single-pose for this seam.
                _ov_k = (seam_overrides or {}).get(k, {})
                if _ov_k.get("force_single_pose"):
                    _by_int_sp = int(by)
                    _half_sp = min(20, int(feathers[k]))
                    _y0_sp = max(0, _by_int_sp - _half_sp)
                    _y1_sp = min(H, _by_int_sp + _half_sp)
                    _fg_a_cnt_sp = int(fg_a[_y0_sp:_y1_sp].sum())
                    _fg_b_cnt_sp = int(fg_b[_y0_sp:_y1_sp].sum())
                    seam_single_pose[k] = fi_a if _fg_a_cnt_sp >= _fg_b_cnt_sp else fi_b
                    seam_post_diffs[k] = 99.0  # sentinel: user-forced single-pose
                    continue

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

                # §1.34: Seam zone texture-energy pre-escalation.
                # Skip ARAP when both frames have flat colour near the seam —
                # optical flow has no gradient signal (aperture problem) and will
                # produce garbage offsets that worsen the blend.
                if _SEAM_LOW_TEXTURE_THRESH > 0.0 and k not in seam_single_pose:
                    _tex = _seam_zone_texture_energy(
                        warped_norm[fi_a], warped_norm[fi_b], int(by)
                    )
                    if _tex < _SEAM_LOW_TEXTURE_THRESH:
                        _by_int = int(by)
                        _half = min(20, int(feathers[k]))
                        _y0 = max(0, _by_int - _half)
                        _y1 = min(H, _by_int + _half)
                        _fg_a_cnt = int(fg_a[_y0:_y1].sum())
                        _fg_b_cnt = int(fg_b[_y0:_y1].sum())
                        _dom = fi_a if _fg_a_cnt >= _fg_b_cnt else fi_b
                        seam_single_pose[k] = _dom
                        seam_post_diffs[k] = _tex
                        n_fallback += 1
                        print(
                            f"[Stitch]     FG-register B{k} (frames {fi_a}/{fi_b}): "
                            f"texture={_tex:.2f} < {_SEAM_LOW_TEXTURE_THRESH:.2f} "
                            f"→ flat-zone single-pose (frame {_dom})"
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

                # §2.10C: user-drawn flow field override
                _flow_ov = None
                _arrows_ov = (_ov_k or {}).get("flow_arrows")
                if _arrows_ov:
                    try:
                        from backend.src.animation.alignment.fg_register import _sparse_flow_to_dense as _s2d

                        _H_ov, _W_ov = warped_norm[fi_a].shape[:2]
                        _flow_ov = _s2d(_arrows_ov, _H_ov, _W_ov)
                    except Exception as _fe:
                        print(
                            f"[Stitch] §2.10C: flow_arrows→dense failed ({_fe}); using RAFT/DIS."
                        )

                adj_a, adj_b, info = register_foreground_at_seam(
                    warped_norm[fi_a],
                    warped_norm[fi_b],
                    fg_a,
                    fg_b,
                    seam_pos=int(by),
                    axis=reg_axis,
                    alpha_a=alpha_a,
                    alpha_b=alpha_b,
                    flow_override=_flow_ov,
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
                    # §1.102: Momentum damping — lower threshold when previous seam was a fallback.
                    if _WARP_MOMENTUM_DAMP and k > 0 and k - 1 in seam_single_pose:
                        _sp_thresh *= _WARP_MOMENTUM_FACTOR
                    if _SP_THRESH_FG_SCALE:
                        _by_int_95 = int(by)
                        _half_95 = int(feathers[k])
                        _y0_95 = max(0, _by_int_95 - _half_95)
                        _y1_95 = min(H, _by_int_95 + _half_95)
                        _bg_a_95 = (
                            warped_bg[fi_a][_y0_95:_y1_95]
                            if warped_bg[fi_a] is not None
                            else None
                        )
                        _bg_b_95 = (
                            warped_bg[fi_b][_y0_95:_y1_95]
                            if warped_bg[fi_b] is not None
                            else None
                        )
                        _frac_95 = _fg_fraction_in_zone(_bg_a_95, _bg_b_95)
                        if _frac_95 > _SP_FG_FRAC_THRESH:
                            _sp_thresh *= _SP_THRESH_FG_FACTOR
                    if post_diff > _sp_thresh:
                        # §2.10A: HITL callback — offer a flow override before committing
                        # to single-pose escalation.
                        if _flow_hitl_callback is not None:
                            try:
                                _hitl_flow = _flow_hitl_callback(
                                    k,
                                    {
                                        "post_warp_diff": post_diff,
                                        "seam_k": k,
                                        "fi_a": fi_a,
                                        "fi_b": fi_b,
                                    },
                                )
                                if _hitl_flow is not None:
                                    _re_adj_a, _re_adj_b, _re_info = (
                                        register_foreground_at_seam(
                                            warped_norm[fi_a],
                                            warped_norm[fi_b],
                                            fg_a,
                                            fg_b,
                                            seam_pos=int(by),
                                            axis=reg_axis,
                                            alpha_a=alpha_a,
                                            alpha_b=alpha_b,
                                            flow_override=_hitl_flow,
                                        )
                                    )
                                    if _re_info["warped"]:
                                        warped_norm[fi_a] = _re_adj_a
                                        warped_norm[fi_b] = _re_adj_b
                                        post_diff = _re_info.get(
                                            "post_warp_diff", post_diff
                                        )
                                        seam_post_diffs[k] = post_diff
                            except Exception as _hitl_exc:
                                print(
                                    f"[Stitch] §2.10A: HITL callback error ({_hitl_exc}); ignoring."
                                )
                        # §1.103: Reference-proximity dominant frame selection.
                        if _SP_REF_PROX:
                            dom = (
                                fi_a
                                if abs(fi_a - ref_fi) <= abs(fi_b - ref_fi)
                                else fi_b
                            )
                        else:
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

            # §2.4A: Post-loop force_blend override — undo single-pose escalation
            # for any seam the user explicitly wants to keep blended.
            if seam_overrides:
                for _k_fb, _opts_fb in seam_overrides.items():
                    if _opts_fb.get("force_blend"):
                        seam_single_pose.pop(int(_k_fb), None)

            # ToonCrafter seam synthesis (§3.6B) — applied to single-pose
            # escalated seams when ASP_TOONCRAFTER_SEAM=1.  Synthesizes a
            # coherent intermediate pose that replaces the hard-partition
            # boundary.  Only the worst seam (highest post_warp_diff) per run
            # is synthesized to keep inference overhead bounded (~24s on A100).
            if _TOONCRAFTER_SEAM and seam_single_pose:
                try:
                    # relocated: from backend.src.animation.rendering.anim_fill import _generate_canonical_cel
                    # relocated: import torch as _tc_torch

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
            # relocated: from backend.src.animation.rendering.anim_fill import _generate_canonical_cel
            # relocated: import torch as _tc_torch

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

    # §4.10: Equalise inter-frame luminance before seam finding.
    if _GLOBAL_GAIN_COMP and len(warped_norm) >= 2:
        warped_norm = _equalize_warped_gains(warped_norm, block_size=32)

    # §4.2/§4.6: GraphCut global seam + optional MultiBand blend (Phase 4).
    # When ASP_GRAPHCUT_SEAM=1, replaces the hard-partition + DP blend loop below
    # with a single global cv::detail::GraphCutSeamFinder call that assigns each
    # canvas pixel to one frame simultaneously across all N frames, eliminating
    # pairwise DP seam conflicts.  If ASP_MULTIBAND_BLEND=1 is also set, the
    # cv::detail::MultiBandBlender replaces the per-zone Laplacian blend.
    if _GRAPHCUT_SEAM and BATCH_AVAILABLE and N >= 2:
        try:
            _gc_frames  = [np.ascontiguousarray(warped_norm[i]) for i in range(N)]
            # Coverage mask: pixels this frame actually covers on the canvas
            _gc_masks   = [
                (warped_norm[i].max(axis=2) > 0).astype(np.uint8) * 255
                for i in range(N)
            ]
            # Frames are full canvas-size — all corners at (0,0)
            _gc_corners = [(0, 0)] * N
            print(f"[Stitch]   §4.2 GraphCut seam (global, {N} frames)...")
            _ownership = batch.seam.graphcut_seam_find(
                _gc_frames, _gc_masks, _gc_corners
            )
            result = canvas.copy()
            if _MULTIBAND_BLEND:
                print(f"[Stitch]   §4.6 MultiBand blend ({N} frames, 5 bands)...")
                _mb_feed_masks = _ownership
                if _MULTIBAND_CONF:
                    _mb_feed_masks = _compute_multiband_confidence(
                        _gc_frames, _ownership, warped_bg
                    )
                    print(
                        f"[Stitch]   §4.6 confidence-weighted feed masks "
                        f"(band={_MULTIBAND_CONF_BAND_PX}px)."
                    )
                _mb = batch.compositing.multiband_blend(
                    _gc_frames, _mb_feed_masks, _gc_corners, num_bands=5
                )
                rh, rw = min(_mb.shape[0], H), min(_mb.shape[1], W)
                result[:rh, :rw] = _mb[:rh, :rw]
                print(f"[Stitch]   MultiBand blend done ({rh}×{rw}px).")
            else:
                for i in range(N):
                    own = _ownership[i] > 127
                    src = warped_norm[i]
                    has_content = src.max(axis=2) > 0
                    _apply_gc = own & has_content
                    if warped_bg[i] is not None:
                        _apply_gc = _apply_gc & (~warped_bg[i])
                    result[_apply_gc] = src[_apply_gc]
            # Gap fill — same as DP path
            _gc_black = result.max(axis=2) == 0
            if _gc_black.any():
                for _gcwn in warped_norm:
                    _gc_fill = _gc_black & (_gcwn.max(axis=2) > 0)
                    if _gc_fill.any():
                        result[_gc_fill] = _gcwn[_gc_fill]
                        _gc_black = result.max(axis=2) == 0
                    if not _gc_black.any():
                        break
            # §3.33: feather GC ownership boundaries (hard-partition only; MultiBand handles its own blend)
            if not _MULTIBAND_BLEND and _GC_FEATHER_PX > 0:
                result = _feather_gc_boundaries(result, _ownership, _gc_frames, feather_px=_GC_FEATHER_PX)
            # Seam metadata for HITL
            if seam_meta_out is not None:
                seam_meta_out.update(
                    {
                        "boundaries": (
                            boundaries.tolist()
                            if hasattr(boundaries, "tolist")
                            else list(boundaries)
                        ),
                        "seam_post_diffs": dict(seam_post_diffs),
                        "seam_single_pose": dict(seam_single_pose),
                        "seam_crops": _extract_seam_crops(result, boundaries),
                    }
                )
            print("[Stitch]   GraphCut composite done.")
            return result
        except Exception as _gc_exc:
            print(
                f"[Stitch]   §4.2 GraphCut seam failed ({_gc_exc}), "
                "falling back to DP blend."
            )

    # §4.5: Canvas-space DP seam (cv2.detail_DpSeamFinder) — intermediate fallback
    # between GraphCut (batch, global) and the pairwise DP blend loop below.
    # Uses the same ownership-mask→composite path as GraphCut but with OpenCV's
    # built-in DpSeamFinder, which handles 3-way overlaps the pairwise DP misses.
    # Enable: ASP_DP_CANVAS_SEAM=1 (only useful when GraphCut is disabled).
    if _DP_CANVAS_SEAM and N >= 2:
        try:
            _dp_result = _canvas_dp_seam_composite(
                warped_norm, warped_bg, canvas, H, W, N
            )
            if _dp_result is not None:
                if seam_meta_out is not None:
                    seam_meta_out.update(
                        {
                            "boundaries": (
                                boundaries.tolist()
                                if hasattr(boundaries, "tolist")
                                else list(boundaries)
                            ),
                            "seam_post_diffs": dict(seam_post_diffs),
                            "seam_single_pose": dict(seam_single_pose),
                            "seam_crops": _extract_seam_crops(_dp_result, boundaries),
                        }
                    )
                print("[Stitch]   §4.5 Canvas-space DP seam done.")
                return _dp_result
        except Exception as _dp_exc:
            print(
                f"[Stitch]   §4.5 Canvas-space DP seam failed ({_dp_exc}), "
                "falling back to pairwise DP."
            )


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
    # relocated: import concurrent.futures as _cf

    def _seam_job(job_args):
        _k, _fa_z, _fb_z, _sem, _W, _zh, _wps = job_args
        _both = (_fa_z.max(axis=2) > 0) & (_fb_z.max(axis=2) > 0)
        if int(_both.sum()) > _zh * _W // 20:
            try:
                return _k, _seam_cut(_fa_z, _fb_z, sem_cost=_sem, waypoints=_wps)
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
        _em_zone = [
            em[_y0:_y1]
            for em in (_eff_exclusion or [])
            if em is not None and em.shape[0] >= _y1
        ]
        _sem = _build_seam_cost_map(
            result[_y0:_y1].copy(),
            ((_bg_a_z.astype(np.uint8) * 255) if _bg_a_z is not None else None),
            ((_bg_b_z.astype(np.uint8) * 255) if _bg_b_z is not None else None),
            exclusion_masks=_em_zone or None,
        )
        # §2.11A: per-seam waypoints from seam_overrides (canvas-space y offset to zone-local)
        _ov_wps_raw = (seam_overrides or {}).get(_k, {}).get("waypoints")
        _ov_wps: Optional[List[Tuple[int, int]]] = None
        if _ov_wps_raw:
            _ov_wps = [
                (int(x), int(y) - _y0)
                for x, y in _ov_wps_raw
                if 0 <= int(y) - _y0 < _y1 - _y0
            ]
        _seam_jobs.append((_k, _fa_z, _fb_z, _sem, W, _y1 - _y0, _ov_wps))

    if _SEAM_BATCH and len(_seam_jobs) > 1:
        # Phase 4: dispatch all seams to C++ OpenMP parallel batch (GIL released)
        _zone_pairs = [
            {
                "fa": np.ascontiguousarray(_j[1]),
                "fb": np.ascontiguousarray(_j[2]),
                "cost": _j[3],
            }
            for _j in _seam_jobs
        ]
        _batch_paths = batch.seam.seam_batch(_zone_pairs, edge_weight=1.0)
        for _ji, (_k, _fa_j, _, _, _W_j, _zh_j, _) in enumerate(_seam_jobs):
            _raw = _batch_paths[_ji]
            _precomp_paths[_k] = _raw if len(_raw) == _W_j else np.full(_W_j, _zh_j // 2, dtype=np.int32)
    elif len(_seam_jobs) > 1:
        _pool = _get_seam_pool()
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

    # §1.119: Zone width variance gate — pre-escalate narrowest seam when
    # boundary layout is highly uneven (indicates bad boundary optimisation).
    if _ZONE_WIDTH_CV_MAX > 0.0 and n_b >= 2:
        _cv119 = _zone_width_cv(list(boundaries))
        if _cv119 > _ZONE_WIDTH_CV_MAX:
            _widths119 = [boundaries[i + 1] - boundaries[i] for i in range(n_b - 1)]
            _worst_k119 = int(np.argmin(_widths119))
            if _worst_k119 not in seam_single_pose:
                _fi_a119 = int(order[_worst_k119])
                _fi_b119 = int(order[_worst_k119 + 1])
                _fga119 = int((warped_norm[_fi_a119].max(axis=2) > 0).sum())
                _fgb119 = int((warped_norm[_fi_b119].max(axis=2) > 0).sum())
                seam_single_pose[_worst_k119] = (
                    _fi_a119 if _fga119 >= _fgb119 else _fi_b119
                )

    # Laplacian blend at each boundary seam zone (foreground pixels only)
    # §1.89 — process lowest-residual seams first to establish quality baseline.
    _seam_order = list(range(n_b))
    if _SEAM_ORDER_RESIDUAL and seam_post_diffs:
        _seam_order = sorted(_seam_order, key=lambda _k: seam_post_diffs.get(_k, 0.0))
    for _loop_idx in _seam_order:
        k, by = _loop_idx, boundaries[_loop_idx]
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

        # §1.60: fg pose-gap pre-escalation — when the two warped frames differ
        # significantly in their shared fg pixels, the character poses are too
        # dissimilar for Laplacian blending to produce a ghost-free result.
        # Escalate to single-pose before the DP seam cut fires.
        if _FG_POSE_GAP_THRESH > 0.0 and k not in seam_single_pose:
            _pose_gap = _fg_zone_pose_gap(fa_zone, fb_zone)
            if _pose_gap > _FG_POSE_GAP_THRESH:
                _fg_a2 = int((fa_zone.max(axis=2) > 0).sum())
                _fg_b2 = int((fb_zone.max(axis=2) > 0).sum())
                seam_single_pose[k] = fi_a if _fg_a2 >= _fg_b2 else fi_b
                print(
                    f"[Stitch]   §1.60 pose-gap B{k}: fg MAD={_pose_gap:.1f} "
                    f"> {_FG_POSE_GAP_THRESH:.1f} → single-pose frame {seam_single_pose[k]}"
                )

        # §1.121: Zone histogram intersection pre-gate (S157).
        if _ZONE_HIST_THRESH > 0.0 and k not in seam_single_pose:
            _hist_score = _zone_hist_intersection(fa_zone, fb_zone)
            if _hist_score < _ZONE_HIST_THRESH:
                _fg_a121 = int((fa_zone.max(axis=2) > 0).sum())
                _fg_b121 = int((fb_zone.max(axis=2) > 0).sum())
                seam_single_pose[k] = fi_a if _fg_a121 >= _fg_b121 else fi_b

        # §1.70: blend-zone fg-coverage pre-escalation — when the entire overlap
        # zone is fg-dominated (no background corridor for the DP seam to use),
        # skip the DP and immediately escalate to single-pose.
        _bg_a_zone = warped_bg[fi_a][y0_f:y1_f] if warped_bg[fi_a] is not None else None
        _bg_b_zone = warped_bg[fi_b][y0_f:y1_f] if warped_bg[fi_b] is not None else None
        # §1.116: Always compute zone bg fraction for diagnostics.
        _zone_bg_frac_116 = 1.0 - _fg_fraction_in_zone(_bg_a_zone, _bg_b_zone)
        if _ZONE_BG_FRAC_DIAG and debug_context is not None:
            _zone_bg_fracs_116 = debug_context.setdefault("zone_bg_fracs", {})
            _zone_bg_fracs_116[k] = _zone_bg_frac_116
        if _SEAM_ZONE_FG_MAX > 0.0 and k not in seam_single_pose:
            _zone_fg_frac = _fg_fraction_in_zone(_bg_a_zone, _bg_b_zone)
            if _zone_fg_frac > _SEAM_ZONE_FG_MAX:
                _fg_a3 = int((fa_zone.max(axis=2) > 0).sum())
                _fg_b3 = int((fb_zone.max(axis=2) > 0).sum())
                seam_single_pose[k] = fi_a if _fg_a3 >= _fg_b3 else fi_b
                print(
                    f"[Stitch]   §1.70 zone-fg B{k}: fg={_zone_fg_frac:.2f} "
                    f"> {_SEAM_ZONE_FG_MAX:.2f} → single-pose frame {seam_single_pose[k]}"
                )

        # §1.86: Zone SSIM pre-gate — escalate to single-pose when the two warped
        # zone crops are structurally incompatible after ARAP registration.  A low
        # SSIM means different character poses that blending will ghost.
        if _ZONE_PRE_SSIM_THRESH > 0.0 and k not in seam_single_pose:
            _zone_ssim = _zone_pair_ssim(fa_zone, fb_zone)
            if _zone_ssim < _ZONE_PRE_SSIM_THRESH:
                _fg_a_86 = int((fa_zone.max(axis=2) > 0).sum())
                _fg_b_86 = int((fb_zone.max(axis=2) > 0).sum())
                seam_single_pose[k] = fi_a if _fg_a_86 >= _fg_b_86 else fi_b
                print(
                    f"[Stitch]   §1.86 zone-ssim B{k}: ssim={_zone_ssim:.3f} "
                    f"< {_ZONE_PRE_SSIM_THRESH:.3f} → single-pose frame {seam_single_pose[k]}"
                )

        # §1.97: Seam zone entropy asymmetry gate.
        if _ENTROPY_GAP_THRESH > 0.0 and k not in seam_single_pose:
            _entr_gap = _seam_zone_entropy_gap(fa_zone, fb_zone)
            if _entr_gap > _ENTROPY_GAP_THRESH:
                _fg_a97 = int((fa_zone.max(axis=2) > 0).sum())
                _fg_b97 = int((fb_zone.max(axis=2) > 0).sum())
                seam_single_pose[k] = fi_a if _fg_a97 >= _fg_b97 else fi_b
                print(
                    f"[Stitch]   §1.97 entropy-gap B{k}: gap={_entr_gap:.2f} "
                    f"> {_ENTROPY_GAP_THRESH:.2f} → single-pose frame {seam_single_pose[k]}"
                )

        # §1.117: Fast thumbnail NCC structural pre-gate.
        if _ZONE_FAST_NCC_THRESH > 0.0 and k not in seam_single_pose:
            _fast_ncc = _zone_pair_ncc(fa_zone, fb_zone)
            if _fast_ncc < _ZONE_FAST_NCC_THRESH:
                _fg_a117 = int((fa_zone.max(axis=2) > 0).sum())
                _fg_b117 = int((fb_zone.max(axis=2) > 0).sum())
                seam_single_pose[k] = fi_a if _fg_a117 >= _fg_b117 else fi_b
                print(
                    f"[Stitch]   §1.117 fast-NCC B{k}: ncc={_fast_ncc:.3f} "
                    f"< {_ZONE_FAST_NCC_THRESH:.3f} → single-pose frame {seam_single_pose[k]}"
                )

        # §1.101: Full blend-zone MAD pre-escalation.
        if _ZONE_MAD_THRESH > 0.0 and k not in seam_single_pose:
            _mad_101 = float(
                np.abs(fa_zone.astype(np.float32) - fb_zone.astype(np.float32)).mean()
            )
            if _mad_101 > _ZONE_MAD_THRESH:
                _fg_a101 = int((fa_zone.max(axis=2) > 0).sum())
                _fg_b101 = int((fb_zone.max(axis=2) > 0).sum())
                seam_single_pose[k] = fi_a if _fg_a101 >= _fg_b101 else fi_b
                print(
                    f"[Stitch]   §1.101 zone-MAD B{k}: mad={_mad_101:.1f} "
                    f"> {_ZONE_MAD_THRESH:.1f} → single-pose frame {seam_single_pose[k]}"
                )

        # P2.4 — Semantic seam routing: build a character-boundary cost map so
        # the DP path avoids cutting through foreground outlines.

        # Use pre-computed seam path when available (parallel pre-computation above)
        path_local = _precomp_paths.get(k)
        if path_local is None:
            # Fallback: compute inline (zone was skipped in pre-compute or < 4px)
            _em_zone_fb = [
                em[y0_f:y1_f]
                for em in (_eff_exclusion or [])
                if em is not None and em.shape[0] >= y1_f
            ]
            _sem_cost = _build_seam_cost_map(
                result[y0_f:y1_f],
                (
                    (_bg_a_zone.astype(np.uint8) * 255)
                    if _bg_a_zone is not None
                    else None
                ),
                (
                    (_bg_b_zone.astype(np.uint8) * 255)
                    if _bg_b_zone is not None
                    else None
                ),
                exclusion_masks=_em_zone_fb or None,
            )
            both = (fa_zone.max(axis=2) > 0) & (fb_zone.max(axis=2) > 0)
            if int(both.sum()) > zone_h * W // 20:
                try:
                    # §2.11A: thread waypoints into inline fallback seam cut
                    _fb_wps_raw = (seam_overrides or {}).get(k, {}).get("waypoints")
                    _fb_wps: Optional[List[Tuple[int, int]]] = None
                    if _fb_wps_raw:
                        _fb_wps = [
                            (int(_wx), int(_wy) - y0_f)
                            for _wx, _wy in _fb_wps_raw
                            if 0 <= int(_wy) - y0_f < zone_h
                        ]
                    path_local = _seam_cut(
                        fa_zone, fb_zone, sem_cost=_sem_cost, waypoints=_fb_wps
                    )
                except Exception:
                    path_local = np.full(W, zone_h // 2, dtype=np.int32)
            else:
                path_local = np.full(W, zone_h // 2, dtype=np.int32)

        # §1.69: Post-DP bg-routing ratio check — if the DP seam was forced
        # through too many fg pixels despite cost-map steering, escalate to
        # single-pose for this boundary before applying the blend.
        if _SEAM_DP_BG_MIN > 0.0 and k not in seam_single_pose:
            _bg_a_dp = (
                warped_bg[fi_a][y0_f:y1_f] if warped_bg[fi_a] is not None else None
            )
            _bg_b_dp = (
                warped_bg[fi_b][y0_f:y1_f] if warped_bg[fi_b] is not None else None
            )
            _dp_bg_r = _seam_dp_bg_ratio(path_local, _bg_a_dp, _bg_b_dp)
            if _dp_bg_r < _SEAM_DP_BG_MIN:
                _fg_a4 = int((fa_zone.max(axis=2) > 0).sum())
                _fg_b4 = int((fb_zone.max(axis=2) > 0).sum())
                seam_single_pose[k] = fi_a if _fg_a4 >= _fg_b4 else fi_b
                print(
                    f"[Stitch]   §1.69 dp-bg-ratio B{k}: bg={_dp_bg_r:.2f} "
                    f"< {_SEAM_DP_BG_MIN:.2f} → single-pose frame {seam_single_pose[k]}"
                )

        # §1.122: High seam path cost escalation (S158) — mean DP path cost gate.
        if (
            _HIGH_PATH_COST_THRESH > 0.0
            and k not in seam_single_pose
            and path_local is not None
        ):
            try:
                _mpc = _mean_path_cost(path_local, _sem_cost)
            except Exception:
                _mpc = 0.0
            if _mpc > _HIGH_PATH_COST_THRESH:
                _fg_a122 = int((fa_zone.max(axis=2) > 0).sum())
                _fg_b122 = int((fb_zone.max(axis=2) > 0).sum())
                seam_single_pose[k] = fi_a if _fg_a122 >= _fg_b122 else fi_b
                print(
                    f"[Stitch]   §1.122 high-path-cost B{k}: mean_cost={_mpc:.3f} "
                    f"> {_HIGH_PATH_COST_THRESH:.3f} → single-pose frame {seam_single_pose[k]}"
                )

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

        _fb_for_blend = fb_zone
        if k not in seam_single_pose:
            if _ZONE_CHROMA_ALIGN:
                _fb_for_blend = _zone_chroma_align(fa_zone, _fb_for_blend)
            if _ZONE_LUM_NORM:
                _fb_for_blend = _zone_lum_norm(fa_zone, _fb_for_blend)
            if _BLOCKS_GAIN_COMP:
                _fb_for_blend = _blocks_gain_compensate(fa_zone, _fb_for_blend)
            if _BLOCKS_LUM_COMP:
                _fb_for_blend = _blocks_lum_compensate(fa_zone, _fb_for_blend)
            if _ZONE_SAT_NORM:
                _fb_for_blend = _zone_sat_norm(fa_zone, _fb_for_blend)
            if _ZONE_CONTRAST_EQ:
                _fb_for_blend = _zone_contrast_eq(fa_zone, _fb_for_blend)
            if _ZONE_HUE_EQ:
                _fb_for_blend = _zone_hue_eq(fa_zone, _fb_for_blend)

        # §1.105: Cap blend weight for fg-overlap pixels with high lum diff.
        _mask_for_blend = mask_float
        if _FG_OVERLAP_BLEND_CAP > 0.0 and k not in seam_single_pose:
            _has_fg_a = fa_zone.max(axis=2) > 0
            _has_fg_b = _fb_for_blend.max(axis=2) > 0
            _both_fg = _has_fg_a & _has_fg_b
            if _both_fg.any():
                _lum_diff = np.abs(
                    fa_zone[..., 0].astype(np.float32) * 0.114
                    + fa_zone[..., 1].astype(np.float32) * 0.587
                    + fa_zone[..., 2].astype(np.float32) * 0.299
                    - (
                        _fb_for_blend[..., 0].astype(np.float32) * 0.114
                        + _fb_for_blend[..., 1].astype(np.float32) * 0.587
                        + _fb_for_blend[..., 2].astype(np.float32) * 0.299
                    )
                )
                _high_diff_fg = _both_fg & (_lum_diff > 10.0)
                if _high_diff_fg.any():
                    _mask_for_blend = mask_float.copy()
                    _mask_for_blend[_high_diff_fg] = np.minimum(
                        _mask_for_blend[_high_diff_fg], _FG_OVERLAP_BLEND_CAP
                    )
        blended = _laplacian_blend(
            fa_zone,
            _fb_for_blend,
            _mask_for_blend,
            alpha_schedule=_LAPLACIAN_ALPHA_SCHEDULE,
        )

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
            and _seam_fg_penetration(path_local, fa_zone, fb_zone)
            > _SEAM_FG_PENETRATION_MAX
        ):
            _fg_a = int((fa_zone.max(axis=2) > 0).sum())
            _fg_b = int((fb_zone.max(axis=2) > 0).sum())
            seam_single_pose[k] = fi_a if _fg_a >= _fg_b else fi_b

        # §1.112: Drift escalation — if the seam path has a sudden vertical
        # column-to-column jump, escalate to single-pose to avoid a kink artefact.
        if (
            _SEAM_DRIFT_THRESH > 0.0
            and k not in seam_single_pose
            and _seam_path_drift(path_local) > _SEAM_DRIFT_THRESH
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
                _adaptive_sp_soft_px(feather) if _ADAPTIVE_SP_SOFT else _sp_soft_px_base
            )
            # §1.124: Residual-based adaptive clipping of soft-edge width (S158).
            # High post-warp diff → narrow ramp (artefact risk); low diff → allow wider.
            _eff_sp_soft_px = _sp_soft_px
            if _ADAPTIVE_SP_SOFT:
                _post_d124 = seam_post_diffs.get(k, 22.0)
                if _post_d124 > 30.0:
                    _eff_sp_soft_px = _ADAPTIVE_SP_SOFT_MIN
                elif _post_d124 < 10.0:
                    _eff_sp_soft_px = _ADAPTIVE_SP_SOFT_MAX
            # §1.107: Adaptive seam band width based on zone height.
            _band_px_sp = (
                _adaptive_seam_band(
                    zone_h, _eff_sp_soft_px + 4, _ADAPTIVE_SEAM_BAND_MAX
                )
                if _ADAPTIVE_SEAM_BAND
                else _eff_sp_soft_px + 4
            )
            _oth_matched = _seam_color_match(
                dom_zone, oth_zone, path_local, _band_px_sp
            )
            # §1.88 — ECDF histogram matching after mean-shift for fuller distribution alignment.
            if _HIST_MATCH_SEAM:
                _oth_matched = _seam_band_hist_match(
                    dom_zone, _oth_matched, path_local, _band_px_sp
                )
            # §1.91 — iterative convergence: re-apply color match if residual delta > target.
            if _SEAM_LUM_CONVERGE:
                _oth_matched = _seam_lum_converge(
                    dom_zone,
                    _oth_matched,
                    path_local,
                    _band_px_sp,
                    target_delta=_SEAM_LUM_CONVERGE_TARGET,
                )
            _sp_zone = _single_pose_soft_edge(
                dom_zone, _oth_matched, path_local, fg_apply, _eff_sp_soft_px
            )
            _both_for_sp = dom_has & (oth_zone.max(axis=2) > 0) & fg_apply
            if _both_for_sp.any():
                result[y0_f:y1_f][_both_for_sp] = _sp_zone[_both_for_sp]

            print(
                f"[Stitch]   Single-pose B{k} (frame {_single}): "
                f"zone=[{y0_f}–{y1_f}] fg_px={int(fg_apply.sum())} "
                f"soft_px={_eff_sp_soft_px}"
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

    # §1.56: Post-composite chroma seam correction.
    if _SEAM_CHROMA_EQ and boundaries:
        result = _seam_chroma_equalize(result, boundaries)

    # §1.90 — post-seam bilateral smoothing pass in ±5px around each seam path.
    if _BILATERAL_SEAM and _precomp_paths:
        result = _bilateral_seam_smooth(result, _precomp_paths)

    # §1.106: Post-composite seam luminance step audit.
    _seam_lum_steps = _audit_seam_lum_steps(
        result, boundaries, band_px=5, warn_thresh=_POST_SEAM_WARN_THRESH
    )
    _max_step = max(_seam_lum_steps.values()) if _seam_lum_steps else 0.0
    if seam_meta_out is not None:
        seam_meta_out.update(
            {
                "seam_lum_steps": _seam_lum_steps,
                "max_seam_lum_step": _max_step,
            }
        )

    # §1.118: Post-composite seam sharpness guard.
    _seam_sharpness = _measure_seam_sharpness(result, boundaries, band_px=5)
    _max_blur_k = (
        min(_seam_sharpness, key=_seam_sharpness.get) if _seam_sharpness else None
    )
    _max_seam_blur = (
        _seam_sharpness.get(_max_blur_k, 0.0) if _max_blur_k is not None else 0.0
    )
    if _SEAM_SHARP_MIN > 0.0:
        for _sh_k, _sh_v in _seam_sharpness.items():
            if _sh_v < _SEAM_SHARP_MIN:
                print(
                    f"[Stitch] §1.118 seam-blur WARNING: B{_sh_k} lap_var={_sh_v:.2f} "
                    f"< {_SEAM_SHARP_MIN:.2f}"
                )
    if seam_meta_out is not None:
        seam_meta_out["seam_sharpness"] = _seam_sharpness
        seam_meta_out["max_seam_blur"] = _max_seam_blur

    # §1.120: Post-composite saturation step audit (S157).
    _seam_sat_steps = _audit_seam_sat_steps(
        result, boundaries, band_px=5, warn_thresh=_SEAM_SAT_WARN_THRESH
    )
    _max_sat_step = max(_seam_sat_steps.values()) if _seam_sat_steps else 0.0
    if seam_meta_out is not None:
        seam_meta_out["seam_sat_steps"] = _seam_sat_steps
        seam_meta_out["max_seam_sat_step"] = _max_sat_step

    # §2.4B: Seam overlay annotation — draw coloured diagnostic lines.
    if _SEAM_OVERLAY and len(boundaries) > 0:
        result = _annotate_seams(result, boundaries, seam_post_diffs, seam_single_pose)

    # §2.4A/C: Populate seam metadata dict for HITL checkpoint 4.6.
    if seam_meta_out is not None:
        seam_meta_out.update(
            {
                "boundaries": (
                    boundaries.tolist()
                    if hasattr(boundaries, "tolist")
                    else list(boundaries)
                ),
                "seam_post_diffs": dict(seam_post_diffs),
                "seam_single_pose": dict(seam_single_pose),
                "seam_crops": _extract_seam_crops(result, boundaries),
            }
        )

    return result


__all__ = [
    "_composite_foreground",
    "_compute_multiband_confidence",
    "_compute_ecc_confidence",
    "_MULTIBAND_CONF",
    "_MULTIBAND_CONF_BAND_PX",
    "_feather_gc_boundaries",
    "_GC_FEATHER_PX",
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
    "_seam_ncc_coherence",
    "_check_seam_ncc_gate",
    "_SEAM_NCC_GATE",
    "_seam_entropy_asymmetry",
    "_check_seam_entropy_gate",
    "_SEAM_ENTROPY_GATE",
    "_seam_max_col_luma_step",
    "_check_seam_max_col_gate",
    "_SEAM_MAX_COL_GATE",
    "_seam_saturation_jump",
    "_check_seam_saturation_gate",
    "_SEAM_SAT_GATE",
    "_seam_hue_shift",
    "_check_seam_hue_gate",
    "_SEAM_HUE_GATE",
    "_seam_sharpness_mismatch",
    "_check_seam_sharpness_gate",
    "_SEAM_SHARP_GATE",
    "_seam_grad_direction",
    "_check_seam_grad_direction_gate",
    "_SEAM_GRAD_DIR_GATE",
    "_seam_band_ssim",
    "_check_seam_ssim_gate",
    "_SEAM_SSIM_GATE",
    "_seam_freq_profile",
    "_check_seam_freq_gate",
    "_SEAM_FREQ_GATE",
    "_seam_noise_mismatch",
    "_check_seam_noise_gate",
    "_SEAM_NOISE_GATE",
    "_seam_rms_contrast_ratio",
    "_check_seam_rms_contrast_gate",
    "_SEAM_CONTRAST_GATE",
    "_seam_gate_vote_counts",
    "_check_seam_ensemble_gate",
    "_SEAM_ENSEMBLE_VOTES",
    "_adaptive_sp_threshold",
    "_fg_density_feather_cap",
    "_compute_seam_step_size",
    "_seam_lum_equalize",
    "_seam_chroma_equalize",
    "_adaptive_sp_soft_px",
    "_seam_corridor_exists",
    "_smooth_seam_path",
    "_clamp_seam_path",
    "_has_sufficient_bg",
    "_seam_path_std",
    "_zone_is_degenerate",
    "_zone_pair_ssim",
    "_ZONE_PRE_SSIM_THRESH",
    "_fg_zone_pose_gap",
    "_fg_fraction_in_zone",
    "_SEAM_ZONE_FG_MAX",
    "_enforce_feather_ratio",
    "_FEATHER_RATIO_MAX",
    "_seam_dp_bg_ratio",
    "_SEAM_DP_BG_MIN",
    "_FG_SEAM_EROSION_PX",
    "_seam_fg_penetration",
    "_seam_zone_texture_energy",
    "_fg_gradient_cost",
    "_build_fg_mesh_barrier",
    "_MESH_BARRIER",
    "_compute_initial_boundaries",
    "_annotate_seams",
    "_extract_seam_crops",
    "set_flow_hitl_callback",
    "_flow_hitl_callback",
    "_seam_band_hist_match",
    "_hf_column_cost",
    "_bilateral_seam_smooth",
    "_SEAM_ORDER_RESIDUAL",
    "_HIST_MATCH_SEAM",
    "_BILATERAL_SEAM",
    "_HF_SEAM_COST",
    "_seam_lum_converge",
    "_smooth_feather_array",
    "_SEAM_LUM_CONVERGE",
    "_SMOOTH_FEATHER",
    "_SP_THRESH_FG_SCALE",
    "_SP_THRESH_FG_FACTOR",
    "_SP_FG_FRAC_THRESH",
    "_zone_chroma_align",
    "_ZONE_CHROMA_ALIGN",
    "_zone_entropy",
    "_seam_zone_entropy_gap",
    "_ENTROPY_GAP_THRESH",
    "_smooth_gain_array",
    "_SMOOTH_GAIN",
    "_SMOOTH_GAIN_SIGMA",
    "_EXTRA_FG_DILATION",
    "_SEAM_PIN_ROWS",
    "_ZONE_MAD_THRESH",
    "_WARP_MOMENTUM_DAMP",
    "_WARP_MOMENTUM_FACTOR",
    "_SP_REF_PROX",
    "_zone_lum_norm",
    "_ZONE_LUM_NORM",
    "_FG_OVERLAP_BLEND_CAP",
    "_audit_seam_lum_steps",
    "_POST_SEAM_WARN_THRESH",
    "_adaptive_seam_band",
    "_ADAPTIVE_SEAM_BAND",
    "_ADAPTIVE_SEAM_BAND_MAX",
    "_LAPLACIAN_ALPHA_SCHEDULE",
    "_COST_MAP_NORM",
    "_COST_MAP_BLUR_SIGMA",
    "_zone_sat_norm",
    "_ZONE_SAT_NORM",
    "_seam_path_drift",
    "_SEAM_DRIFT_THRESH",
    "_COST_COL_SMOOTH_SIGMA",
    "_zone_contrast_eq",
    "_ZONE_CONTRAST_EQ",
    "_cap_feather_jumps",
    "_FEATHER_JUMP_MAX",
    "_ZONE_BG_FRAC_DIAG",
    "_zone_pair_ncc",
    "_ZONE_FAST_NCC_THRESH",
    "_measure_seam_sharpness",
    "_SEAM_SHARP_MIN",
    "_audit_seam_sat_steps",
    "_SEAM_SAT_WARN_THRESH",
    "_zone_hist_intersection",
    "_ZONE_HIST_THRESH",
    "_zone_width_cv",
    "_ZONE_WIDTH_CV_MAX",
    "_mean_path_cost",
    "_HIGH_PATH_COST_THRESH",
    "_SCATTER_COST",
    "_SCATTER_COST_WEIGHT",
    "_ADAPTIVE_SP_SOFT_MIN",
    "_ADAPTIVE_SP_SOFT_MAX",
    "_SEAM_TRANSITION_PEN",
    "_FG_MAJORITY_FLOOR",
    "_zone_hue_eq",
    "_ZONE_HUE_EQ",
    "_blocks_gain_compensate",
    "_BLOCKS_GAIN_COMP",
    "_blocks_lum_compensate",
    "_BLOCKS_LUM_COMP",
    "_equalize_warped_gains",
    "_GLOBAL_GAIN_COMP",
    "_DP_CANVAS_SEAM",
    "_canvas_dp_seam_composite",
]

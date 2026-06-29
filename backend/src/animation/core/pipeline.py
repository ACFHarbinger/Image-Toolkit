"""
AnimeStitchPipeline — top-level orchestrator.

Delegates each pipeline stage to its sibling module (matching, photometric,
masking, ECC, rendering, compositing, canvas, bundle adjustment).  Optionally
runs the MFSR super-resolution pass after stage 10 when ``mfsr_mode=True``.
"""

from __future__ import annotations

from backend.src.constants import LUMINANCE_WEIGHTS
from scipy.ndimage import gaussian_filter1d
from backend.src.animation.mfsr import run_mfsr
from backend.src.animation.mfsr import inpaint_gaps

from pathlib import Path

import gc
import os
import re
import warnings
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from backend.src.animation.alignment.bundle_adjust import _bundle_adjust_affine
from backend.src.animation.core.validation import (
    _validate_affines,
    _compute_adaptive_min_gap,
    _compute_adaptive_rot_scale,
)
from backend.src.animation.alignment.canvas import (
    _canvas_aspect_ratio,
    _canvas_gain_uniformity,
    _canvas_ghosting_siqe,
    _canvas_valid_area_ratio,
    _compute_adaptive_seam_smooth_px,
    _compute_canvas,
    _correct_seam_lum_steps,
    _crop_to_valid,
    _detect_scroll_axis,
    _chroma_seam_coherence,
    _horizontal_fft_banding,
    _load_frames,
    _normalise_widths,
    _panorama_stitch_fallback,
    _per_seam_lum_step_px,
    _scan_stitch_fallback,
    _seam_band_ncc_min,
    _seam_blue_shift_cv,
    _seam_red_shift_cv,
    _seam_green_shift_cv,
    _seam_boundary_sharpness_ratio,
    _seam_chroma_jump,
    _seam_chroma_step_cv,
    _seam_coherence_score,
    _seam_column_variance_cv,
    _seam_gradient_cv,
    _seam_edge_density,
    _seam_entropy_shift_cv,
    _seam_hue_shift_cv,
    _seam_local_contrast_cv,
    _seam_luma_step_cv,
    _seam_saturation_shift_cv,
    _seam_signed_step_cv,
    _seam_value_shift_cv,
    _seam_texture_ratio_cv,
    _seam_visibility_score,
    _smooth_seam_bands,
    _strip_contrast_cv,
    _strip_dark_pixel_fraction_cv,
    _strip_edge_density_cv,
    _strip_chroma_energy_cv,
    _strip_entropy_cv,
    _strip_luma_iqr_cv,
    _strip_luma_kurtosis_cv,
    _strip_gradient_cv,
    _strip_hist_intersection_min,
    _strip_hue_cv,
    _strip_luma_mad,
    _strip_median_luma_cv,
    _strip_luma_monotonicity,
    _strip_luma_p90p10_cv,
    _strip_luma_range,
    _strip_luma_skewness_cv,
    _strip_noise_cv,
    _strip_red_channel_cv,
    _strip_green_channel_cv,
    _strip_blue_channel_cv,
    _strip_sat_cv,
    _strip_seam_gradient_score,
    _strip_self_ssim,
    _strip_sharpness_cv,
    _strip_sobel_energy_cv,
    _telea_fill_gaps,
    find_optimal_sequence,
)
from backend.src.animation.rendering.compositing import (
    _check_seam_color_gate,
    _check_seam_entropy_gate,
    _check_seam_ensemble_gate,
    _check_seam_freq_gate,
    _check_seam_grad_direction_gate,
    _check_seam_hue_gate,
    _check_seam_max_col_gate,
    _check_seam_ncc_gate,
    _check_seam_noise_gate,
    _check_seam_rms_contrast_gate,
    _check_seam_saturation_gate,
    _check_seam_sharpness_gate,
    _check_seam_ssim_gate,
    _composite_foreground,
)
from backend.src.constants import (
    ADAPTIVE_MIN_DISP_FRAC,
    HIGH_CONF_EDGE_THRESH,
    LAPLACIAN_BANDS,
    MATCH_EDGE_CROP,
    MIN_EXPECTED_STEP,
    NEAR_DUP_LUMA_THRESH,
    SCALE_NORM_THRESH,
    SCENE_CHANGE_LUMA_THRESH,  # noqa: F401
    SCENE_CHANGE_BGR_THRESH,  # noqa: F401
    SEAM_COLOR_GATE_THRESH,  # noqa: F401
    STATIC_EDGE_MIN_DISP_PX,
    TRI_CONSISTENCY_PENALTY,
    SPATIAL_DEDUP_PX,
)
from backend.src.animation.alignment.ecc import _ecc_refine
from backend.src.animation.ingestion.bg_complete import complete_background, _propainter_complete_frames
from backend.src.animation.hitl.hitl_presets import load_hitl_preset, apply_hitl_preset
from backend.src.animation.ingestion.masking import (
    _cleanup_sam2_state,
    _compute_fg_masks,
    _compute_fg_masks_sam2,  # noqa: F401
    _compute_fg_masks_sam2_stateful,
)
from backend.src.animation.alignment.matching import (
    _match_pair,
    _pairwise_match,
    _phase_correlate,
    _sample_bg_points,
    _sample_bg_points_grid,  # noqa: F401
    _template_match,
)
from backend.src.animation.rendering.photometric import _apply_basic, _correct_vignetting
from backend.src.exceptions import (
    AlignmentFailedError,  # noqa: F401
    CanvasError,
    PipelineError,
)
from backend.src.animation.rendering.rendering import (
    _cluster_animation_phases,
    _render,
    _render_first,
    _render_laplacian,
    _render_median,
)

# §3.14 — Heavy model wrapper imports are deferred to first use.
# Each module-level try/except was loading kornia/transformers/torchvision at pytest
# collection time, contributing to the test-suite freeze (S140 root causes).
# We probe availability cheaply with importlib.util.find_spec(); the actual class
# is imported inside the method that instantiates it.
import importlib.util as _importlib_util_pipeline

import logging

logger = logging.getLogger(__name__)

os.environ.setdefault("PYTORCH_ALLOC_CONF", "expandable_segments:True")

try:
    import torch
except ImportError:
    torch = None  # type: ignore[assignment]

try:
    from PIL import Image
except ImportError:
    Image = None  # type: ignore[assignment]

try:
    from backend.src.animation import base as _batch
    _HAS_BATCH: bool = True
except ImportError:
    _batch = None  # type: ignore[assignment]
    _HAS_BATCH: bool = False

# BaSiCWrapper only uses cv2/numpy/torch — safe to import at module level.
try:
    from backend.src.models.wrappers.basic_wrapper import BaSiCWrapper

    _BASIC_OK = True
except ImportError:
    _BASIC_OK = False

# birefnet_wrapper → transformers; kornia wrappers → kornia+torchvision; EfficientLoFTR → transformers
_BIREFNET_OK: bool = _importlib_util_pipeline.find_spec("transformers") is not None
_LOFTR_OK: bool = _importlib_util_pipeline.find_spec("kornia") is not None
_ELOFTR_OK: bool = _importlib_util_pipeline.find_spec("transformers") is not None
_ALIKED_OK: bool = _importlib_util_pipeline.find_spec("kornia") is not None

# roma_wrapper: romatch library (not typically installed)
try:
    from backend.src.models.wrappers.roma_wrapper import RoMaWrapper

    _ROMA_OK = True
except ImportError:
    _ROMA_OK = False

try:
    from backend.src.animation.flow.flow_refine import _flow_refine, _load_sea_raft

    _SEA_RAFT_OK = True
except ImportError:
    _SEA_RAFT_OK = False

try:
    from backend.src.animation.rendering.super_res import upscale_anime, _UPSCALE_OK as _SR_OK
except ImportError:
    _SR_OK = False

try:
    from backend.src.animation.rendering.anim_fill import tooncrafter_ghost_fill

    _TOONCRAFTER_OK = True
except ImportError:
    _TOONCRAFTER_OK = False

try:
    from backend.src.animation.rendering.sr_stitcher import (
        seam_diffusion_fusion,
        border_diffusion_fill,
        _DIFFUSERS_OK as _SRSTITCHER_OK,
    )
except ImportError:
    _SRSTITCHER_OK = False

# §1.9C — When True the Stage-2 scans_frames snapshot is omitted; SCANS/PANORAMA
# fallbacks reload from image_paths on demand.  Saves ~87 MB for 14-frame 1080p.
_SCANS_RELOAD = os.environ.get("ASP_SCANS_RELOAD", "0") != "0"

# §1.13 — Scene-change luma gate.  Edges between frames whose mean-luma differs
# by more than this value are discarded before any geometric or BA processing.
# 0.0 disables the gate entirely (default, backward-compatible).
_SCENE_CHANGE_LUMA_THRESH: float = float(
    os.environ.get("ASP_SCENE_CHANGE_LUMA_THRESH", "0.0")
)
_SCENE_CHANGE_BGR_THRESH: float = float(
    os.environ.get("ASP_SCENE_CHANGE_BGR_THRESH", "0.0")
)

# §1.3C — Scale normalisation gate.  When inter-frame zoom produces a
# max/min scale ratio deviation >= this value, frames are resized to the
# reference (frame 0) scale before bundle adjustment.  0.0 disables entirely.
_SCALE_NORM_THRESH: float = float(os.environ.get("ASP_SCALE_NORM_THRESH", "0.0"))
_SEAM_COLOR_GATE_THRESH: float = float(os.environ.get("ASP_SEAM_COLOR_GATE", "0.0"))
_SEAM_COLOR_GATE_BGR: bool = os.environ.get("ASP_SEAM_COLOR_GATE_BGR", "0") != "0"
# §1.16 — MST weight gate (S60).
# After edge filtering, build the maximum spanning tree and compute the mean
# edge weight.  When < _MST_MIN_WEIGHT the overall match quality is too poor
# for reliable BA (graph dominated by TM/PC fallback edges at weight~0.15–0.3).
# Default 0.0 = disabled. Recommended: ASP_MST_MIN_WEIGHT=0.35.
_MST_MIN_WEIGHT: float = float(os.environ.get("ASP_MST_MIN_WEIGHT", "0.0"))
# §1.43 — Adjacent edge coverage ratio gate (S107).
# Counts what fraction of the N-1 adjacent frame pairs (|i−j|=1) have at least
# one edge in the filtered graph.  When most adjacent pairs are missing (only
# skip-edges connect them), BA has no local displacement constraints to work from
# and the solution is unreliable even if the graph is still connected.
# Distinct from §1.15 (connectivity via any path) and §1.16 (spanning tree weight):
# those can pass with a fully skip-edge graph; this fires specifically when
# adjacent-pair coverage is low.
# Default 0.0 = off.  Recommend ASP_ADJ_COVERAGE_MIN=0.60.
_ADJ_COVERAGE_MIN: float = float(os.environ.get("ASP_ADJ_COVERAGE_MIN", "0.0"))
# §1.47 — Adjacent displacement sign consistency gate (S111).
# Among adjacent edges (|i−j|=1), determines the dominant scroll direction
# (majority dy sign for vertical, majority dx sign for horizontal scroll).
# Edges whose dominant-axis displacement opposes the majority sign are
# "wrong-direction" matches — almost certainly incorrect matches where PC/TM
# latched onto a local peak that reversed the apparent motion direction.
# The minority-sign fraction (rate) is compared against a threshold; high
# rate → SCANS fallback before BA wastes time averaging contradictory edges.
# Default 0.0 = off.  Recommend ASP_SIGN_INCONSISTENCY_MAX=0.20.
_SIGN_INCONSISTENCY_MAX: float = float(
    os.environ.get("ASP_SIGN_INCONSISTENCY_MAX", "0.0")
)
# §1.48 — Adjacent displacement magnitude CV gate (S112).
# Among adjacent edges (|i−j|=1), measures the coefficient of variation
# (std / mean) of dominant-axis displacement magnitudes.  A high CV (e.g. >0.5)
# indicates that one or more adjacent edges report a displacement wildly
# different from the rest — e.g. PC locked onto the 2nd harmonic giving 2×
# the true step, or TM jumped to non-adjacent content.  Complementary to
# §1.47 (sign consistency): an outlier edge that agrees with the scroll
# direction but reports 10× the typical magnitude will pass §1.47 but fail
# §1.48.  Returns 0.0 for <2 adj edges (safe no-op).
# Default 0.0 = off.  Recommend ASP_ADJ_DISP_CV_MAX=0.5.
_ADJ_DISP_CV_MAX: float = float(os.environ.get("ASP_ADJ_DISP_CV_MAX", "0.0"))
# §1.49 — Adjacent edge minimum weight gate (S113).
# §1.16 checks the *mean* MST edge weight (average quality across the spanning
# tree) and §1.43 checks that every adjacent pair has *at least one* edge.
# §1.49 fills the gap between them: a pair may have an edge (passes §1.43) and
# the MST mean may look acceptable (passes §1.16), but if that specific edge
# has near-zero confidence (weight < floor) the compositing seam at that
# boundary will be garbage regardless of how cleanly BA solves the rest.
# Returns 1.0 when no adjacent edges exist (safe no-op).
# Default 0.0 = off.  Recommend ASP_ADJ_MIN_WEIGHT=0.20.
_ADJ_MIN_WEIGHT: float = float(os.environ.get("ASP_ADJ_MIN_WEIGHT", "0.0"))
# §1.50 — Bundle-adjustment max residual gate (S114).
# After Stage 7 (BA), each edge has an "observed" displacement (e["M"][:2,2])
# and a "predicted" displacement (affines[j][:2,2] − affines[i][:2,2]).
# The L2 distance between these is the per-edge BA residual.  For a healthy
# solve the median residual is ≤ 5–15 px; the GNC Cauchy/TLS weighting
# (§1.1C, §1.17) down-weights outlier edges but cannot suppress them when a
# single high-weight wrong match corrupts the median (Category B failure).
# Gate fires when the *maximum* per-edge residual exceeds a pixel threshold,
# indicating that at least one edge is wildly inconsistent with the solved
# frame placement.  Wired between Stage 7 and Stage 7b validation.
# Default 0.0 = off.  Recommend ASP_BA_RESIDUAL_MAX=200.0.
_BA_RESIDUAL_MAX: float = float(os.environ.get("ASP_BA_RESIDUAL_MAX", "0.0"))
# §1.51 — Minimum adjacent frame overlap gate (S115).
# §1.44 fires when adjacent frames are too FAR APART (gap > threshold, i.e.
# coverage hole).  §1.51 is the complementary gate: fires when adjacent frames
# are too CLOSE TOGETHER — the canvas-space overlap between frame i's trailing
# edge and frame i+1's leading edge is below a pixel floor, making the
# compositing seam zone too narrow for reliable DP cutting or feathering.
# An overlap of 1–19 px means there are ≤ 19 rows for the seam to traverse;
# the FEATHER_MIN=80 px feather clamp cannot be satisfied and the DP seam will
# almost certainly pass through character pixels.
# Returns the minimum overlap across all adjacent pairs (negative = gap).
# Default 0.0 = off.  Recommend ASP_MIN_ADJACENT_OVERLAP_PX=20.0.
_MIN_ADJACENT_OVERLAP_PX: float = float(
    os.environ.get("ASP_MIN_ADJACENT_OVERLAP_PX", "0.0")
)
# §1.52 — BA weighted mean residual gate (S116).
# §1.50 fires when the *maximum* per-edge residual exceeds a threshold —
# catching a single catastrophic outlier edge (Category B failure).
# §1.52 is the complementary gate: it fires when the *confidence-weighted
# mean* per-edge residual exceeds a lower threshold, catching systematic BA
# drift where all (or many) edges are moderately wrong (e.g. all 40–60 px
# off due to a biased global translation or a repeated texture that shifted
# the phase-correlation response surface).  This scenario passes §1.50
# (no single edge is >200 px off) but indicates the entire BA solution is
# unreliable.  Weighted mean = Σ(w_i × r_i) / Σ(w_i) where r_i is the L2
# residual for edge i and w_i is its match confidence weight.
# Default 0.0 = off.  Recommend ASP_BA_WMEAN_RESIDUAL_MAX=30.0.
_BA_WMEAN_RESIDUAL_MAX: float = float(
    os.environ.get("ASP_BA_WMEAN_RESIDUAL_MAX", "0.0")
)
# §1.53 — Canvas memory size gate (S117).
# After Stage 9 canvas geometry is determined, the estimated float32 array
# footprint (canvas_h × canvas_w × 3 channels × 4 bytes) is checked against
# a RAM budget.  CANVAS_MAX_DIM=32768 prevents individually extreme dimensions
# but does not bound the product: a 32768×1920 canvas costs ≈720 MB for the
# array alone — multiply by warped-frame buffers, masks, and intermediate
# compositing layers and a 4-GB system will OOM silently before hitting the
# compositing step.  This gate fires early and falls back to SCANS, whose
# simple scan-line pass has negligible peak memory.
# Returns the estimated footprint in megabytes (float32 RGB).
# Default 0.0 = off.  Recommend ASP_CANVAS_MAX_MEMORY_MB=2048.0 (2 GB).
_CANVAS_MAX_MEMORY_MB: float = float(os.environ.get("ASP_CANVAS_MAX_MEMORY_MB", "0.0"))
# §1.54 — Render luminance std gate (S118).
# After Stage 10 temporal render, measures the pixel luminance standard
# deviation within the *valid* (covered) canvas region.  The valid region
# is defined by valid_mask > 0.
# A std near zero means all covered pixels share the same luminance —
# indicating degenerate render output from BaSiC photometric over-correction
# (clamps all frames to the same mean luminance), silent warp failure (all
# frames mapped to an identical region), or hold-block leakage that the
# temporal median fused into one flat frame.  This failure mode produces no
# visible seams and passes §1.39 (coverage) and §1.24 (seam step), but the
# resulting panorama is a solid-colour slab.
# Luminance is approximated as the simple BGR mean per pixel (fast; avoids
# importing cv2.cvtColor in a pure-math helper).
# Default 0.0 = off.  Recommend ASP_RENDER_LUMA_STD_MIN=5.0.
_RENDER_LUMA_STD_MIN: float = float(os.environ.get("ASP_RENDER_LUMA_STD_MIN", "0.0"))
# §1.55 — BA affine rotation gate (S120).
# After Stage 7 bundle adjustment, each affine's rotation component is
# extracted via arctan2(M[1,0], M[0,0]).  For a pure scroll-capture sequence
# all affines should be near-identity rotations (angle ≈ 0°).  A large
# rotation in any affine means LoFTR or phase-correlation latched onto a
# rotationally-similar texture patch (repeated decorative border, mirrored
# panel art, or a landscape panel in a portrait scroll).  The resulting
# translation component is unreliable even if the BA residual is low, because
# the solver optimises displacement not orientation.
# Default 0.0 = off.  Recommend ASP_MAX_AFFINE_ROTATION_DEG=5.0.
_MAX_AFFINE_ROTATION_DEG: float = float(
    os.environ.get("ASP_MAX_AFFINE_ROTATION_DEG", "0.0")
)
# §3.16 — StabStitch++ simplified trajectory smoother (S121).
# After Stage 7 bundle adjustment, the tx/ty sequences may have per-frame
# jitter from phase-correlation noise even when pairwise translations are
# individually correct.  This happens on sequences with non-linear scroll
# (deceleration at a scene break) or combined tx+ty drift — the 4 confirmed
# genuine SCANS fallbacks (tests 54, 59, 73, 89) show this pattern.
# StabStitch++ (AAAI 2023) addresses this by fitting a bidirectional
# midplane-smoothed trajectory.  This module implements a lightweight
# version: scipy.ndimage.gaussian_filter1d applied independently to the
# 1D tx and ty sequences with mode='nearest' (boundary-correct, no edge
# attenuation).  Rotation and scale matrix components are copied unchanged.
# The smoother is activation-gated: it fires only when the IQR of
# adjacent-step residuals in the dominant axis exceeds ASP_TRAJ_SMOOTH_IQR
# pixels, leaving clean linear-scroll sequences completely untouched.
# Default sigma=0.0 = off.  Recommend ASP_TRAJ_SMOOTH_SIGMA=1.5.
_TRAJ_SMOOTH_SIGMA: float = float(os.environ.get("ASP_TRAJ_SMOOTH_SIGMA", "0.0"))
# Default 10.0 px.  Sequences with IQR ≤ threshold are not smoothed.
_TRAJ_SMOOTH_IQR_THRESH: float = float(
    os.environ.get("ASP_TRAJ_SMOOTH_IQR_THRESH", "10.0")
)
# §4.3 — Post-BA wave correction (S160).
# For vertical-scroll sequences, any systematic tx drift across frames is a
# "wave" (accumulated BA translation error along the cross-axis).  Fits a
# linear trend to tx (or ty for horizontal-scroll) values and subtracts it
# so the sequence midline is straightened.  Only fires when the range of tx/ty
# exceeds WAVE_CORRECT_MIN_TX_RANGE (avoids correcting already-clean sequences).
# Default "" = off.  Enable: ASP_WAVE_CORRECT=vertical or horizontal.
_WAVE_CORRECT: str = os.environ.get("ASP_WAVE_CORRECT", "")
# §4.7 — dy_cv pre-detection gate.
# Coefficient of variation of adjacent vertical frame steps.  When dy_cv ≥ threshold
# the pipeline immediately falls back to SCANS before expensive ARAP/BiRefNet work.
# 97-test benchmark: dy_cv ≥ 1.5 → catastrophic ASP failure (AlSSIM −22 to −37%,
# seam_vis 60–120 vs SCANS 2–3) while SCANS handles these sequences trivially.
# Default 1.5 (enabled). Set ASP_DY_CV_MAX=0 to disable.
_DY_CV_MAX: float = float(os.environ.get("ASP_DY_CV_MAX", "1.5"))
# §4.9 — Post-composite seam band smoothing half-width (px).  After Stage 11,
# a narrow vertical Gaussian blur is applied at each inter-frame seam row to
# reduce the hard luminance step measured by seam_visibility_score.
# Default 4 (enabled, S166). Set ASP_SEAM_SMOOTH_PX=0 to disable.
_SEAM_SMOOTH_PX: int = int(os.environ.get("ASP_SEAM_SMOOTH_PX", "4"))
# §5.1 — Post-composite seam luminance step correction (S166).
# 0 = disabled (default). Set ASP_SEAM_LUM_STEP=20 to enable 20px half-band.
_SEAM_LUM_STEP_PX: int = int(os.environ.get("ASP_SEAM_LUM_STEP", "0"))
# §5.3 — Canvas Gain Uniformity absolute gate (S167).
# After Stage 11 compositing, measures strip-level luminance banding.
# If canvas_gain_uniformity > _CGU_GATE_FLOOR → SCANS fallback.
# Default 0.20 (ASP test82=0.238 is clearly wrong). Set ASP_GATE_CGU_FLOOR=1.0 to disable.
_CGU_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_CGU_FLOOR", "0.20"))
# §5.19 — Pipeline Seam Coherence gate (S174).
_SC_GATE_ENABLED: bool = os.environ.get("ASP_GATE_SEAM_COH", "1") != "0"
_SC_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_SEAM_COH_FLOOR", "25.0"))
# §5.21 — Pipeline FFT Banding Gate (S174).
_FFT_BAND_GATE_ENABLED: bool = os.environ.get("ASP_GATE_FFT_BAND", "1") != "0"
_FFT_BAND_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_FFT_BAND_FLOOR", "0.35"))
# §5.23 — Pipeline Seam Visibility Gate (Stage 11.25).
# After Stage 11 compositing, measures worst-case adjacent-row luminance jump.
# If seam_vis > _SV_GATE_FLOOR → SCANS fallback. Set ASP_GATE_SEAM_VIS=0 to disable.
_SV_GATE_ENABLED: bool = os.environ.get("ASP_GATE_SEAM_VIS", "1") != "0"
_SV_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_SEAM_VIS_FLOOR", "30.0"))
# §5.24 — Pipeline Chroma Seam Coherence Gate (S174).
_CHROMA_COH_GATE_ENABLED: bool = os.environ.get("ASP_GATE_CHROMA_PIPE", "1") != "0"
_CHROMA_COH_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_CHROMA_PIPE_FLOOR", "20.0"))
# §5.9 — Auto-enable seam lum-step correction when canvas_gain_uniformity
# exceeds this threshold. Default 0.08 (mild banding). 0.0 = always on,
# 1.0 = effectively disabled (manual-only via ASP_SEAM_LUM_STEP).
_CGU_AUTO_LUM_STEP: float = float(os.environ.get("ASP_CGU_AUTO_LUM_STEP", "0.08"))
# §5.22 — Pipeline Strip Luma Monotonicity Gate (Stage 11.24).
# Measures fraction of adjacent strip pairs with luminance direction reversal.
# High = alternating bright/dark stripes. Falls back to SCANS if value > floor.
# Set ASP_GATE_MONO_PIPE=0 to disable; default floor 0.60.
_MONO_GATE_ENABLED: bool = os.environ.get("ASP_GATE_MONO_PIPE", "1") != "0"
_MONO_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_MONO_PIPE_FLOOR", "0.60"))
# §1.17 — Canvas span utilisation gate (S61).
# After bundle adjustment and canvas construction (Stage 9), the actual
# dominant-axis span of the solved affines is compared against the expected
# span (median adjacent step × (N−1)).  A ratio well below 1.0 means BA has
# collapsed frames into a compact cluster — valid-range checks (min_gap, ratio)
# passed but the assembled canvas is far too short.
# Default 0.0 = disabled. Recommended: ASP_CANVAS_SPAN_MIN_UTIL=0.3.
_CANVAS_SPAN_MIN_UTIL: float = float(os.environ.get("ASP_CANVAS_SPAN_MIN_UTIL", "0.0"))
# §1.24 — Post-composite seam-step gate (S68).
# After compositing, measures the max luminance step across all inter-strip seam
# boundaries.  If > threshold → SCANS fallback before the output is written.
# Complements Stage 11.2 (colour-similarity gate, pre-composite): this gate
# catches composites where photometric normalisation failed in the final output.
# Default 0.0 = disabled. Recommended: ASP_SEAM_STEP_GATE=25.0.
_SEAM_STEP_GATE: float = float(os.environ.get("ASP_SEAM_STEP_GATE", "0.0"))

# §1.66 — NCC structural coherence gate (S131).
# After compositing (Stage 11), measures normalised cross-correlation between
# the texture bands above and below each seam boundary.  NCC < thresh indicates
# that adjacent strips are structurally discontinuous (different line-art /
# different character pose) even when their luminance histograms are similar.
# Gate fires on the worst-NCC seam if any seam falls below thresh → SCANS
# fallback.  Complementary to Stage 11.2 (Bhattacharyya) and Stage 11.3 (luma
# step): Stage 11.4 detects structural pattern mismatch the other two miss.
# Default 0.0 = off.  Recommend ASP_SEAM_NCC_GATE=0.45.
_SEAM_NCC_GATE: float = float(os.environ.get("ASP_SEAM_NCC_GATE", "0.0"))

# §1.72 — Post-composite seam entropy asymmetry gate.
# Fires when the Shannon entropy difference between bands above/below a seam
# exceeds the threshold, indicating perceptible texture-density discontinuity.
# Default 0.0 = off.  Recommend ASP_SEAM_ENTROPY_GATE=1.5.
_SEAM_ENTROPY_GATE: float = float(os.environ.get("ASP_SEAM_ENTROPY_GATE", "0.0"))

# §1.76 — Post-composite per-column luma-step gate (S134).
# Unlike §1.24 which averages luma across the full band width, this gate reports
# the *worst single-column* luma step — catching localised hot-spots (a character
# outline or shadow edge crossing the seam at one column) that the mean smooths
# away.  Default 0.0 = off.  Recommend ASP_SEAM_MAX_COL_GATE=40.0.
_SEAM_MAX_COL_GATE: float = float(os.environ.get("ASP_SEAM_MAX_COL_GATE", "0.0"))

# §1.77 — Post-composite seam saturation jump gate (S135).
# Fires when the mean HSV saturation jump between bands above/below a seam
# exceeds the threshold, catching vibrancy discontinuities (muted bg vs vivid
# character colours) that luma and entropy gates miss.
# Default 0.0 = off.  Recommend ASP_SEAM_SAT_GATE=40.0.
_SEAM_SAT_GATE: float = float(os.environ.get("ASP_SEAM_SAT_GATE", "0.0"))

# §1.78 — Post-composite seam hue shift gate (S135).
# Fires when the circular mean hue distance between bands above/below a seam
# exceeds the threshold, catching colour-temperature discontinuities (warm vs
# cool strips) that saturation and luma gates miss.
# Default 0.0 = off.  Recommend ASP_SEAM_HUE_GATE=30.0.
_SEAM_HUE_GATE: float = float(os.environ.get("ASP_SEAM_HUE_GATE", "0.0"))

# §1.79 — Post-composite seam sharpness mismatch gate (S136).
# Fires when the |log₂(Laplacian-variance-top / Laplacian-variance-bottom)|
# exceeds the threshold — catching blur/sharpness discontinuities caused by
# different MPEG compression or upscaling applied to source frames.  Two strips
# can have identical colour profiles yet one looks noticeably blurrier; colour
# gates (luma, saturation, hue, entropy) are all blind to this.
# Default 0.0 = off.  Recommend ASP_SEAM_SHARP_GATE=3.0.
_SEAM_SHARP_GATE: float = float(os.environ.get("ASP_SEAM_SHARP_GATE", "0.0"))

# §1.80 — Seam gradient direction coherence gate (S137).
# Detects structural orientation discontinuities invisible to all colour-space
# gates: two strips can have identical photometric profiles yet opposing
# dominant edge directions (e.g., diagonal speed-lines above, horizontal
# horizon lines below).  Uses Sobel gx/gy → undirected orientation mod π,
# angle-doubling circular mean per band, circular distance in degrees [0, 90].
# Only strong-gradient pixels (mag > 10) contribute; flat regions ignored.
# Default 0.0 = off.  Recommend ASP_SEAM_GRAD_DIR_GATE=45.0.
_SEAM_GRAD_DIR_GATE: float = float(os.environ.get("ASP_SEAM_GRAD_DIR_GATE", "0.0"))

# §1.81 — Post-composite seam band SSIM gate (S138).
# Fires when ANY seam's band-SSIM falls *below* the threshold.  SSIM jointly
# captures luminance, contrast, and structure, making it a perceptual catch-all
# complement to the targeted §1.76–§1.80 single-dimension gates.  A score of
# 1.0 = bands are perceptually identical; < 0.85 = clear discontinuity.
# Default 0.0 = off.  Recommend ASP_SEAM_SSIM_GATE=0.85.
_SEAM_SSIM_GATE: float = float(os.environ.get("ASP_SEAM_SSIM_GATE", "0.0"))

# §1.82 — Post-composite seam spatial-frequency profile mismatch gate (S138).
# Fires when 1 − Pearson-r between the column-averaged FFT magnitude spectra
# of the bands above and below a seam exceeds the threshold.  Catches spectral
# content discontinuities (fine noise texture vs smooth gradient) invisible to
# all §1.76–§1.81 gates.  0=identical spectra; 1=orthogonal.
# Default 0.0 = off.  Recommend ASP_SEAM_FREQ_GATE=0.6.
_SEAM_FREQ_GATE: float = float(os.environ.get("ASP_SEAM_FREQ_GATE", "0.0"))

# §1.83 — Post-composite seam noise-level asymmetry gate (S139).
# Fires when |σ_top − σ_bot| / mean(σ) exceeds the threshold where σ is the
# per-strip Laplacian-std noise estimate (Immerkær 1996).  Catches codec or
# exposure bitrate discontinuities invisible to luma/chroma/spectral gates.
# Default 0.0 = off.  Recommend ASP_SEAM_NOISE_GATE=1.0.
_SEAM_NOISE_GATE: float = float(os.environ.get("ASP_SEAM_NOISE_GATE", "0.0"))

# §1.84 — Post-composite seam RMS contrast ratio gate (S139).
# Fires when max(c_top,c_bot)/min(c_top,c_bot) > threshold where c = std/mean
# (coefficient of variation).  Catches broad dynamic-range discontinuities
# distinct from §1.79 sharpness and §1.82 spectral profile.
# Default 0.0 = off.  Recommend ASP_SEAM_CONTRAST_GATE=4.0.
_SEAM_CONTRAST_GATE: float = float(os.environ.get("ASP_SEAM_CONTRAST_GATE", "0.0"))

# §1.85 — Post-composite multi-gate ensemble combiner (S139).
# Fires when the seam with the most gate-failure votes accumulates ≥ min_votes.
# Each gate threshold below is used as the per-gate activation criterion; a
# gate with threshold=0.0 contributes no votes.
# Default 0 = off.  Recommend ASP_SEAM_ENSEMBLE_VOTES=3.
_SEAM_ENSEMBLE_VOTES: int = int(os.environ.get("ASP_SEAM_ENSEMBLE_VOTES", "0"))

# §5.6 — Post-composite seam Gaussian blur (Stage 11.19).
# Applies a ±_SEAM_SMOOTH_PX Gaussian blur at each seam row after compositing.
# Default 4 px (§5.6, S168). Set ASP_SEAM_SMOOTH_PX=0 to disable.
_SEAM_SMOOTH_PX: int = int(os.environ.get("ASP_SEAM_SMOOTH_PX", "4"))
# §5.11 — Adaptive seam-smooth: widen/narrow based on seam_coherence.
# True by default when _SEAM_SMOOTH_PX > 0. Set ASP_SEAM_SMOOTH_ADAPTIVE=0 to disable.
_SEAM_SMOOTH_ADAPTIVE: bool = os.environ.get("ASP_SEAM_SMOOTH_ADAPTIVE", "1") != "0"
# §5.29 — Pipeline Ghosting SIQE Gate (Stage 11.28).
# Fires when FFT-autocorrelation ghost score > floor → SCANS fallback.
# Set ASP_GATE_GHOSTING_SIQE=0 to disable.
_SIQE_GATE_ENABLED: bool = os.environ.get("ASP_GATE_GHOSTING_SIQE", "1") != "0"
_SIQE_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_GHOSTING_SIQE_FLOOR", "30.0"))
# §5.31 — Pipeline Seam Band NCC Gate (Stage 11.29).
# Fires when minimum cross-boundary NCC < floor → SCANS fallback.
# Low NCC = structural discontinuity at seam boundary. Set ASP_GATE_SEAM_BAND_NCC=0 to disable.
_SEAM_BAND_NCC_GATE_ENABLED: bool = os.environ.get("ASP_GATE_SEAM_BAND_NCC", "1") != "0"
_SEAM_BAND_NCC_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_SEAM_BAND_NCC_FLOOR", "0.30"))
# §5.32 — Pipeline Strip Gradient CV Gate (Stage 11.30).
# Fires when per-strip Laplacian energy CV > floor → SCANS fallback.
# High CV = sharpness discontinuity across strips. Set ASP_GATE_STRIP_GRAD_CV=0 to disable.
_STRIP_GRAD_CV_GATE_ENABLED: bool = os.environ.get("ASP_GATE_STRIP_GRAD_CV", "1") != "0"
_STRIP_GRAD_CV_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_STRIP_GRAD_CV_FLOOR", "0.50"))
# §5.33 — Pipeline Seam Gradient Ratio Gate (Stage 11.31).
# Fires when max boundary/interior gradient ratio > floor → hard seam cuts visible.
# Set ASP_GATE_SEAM_GRAD_RATIO=0 to disable.
_SEAM_GRAD_RATIO_GATE_ENABLED: bool = os.environ.get("ASP_GATE_SEAM_GRAD_RATIO", "1") != "0"
_SEAM_GRAD_RATIO_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_SEAM_GRAD_RATIO_FLOOR", "3.0"))
# §5.34 — Pipeline Canvas Aspect-Ratio Gate (Stage 11.32).
# Fires when H/W ratio < floor → landscape canvas indicating wrong scroll axis.
# Set ASP_GATE_CANVAS_ASPECT=0 to disable.
_CANVAS_ASPECT_GATE_ENABLED: bool = os.environ.get("ASP_GATE_CANVAS_ASPECT", "1") != "0"
_CANVAS_ASPECT_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_CANVAS_ASPECT_FLOOR", "1.2"))
# §5.38 — Pipeline Strip Saturation CV Gate (Stage 11.34).
# Fires when CV of per-strip mean HSV saturation exceeds floor → SCANS fallback.
# High CV = seam-induced color saturation mismatches between strips.
_SAT_CV_GATE_ENABLED: bool = os.environ.get("ASP_GATE_SAT_CV", "1") != "0"
_SAT_CV_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_SAT_CV_FLOOR", "0.40"))
# §5.39 — Pipeline Canvas Valid-Area Ratio Gate (Stage 11.35).
# Fires when the fraction of non-black pixels is below floor → SCANS fallback.
# Low ratio = significant black borders / underfilled canvas = alignment failure.
_VALID_AREA_GATE_ENABLED: bool = os.environ.get("ASP_GATE_VALID_AREA", "1") != "0"
_VALID_AREA_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_VALID_AREA_FLOOR", "0.55"))

# §5.50 — Pipeline Strip Sharpness CV Gate (Stage 11.41).
# Fires when coefficient of variation of per-strip Laplacian variance > floor → SCANS.
# High CV = mixed-sharpness strips from mismatched frames or failed normalization.
_SHARPNESS_CV_GATE_ENABLED: bool = os.environ.get("ASP_GATE_SHARPNESS_CV", "1") != "0"
_SHARPNESS_CV_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_SHARPNESS_CV_FLOOR", "1.0"))
# §5.53 — Pipeline Strip Contrast CV Gate (Stage 11.42).
_CONTRAST_CV_GATE_ENABLED: bool = os.environ.get("ASP_GATE_CONTRAST_CV", "1") != "0"
_CONTRAST_CV_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_CONTRAST_CV_FLOOR", "1.5"))
# §5.54 — Pipeline Seam Chroma Jump Gate (Stage 11.43).
_CHROMA_JUMP_GATE_ENABLED: bool = os.environ.get("ASP_GATE_CHROMA_JUMP", "1") != "0"
_CHROMA_JUMP_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_CHROMA_JUMP_FLOOR", "15.0"))
# §5.57 — Pipeline Strip Noise CV Gate (Stage 11.44).
_NOISE_CV_GATE_ENABLED: bool = os.environ.get("ASP_GATE_NOISE_CV", "1") != "0"
_NOISE_CV_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_NOISE_CV_FLOOR", "1.2"))

# §1.67 — Frame canvas spread validation (S131).
# After phase correlation (Stage 5), checks whether the estimated camera
# translations span at least *min_spread_fraction* of the expected full-canvas
# range (median_step × (N-1)).  When selected frames cluster near one end of
# the scroll (e.g., the first 30% of the scene), the resulting panorama will
# be a narrow slice rather than the full scroll extent.  Fires before BA so
# the retry chain is not wasted on a frame set that cannot produce good coverage.
# Dominant axis: whichever of |Σty| / |Σtx| is larger.
# Default 0.0 = off.  Recommend ASP_CANVAS_SPREAD_MIN=0.5.
_CANVAS_SPREAD_MIN: float = float(os.environ.get("ASP_CANVAS_SPREAD_MIN", "0.0"))

# §1.29 — Static input detection gate (S73).
# Before Stage 1, check whether all consecutive input-frame thumbnail pairs have
# mean absolute difference (MAD) below a threshold.  When all pairs are below the
# floor the input is almost certainly a static image repeated N times — Phase
# Correlation will report near-zero displacement for every pair, producing a
# degenerate panorama.  Early exit: copy frame 0 directly to output_path.
# Default 0.0 = off.  Recommend 2.0 (2/255 ≈ 0.8% pixel noise tolerance).
_STATIC_INPUT_MAX_MAD: float = float(os.environ.get("ASP_STATIC_INPUT_MAX_MAD", "0.0"))
_USE_SAM2: bool = os.environ.get("ASP_USE_SAM2", "0") != "0"
_BG_COMPLETE: int = int(os.environ.get("ASP_BG_COMPLETE", "0"))
# §3.13 — ProPainter Stage 4.7 background completion.
# When enabled, runs ProPainter on all selected frames after BiRefNet masking
# and photometric normalisation (Stage 4.7) to replace foreground-masked pixels
# with temporally coherent background estimates before phase correlation (Stage 5)
# and temporal median render (Stage 10).  Eliminates ghost strips from rows where
# the character occupied >40% of pixels in every selected frame.
# Default OFF.  Enable: ASP_PROPAINTER=1.
_PROPAINTER: bool = os.environ.get("ASP_PROPAINTER", "0") != "0"
# §3.14B — Horizontal-strip compositing.
# When enabled and scroll_axis='horizontal', allows the pipeline to continue
# instead of falling back to SCANS.  _composite_foreground already handles
# horizontal scroll by returning the temporal median unchanged (the overlap
# zone per pixel is ≤2 frames, ghosting is minimal, and vertical seam cuts
# would be misaligned).  This flag simply suppresses the hard SCANS fallback.
# Default OFF.  Enable: ASP_HORIZONTAL_COMPOSITE=1.
_HORIZONTAL_COMPOSITE: bool = os.environ.get("ASP_HORIZONTAL_COMPOSITE", "0") != "0"
# §2.8 — HybridStitch export path.  Empty = disabled.
_HYBRID_EXPORT_PATH: str = os.environ.get("ASP_HYBRID_EXPORT_PATH", "")
# §5.1 — Seam luminance step correction half-band (px); 0 = disabled.
_SEAM_LUM_STEP_PX: int = int(os.environ.get("ASP_SEAM_LUM_STEP", "0"))
# §5.9 — CGU threshold to auto-enable seam lum-step correction; 1.0 = disabled.
_CGU_AUTO_LUM_STEP: float = float(os.environ.get("ASP_CGU_AUTO_LUM_STEP", "0.08"))
# §5.16 — Per-seam adaptive correction width. True=adapt width per seam; False=uniform.
_SEAM_LUM_STEP_ADAPTIVE: bool = os.environ.get("ASP_SEAM_LUM_STEP_ADAPTIVE", "1") != "0"
# §5.58 — Pipeline Seam Luma Step CV Gate (Stage 11.45).
_LUMA_STEP_CV_GATE_ENABLED: bool = os.environ.get("ASP_GATE_LUMA_STEP_CV", "1") != "0"
_LUMA_STEP_CV_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_LUMA_STEP_CV_FLOOR", "1.0"))
# §5.61 — Pipeline Strip Entropy CV Gate (Stage 11.46).
_ENTROPY_CV_GATE_ENABLED: bool = os.environ.get("ASP_GATE_ENTROPY_CV", "1") != "0"
_ENTROPY_CV_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_ENTROPY_CV_FLOOR", "0.5"))
# §5.62 — Pipeline Seam Chroma Step CV Gate (Stage 11.47).
_CHROMA_STEP_CV_GATE_ENABLED: bool = os.environ.get("ASP_GATE_CHROMA_STEP_CV", "1") != "0"
_CHROMA_STEP_CV_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_CHROMA_STEP_CV_FLOOR", "1.0"))
# §5.65 — Pipeline Strip Chroma Energy CV Gate (Stage 11.48).
_CHROMA_ENERGY_CV_GATE_ENABLED: bool = os.environ.get("ASP_GATE_CHROMA_ENERGY_CV", "1") != "0"
_CHROMA_ENERGY_CV_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_CHROMA_ENERGY_CV_FLOOR", "0.6"))
# §5.66 — Pipeline Seam Gradient CV Gate (Stage 11.49).
_SEAM_GRADIENT_CV_GATE_ENABLED: bool = os.environ.get("ASP_GATE_SEAM_GRADIENT_CV", "1") != "0"
_SEAM_GRADIENT_CV_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_SEAM_GRADIENT_CV_FLOOR", "1.0"))
# §5.69 — Pipeline Strip Luma IQR CV Gate (Stage 11.50).
_LUMA_IQR_CV_GATE_ENABLED: bool = os.environ.get("ASP_GATE_LUMA_IQR_CV", "1") != "0"
_LUMA_IQR_CV_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_LUMA_IQR_CV_FLOOR", "0.8"))
# §5.70 — Pipeline Seam Column Variance CV Gate (Stage 11.51).
_SEAM_COL_VAR_CV_GATE_ENABLED: bool = os.environ.get("ASP_GATE_SEAM_COL_VAR_CV", "1") != "0"
_SEAM_COL_VAR_CV_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_SEAM_COL_VAR_CV_FLOOR", "1.0"))
_LUMA_SKEW_CV_GATE_ENABLED: bool = os.environ.get("ASP_GATE_LUMA_SKEW_CV", "1") != "0"
_LUMA_SKEW_CV_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_LUMA_SKEW_CV_FLOOR", "1.5"))
_SEAM_SIGNED_STEP_CV_GATE_ENABLED: bool = os.environ.get("ASP_GATE_SEAM_SIGNED_STEP_CV", "1") != "0"
_SEAM_SIGNED_STEP_CV_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_SEAM_SIGNED_STEP_CV_FLOOR", "1.2"))
_LUMA_KURTOSIS_CV_GATE_ENABLED: bool = os.environ.get("ASP_GATE_LUMA_KURTOSIS_CV", "1") != "0"
_LUMA_KURTOSIS_CV_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_LUMA_KURTOSIS_CV_FLOOR", "1.5"))
_SEAM_TEXTURE_RATIO_CV_GATE_ENABLED: bool = os.environ.get("ASP_GATE_SEAM_TEXTURE_RATIO_CV", "1") != "0"
_SEAM_TEXTURE_RATIO_CV_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_SEAM_TEXTURE_RATIO_CV_FLOOR", "1.2"))
_EDGE_DENSITY_CV_GATE_ENABLED: bool = os.environ.get("ASP_GATE_EDGE_DENSITY_CV", "1") != "0"
_EDGE_DENSITY_CV_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_EDGE_DENSITY_CV_FLOOR", "1.2"))
_SEAM_LOCAL_CONTRAST_CV_GATE_ENABLED: bool = os.environ.get("ASP_GATE_SEAM_LOCAL_CONTRAST_CV", "1") != "0"
_SEAM_LOCAL_CONTRAST_CV_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_SEAM_LOCAL_CONTRAST_CV_FLOOR", "1.0"))
_LUMA_P90P10_CV_GATE_ENABLED: bool = os.environ.get("ASP_GATE_LUMA_P90P10_CV", "1") != "0"
_LUMA_P90P10_CV_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_LUMA_P90P10_CV_FLOOR", "0.8"))
_SEAM_HUE_SHIFT_CV_GATE_ENABLED: bool = os.environ.get("ASP_GATE_SEAM_HUE_SHIFT_CV", "1") != "0"
_SEAM_HUE_SHIFT_CV_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_SEAM_HUE_SHIFT_CV_FLOOR", "1.5"))
_DARK_PIXEL_FRAC_CV_GATE_ENABLED: bool = os.environ.get("ASP_GATE_DARK_PIXEL_FRAC_CV", "1") != "0"
_DARK_PIXEL_FRAC_CV_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_DARK_PIXEL_FRAC_CV_FLOOR", "1.5"))
_SEAM_SAT_SHIFT_CV_GATE_ENABLED: bool = os.environ.get("ASP_GATE_SEAM_SAT_SHIFT_CV", "1") != "0"
_SEAM_SAT_SHIFT_CV_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_SEAM_SAT_SHIFT_CV_FLOOR", "1.5"))
_SOBEL_ENERGY_CV_GATE_ENABLED: bool = os.environ.get("ASP_GATE_SOBEL_ENERGY_CV", "1") != "0"
_SOBEL_ENERGY_CV_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_SOBEL_ENERGY_CV_FLOOR", "1.2"))
_SEAM_VALUE_SHIFT_CV_GATE_ENABLED: bool = os.environ.get("ASP_GATE_SEAM_VALUE_SHIFT_CV", "1") != "0"
_SEAM_VALUE_SHIFT_CV_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_SEAM_VALUE_SHIFT_CV_FLOOR", "1.2"))
_MEDIAN_LUMA_CV_GATE_ENABLED: bool = os.environ.get("ASP_GATE_MEDIAN_LUMA_CV", "1") != "0"
_MEDIAN_LUMA_CV_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_MEDIAN_LUMA_CV_FLOOR", "0.5"))
_SEAM_ENTROPY_SHIFT_CV_GATE_ENABLED: bool = os.environ.get("ASP_GATE_SEAM_ENTROPY_SHIFT_CV", "1") != "0"
_SEAM_ENTROPY_SHIFT_CV_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_SEAM_ENTROPY_SHIFT_CV_FLOOR", "1.5"))
_RED_CHANNEL_CV_GATE_ENABLED: bool = os.environ.get("ASP_GATE_RED_CHANNEL_CV", "1") != "0"
_RED_CHANNEL_CV_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_RED_CHANNEL_CV_FLOOR", "0.6"))
_SEAM_BLUE_SHIFT_CV_GATE_ENABLED: bool = os.environ.get("ASP_GATE_SEAM_BLUE_SHIFT_CV", "1") != "0"
_SEAM_BLUE_SHIFT_CV_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_SEAM_BLUE_SHIFT_CV_FLOOR", "1.2"))
_GREEN_CHANNEL_CV_GATE_ENABLED: bool = os.environ.get("ASP_GATE_GREEN_CHANNEL_CV", "1") != "0"
_GREEN_CHANNEL_CV_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_GREEN_CHANNEL_CV_FLOOR", "0.5"))
_SEAM_RED_SHIFT_CV_GATE_ENABLED: bool = os.environ.get("ASP_GATE_SEAM_RED_SHIFT_CV", "1") != "0"
_SEAM_RED_SHIFT_CV_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_SEAM_RED_SHIFT_CV_FLOOR", "1.2"))
_BLUE_CHANNEL_CV_GATE_ENABLED: bool = os.environ.get("ASP_GATE_BLUE_CHANNEL_CV", "1") != "0"
_BLUE_CHANNEL_CV_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_BLUE_CHANNEL_CV_FLOOR", "0.6"))
_SEAM_GREEN_SHIFT_CV_GATE_ENABLED: bool = os.environ.get("ASP_GATE_SEAM_GREEN_SHIFT_CV", "1") != "0"
_SEAM_GREEN_SHIFT_CV_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_SEAM_GREEN_SHIFT_CV_FLOOR", "1.2"))
# §2.14 — Triangular consistency filter (S93).
# For every triangle (i→j, j→k, i→k) in the edge graph, compute the L2
# residual between the predicted displacement (sum of two sides) and the
# observed displacement (hypotenuse).  When the residual exceeds this
# threshold the weakest edge in the triangle is penalised (weight × 0.5).
# Default 0.0 = off.  Recommended: ASP_TRI_CONSISTENCY=80.0.
_TRI_CONSISTENCY_MAX_RESIDUAL: float = float(
    os.environ.get("ASP_TRI_CONSISTENCY", "0.0")
)
# §1.37 — Background pixel coverage fraction gate (S101).
# After Stage 4, compute the mean fraction of bg pixels across all masks.
# When below this value, BiRefNet has classified the scene as fg-dominant and
# the bg-based normalization (Stage 4.5), bg-masked phase correlation and
# ba-weight pipeline will all operate on insufficient bg signal.
# Default 0.0 = off.  Recommend ASP_MIN_BG_FRACTION=0.05.
_MIN_BG_FRACTION: float = float(os.environ.get("ASP_MIN_BG_FRACTION", "0.0"))

# §1.39 — Render canvas coverage fraction gate (S103).
# After Stage 10 temporal render, the valid_mask (non-zero = geometrically covered)
# tells us what fraction of canvas pixels are reached by at least one warped frame.
# When affines are badly wrong (all frames piled in a small overlap zone, or a very
# sparse canvas with huge untouched regions), this fraction can be very low while
# Stage 10.5 multi-frame row coverage still passes (a single dense clump satisfies
# the row check).  Gate fires before Stage 10.5 to catch total coverage failure first.
# Default 0.0 = off.  Recommend ASP_RENDER_MIN_COVERAGE=0.30.
_RENDER_MIN_COVERAGE: float = float(os.environ.get("ASP_RENDER_MIN_COVERAGE", "0.0"))

# §1.44 — Maximum adjacent frame gap gate (S108).
# After Stage 9 canvas construction, checks that no adjacent frame pair (i, i+1)
# has been placed so far apart that there is an uncovered canvas strip between them.
# For vertical scroll the gap = ty_{i+1} - (ty_i + H_i); for horizontal,
# tx_{i+1} - (tx_i + W_i).  A large positive gap means BA "stretched" those frames
# apart — the rendered canvas will have a black stripe there.  Complements §1.17
# (total span utilization) which catches global collapse, and §1.39 (render coverage)
# which fires after the expensive warp step; this gate is cheaper (pure affine math).
# Default 0.0 = off.  Recommend ASP_MAX_ADJACENT_GAP_PX=100.0.
_MAX_ADJACENT_GAP_PX: float = float(os.environ.get("ASP_MAX_ADJACENT_GAP_PX", "0.0"))

# §1.45 — Canvas width ratio gate (S109).
# After Stage 9 canvas construction, compares canvas_w to the median source-frame
# width.  For a vertical scroll the canvas should be ≈ 1× frame width; a ratio
# significantly above 1.0 means BA has introduced large horizontal offsets between
# frames (tx drift), producing an oversized canvas with mostly empty black columns.
# This is distinct from §3.14 (pure horizontal scroll, where ty_span≈0) because
# the sequence is still dominantly vertical (ty_span >> tx_span) while frames
# drift sideways — §3.14 does not fire; §1.45 catches the drift via canvas width.
# Default 0.0 = off.  Recommend ASP_MAX_CANVAS_WIDTH_RATIO=1.5.
_MAX_CANVAS_WIDTH_RATIO: float = float(
    os.environ.get("ASP_MAX_CANVAS_WIDTH_RATIO", "0.0")
)
# §1.62 — Canvas aspect-ratio sanity gate (S125).
# For a vertical-scroll sequence the canvas must be taller than it is wide
# (canvas_h > canvas_w).  If BA drift, diagonal scroll, or a misidentified scroll
# axis produces a canvas that is wider than it is tall (aspect < 1.0), the
# compositing step will produce a garbled landscape-orientation panorama instead
# of the expected portrait manga strip.  This gate catches that failure case
# before compositing allocates memory and wastes time on a doomed render.
# The check is only meaningful for vertical-scroll sequences (ty_span > tx_span);
# for horizontal scroll §3.14 fires first.  For mixed-scroll sequences the ratio
# may legitimately exceed 1.0, so a generous floor of 0.5 is recommended.
# Default 0.0 = off.  Recommend ASP_MIN_CANVAS_ASPECT=0.5.
_MIN_CANVAS_ASPECT: float = float(os.environ.get("ASP_MIN_CANVAS_ASPECT", "0.0"))

# §1.71 — Pre-composite background luminance spread gate.
# Fires when the range (max−min) of per-frame background median luma exceeds
# the threshold, indicating that sequential gain normalisation would need to
# apply extreme corrections (≥ 2× on some frames) → SCANS fallback.
# Default 0.0 = off.  Recommend ASP_BG_LUM_SPREAD_MAX=80.0.
_BG_LUM_SPREAD_MAX: float = float(os.environ.get("ASP_BG_LUM_SPREAD_MAX", "0.0"))

# §1.73 — Pre-composite per-frame gain monotonicity drift gate.
# Fires when the Kendall-τ correlation between frame order and per-frame
# background median luma exceeds the threshold in absolute value, indicating
# a systematic brightening or darkening staircase that gain normalisation
# cannot fully cancel (it corrects amplitude but not the monotonic sequence).
# Distinct from §1.71 (spread): a gradual 4-luma-unit/frame drift produces
# acceptable spread but a τ ≈ 0.95 slope that is perceptually objectionable.
# Default 0.0 = off.  Recommend ASP_BG_GAIN_MONOTONE_THRESH=0.85.
_BG_GAIN_MONOTONE_THRESH: float = float(
    os.environ.get("ASP_BG_GAIN_MONOTONE_THRESH", "0.0")
)

# §1.74 — Post-composite canvas fill ratio gate.
# Fires when the fraction of pixels with max(B,G,R) > fill_threshold is below
# the minimum, indicating that large canvas regions are empty (zero-initialized
# background never covered by any warped frame) → SCANS fallback.
# Default 0.0 = off.  Recommend ASP_CANVAS_FILL_MIN=0.60.
_CANVAS_FILL_MIN: float = float(os.environ.get("ASP_CANVAS_FILL_MIN", "0.0"))
_CANVAS_FILL_PIX_THRESH: int = int(os.environ.get("ASP_CANVAS_FILL_PIX_THRESH", "10"))

# §1.75 — Post-composite strip Laplacian variance ratio gate.
# Fires when the ratio of the most-detailed strip's Laplacian variance to the
# least-detailed strip's variance exceeds the threshold, indicating that one
# strip is dramatically more textured than its neighbours (e.g., one strip is
# pure flat-colour background while another is rich-detail scene).
# Default 0.0 = off.  Recommend ASP_STRIP_VARIANCE_RATIO_MAX=10.0.
_STRIP_VARIANCE_RATIO_MAX: float = float(
    os.environ.get("ASP_STRIP_VARIANCE_RATIO_MAX", "0.0")
)

# §1.77 — Post-composite canvas edge void rate gate.
# Fires when the fraction of outermost border pixels that are all-zero exceeds
# the threshold, indicating frames did not cover the canvas corners (registration
# failure or extreme parallax producing an under-filled canvas).
# Default 0.0 = off.  Recommend ASP_CANVAS_EDGE_VOID_MAX=0.4.
_CANVAS_EDGE_VOID_MAX: float = float(os.environ.get("ASP_CANVAS_EDGE_VOID_MAX", "0.0"))
_CANVAS_EDGE_BORDER_PX: int = int(os.environ.get("ASP_CANVAS_EDGE_BORDER_PX", "10"))

# §1.78 — Pre-composite background gain sign flip rate gate.
# Fires when adjacent-frame bg-luma direction changes sign more often than the
# threshold fraction of consecutive triples, indicating oscillating bg luma that
# gain normalisation will chase as noise rather than a real scene luminance drift.
# Default 0.0 = off.  Recommend ASP_GAIN_SIGN_FLIP_MAX=0.6.
_GAIN_SIGN_FLIP_MAX: float = float(os.environ.get("ASP_GAIN_SIGN_FLIP_MAX", "0.0"))

# §5.25 — Post-composite strip self-SSIM gate (Stage 11.27).
# Fires when the mean SSIM between adjacent horizontal strips of the composite
# canvas exceeds the floor, indicating an overly uniform/banded output (all strips
# look alike → frame registration failure or degenerate warp collapsed content).
# Gate fires on HIGH ssim (repetition artefact), unlike seam-band SSIM (§1.81)
# which fires on LOW ssim.  Default ON with floor=0.85.
_STRIP_SSIM_GATE_ENABLED: bool = os.environ.get("ASP_GATE_STRIP_SSIM", "1") != "0"
_STRIP_SSIM_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_STRIP_SSIM_FLOOR", "0.85"))

# §5.36 — Pipeline Strip Histogram Intersection Gate (Stage 11.33).
# Fires when minimum inter-strip histogram intersection < floor → SCANS fallback.
# Low intersection = color mismatch between adjacent strips. Set ASP_GATE_HIST_INTERSECT=0 to disable.
_HIST_INTERSECT_GATE_ENABLED: bool = os.environ.get("ASP_GATE_HIST_INTERSECT", "1") != "0"
_HIST_INTERSECT_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_HIST_INTERSECT_FLOOR", "0.35"))
# §5.41 — Pipeline Strip Hue CV Gate (Stage 11.36).
# Fires when CV of per-strip mean HSV hue exceeds floor → SCANS fallback.
# High CV = seam-induced hue shifts between strips.
_HUE_CV_GATE_ENABLED: bool = os.environ.get("ASP_GATE_HUE_CV", "1") != "0"
_HUE_CV_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_HUE_CV_FLOOR", "0.50"))

# §5.42 — Pipeline Seam Boundary Sharpness Ratio Gate (Stage 11.37).
# Fires when max seam-boundary Laplacian variance / interior variance > floor → SCANS fallback.
# High ratio = seam rows have unusually high sharpness relative to content = hard cut.
_SEAM_SHARP_RATIO_GATE_ENABLED: bool = os.environ.get("ASP_GATE_SEAM_SHARP_RATIO", "1") != "0"
_SEAM_SHARP_RATIO_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_SEAM_SHARP_RATIO_FLOOR", "4.0"))

# §5.45 — Pipeline Strip Luma Range Gate (Stage 11.38).
# Fires when absolute luma range across 8 strips > floor → SCANS fallback.
# High range = strip-level banding from failed brightness normalization.
_LUMA_RANGE_GATE_ENABLED: bool = os.environ.get("ASP_GATE_LUMA_RANGE", "1") != "0"
_LUMA_RANGE_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_LUMA_RANGE_FLOOR", "60.0"))

# §5.46 — Pipeline Seam Edge Density Gate (Stage 11.39).
# Fires when max Canny edge-pixel fraction in any strip > floor → SCANS fallback.
# High density = cluttered/artifacted strip or hard seam in dense-edge region.
_EDGE_DENSITY_GATE_ENABLED: bool = os.environ.get("ASP_GATE_EDGE_DENSITY", "1") != "0"
_EDGE_DENSITY_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_EDGE_DENSITY_FLOOR", "0.30"))

# §5.49 — Pipeline Strip Luma MAD Gate (Stage 11.40).
# Fires when mean absolute deviation of strip luma means from global mean > floor → SCANS.
# High MAD = strip-level banding (complements luma range which only captures extremes).
_LUMA_MAD_GATE_ENABLED: bool = os.environ.get("ASP_GATE_LUMA_MAD", "1") != "0"
_LUMA_MAD_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_LUMA_MAD_FLOOR", "20.0"))


def _compute_bg_lum_spread(
    frames: "List[np.ndarray]",
    bg_masks: "List[Optional[np.ndarray]]",
    min_bg_px: int = 200,
) -> float:
    """§1.71: Max-minus-min spread of per-frame background median luminance.

    For each frame, computes the median background luminance from the raw
    (non-warped) frame using the corresponding BiRefNet bg_mask.  Returns
    the range ``max(lums) − min(lums)`` across all frames that have
    sufficient background coverage.

    Parameters
    ----------
    frames:
        Raw BGR uint8 frames (not warped into canvas space).
    bg_masks:
        Per-frame background masks (uint8, non-zero = background).
        May contain ``None`` entries (masking disabled for that frame).
    min_bg_px:
        Minimum number of background pixels required to include a frame
        in the spread computation.  Default 200.

    Returns
    -------
    float
        Background luminance range in [0, 255].  Returns 0.0 when fewer
        than 2 frames have sufficient background coverage.
    """
    # relocated: from backend.src.constants import LUMINANCE_WEIGHTS

    lums: List[float] = []
    for frame, mask in zip(frames, bg_masks):
        if mask is None:
            bg_sel = np.ones(frame.shape[:2], dtype=bool)
        else:
            bg_sel = mask > 127
        bg_px = frame[bg_sel]
        if len(bg_px) < min_bg_px:
            continue
        lum = float(bg_px.astype(np.float32).dot(LUMINANCE_WEIGHTS).mean())
        lums.append(lum)
    if len(lums) < 2:
        return 0.0
    return max(lums) - min(lums)


def _compute_bg_lum_monotonicity(
    frames: "List[np.ndarray]",
    bg_masks: "List[Optional[np.ndarray]]",
    min_bg_px: int = 200,
) -> float:
    """§1.73: Kendall-τ correlation between frame order and bg luminance.

    Extracts the background median luminance for each frame (same method as
    :func:`_compute_bg_lum_spread`) and computes the absolute Kendall rank
    correlation ``|τ|`` between the frame index and the luma sequence.

    ``|τ| ≈ 1.0`` means the luma sequence is perfectly monotone — each
    successive frame is brighter (or darker) than the previous.  Even when the
    total spread is within :data:`_BG_LUM_SPREAD_MAX`, a monotone drift
    creates a visible "brightness staircase" across the composite that gain
    normalisation cannot fully suppress.

    Parameters
    ----------
    frames, bg_masks, min_bg_px:
        Same meaning as :func:`_compute_bg_lum_spread`.

    Returns
    -------
    float
        ``|τ|`` in [0, 1].  Returns 0.0 when fewer than 3 frames have
        sufficient background coverage (fewer than 3 points cannot form a
        meaningful monotone sequence).
    """
    # relocated: from backend.src.constants import LUMINANCE_WEIGHTS

    lums: List[float] = []
    for frame, mask in zip(frames, bg_masks):
        if mask is None:
            bg_sel = np.ones(frame.shape[:2], dtype=bool)
        else:
            bg_sel = mask > 127
        bg_px = frame[bg_sel]
        if len(bg_px) < min_bg_px:
            continue
        lums.append(float(bg_px.astype(np.float32).dot(LUMINANCE_WEIGHTS).mean()))

    n = len(lums)
    if n < 3:
        return 0.0
    concordant = discordant = 0
    for i in range(n - 1):
        for j in range(i + 1, n):
            diff = lums[j] - lums[i]
            if diff > 0:
                concordant += 1
            elif diff < 0:
                discordant += 1
    total_pairs = n * (n - 1) // 2
    return abs(concordant - discordant) / max(total_pairs, 1)


def _compute_canvas_fill_ratio(
    canvas: "np.ndarray",
    pix_thresh: int = 10,
) -> float:
    """§1.74: Fraction of canvas pixels with any channel above *pix_thresh*.

    The canvas is zero-initialised before compositing.  Pixels that remain
    zero after all warped frames are composited are empty regions — either
    geometric gaps between frames or areas never covered by any warp.
    Returns ``filled_pixels / total_pixels`` where a pixel is considered
    filled when ``max(B, G, R) > pix_thresh``.

    Parameters
    ----------
    canvas:
        BGR uint8 composite image of shape (H, W, 3).
    pix_thresh:
        Per-channel intensity floor; pixels at or below this value in all
        channels are treated as empty.  Default 10 avoids counting deep
        black content (e.g., night-sky backgrounds) as empty.

    Returns
    -------
    float
        Fill ratio in [0, 1].  Returns 1.0 for a zero-size canvas.
    """
    if canvas.size == 0:
        return 1.0
    total = canvas.shape[0] * canvas.shape[1]
    filled = int((canvas.max(axis=2) > pix_thresh).sum())
    return filled / total


def _compute_strip_variance_ratio(
    canvas: "np.ndarray",
    n_strips: int,
) -> float:
    """§1.75: Ratio of most- to least-textured strip Laplacian variance.

    Splits the composite into *n_strips* horizontal bands and computes the
    Laplacian variance (focus/sharpness proxy) for each.  Returns
    ``max_var / min_var``.  A high ratio indicates one strip is dramatically
    more textured than another — e.g., one strip contains flat-colour
    character body while the adjacent strip shows a detailed background
    scene — signalling a structural incompatibility that blend-only fixes
    cannot resolve.

    Parameters
    ----------
    canvas:
        BGR uint8 composite image.
    n_strips:
        Number of composited strips (= number of selected frames).

    Returns
    -------
    float
        Variance ratio ≥ 1.0.  Returns 1.0 when *n_strips* ≤ 1 or when
        any strip Laplacian variance is zero (uniform image).
    """
    if n_strips <= 1 or canvas.size == 0:
        return 1.0
    gray = cv2.cvtColor(canvas, cv2.COLOR_BGR2GRAY)
    H = gray.shape[0]
    variances: List[float] = []
    for k in range(n_strips):
        y0 = H * k // n_strips
        y1 = H * (k + 1) // n_strips
        strip = gray[y0:y1]
        if strip.size == 0:
            continue
        v = float(cv2.Laplacian(strip, cv2.CV_64F).var())
        variances.append(v)
    if len(variances) < 2 or min(variances) <= 0.0:
        return 1.0
    return max(variances) / min(variances)


def _compute_canvas_edge_void_rate(
    canvas: "np.ndarray",
    border_px: int = 10,
    pix_thresh: int = 8,
) -> float:
    """§1.77: Fraction of canvas border pixels with max channel ≤ pix_thresh (S134).

    Examines the outermost *border_px* rows and columns of the composite canvas
    (top, bottom, left, right bands).  Returns the fraction of these border pixels
    whose brightest channel is ≤ *pix_thresh* — i.e., effectively empty
    (zero-initialised canvas area never covered by any warped frame).

    A high void rate means frames did not reach the canvas corners, indicating a
    registration failure or extreme parallax.  Complementary to §1.74 (fill ratio
    which measures the *whole canvas*): §1.77 specifically flags border-region gaps
    that interior-heavy composites can hide.

    Parameters
    ----------
    canvas : BGR uint8 composite.
    border_px : Width of the border band to examine on each side.
    pix_thresh : Max-channel threshold below which a pixel is considered empty.

    Returns
    -------
    float
        Void fraction in [0, 1].  Returns 0.0 when the canvas is too small for
        a distinct border (H or W ≤ 2 × border_px).
    """
    H, W = canvas.shape[:2]
    if H < 2 * border_px or W < 2 * border_px:
        return 0.0
    top = canvas[:border_px, :, :].reshape(-1, 3)
    bottom = canvas[-border_px:, :, :].reshape(-1, 3)
    left = canvas[border_px:-border_px, :border_px, :].reshape(-1, 3)
    right = canvas[border_px:-border_px, -border_px:, :].reshape(-1, 3)
    border = np.concatenate([top, bottom, left, right], axis=0)
    void_count = int((border.max(axis=1) <= pix_thresh).sum())
    return void_count / len(border)


def _compute_gain_sign_flips(
    frames: "List[np.ndarray]",
    bg_masks: "List[Optional[np.ndarray]]",
    min_bg_px: int = 200,
) -> float:
    """§1.78: Fraction of consecutive frame triples with oscillating bg-luma direction (S134).

    Computes per-frame background median luminance (same sample as §1.71/§1.73).
    For each consecutive triple (i-1, i, i+1), records whether the luma direction
    flips sign (bright→dark→bright or dark→bright→dark).  Returns
    ``n_flips / (N_valid − 2)``.  A high flip rate means the bg-luma sequence
    oscillates — gain normalisation will amplify noise rather than correct a
    real scene-wide luminance drift.

    Parameters
    ----------
    frames : Raw BGR uint8 frames.
    bg_masks : Per-frame bg masks (uint8, non-zero = bg).  None = all-bg.
    min_bg_px : Minimum bg pixels required to include a frame.

    Returns
    -------
    float
        Flip rate in [0, 1].  Returns 0.0 when fewer than 3 valid frames.
    """
    # relocated: from backend.src.constants import LUMINANCE_WEIGHTS

    lums: "List[float]" = []
    for frame, mask in zip(frames, bg_masks):
        if mask is None:
            bg_sel = np.ones(frame.shape[:2], dtype=bool)
        else:
            bg_sel = mask > 127
        bg_px = frame[bg_sel]
        if len(bg_px) < min_bg_px:
            continue
        lums.append(float(bg_px.astype(np.float32).dot(LUMINANCE_WEIGHTS).mean()))
    if len(lums) < 3:
        return 0.0
    diffs = np.diff(lums)
    signs = np.sign(diffs)
    flips = int(
        np.sum((signs[:-1] != 0) & (signs[1:] != 0) & (signs[:-1] != signs[1:]))
    )
    return flips / (len(lums) - 2)


def _compute_bg_coverage_fraction(
    bg_masks: "List[Optional[np.ndarray]]",
) -> float:
    """§1.37: Mean fraction of bg pixels (mask > 127) across all valid masks.

    Returns 1.0 when *bg_masks* is empty or contains only None entries so that
    the gate does not fire when masking is disabled.
    """
    fractions: List[float] = []
    for mask in bg_masks:
        if mask is None:
            continue
        total = mask.size
        if total == 0:
            continue
        fractions.append(float((mask > 127).sum()) / total)
    if not fractions:
        return 1.0
    return float(np.mean(fractions))


def _compute_render_coverage(valid_mask: np.ndarray) -> float:
    """§1.39: Fraction of canvas pixels covered by at least one warped frame.

    *valid_mask* is the uint8 mask returned by ``_render`` (255 = covered by ≥1
    frame, 0 = no frame reaches this pixel).  Returns the fraction of non-zero
    pixels over the total canvas area.

    Returns 0.0 for an empty mask so the gate can fire; returns 1.0 when
    *valid_mask* is all-covered (normal healthy render).
    """
    total = valid_mask.size
    if total == 0:
        return 0.0
    return float((valid_mask > 0).sum()) / float(total)


def _measure_max_seam_step(
    canvas: np.ndarray,
    n_strips: int,
    band_px: int = 10,
    guard: int = 3,
) -> float:
    """§1.24: Measure the maximum luminance step across inter-strip seam boundaries.

    For each of the N-1 inter-strip boundaries (positioned at canvas_h * k // n_strips),
    samples mean greyscale luminance in *band_px* rows above and below (with *guard*
    rows excluded to avoid the seam artefact itself). Returns max(|above - below|)
    across all boundaries. Returns 0.0 when n_strips ≤ 1 or the canvas is too small.
    """
    H = canvas.shape[0]
    if n_strips <= 1 or H < 2 * (band_px + guard):
        return 0.0
    luma = cv2.cvtColor(canvas, cv2.COLOR_BGR2GRAY).astype(np.float32)
    max_step = 0.0
    for k in range(1, n_strips):
        by = H * k // n_strips
        a0 = max(0, by - band_px - guard)
        a1 = max(0, by - guard)
        b0 = min(H, by + guard)
        b1 = min(H, by + band_px + guard)
        if a1 <= a0 or b1 <= b0:
            continue
        above_mean = float(luma[a0:a1].mean())
        below_mean = float(luma[b0:b1].mean())
        max_step = max(max_step, abs(below_mean - above_mean))
    return max_step


def _detect_static_input(
    frames: List[np.ndarray],
    max_mad: float = 2.0,
    thumb_size: int = 64,
) -> bool:
    """§1.29: Return True when all consecutive frame pairs are near-identical.

    Resizes each frame to a *thumb_size* × *thumb_size* greyscale thumbnail and
    computes the mean absolute difference (MAD) between each adjacent pair.  When
    ALL pairs fall below *max_mad* (on the [0, 255] scale) the input is almost
    certainly a static image repeated N times — Phase Correlation will report
    near-zero displacement and the pipeline will produce a degenerate result.

    Parameters
    ----------
    frames:
        Input frames (BGR, uint8).  Fewer than 2 frames always returns False.
    max_mad:
        MAD ceiling (luma units, 0–255) below which a pair is considered static.
        2.0 ≈ 0.8 % pixel noise, sufficient to tolerate MPEG compression noise
        while catching genuine static sequences.
    thumb_size:
        Side length of the greyscale thumbnail used for comparison.

    Returns
    -------
    bool
        True if the entire input is static (all pairs below *max_mad*).
    """
    if len(frames) < 2:
        return False
    prev_thumb: Optional[np.ndarray] = None
    for frame in frames:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        thumb = cv2.resize(gray, (thumb_size, thumb_size), interpolation=cv2.INTER_AREA)
        if prev_thumb is not None:
            mad = float(
                np.abs(thumb.astype(np.float32) - prev_thumb.astype(np.float32)).mean()
            )
            if mad > max_mad:
                return False
        prev_thumb = thumb
    return True


def _reject_scene_change_edges(
    edges: List[Dict],
    frames: List[np.ndarray],
    max_luma_diff: float = 60.0,
    use_bgr: bool = False,
) -> List[Dict]:
    """§1.13 / §1.13B: Discard edges where frames differ by > *max_luma_diff*.

    When *use_bgr* is False (default, §1.13A): comparison uses mean grayscale
    luminance — catches overall brightness discontinuities.

    When *use_bgr* is True (§1.13B): comparison uses the per-channel (B, G, R)
    thumbnail means; the maximum channel delta is compared against the threshold.
    This catches chroma-shifted scene changes (e.g., warm orange sunset vs cold
    blue interior) that have similar grayscale luma but completely different colour
    distributions.

    Comparison is done on a 64×64 thumbnail for speed.  The gate is disabled
    when *max_luma_diff* ≤ 0 or when *frames* is empty.
    """
    if max_luma_diff <= 0 or not frames:
        return edges

    _THUMB = 64

    def _channel_means(f: np.ndarray) -> np.ndarray:
        t = cv2.resize(f, (_THUMB, _THUMB), interpolation=cv2.INTER_AREA)
        return t.reshape(-1, 3).mean(axis=0).astype(np.float32)  # [B, G, R]

    def _mean_luma(f: np.ndarray) -> float:
        means = _channel_means(f)
        return float(np.dot(means, [0.114, 0.587, 0.299]))

    kept: List[Dict] = []
    for e in edges:
        fi, fj = e["i"], e["j"]
        if fi < len(frames) and fj < len(frames):
            if use_bgr:
                means_i = _channel_means(frames[fi])
                means_j = _channel_means(frames[fj])
                diff = float(np.abs(means_i - means_j).max())
                label = "bgr_max_diff"
            else:
                diff = abs(_mean_luma(frames[fi]) - _mean_luma(frames[fj]))
                label = "luma_diff"
            if diff > max_luma_diff:
                logger.debug(
                    "[Stitch]   Scene-change gate: edge %d→%d rejected "
                    "(%s=%.1f > %.1f)",
                    fi,
                    fj,
                    label,
                    diff,
                    max_luma_diff,
                )
                continue
        kept.append(e)
    return kept


def _normalize_frame_scales(
    frames: List[np.ndarray],
    edges: List[Dict],
    scale_thresh: float = SCALE_NORM_THRESH,
) -> Tuple[List[np.ndarray], List[Dict]]:
    """§1.3C: Scale normalisation before bundle adjustment.

    When the matched affines reveal inter-frame zoom (camera zooming in or
    out during the pan), resizing all frames to the *reference* (frame 0)
    scale converts the zoom-pan problem into a pure-translation problem that
    the existing BA pipeline handles correctly.

    **Algorithm**
    1. Extract per-edge scale factor ``s_ij = sqrt(a² + b²)`` from the 2×2
       rotation-scale block of the matched affine M.
    2. Build a maximum-weight spanning tree (greedy/Kruskal) and BFS-propagate
       relative scales to compute an *absolute* per-frame scale ``scale[i]``
       (frame 0 is the reference: ``scale[0] = 1.0``).
    3. If ``max(scale) / min(scale) − 1 < scale_thresh`` the deviation is
       negligible — return the originals unchanged (no-op).
    4. Resize each frame *i* by the factor ``1 / scale[i]`` using Lanczos-4
       interpolation.
    5. Update every edge affine: reset the 2×2 rotation-scale block to identity
       and divide the translation components by ``scale[i]`` (the reference-space
       displacement is ``t / scale_i``).

    Returns the normalised frames and updated edges.  Falls back to the
    originals when the spanning tree cannot reach every frame (disconnected
    graph) or ``scale_thresh ≤ 0`` (disabled).

    Parameters
    ----------
    frames : frames in temporal order (as loaded after Stage 2).
    edges : matched edge dicts with keys ``"i"``, ``"j"``, ``"M"``.
    scale_thresh : minimum scale ratio deviation to trigger normalisation.
                  Default ``SCALE_NORM_THRESH=0.05``.  Set
                  ``ASP_SCALE_NORM_THRESH=0.05`` in the environment to
                  enable.
    """
    N = len(frames)
    if scale_thresh <= 0.0 or N < 2 or not edges:
        return frames, edges

    # ── Step 1: spanning tree (greedy, highest-weight-first) ─────────────────
    sorted_edges = sorted(
        edges, key=lambda e: float(e.get("weight", 1.0)), reverse=True
    )

    parent: List[int] = list(range(N))

    def _find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    adj: Dict[int, List[Tuple[int, float]]] = {f: [] for f in range(N)}
    n_tree = 0
    for e in sorted_edges:
        ei, ej = int(e["i"]), int(e["j"])
        if not (0 <= ei < N and 0 <= ej < N):
            continue
        pi, pj = _find(ei), _find(ej)
        if pi != pj:
            parent[pi] = pj
            M = e["M"]
            a, b = float(M[0, 0]), float(M[0, 1])
            s_ij = float(np.sqrt(a * a + b * b))
            s_ij = max(s_ij, 1e-6)
            adj[ei].append((ej, s_ij))
            adj[ej].append((ei, 1.0 / s_ij))
            n_tree += 1
        if n_tree == N - 1:
            break

    # ── Step 2: BFS to propagate absolute scale factors ───────────────────────
    scale: List[Optional[float]] = [None] * N
    scale[0] = 1.0
    queue: List[int] = [0]
    visited = [False] * N
    visited[0] = True
    head = 0
    while head < len(queue):
        curr = queue[head]
        head += 1
        for nbr, s in adj[curr]:
            if not visited[nbr]:
                visited[nbr] = True
                scale[nbr] = scale[curr] * s  # type: ignore[operator]
                queue.append(nbr)

    if any(s is None for s in scale):
        return frames, edges  # disconnected graph

    scale_vals = [float(s) for s in scale]
    s_min = min(scale_vals)
    s_max = max(scale_vals)
    if s_min < 1e-9 or (s_max / s_min - 1.0) < scale_thresh:
        return frames, edges  # deviation below threshold

    # ── Step 3: resize frames ─────────────────────────────────────────────────
    ref_scale = scale_vals[0]  # 1.0
    new_frames: List[np.ndarray] = []
    for i, f in enumerate(frames):
        s_i = scale_vals[i]
        if abs(s_i - ref_scale) < 1e-4:
            new_frames.append(f)
        else:
            factor = ref_scale / s_i
            h, w = f.shape[:2]
            nw = max(1, int(round(w * factor)))
            nh = max(1, int(round(h * factor)))
            new_frames.append(cv2.resize(f, (nw, nh), interpolation=cv2.INTER_LANCZOS4))

    # ── Step 4: update edge affines (reset scale, rescale translation) ────────
    new_edges: List[Dict] = []
    for e in edges:
        ei = int(e["i"])
        if not (0 <= ei < N):
            new_edges.append(e)
            continue
        s_i = scale_vals[ei]
        M = np.array(e["M"], dtype=np.float32)
        tx, ty = float(M[0, 2]), float(M[1, 2])
        M[0, 0] = 1.0
        M[0, 1] = 0.0
        M[0, 2] = tx / s_i
        M[1, 0] = 0.0
        M[1, 1] = 1.0
        M[1, 2] = ty / s_i
        new_e = dict(e)
        new_e["M"] = M
        new_edges.append(new_e)

    logger.debug(
        "[Stitch] §1.3C: scale normalised %d frames (scale range %.3f–%.3f → 1.0)",
        N,
        s_min,
        s_max,
    )
    return new_frames, new_edges


def _reject_static_edges(
    edges: List[Dict],
    min_disp_px: float = STATIC_EDGE_MIN_DISP_PX,
) -> List[Dict]:
    """§1.2A — Drop edges where |dx| < min_disp_px AND |dy| < min_disp_px.

    Rejects near-zero-2D-displacement matches for ALL edges (adjacent and
    skip-frame).  When such edges survive into bundle adjustment they anchor
    two frames at essentially the same canvas position, corrupting the global
    translation estimate for the rest of the sequence.

    A match is kept if EITHER axis displacement meets or exceeds the threshold,
    so valid diagonal-scroll edges (large |dx|, small |dy|) are preserved.
    """
    return [
        e
        for e in edges
        if abs(float(e["M"][0, 2])) >= min_disp_px
        or abs(float(e["M"][1, 2])) >= min_disp_px
    ]


def _compute_adaptive_min_disp(edges: List[Dict]) -> float:
    """§1.2C — Content-adaptive minimum displacement threshold.

    Estimates the expected inter-frame step from the median of adjacent-edge
    displacements on the dominant scroll axis and returns
    ``max(STATIC_EDGE_MIN_DISP_PX, ADAPTIVE_MIN_DISP_FRAC * expected_step)``.

    For typical scroll sequences the floor dominates (step ≤ 500 px → 10% ≤
    50 px).  For high-resolution or fast-scroll content the adaptive value
    exceeds the floor and provides proportionally stronger rejection (e.g.,
    1 000 px/frame → threshold 100 px instead of 50 px).
    """
    adj_edges = [e for e in edges if e["j"] == e["i"] + 1]
    if not adj_edges:
        return float(STATIC_EDGE_MIN_DISP_PX)

    adx = np.array([abs(float(e["M"][0, 2])) for e in adj_edges])
    ady = np.array([abs(float(e["M"][1, 2])) for e in adj_edges])
    disps = adx if float(np.median(adx)) >= float(np.median(ady)) else ady

    expected_step = float(np.median(disps))
    return max(float(STATIC_EDGE_MIN_DISP_PX), ADAPTIVE_MIN_DISP_FRAC * expected_step)


def _filter_high_conf_edges(
    edges: List[Dict],
    min_weight: float = HIGH_CONF_EDGE_THRESH,
) -> List[Dict]:
    """§2.9C — Keep only edges whose match weight meets the high-confidence floor.

    LoFTR edges typically have ``weight`` in [0.7, 0.95]; template-match and
    phase-correlation fallbacks land in [0.15, 0.55].  When bundle adjustment
    produces a bad ratio (one outlier edge pulling frames together), filtering
    to high-confidence edges removes the low-quality fallback edges that are
    most likely to be wrong.

    Used as a pre-check before the existing Retry-1 (adjacent-only) path: if
    at least ``N-1`` high-confidence edges survive, re-solve the bundle.  If
    fewer survive, fall through to Retry 1 unchanged — no information is lost.
    """
    return [e for e in edges if float(e.get("weight", 0.0)) >= min_weight]


def _triangular_consistency_filter(
    edges: List[Dict],
    max_residual_px: float,
) -> List[Dict]:
    """§2.14 — Penalise the weakest edge in every inconsistent triangle.

    The existing geometric consistency filter (inside ``_filter_edges``) only
    tests **skip** edges against the sum of their adjacent chain.  When an
    **adjacent** edge (i→i+1) is wrong the skip edges it anchors are dropped
    even though they might be correct — the wrong adjacent edge is never
    questioned.

    This filter iterates over all triangles (i→j, j→k, i→k) present in the
    edge graph, computes the L2 residual between the predicted hypotenuse
    displacement (sum of two shorter legs) and the observed displacement
    (hypotenuse edge), and halves the *weight* of the weakest edge whenever the
    residual exceeds *max_residual_px*.

    Weight halving (not dropping) is intentional: bundle adjustment should still
    receive the edge; it is just trusted less.  Systematic triangles where all
    three edges are consistent gain no penalty.

    Parameters
    ----------
    edges : list of edge dicts (keys: ``"i"``, ``"j"``, ``"M"``, ``"weight"``).
    max_residual_px : L2 residual floor; triangles below are ignored.
    """
    if max_residual_px <= 0.0 or len(edges) < 3:
        return edges

    # Build quick lookup: (i, j) → index in edges list (j > i always)
    edge_map: Dict[Tuple[int, int], int] = {}
    for idx, e in enumerate(edges):
        ei, ej = int(e["i"]), int(e["j"])
        edge_map[(ei, ej)] = idx

    # Collect all unique frame indices
    frame_ids = sorted({int(e["i"]) for e in edges} | {int(e["j"]) for e in edges})

    # Accumulate penalty multipliers; each edge starts at 1.0.
    # Multiple inconsistent triangles can each contribute a 0.5× factor.
    penalty: Dict[int, float] = {}  # edge index → accumulated multiplier

    def _get_tx(e: Dict) -> Tuple[float, float]:
        return float(e["M"][0, 2]), float(e["M"][1, 2])

    for a_idx, fi in enumerate(frame_ids):
        for fj in frame_ids[a_idx + 1 :]:
            for fk in frame_ids:
                if fk <= fj:
                    continue
                # Triangle vertices: fi → fj, fj → fk, fi → fk
                ij = (fi, fj)
                jk = (fj, fk)
                ik = (fi, fk)
                if ij not in edge_map or jk not in edge_map or ik not in edge_map:
                    continue
                idx_ij = edge_map[ij]
                idx_jk = edge_map[jk]
                idx_ik = edge_map[ik]
                e_ij = edges[idx_ij]
                e_jk = edges[idx_jk]
                e_ik = edges[idx_ik]
                tx_ij, ty_ij = _get_tx(e_ij)
                tx_jk, ty_jk = _get_tx(e_jk)
                tx_ik, ty_ik = _get_tx(e_ik)
                # Predicted hypotenuse from the two shorter legs
                pred_x = tx_ij + tx_jk
                pred_y = ty_ij + ty_jk
                residual = float(np.sqrt((tx_ik - pred_x) ** 2 + (ty_ik - pred_y) ** 2))
                if residual <= max_residual_px:
                    continue
                # Penalise weakest edge
                weights = [
                    float(e_ij.get("weight", 0.0)),
                    float(e_jk.get("weight", 0.0)),
                    float(e_ik.get("weight", 0.0)),
                ]
                weakest_local = int(np.argmin(weights))
                weakest_idx = [idx_ij, idx_jk, idx_ik][weakest_local]
                penalty[weakest_idx] = (
                    penalty.get(weakest_idx, 1.0) * TRI_CONSISTENCY_PENALTY
                )
                logger.debug(
                    "[Stitch]   §2.14 Triangle (%d→%d, %d→%d, %d→%d) residual=%.1f px"
                    " — penalised edge %d→%d (weight %.3f → %.3f)",
                    fi,
                    fj,
                    fj,
                    fk,
                    fi,
                    fk,
                    residual,
                    int(edges[weakest_idx]["i"]),
                    int(edges[weakest_idx]["j"]),
                    weights[weakest_local],
                    weights[weakest_local] * TRI_CONSISTENCY_PENALTY,
                )

    if not penalty:
        return edges

    result = [dict(e) for e in edges]
    for edge_idx, mult in penalty.items():
        result[edge_idx]["weight"] = float(result[edge_idx].get("weight", 0.0)) * mult
    return result


def _check_edge_graph_connectivity(
    edges: List[Dict],
    n_frames: int,
) -> bool:
    """§1.15: Return True iff all frames 0..n_frames-1 are in one connected component.

    Uses iterative path-compression Union-Find (same algorithm as §1.1B spanning
    tree) to check graph connectivity after all edge filters have run.  A
    disconnected graph fed into bundle adjustment assigns wrong translations to
    isolated frames — catching this before BA allows an immediate fallback rather
    than a corrupt solve followed by a downstream validation failure.

    Trivially returns True when *n_frames* ≤ 1 (nothing to connect) or when
    *n_frames* − 1 edges already span all nodes (lower bound for connectivity).
    """
    if n_frames <= 1:
        return True

    parent = list(range(n_frames))

    def _find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for e in edges:
        ei, ej = int(e.get("i", -1)), int(e.get("j", -1))
        if not (0 <= ei < n_frames and 0 <= ej < n_frames):
            continue
        pi, pj = _find(ei), _find(ej)
        if pi != pj:
            parent[pi] = pj

    root = _find(0)
    return all(_find(f) == root for f in range(n_frames))


def _compute_mst_weight(
    edges: List[Dict],
    n_frames: int,
) -> float:
    """§1.16: Mean edge weight of the maximum spanning tree.

    Builds the max-weight spanning tree (Kruskal greedy, highest-weight-first)
    using iterative path-compression Union-Find — the same algorithm as §1.1B.
    Returns ``total_weight / (N-1)`` where N-1 is the number of spanning-tree
    edges needed to connect all frames.

    A high mean MST weight (≥ 0.6) indicates the graph is well-anchored by
    reliable LoFTR matches.  A low mean MST weight (< 0.35) means the spanning
    tree is forced to use TM/PC fallback edges (weight~0.15–0.3) — BA will
    likely produce bad affines for those frames.

    Returns 0.0 when ``n_frames ≤ 1`` or there are no edges.  Returns the
    weight of a single edge divided by ``max(1, n_frames-1)`` when only one
    edge exists.
    """
    if n_frames <= 1 or not edges:
        return 0.0

    sorted_edges = sorted(
        edges, key=lambda e: float(e.get("weight", 0.0)), reverse=True
    )

    parent = list(range(n_frames))

    def _find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    total_weight = 0.0
    tree_edges = 0
    needed = n_frames - 1

    for e in sorted_edges:
        if tree_edges >= needed:
            break
        ei, ej = int(e.get("i", -1)), int(e.get("j", -1))
        if not (0 <= ei < n_frames and 0 <= ej < n_frames):
            continue
        pi, pj = _find(ei), _find(ej)
        if pi != pj:
            parent[pi] = pj
            total_weight += float(e.get("weight", 0.0))
            tree_edges += 1

    if tree_edges == 0:
        return 0.0
    return total_weight / max(1, needed)


def _compute_adj_edge_coverage(
    edges: List[dict],
    n_frames: int,
) -> float:
    """§1.43: Fraction of adjacent frame pairs (|i−j|=1) with at least one edge.

    Bundle adjustment is most reliable when every consecutive frame pair has a
    direct matching edge.  When large fractions of adjacent pairs are missing
    (matching fell through for all attempts), BA has to rely on skip-edges
    which carry inherently noisier displacement estimates.

    Distinct from ``_check_edge_graph_connectivity`` (which only checks global
    reachability, not local adjacency density) and ``_compute_mst_weight``
    (which checks confidence quality, not structural coverage).

    Parameters
    ----------
    edges     : list of edge dicts with 'i' and 'j' integer frame indices.
    n_frames  : total number of frames in the sequence.

    Returns
    -------
    float in [0, 1].  Returns 1.0 when n_frames ≤ 1 (trivially covered).
    """
    if n_frames <= 1:
        return 1.0
    n_adj = n_frames - 1
    covered = {
        (min(int(e["i"]), int(e["j"])), max(int(e["i"]), int(e["j"])))
        for e in edges
        if abs(int(e["i"]) - int(e["j"])) == 1
    }
    return float(len(covered)) / float(n_adj)


def _compute_sign_inconsistency_rate(edges: "List[dict]") -> float:
    """§1.47: Minority-sign fraction of adjacent-edge dominant-axis displacements.

    For a consistent scroll all adjacent edges should report camera movement in
    the same direction.  The dominant axis is determined by comparing
    ``|median(dy)|`` vs ``|median(dx)|`` across adjacent edges.

    *Sign inconsistency rate* = ``min(n_pos, n_neg) / n_total`` where
    ``n_pos`` / ``n_neg`` are the counts of positive / negative displacements
    along the dominant axis.  Zero-displacement edges are ignored.

    Returns
    -------
    float in [0, 0.5].  0.0 means perfect sign agreement.  0.5 means the
    graph is evenly split (maximum confusion).  Returns 0.0 when fewer than
    2 adjacent edges have non-zero displacement.
    """
    adj = [e for e in edges if abs(int(e["i"]) - int(e["j"])) == 1]
    if len(adj) < 2:
        return 0.0

    dys = [float(e["M"][1, 2]) for e in adj]
    dxs = [float(e["M"][0, 2]) for e in adj]
    med_dy = float(np.median([abs(d) for d in dys]))
    med_dx = float(np.median([abs(d) for d in dxs]))
    disps = dys if med_dy >= med_dx else dxs

    nonzero = [d for d in disps if d != 0.0]
    if len(nonzero) < 2:
        return 0.0

    n_pos = sum(1 for d in nonzero if d > 0)
    n_neg = len(nonzero) - n_pos
    return float(min(n_pos, n_neg)) / float(len(nonzero))


def _compute_adj_disp_cv(edges: "List[dict]") -> float:
    """§1.48: Coefficient of variation of adjacent-edge dominant-axis displacement magnitudes.

    Filters to adjacent edges (``|i-j|=1``), selects the dominant scroll axis
    (larger median absolute displacement), and returns ``std(|disp|)/mean(|disp|)``
    across those magnitudes.  A high CV (e.g. >0.5) indicates one or more
    adjacent edges with wildly different displacement from the rest — e.g. a
    phase-correlation match locked onto the 2nd harmonic (2× true step) or a
    template-match that jumped to non-adjacent content.

    Complementary to §1.47 (sign gate): an outlier that agrees on scroll
    *direction* but reports 10× the typical *magnitude* passes §1.47 but fails
    this gate.

    Returns
    -------
    float ≥ 0.  0.0 for fewer than 2 adjacent edges (safe no-op) or when
    mean magnitude is 0.
    """
    adj = [e for e in edges if abs(int(e["i"]) - int(e["j"])) == 1]
    if len(adj) < 2:
        return 0.0

    dys = [abs(float(e["M"][1, 2])) for e in adj]
    dxs = [abs(float(e["M"][0, 2])) for e in adj]
    mags = dys if float(np.median(dys)) >= float(np.median(dxs)) else dxs

    mean_m = float(np.mean(mags))
    if mean_m == 0.0:
        return 0.0
    return float(np.std(mags)) / mean_m


def _compute_adj_min_weight(edges: "List[dict]") -> float:
    """§1.49: Minimum match confidence weight among all adjacent edges (|i−j|=1).

    §1.16 guards the *mean* MST weight; §1.43 guards *coverage* (at least one
    edge per adjacent pair).  This function fills the gap: even when coverage
    is complete and the mean looks acceptable, a single adjacent edge whose
    weight is near zero guarantees an unreliable displacement for that pair —
    the compositing seam at that boundary will be ill-placed regardless of how
    cleanly BA solves the remaining graph.

    Returns
    -------
    float in [0, 1].  Minimum weight among adjacent edges.  Returns 1.0 when
    no adjacent edges exist (safe no-op — nothing to fail on).
    """
    adj = [e for e in edges if abs(int(e["i"]) - int(e["j"])) == 1]
    if not adj:
        return 1.0
    return min(float(e["weight"]) for e in adj)


def _compute_ba_max_residual(
    edges: "List[dict]",
    affines: "List[np.ndarray]",
) -> float:
    """§1.50: Maximum per-edge BA residual (L2, pixels) across all edges.

    For each edge (i→j) the *observed* displacement is ``e["M"][:2, 2]`` (the
    raw pairwise match translation vector) and the *predicted* displacement is
    ``affines[j][:2, 2] − affines[i][:2, 2]`` (what the solved global frame
    placement implies).  The L2 distance between the two is the edge residual.

    A healthy BA solve with GNC/Cauchy weighting has a median residual of
    ≤ 5–15 px.  A catastrophically bad match (Category B failure) that survived
    all pre-BA gates will still produce a large residual because the solved
    affines will be pulled *toward* but not fully to the bad edge's implied
    position — typically 50–500 px off for a corrupted outlier.

    Returns
    -------
    float ≥ 0.  Maximum residual across all edges.  Returns 0.0 when the edge
    list is empty or any affine index is out of range (safe no-op).
    """
    if not edges or not affines:
        return 0.0
    n = len(affines)
    max_res = 0.0
    for e in edges:
        i, j = int(e["i"]), int(e["j"])
        if i >= n or j >= n:
            continue
        observed = np.array([float(e["M"][0, 2]), float(e["M"][1, 2])])
        predicted = affines[j][:2, 2] - affines[i][:2, 2]
        res = float(np.linalg.norm(observed - predicted))
        if res > max_res:
            max_res = res
    return max_res


def _compute_ba_weighted_mean_residual(
    edges: "List[dict]",
    affines: "List[np.ndarray]",
) -> float:
    """§1.52: Confidence-weighted mean per-edge BA residual (L2, pixels).

    For each edge (i→j) the residual is::

        r = ‖observed_disp − (affines[j][:2,2] − affines[i][:2,2])‖₂

    The weighted mean is::

        Σ(w_i × r_i) / Σ(w_i)

    where ``w_i = e["weight"]`` is the match confidence score.

    Complements §1.50 (max residual):

    * §1.50 fires when *one* edge has a catastrophically large residual
      (Category B single outlier).
    * §1.52 fires when *all* or *many* edges have moderate residuals —
      e.g., systematic BA drift from a global translation bias caused by
      repeated background texture or phase-correlation peak shifting.
      In this scenario no individual residual exceeds §1.50's threshold,
      yet the entire solved frame placement is unreliable.

    Returns
    -------
    float ≥ 0.  Weighted mean residual in pixels.  Returns 0.0 when the
    edge list is empty, all weights are zero, or any affine index is out
    of range (safe no-op).
    """
    if not edges or not affines:
        return 0.0
    n = len(affines)
    total_w = 0.0
    total_wr = 0.0
    for e in edges:
        i, j = int(e["i"]), int(e["j"])
        if i >= n or j >= n:
            continue
        w = float(e["weight"])
        observed = np.array([float(e["M"][0, 2]), float(e["M"][1, 2])])
        predicted = affines[j][:2, 2] - affines[i][:2, 2]
        r = float(np.linalg.norm(observed - predicted))
        total_w += w
        total_wr += w * r
    if total_w == 0.0:
        return 0.0
    return total_wr / total_w


def _compute_max_adjacent_gap(
    affines: List[np.ndarray],
    frames: List[np.ndarray],
) -> float:
    """§1.44: Maximum pixel gap between adjacent frames along the dominant scroll axis.

    For each consecutive pair (i, i+1) computes the canvas-space distance
    between the trailing edge of frame i and the leading edge of frame i+1:

    * **Vertical scroll** (ty_span ≥ tx_span): gap = ty_{i+1} − (ty_i + H_i)
    * **Horizontal scroll** (tx_span > ty_span): gap = tx_{i+1} − (tx_i + W_i)

    A gap > 0 means the two frames do not overlap and there is an uncovered
    canvas strip between them.  A gap < 0 means the frames overlap normally
    (the expected case for a stitched panorama).

    Returns the maximum gap over all N-1 adjacent pairs, or 0.0 for N < 2.

    Complementary to §1.17 (global span utilisation, which catches total
    collapse) and §1.39 (post-render coverage, expensive warp step); this gate
    uses only affine math and fires before Stage 10.
    """
    if len(affines) < 2 or len(frames) < 2:
        return 0.0

    tys = [float(a[1, 2]) for a in affines]
    txs = [float(a[0, 2]) for a in affines]
    ty_span = max(tys) - min(tys)
    tx_span = max(txs) - min(txs)
    vertical = ty_span >= tx_span

    max_gap = -float("inf")
    for i in range(len(affines) - 1):
        if vertical:
            trailing = float(affines[i][1, 2]) + frames[i].shape[0]
            leading = float(affines[i + 1][1, 2])
        else:
            trailing = float(affines[i][0, 2]) + frames[i].shape[1]
            leading = float(affines[i + 1][0, 2])
        max_gap = max(max_gap, leading - trailing)

    return max_gap


def _compute_min_adjacent_overlap(
    affines: "List[np.ndarray]",
    frames: "List[np.ndarray]",
) -> float:
    """§1.51: Minimum canvas-space overlap between consecutive frame pairs.

    For each adjacent pair (i, i+1) computes::

        overlap = trailing_edge(i) − leading_edge(i+1)

    where *trailing_edge* is the far edge of frame i along the dominant scroll
    axis (``affines[i].ty + frame_height`` for vertical, ``affines[i].tx +
    frame_width`` for horizontal) and *leading_edge* is the near edge of frame
    i+1.  Positive overlap means frames share rows in canvas space; negative
    overlap is a gap (caught by §1.44).

    The minimum overlap across all N−1 pairs is returned.  A very small
    positive value (e.g. 1–19 px) means the compositing seam zone for that
    pair is too narrow for reliable DP cutting or feathering — the seam will
    almost certainly clip through foreground character pixels, and
    ``FEATHER_MIN=80`` cannot be satisfied.

    Returns
    -------
    float.  Minimum overlap in pixels.  Returns 0.0 when fewer than 2 frames
    or affines are supplied (safe no-op).
    """
    if len(affines) < 2 or len(frames) < 2:
        return 0.0
    tys = [float(a[1, 2]) for a in affines]
    txs = [float(a[0, 2]) for a in affines]
    ty_span = max(tys) - min(tys)
    tx_span = max(txs) - min(txs)
    vertical = ty_span >= tx_span
    min_overlap = float("inf")
    for i in range(len(affines) - 1):
        if vertical:
            trailing = float(affines[i][1, 2]) + frames[i].shape[0]
            leading = float(affines[i + 1][1, 2])
        else:
            trailing = float(affines[i][0, 2]) + frames[i].shape[1]
            leading = float(affines[i + 1][0, 2])
        min_overlap = min(min_overlap, trailing - leading)
    return min_overlap


def _compute_canvas_width_ratio(
    canvas_w: int,
    frames: "List[np.ndarray]",
) -> float:
    """§1.45: Canvas width relative to median source-frame width.

    For a vertical-scroll panorama the canvas should be approximately as wide
    as the individual source frames — frames are stacked top-to-bottom with
    only minor horizontal offsets.  A ratio significantly above 1.0 indicates
    that bundle adjustment introduced substantial horizontal tx drift:

    * **ratio ≈ 1.0** — healthy vertical scroll; frames roughly aligned.
    * **ratio > 1.5** — frames scattered horizontally; canvas is mostly black
      columns on the sides; compositing will produce a thin vertical strip of
      content in a very wide black canvas.

    This is distinct from §3.14 (pure horizontal scroll, caught by
    ``_detect_scroll_axis``) because ty_span can still dominate while the
    per-frame tx values drift monotonically across the sequence.

    Parameters
    ----------
    canvas_w : canvas width in pixels after Stage 9 (T_global already applied).
    frames   : source frames (used to derive median width).

    Returns
    -------
    float ≥ 0.  Returns 1.0 when *frames* is empty.
    """
    if not frames:
        return 1.0
    median_w = float(np.median([f.shape[1] for f in frames]))
    if median_w <= 0.0:
        return 1.0
    return float(canvas_w) / median_w


def _compute_canvas_memory_mb(canvas_h: int, canvas_w: int) -> float:
    """§1.53: Estimated float32 RGB canvas array footprint in megabytes.

    Computes ``canvas_h × canvas_w × 3 channels × 4 bytes / 1024²``.

    This is a *lower-bound* estimate — in practice the compositing pipeline
    allocates several same-sized buffers (canvas, valid_mask, warped frames,
    foreground masks, intermediate blend zones) so the true peak RSS is
    3–6× this value.  The gate is intended to catch pathological cases
    (e.g. 32768 × 32768 canvas → 12 GB estimate) before the allocation
    attempt causes an OOM kill or swap thrash.

    ``CANVAS_MAX_DIM = 32768`` prevents any single dimension from being
    extreme but does not bound the product: 32768 × 1920 = ~720 MB (float32
    RGB) is well within CANVAS_MAX_DIM yet may exceed available RAM when
    combined with intermediate buffers on a 4-GB system.

    Returns
    -------
    float ≥ 0.  Estimated megabytes.  Returns 0.0 for zero or negative
    dimensions (safe no-op).
    """
    if canvas_h <= 0 or canvas_w <= 0:
        return 0.0
    return float(canvas_h) * float(canvas_w) * 3.0 * 4.0 / (1024.0**2)


def _compute_canvas_aspect_ratio(canvas_h: int, canvas_w: int) -> float:
    """§1.62: Canvas height-to-width aspect ratio (S125).

    Returns ``canvas_h / canvas_w``.  For a vertical-scroll panorama this
    ratio should be well above 1.0 — a typical manga strip of 14 frames at
    150 px/step would give canvas_h ≈ 14 × 900 px ≈ 12600, canvas_w ≈ 1080,
    so aspect ≈ 11.7.  A ratio below 1.0 means the canvas is wider than tall,
    indicating that BA drift, a misidentified scroll axis, or a very short
    sequence has produced a landscape-orientation result instead of the expected
    portrait manga strip.

    Returns 0.0 for non-positive dimensions (safe no-op default).
    """
    if canvas_h <= 0 or canvas_w <= 0:
        return 0.0
    return float(canvas_h) / float(canvas_w)


def _sort_frames_by_index(paths: List[str]) -> List[str]:
    """§1.63: Sort frame paths by numeric suffix extracted from the filename (S127).

    Frame file names produced by video extraction tools (FFmpeg, OpenCV) are
    typically ``frame_00001.png``, ``frame_00002.png``, etc.  When the caller
    discovers frames via ``glob()`` on some file systems (e.g. ext4 with dir_index)
    the OS-level directory order may not be numeric.  An out-of-order frame list
    causes the pipeline to treat consecutive file-system neighbours as adjacent
    camera positions, producing nonsensical phase-correlation displacements,
    reversed scroll direction, and incorrect BA edge graphs.

    This function re-sorts *paths* by the rightmost contiguous digit run in the
    stem (filename without extension).  When no digit run is found for a path,
    that path is sorted by its original index in *paths* (stable), placing it
    after all numerically-indexed paths.  This keeps the behaviour predictable
    for mixed-name directories while avoiding an import of ``natsort``.

    Parameters
    ----------
    paths : list of file paths to sort.

    Returns
    -------
    list[str]
        New list in ascending numeric-suffix order.  If all stems lack a digit
        suffix (e.g. user-supplied paths with descriptive names), the original
        order is returned unchanged.
    """
    # relocated: import re

    def _key(p: str) -> tuple:
        stem = os.path.splitext(os.path.basename(p))[0]
        m = re.search(r"(\d+)$", stem)
        return (0, int(m.group(1))) if m else (1, 0)

    sorted_paths = sorted(paths, key=_key)
    return sorted_paths


def _compute_render_luma_std(
    canvas: np.ndarray,
    valid_mask: np.ndarray,
) -> float:
    """§1.54: Pixel luminance std across valid (covered) canvas pixels.

    Computes the standard deviation of per-pixel luminance for all pixels
    where ``valid_mask > 0``.  Luminance is approximated as the simple mean of
    BGR channels::

        luma[y, x] = (B + G + R) / 3

    A value near zero indicates all covered pixels share the same luminance —
    a degenerate render caused by:

    * **BaSiC over-correction**: photometric normalisation clamped every frame
      to the same mean luminance, fusing into a flat-grey slab.
    * **Silent warp failure**: all frames were mapped to an identical canvas
      region whose contents cancel in the temporal median.
    * **Hold-block leakage**: temporally static frames that slipped through
      §1.2D / §1.11C produce a single repeated frame with no per-seam
      luminance variation.

    This failure mode produces no visible seam (§1.24 passes), adequate
    pixel coverage (§1.39 passes), but the panorama output is essentially
    a solid-colour image.  Distinct from §1.39 which checks *coverage
    quantity*; §1.54 checks *luminance variety*.

    Returns
    -------
    float ≥ 0.  Std of valid-pixel luminance in [0, 255] scale.  Returns
    0.0 when ``canvas`` or ``valid_mask`` is None, or when no valid pixels
    exist.
    """
    if canvas is None or valid_mask is None:
        return 0.0
    valid = valid_mask > 0
    if not valid.any():
        return 0.0
    pixels = canvas[valid].astype(np.float32)
    luma = pixels.mean(axis=1) if pixels.ndim == 2 else pixels.mean(axis=-1)
    return float(np.std(luma))


def _compute_max_affine_rotation_deg(affines: "List[np.ndarray]") -> float:
    """§1.55: Maximum per-affine rotation angle (degrees) across all BA-solved affines.

    Extracts the rotation angle from each 2×3 affine matrix via
    ``arctan2(M[1, 0], M[0, 0])`` and returns the largest absolute value in
    degrees.  For a pure-translation scroll capture all affines should have
    near-zero rotation (angle < 1°).  A large rotation in any affine means
    the feature matcher latched onto a rotationally-similar texture patch,
    producing a corrupted translation estimate even when per-edge BA residuals
    look acceptable.

    Returns
    -------
    float ≥ 0.  Maximum absolute rotation angle in degrees.  Returns 0.0 for
    an empty affine list.
    """
    if not affines:
        return 0.0
    max_deg = 0.0
    for M in affines:
        angle_rad = float(np.arctan2(float(M[1, 0]), float(M[0, 0])))
        deg = abs(float(np.degrees(angle_rad)))
        if deg > max_deg:
            max_deg = deg
    return max_deg


def _smooth_affine_trajectory(
    affines: "List[np.ndarray]",
    sigma: float,
    iqr_threshold: float = 10.0,
) -> "Tuple[List[np.ndarray], bool]":
    """§3.16: Gaussian 1D trajectory smoother for BA-solved affine translations.

    Applies ``scipy.ndimage.gaussian_filter1d(mode='nearest')`` independently
    to the tx and ty sequences extracted from all affines.  The boundary
    mode='nearest' avoids edge attenuation — corner affines do not drift
    toward zero translation.  Rotation and scale components are copied from
    the original affine unchanged.

    The smoother is activation-gated: it fires only when the IQR of
    absolute adjacent-step magnitudes in the dominant scroll axis exceeds
    ``iqr_threshold`` pixels.  This ensures clean linear-scroll sequences
    (uniform inter-frame displacement) are not modified at all.

    Parameters
    ----------
    affines :
        List of 2×3 float32 ndarray as returned by ``_bundle_adjust_affine``.
    sigma :
        Gaussian σ in frames.  Values < 3 produce gentle smoothing (~1.5 is
        recommended); values > 5 risk over-smoothing short sequences.
    iqr_threshold :
        Minimum IQR of adjacent-step magnitudes (dominant axis, pixels) required
        to trigger smoothing.  Default 10.0 px.

    Returns
    -------
    (smoothed_affines, was_applied)
        ``smoothed_affines`` — same-length list of 2×3 arrays with smoothed
        tx/ty (rotation and scale unchanged).
        ``was_applied`` — True when smoothing fired (IQR exceeded threshold).
        When False, ``smoothed_affines is affines`` (same object, no copy).
    """
    # relocated: from scipy.ndimage import gaussian_filter1d  # deferred — avoid import at module level

    if len(affines) < 3 or sigma <= 0.0:
        return affines, False

    txs = np.array([float(a[0, 2]) for a in affines], dtype=np.float64)
    tys = np.array([float(a[1, 2]) for a in affines], dtype=np.float64)

    steps_x = np.abs(np.diff(txs))
    steps_y = np.abs(np.diff(tys))
    iqr_x = float(np.percentile(steps_x, 75) - np.percentile(steps_x, 25))
    iqr_y = float(np.percentile(steps_y, 75) - np.percentile(steps_y, 25))

    if max(iqr_x, iqr_y) <= iqr_threshold:
        return affines, False

    txs_smooth = gaussian_filter1d(txs, sigma=sigma, mode="nearest")
    tys_smooth = gaussian_filter1d(tys, sigma=sigma, mode="nearest")

    smoothed: List[np.ndarray] = []
    for i, a in enumerate(affines):
        a_new = a.copy()
        a_new[0, 2] = float(txs_smooth[i])
        a_new[1, 2] = float(tys_smooth[i])
        smoothed.append(a_new)

    return smoothed, True


def _wave_correct_affines(
    affines: List[np.ndarray],
    axis: str = "vertical",
) -> List[np.ndarray]:
    """§4.3: Post-BA linear wave correction (S160).

    For vertical-scroll sequences the x-translations (tx) should ideally be
    zero; any systematic drift is a "wave" caused by accumulated BA error along
    the cross-axis.  This function fits a linear trend (``np.polyfit`` degree 1)
    to the tx (or ty for horizontal-scroll) sequence and subtracts it so the
    sequence midline is straightened.

    Only corrects the cross-axis component:
      * ``axis='vertical'``   — corrects tx drift; ty unchanged.
      * ``axis='horizontal'`` — corrects ty drift; tx unchanged.

    The other axis (dominant scroll axis) is never modified.  For N < 3 or when
    the range of the corrected axis is less than ``WAVE_CORRECT_MIN_TX_RANGE``
    pixels, the original list is returned unchanged (no copy).

    Parameters
    ----------
    affines :
        List of N 2×3 float32 ndarray as returned by ``_bundle_adjust_affine``.
    axis :
        Which axis to straighten — ``'vertical'`` (correct tx) or
        ``'horizontal'`` (correct ty).

    Returns
    -------
    List of 2×3 float32 arrays with the cross-axis drift removed.
    """
    from backend.src.constants.animation import WAVE_CORRECT_MIN_TX_RANGE

    if _HAS_BATCH:
        result = _batch.wave_correct.wave_correct_affines(
            [np.asarray(a, dtype=np.float32) for a in affines],
            axis=axis,
            min_range_px=float(WAVE_CORRECT_MIN_TX_RANGE),
        )
        return [np.asarray(r, dtype=np.float32) for r in result]

    N = len(affines)
    if N < 3:
        return affines

    correct_tx = axis.lower() != "horizontal"
    # idx = 2 if correct_tx else (1, 2)  # matrix column index for tx vs ty
    # Extract the sequence to correct
    if correct_tx:
        vals = np.array([float(M[0, 2]) for M in affines])
    else:
        vals = np.array([float(M[1, 2]) for M in affines])

    if (vals.max() - vals.min()) < WAVE_CORRECT_MIN_TX_RANGE:
        return affines

    frame_idx = np.arange(N, dtype=np.float64)
    slope, intercept = np.polyfit(frame_idx, vals, 1)
    trend = slope * frame_idx + intercept
    corrected_vals = vals - trend + vals[0]  # anchor first frame

    out = []
    for i, M in enumerate(affines):
        M_new = M.copy()
        if correct_tx:
            M_new[0, 2] = float(corrected_vals[i])
        else:
            M_new[1, 2] = float(corrected_vals[i])
        out.append(M_new)
    return out


def _compute_canvas_span_utilization(affines: List[np.ndarray]) -> float:
    """§1.17: Canvas span utilisation ratio (S61).

    After bundle adjustment, computes the ratio of the *actual* dominant-axis
    span (``max(ty) − min(ty)`` or ``max(tx) − min(tx)``, whichever is
    larger) to the *expected* span (``median_adjacent_step × (N−1)``).

    A ratio well below 1.0 indicates that the BA solution has collapsed most
    frames into a compact cluster — the per-edge validation checks (min_gap,
    ratio, rotation) all passed, yet the assembled canvas is far shorter than
    physics would predict.  In that case the composite will show heavily
    overlapping strips (low new-canvas-area coverage per frame), which makes
    the temporal median degenerate into a blurry average of animated poses.

    Returns 1.0 when N < 2 or the expected span is zero (safe fallback —
    caller should not trigger the gate).

    Parameters
    ----------
    affines:
        List of N 2×3 float32 affine matrices (after global canvas offset).
        ``affines[i][0, 2]`` = tx for frame i; ``affines[i][1, 2]`` = ty.

    Returns
    -------
    float
        Utilisation ratio ≥ 0.  Values > 1.0 are possible when individual
        frames are placed non-monotonically (large BA corrections).
    """
    N = len(affines)
    if N < 2:
        return 1.0
    ty_vals = [float(a[1, 2]) for a in affines]
    tx_vals = [float(a[0, 2]) for a in affines]
    ty_span = max(ty_vals) - min(ty_vals)
    tx_span = max(tx_vals) - min(tx_vals)

    # Use dominant axis (larger span) for the expected-step estimate.
    if ty_span >= tx_span:
        vals = ty_vals
        span = ty_span
    else:
        vals = tx_vals
        span = tx_span

    adj_steps = [abs(vals[i + 1] - vals[i]) for i in range(N - 1)]
    median_step = float(np.median(adj_steps))
    expected_span = median_step * (N - 1)
    if expected_span <= 0.0:
        return 1.0
    return span / expected_span


def _compute_dy_cv(affines: List[np.ndarray]) -> float:
    """§4.7: Coefficient of variation of adjacent vertical frame steps.

    Computes ``std(|Δty|) / mean(|Δty|)`` from the bundle-adjusted affines.
    A high dy_cv indicates an irregular scroll pattern (variable step sizes)
    where ASP's compositing assumptions break down.

    97-test benchmark (S160, 2026-06-23): dy_cv ≥ 1.5 → catastrophic ASP
    failure on every test in that regime (AlSSIM −22 to −37%, seam_vis
    60–120 vs SCANS 2–3).  SCANS handles these sequences trivially because
    it requires no frame-to-frame registration.

    Returns 0.0 when N < 2 (gate will not fire).

    Parameters
    ----------
    affines:
        List of N 2×3 float32 affine matrices from bundle adjustment.

    Returns
    -------
    float
        dy_cv ≥ 0.  Zero when N < 2.
    """
    N = len(affines)
    if N < 2:
        return 0.0
    dy_steps = [abs(float(affines[k][1, 2]) - float(affines[k - 1][1, 2])) for k in range(1, N)]
    mean_dy = float(np.mean(dy_steps))
    if mean_dy < 1.0:
        return 0.0
    return float(np.std(dy_steps)) / mean_dy


def _compute_adaptive_dy_cv_max(n_frames: int, base_max: float = 1.5) -> float:
    """§5.8: Lower dy_cv ceiling for sequences with many frames.

    With N≥8 frames, step irregularity compounds across more seams.
    Scale: max(base_max * 8 / max(n_frames, 8), 0.8)
    - N=8: base_max (no change, floor ≥0.8)
    - N=16: base_max * 0.5 = 0.75 (→ floor 0.8)
    - N=4: base_max (unchanged, below 8)
    """
    if n_frames < 8:
        return base_max
    return max(base_max * 8.0 / n_frames, 0.8)


def _check_canvas_spread(
    edges: "List[dict]",
    min_spread_fraction: float,
) -> bool:
    """§1.67: Frame canvas spread validation (S131).

    After phase correlation, verifies that the raw pairwise translations
    span at least *min_spread_fraction* of the expected full-canvas range
    (``median_adjacent_step × (N-1)``).

    When selected frames cluster near one end of the scroll (e.g., only the
    first 30 % of a 14-frame scroll is represented), the assembled panorama
    will be a narrow slice.  Catching this early (before BA allocates
    matrices and the retry chain runs) avoids wasted computation.

    **Dominant axis**: whichever of the cumulative |ty_sum| / |tx_sum|
    is larger over all edges.

    Parameters
    ----------
    edges :
        List of edge dicts with keys ``"i"``, ``"j"``, ``"ty"``, ``"tx"``.
    min_spread_fraction :
        Minimum ratio of actual dominant-axis span to expected span in (0, 1].
        Recommended: 0.5 (flag sequences that cover < 50 % of expected range).

    Returns
    -------
    bool
        ``True`` when the spread is adequate (≥ min_spread_fraction) or when
        the check cannot be performed (< 2 edges, zero expected span, etc.)
        so that the gate never fires erroneously on degenerate inputs.
        ``False`` when the spread is below the threshold — caller should
        trigger SCANS fallback.
    """
    if not edges or min_spread_fraction <= 0.0:
        return True
    # Collect per-frame cumulative translations from the edge graph.
    # Use a simple BFS from frame 0 to propagate translations.
    node_ids: set = set()
    for e in edges:
        node_ids.add(e["i"])
        node_ids.add(e["j"])
    if len(node_ids) < 2:
        return True
    N_nodes = max(node_ids) + 1
    ty_pos: List[Optional[float]] = [None] * N_nodes
    tx_pos: List[Optional[float]] = [None] * N_nodes
    # Sort edges by (i,j) so BFS from 0 propagates through adjacent pairs.
    sorted_edges = sorted(edges, key=lambda e: (e["i"], e["j"]))
    ty_pos[sorted_edges[0]["i"]] = 0.0
    tx_pos[sorted_edges[0]["i"]] = 0.0
    for e in sorted_edges:
        fi, fj = e["i"], e["j"]
        if ty_pos[fi] is not None and ty_pos[fj] is None:
            ty_pos[fj] = ty_pos[fi] + float(e.get("ty", 0.0))
            tx_pos[fj] = tx_pos[fi] + float(e.get("tx", 0.0))
        elif ty_pos[fj] is not None and ty_pos[fi] is None:
            ty_pos[fi] = ty_pos[fj] - float(e.get("ty", 0.0))
            tx_pos[fi] = tx_pos[fj] - float(e.get("tx", 0.0))
    ty_vals = [v for v in ty_pos if v is not None]
    tx_vals = [v for v in tx_pos if v is not None]
    if len(ty_vals) < 2:
        return True
    ty_span = max(ty_vals) - min(ty_vals)
    tx_span = max(tx_vals) - min(tx_vals)
    if ty_span >= tx_span:
        dom_vals = ty_vals
        dom_span = ty_span
    else:
        dom_vals = tx_vals
        dom_span = tx_span
    N_dom = len(dom_vals)
    adj_steps = sorted([abs(dom_vals[i + 1] - dom_vals[i]) for i in range(N_dom - 1)])
    median_step = float(np.median(adj_steps)) if adj_steps else 0.0
    expected_span = median_step * (N_dom - 1)
    if expected_span <= 0.0:
        return True
    return (dom_span / expected_span) >= min_spread_fraction


def _spatial_dedup_frames(
    frames: List[np.ndarray],
    scans_frames: List[np.ndarray],
    bg_masks: List[np.ndarray],
    image_paths: List[str],
    edges: List[dict],
    min_displacement_px: float,
) -> Tuple[
    List[np.ndarray], List[np.ndarray], List[np.ndarray], List[str], List[dict], int
]:
    """One pass of spatial near-static frame dedup (§1.9A).

    Identifies adjacent frames (j = i+1 in current edge list) whose
    measured displacement is below ``min_displacement_px`` on the dominant
    scroll axis and removes them.  ``scans_frames`` is kept synchronised
    with ``frames`` so every SCANS fallback path uses the same frame
    subset as the main compositing branch — eliminating the desync
    that previously caused the fallback to receive near-duplicate frames
    the compositor had already discarded.

    Returns ``(frames, scans_frames, bg_masks, image_paths, edges, n_dropped)``.
    When ``n_dropped == 0`` all lists are returned unchanged (no allocation).
    """
    adj_m: dict = {e["j"]: e for e in edges if e["j"] == e["i"] + 1}
    if not adj_m:
        return frames, scans_frames, bg_masks, image_paths, edges, 0

    if _HAS_BATCH and hasattr(_batch, "frame_selection"):
        try:
            # Convert M-affine edges to dx/dy format for C++ function
            dx_dy_edges = [
                {"i": e["i"], "j": e["j"], "dx": float(e["M"][0, 2]), "dy": float(e["M"][1, 2])}
                for e in edges
            ]
            keep_idx_raw = list(
                _batch.frame_selection.spatial_dedup_frames(
                    frames, scans_frames or [], bg_masks, image_paths,
                    dx_dy_edges, float(min_displacement_px),
                )
            )
            keep_idx = [int(i) for i in keep_idx_raw]
            if len(keep_idx) == len(frames):
                return frames, scans_frames, bg_masks, image_paths, edges, 0
            o2n: dict = {old: new for new, old in enumerate(keep_idx)}
            drop_set = set(range(len(frames))) - set(keep_idx)
            new_edges = [
                {**e, "i": o2n[e["i"]], "j": o2n[e["j"]]}
                for e in edges
                if e["i"] not in drop_set and e["j"] not in drop_set
            ]
            return (
                [frames[i] for i in keep_idx],
                [scans_frames[i] for i in keep_idx] if scans_frames else [],
                [bg_masks[i] for i in keep_idx],
                [image_paths[i] for i in keep_idx],
                new_edges,
                len(drop_set),
            )
        except Exception:
            pass

    adx = [abs(float(e["M"][0, 2])) for e in adj_m.values()]
    ady = [abs(float(e["M"][1, 2])) for e in adj_m.values()]
    spa_axis = 0 if float(np.median(adx)) > float(np.median(ady)) else 1

    drop: set = set()
    for jj in sorted(adj_m):
        ee = adj_m[jj]
        if ee["i"] in drop:
            continue
        if abs(float(ee["M"][spa_axis, 2])) < min_displacement_px:
            drop.add(jj)

    if not drop:
        return frames, scans_frames, bg_masks, image_paths, edges, 0

    N = len(frames)
    keep_idx = [i for i in range(N) if i not in drop]
    o2n: dict = {old: new for new, old in enumerate(keep_idx)}
    new_edges = [
        {**e, "i": o2n[e["i"]], "j": o2n[e["j"]]}
        for e in edges
        if e["i"] not in drop and e["j"] not in drop
    ]
    return (
        [frames[i] for i in keep_idx],
        [scans_frames[i] for i in keep_idx] if scans_frames else [],  # §1.9A/§1.9C
        [bg_masks[i] for i in keep_idx],
        [image_paths[i] for i in keep_idx],
        new_edges,
        len(drop),
    )


def _reload_scans_frames(paths: List[str]) -> List[np.ndarray]:
    """§1.9C: Reload and width-normalise original frames from disk on demand.

    Called only when a SCANS/PANORAMA fallback actually fires and
    ``_SCANS_RELOAD=True``, so the Stage-2 snapshot allocation is avoided for
    the common (success) path.  ``paths`` is already synchronised with the
    live frame list by §1.9A spatial dedup, so the reloaded set matches what
    the pipeline was working with when it failed.
    """
    loaded = _load_frames(paths)
    if not loaded:
        return []
    return _normalise_widths(loaded)


def _compute_row_coverage(
    affines: list,
    frames: list,
    canvas_h: int,
) -> tuple:
    """
    Compute per-row frame coverage for the multi-frame canvas coverage gate.

    Returns
    -------
    (row_cov, pct_multi, median_cov) where:
      row_cov    : (canvas_h,) int32 — number of frames covering each row
      pct_multi  : fraction of content rows with ≥2-frame coverage (0–1)
      median_cov : median coverage among content rows
    """
    row_cov = np.zeros(canvas_h, dtype=np.int32)
    for _aff, _frame in zip(affines, frames):
        _r0 = max(0, round(float(_aff[1, 2])))
        _r1 = min(canvas_h, _r0 + _frame.shape[0])
        if _r1 > _r0:
            row_cov[_r0:_r1] += 1
    content_rows = row_cov > 0
    n_content = int(content_rows.sum())
    if n_content == 0:
        return row_cov, 0.0, 0.0
    n_multi = int((row_cov[content_rows] >= 2).sum())
    pct_multi = n_multi / n_content
    median_cov = float(np.median(row_cov[content_rows]))
    return row_cov, pct_multi, median_cov


def _apply_hires_keyframes(
    frames: List[np.ndarray],
    affines: List[np.ndarray],
    bg_masks: List[Optional[np.ndarray]],
    hires_keyframes: Dict[int, str],
) -> Tuple[int, List[np.ndarray], List[np.ndarray], List[Optional[np.ndarray]]]:
    """
    Replace proxy frames with hires counterparts and scale affines/masks.

    Issue 9C (Sprint 8) — Hybrid 4K/1080p compositing.

    All heavy computation (phases 1–8: photometric correction, masking, matching,
    BA, ECC) ran at proxy (1080p) resolution. This function:
    1. Loads hires frames for the indices listed in *hires_keyframes*.
    2. Determines the (scale_y, scale_x) factor from the first successfully
       loaded hires frame vs. its proxy counterpart.
    3. Scales affine translation components (tx, ty) by (scale_x, scale_y).
       The linear sub-matrix (rotation/scale/shear) is dimensionless and unchanged.
    4. For frame indices NOT in hires_keyframes, bicubic-upscales the proxy.
    5. Resizes all bg_masks to match the hires frame dimensions.

    Returns (n_loaded, frames_hires, affines_scaled, masks_resized).
    When n_loaded == 0 all inputs are returned unchanged.
    """
    hires_imgs: Dict[int, np.ndarray] = {}
    for idx, path in hires_keyframes.items():
        if 0 <= idx < len(frames):
            img = cv2.imread(path)
            if img is not None:
                hires_imgs[idx] = img

    if not hires_imgs:
        return 0, frames, affines, bg_masks

    ref_idx = next(iter(hires_imgs))
    hires_h, hires_w = hires_imgs[ref_idx].shape[:2]
    proxy_h, proxy_w = frames[ref_idx].shape[:2]
    if proxy_h == 0 or proxy_w == 0:
        return 0, frames, affines, bg_masks

    scale_y = hires_h / proxy_h
    scale_x = hires_w / proxy_w

    affines_scaled = []
    for a in affines:
        a_new = a.copy().astype(np.float64)
        a_new[0, 2] *= scale_x
        a_new[1, 2] *= scale_y
        affines_scaled.append(a_new)

    frames_hires: List[np.ndarray] = []
    for i, f in enumerate(frames):
        if i in hires_imgs:
            frames_hires.append(hires_imgs[i])
        else:
            frames_hires.append(
                cv2.resize(f, (hires_w, hires_h), interpolation=cv2.INTER_LANCZOS4)
            )

    masks_resized: List[Optional[np.ndarray]] = []
    for m in bg_masks:
        if m is None:
            masks_resized.append(None)
        else:
            masks_resized.append(
                cv2.resize(m, (hires_w, hires_h), interpolation=cv2.INTER_NEAREST)
            )

    return len(hires_imgs), frames_hires, affines_scaled, masks_resized


class AnimeStitchPipeline:
    """
    Multi-stage anime frame stitching pipeline.

    Parameters
    ----------
    use_basic    : enable BaSiC photometric correction (broadcast dimming removal).
    use_birefnet : enable BiRefNet foreground masking (character exclusion).
    use_loftr    : enable LoFTR dense matching (falls back to template match if False).
    use_ecc      : enable ECC sub-pixel refinement after bundle adjustment.
    renderer     : 'median' — temporal Overmix-style median (suppresses noise);
                   'first'  — always use the first valid frame per canvas pixel;
                   'blend'  — sequential Laplacian blend (nearest to SCANS mode).
    composite_fg : paste the foreground character from the best single frame back
                   onto the median background.
    laplacian_bands : pyramid depth for multi-band blending.
    mfsr_mode    : when True, runs the MFSR super-resolution pipeline after the
                   temporal render (stage 10) to sharpen edges and reverse
                   compression artifacts.
    """

    def __init__(
        self,
        use_basic: bool = True,
        use_birefnet: bool = True,
        use_loftr: bool = True,
        use_efficient_loftr: bool = True,
        use_aliked: bool = True,
        use_roma: bool = True,
        use_sea_raft: bool = True,
        sr_mode: bool = False,
        sr_scale: int = 2,
        use_ecc: bool = True,
        renderer: str = "median",  # 'median' | 'first' | 'blend'
        composite_fg: bool = True,
        laplacian_bands: int = LAPLACIAN_BANDS,
        stitch_net_ckpt: str = "",  # path to AnimeStitchNet checkpoint
        edge_crop: int = 30,
        motion_model: str = "translation",  # 'translation' or 'affine' (4-DOF)
        mfsr_mode: bool = False,
        mfsr_n_dct_iter: int = 20,
        mfsr_use_prior: bool = True,
        mfsr_use_diffusion: bool = False,
        **kwargs,
    ):
        self.kwargs = kwargs
        self.use_basic = use_basic and _BASIC_OK
        self.use_birefnet = use_birefnet and _BIREFNET_OK
        self.use_loftr = use_loftr and _LOFTR_OK
        self.use_efficient_loftr = use_efficient_loftr and _ELOFTR_OK
        self.use_aliked = use_aliked and _ALIKED_OK
        self.use_roma = use_roma and _ROMA_OK
        self.use_sea_raft = use_sea_raft and _SEA_RAFT_OK
        self.sr_mode = sr_mode and _SR_OK
        self.sr_scale = sr_scale
        self.use_tooncrafter = kwargs.get("use_tooncrafter", False) and _TOONCRAFTER_OK
        self.use_srstitcher = kwargs.get("use_srstitcher", False) and _SRSTITCHER_OK
        self.use_jamma = kwargs.get("use_jamma", False)
        self.use_ecc = use_ecc
        self.renderer = renderer
        self.composite_fg = composite_fg
        self.bands = laplacian_bands
        self.stitch_net_ckpt = stitch_net_ckpt
        self.edge_crop = edge_crop
        self.motion_model = motion_model
        self.mfsr_mode = mfsr_mode
        self.mfsr_n_dct_iter = mfsr_n_dct_iter
        self.mfsr_use_prior = mfsr_use_prior
        self.mfsr_use_diffusion = mfsr_use_diffusion

        # §1.5D: seam path cache shared across run() invocations on the same frame set
        self._seam_path_cache: Dict = {}

        # Issue 10A3: NL seam routing exclusion masks — set externally before run()
        # List of per-frame uint8 (H,W) masks where >127 forces seam cost=1e6.
        self.exclusion_masks: Optional[List[np.ndarray]] = None

        # Issue 10A2 S83: live SAM-2 predictor state preserved across HITL boundary.
        # Populated by _compute_fg_masks() when _USE_SAM2 is True; freed by
        # _cleanup_sam2_state() after checkpoint 1.5 mask review completes.
        self._sam2_predictor = None
        self._sam2_inference_state = None
        self._sam2_tmp_dir: Optional[str] = None
        self._sam2_frame_h: int = 0
        self._sam2_frame_w: int = 0

        # Lazy-loaded model instances (only allocated if the flag is True)
        self._basic: Optional["BaSiCWrapper"] = None
        self._baselines: Optional[List[float]] = None
        self._birefnet: Optional["BiRefNetWrapper"] = None
        self._loftr: Optional["LoFTRWrapper"] = None
        self._eloftr: Optional["EfficientLoFTRWrapper"] = None
        self._aliked: Optional["ALIKEDLightGlueWrapper"] = None
        self._roma: Optional["RoMaWrapper"] = None
        self._sea_raft = None
        self._stitch_net: Optional["AnimeStitchNet"] = None

    # -------------------------------------------------------------- edge filter

    def _filter_edges(
        self,
        edges: List[Dict],
        image_paths: List[str],
        H: int,
        W: int,
        frames: List[np.ndarray],
        bg_masks: List[Optional[np.ndarray]],
    ) -> List[Dict]:
        """
        Apply geometric-consistency + direction-consensus filters to raw edges.

        Separated from ``run()`` so the progress-aware subclass can call it
        after its overridden ``_pairwise_match``.
        """
        # ── §1.13: Scene-change luma gate ────────────────────────────────────
        # Discard edges between frames with a large mean-luma difference before
        # any geometric or BA processing.  Enabled only when env var is set > 0.
        if _SCENE_CHANGE_LUMA_THRESH > 0:
            edges = _reject_scene_change_edges(edges, frames, _SCENE_CHANGE_LUMA_THRESH)

        # ── §1.13B: Scene-change BGR gate ────────────────────────────────────
        # Per-channel max-delta comparison catches chroma-shifted scene changes
        # (e.g., warm sunset vs cool interior) that grayscale luma misses.
        if _SCENE_CHANGE_BGR_THRESH > 0:
            edges = _reject_scene_change_edges(
                edges, frames, _SCENE_CHANGE_BGR_THRESH, use_bgr=True
            )

        # ── §1.2A+C: Pre-filter static edges (adaptive threshold) ───────────
        # §1.2C: derive content-adaptive threshold before §1.2A rejection so
        # that high-resolution / fast-scroll sequences apply a proportionally
        # higher floor (10 % of median adjacent step, min STATIC_EDGE_MIN_DISP_PX).
        _min_disp = _compute_adaptive_min_disp(edges)
        edges = _reject_static_edges(edges, min_disp_px=_min_disp)

        # ── §2.14 + Geometric Consistency + Min-step (batch or Python) ──────
        # C++ batch.matching.filter_edge_graph covers all three classical gates
        # in a single pass; Python fallbacks run individually when batch is absent.
        _batch_filter_ok = False
        if _HAS_BATCH and hasattr(_batch, "matching"):
            try:
                edges = list(
                    _batch.matching.filter_edge_graph(
                        edges,
                        float(MIN_EXPECTED_STEP),
                        15.0,
                        float(_TRI_CONSISTENCY_MAX_RESIDUAL),
                    )
                )
                _batch_filter_ok = True
            except Exception:
                pass

        if not _batch_filter_ok:
            # ── §2.14: Triangular Consistency Filter ─────────────────────────
            if _TRI_CONSISTENCY_MAX_RESIDUAL > 0.0:
                edges = _triangular_consistency_filter(
                    edges, max_residual_px=_TRI_CONSISTENCY_MAX_RESIDUAL
                )

            # ── Geometric Consistency Filter ──────────────────────────────────
            if len(edges) > 0:
                adj_map: Dict[int, Tuple[float, float]] = {}
                for e in edges:
                    if e["j"] == e["i"] + 1:
                        adj_map[e["i"]] = (e["M"][0, 2], e["M"][1, 2])

                filtered: List[Dict] = []
                for e in edges:
                    i, j = e["i"], e["j"]
                    if j == i + 1:
                        filtered.append(e)
                        continue
                    can_verify = True
                    sum_dx, sum_dy = 0.0, 0.0
                    for k in range(i, j):
                        if k in adj_map:
                            sum_dx += adj_map[k][0]
                            sum_dy += adj_map[k][1]
                        else:
                            can_verify = False
                            break
                    if can_verify:
                        diff_x = abs(e["M"][0, 2] - sum_dx)
                        diff_y = abs(e["M"][1, 2] - sum_dy)
                        if diff_x < 15.0 and diff_y < 15.0:
                            filtered.append(e)
                        else:
                            logger.debug(
                                f"[Stitch]   Edge {i}→{j} rejected: inconsistency "
                                f"(dx={diff_x:.1f}, dy={diff_y:.1f})"
                            )
                    else:
                        filtered.append(e)
                edges = filtered

            # ── Min-step guard ─────────────────────────────────────────────────
            # Reject adjacent edges with near-zero displacement BEFORE the direction
            # consensus filter so the consensus median is not pulled toward zero.
            if len(edges) >= 3:
                adj_edges = [e for e in edges if e["j"] == e["i"] + 1]
                if len(adj_edges) > 0:
                    median_dx_abs = float(np.median([abs(e["M"][0, 2]) for e in adj_edges]))
                    median_dy_abs = float(np.median([abs(e["M"][1, 2]) for e in adj_edges]))
                    primary_axis = 0 if median_dx_abs > median_dy_abs else 1

                    adj_before = len(adj_edges)
                    edges = [
                        e
                        for e in edges
                        if e["j"] != e["i"] + 1
                        or abs(float(e["M"][primary_axis, 2])) >= MIN_EXPECTED_STEP
                    ]
                    adj_after = sum(1 for e in edges if e["j"] == e["i"] + 1)
                    n_rejected = adj_before - adj_after
                    if n_rejected > 0:
                        logger.debug(
                            f"[Stitch]   Min-step guard: rejected {n_rejected} near-zero "
                            f"edges (threshold={MIN_EXPECTED_STEP}px on axis {primary_axis})"
                        )

        # ── Direction Consensus Filter ────────────────────────────────────────
        if len(edges) >= 3:
            adj_edges = [e for e in edges if e["j"] == e["i"] + 1]
            if len(adj_edges) >= 3:
                median_dx_abs = float(np.median([abs(e["M"][0, 2]) for e in adj_edges]))
                median_dy_abs = float(np.median([abs(e["M"][1, 2]) for e in adj_edges]))
                primary_axis = 0 if median_dx_abs > median_dy_abs else 1

                adj_vals = [e["M"][primary_axis, 2] for e in adj_edges]
                median_val = float(np.median(adj_vals))
                consensus_sign = int(np.sign(median_val))

                # Drop skip edges (j > i+1) that scroll the wrong direction or are noise
                if consensus_sign != 0:
                    _pre_skip_n = len(edges)
                    edges = [
                        e
                        for e in edges
                        if e["j"] == e["i"] + 1
                        or abs(float(e["M"][primary_axis, 2])) < 20.0
                        or int(np.sign(float(e["M"][primary_axis, 2])))
                        == consensus_sign
                    ]
                    _n_skip_dropped = _pre_skip_n - len(edges)
                    if _n_skip_dropped:
                        logger.debug(
                            f"[Stitch]   Skip-edge sign filter: dropped "
                            f"{_n_skip_dropped} wrong-sign skip edges"
                        )

                _ts_pat = re.compile(r"_(\d+)ms", re.IGNORECASE)
                timestamps_ms: List[Optional[int]] = []
                for p in image_paths:
                    m = _ts_pat.search(os.path.basename(p))
                    timestamps_ms.append(int(m.group(1)) if m else None)

                def _interval_ms(fi: int, fj: int) -> Optional[int]:
                    t_i = timestamps_ms[fi] if fi < len(timestamps_ms) else None
                    t_j = timestamps_ms[fj] if fj < len(timestamps_ms) else None
                    if t_i is not None and t_j is not None and t_j != t_i:
                        return abs(t_j - t_i)
                    return None

                def _wrong_sign(val: float) -> bool:
                    return (
                        consensus_sign != 0
                        and np.sign(val) != 0
                        and int(np.sign(val)) != consensus_sign
                    )

                def _gross_outlier(val: float) -> bool:
                    return (
                        abs(val) > 2.0 * abs(median_val)
                        and abs(val - median_val) > 200.0
                    )

                vel_samples = []
                for e in edges:
                    if e["j"] != e["i"] + 1:
                        continue
                    v_e = float(e["M"][primary_axis, 2])
                    if _wrong_sign(v_e) or _gross_outlier(v_e):
                        continue
                    iv = _interval_ms(e["i"], e["j"])
                    if iv is not None:
                        vel_samples.append(v_e / iv)
                vel_px_per_ms: Optional[float] = (
                    float(np.median(vel_samples)) if vel_samples else None
                )
                if vel_px_per_ms is not None:
                    logger.debug(
                        f"[Stitch]   Scroll velocity: {vel_px_per_ms:.4f} px/ms "
                        f"(from {len(vel_samples)} reliable edges)"
                    )

                def _is_outlier(val: float, fi: int, fj: int) -> Tuple[bool, str]:
                    if _wrong_sign(val):
                        return True, "wrong sign"
                    if _gross_outlier(val):
                        return True, "gross outlier"
                    if vel_px_per_ms is not None:
                        iv = _interval_ms(fi, fj)
                        if iv is not None:
                            expected = abs(vel_px_per_ms) * iv
                            if abs(val - expected * consensus_sign) > max(
                                0.15 * expected, 15.0
                            ):
                                return (
                                    True,
                                    f"velocity outlier (expected {expected * consensus_sign:.1f})",
                                )
                    return False, ""

                def _apply_corrected_M(
                    edge: Dict, new_M: np.ndarray, new_weight: float
                ) -> Dict:
                    new_pts_j = edge["pts_i"] + new_M[:, 2].astype(np.float32)
                    return dict(edge, M=new_M, pts_j=new_pts_j, weight=new_weight)

                ec_h = int(H * MATCH_EDGE_CROP)
                ec_w = int(W * MATCH_EDGE_CROP)
                corrected: List[Dict] = []
                for e in edges:
                    if e["j"] == e["i"] + 1:
                        fi, fj = e["i"], e["j"]
                        val = float(e["M"][primary_axis, 2])
                        outlier, reason = _is_outlier(val, fi, fj)
                        if outlier:
                            iv = _interval_ms(fi, fj)
                            replaced = False
                            if vel_px_per_ms is not None and iv is not None:
                                est_val = vel_px_per_ms * iv
                                logger.debug(
                                    f"[Stitch]   Edge {fi}→{fj}: val={val:.1f} ({reason}); "
                                    f"velocity → val={est_val:.1f}"
                                )
                                M_fix = np.eye(2, 3, dtype=np.float32)
                                M_fix[1 - primary_axis, 2] = e["M"][1 - primary_axis, 2]
                                M_fix[primary_axis, 2] = est_val
                                e = _apply_corrected_M(e, M_fix, 0.55)
                                replaced = True
                            if not replaced and primary_axis == 1:
                                img_i_c = frames[fi][ec_h:-ec_h, ec_w:-ec_w]
                                img_j_c = frames[fj][ec_h:-ec_h, ec_w:-ec_w]
                                m_i_c = (
                                    bg_masks[fi][ec_h:-ec_h, ec_w:-ec_w]
                                    if bg_masks[fi] is not None
                                    else None
                                )
                                M_dir, c_dir = _template_match(
                                    img_i_c,
                                    img_j_c,
                                    m_i_c,
                                    None,
                                    img_i_c.shape[0],
                                    direction_sign=consensus_sign,
                                )
                                if (
                                    M_dir is not None
                                    and int(np.sign(M_dir[1, 2])) == consensus_sign
                                ):
                                    new_val = float(M_dir[1, 2])
                                    logger.debug(
                                        f"[Stitch]   Edge {fi}→{fj}: directed TM → "
                                        f"val={new_val:.1f} conf={c_dir:.3f}"
                                    )
                                    M_new = np.array(
                                        [[1, 0, e["M"][0, 2]], [0, 1, new_val]],
                                        dtype=np.float32,
                                    )
                                    e = _apply_corrected_M(e, M_new, c_dir * 0.7)
                                    replaced = True
                            if not replaced:
                                logger.debug(
                                    f"[Stitch]   Edge {fi}→{fj}: val={val:.1f} ({reason}); "
                                    f"using median {median_val:.1f}"
                                )
                                M_fix = np.eye(2, 3, dtype=np.float32)
                                M_fix[1 - primary_axis, 2] = e["M"][1 - primary_axis, 2]
                                M_fix[primary_axis, 2] = median_val
                                e = _apply_corrected_M(
                                    e, M_fix, e.get("weight", 1.0) * 0.3
                                )
                        else:
                            logger.debug(
                                f"[Stitch]   Edge {fi}→{fj}: val={val:.1f} kept "
                                f"(consensus {median_val:.1f})"
                            )
                    corrected.append(e)
                edges = corrected

        return edges

    # ---------------------------------------------------------------- public

    def run(
        self,
        image_paths: List[str],
        output_path: str,
        hires_keyframes: Optional[Dict[int, str]] = None,
    ) -> Image.Image:
        """
        Execute the full stitching pipeline.

        Parameters
        ----------
        image_paths : ordered list of source frame paths (first = leftmost/topmost).
        output_path : destination PNG/WEBP path.
        hires_keyframes : optional mapping of {frame_idx: hires_path} (§9C Sprint 8).
            When provided, all heavy computation runs at proxy (1080p) resolution;
            after Stage 8 (ECC/SEA-RAFT refinement), the selected frames are
            replaced by their hires counterparts and affines are scaled accordingly.
            Frame indices not listed are bicubic-upscaled from the proxy.
            The final panorama is rendered at the hires resolution.

        Returns
        -------
        PIL.Image of the final stitched panorama.
        """
        # Exclude the output file if it was accidentally included in the input list.
        out_abs = os.path.abspath(output_path)
        image_paths = [p for p in image_paths if os.path.abspath(p) != out_abs]

        # §1.63: Sort frame paths by numeric suffix so glob-discovered frames are
        # always in temporal order, regardless of OS directory-entry order.
        image_paths = _sort_frames_by_index(image_paths)

        logger.info(
            f"[Stitch] Starting AnimeStitchPipeline on {len(image_paths)} frames."
        )
        self._baselines = None

        # ── §3.16B: Per-test HITL preset ─────────────────────────────────────
        _test_name = Path(image_paths[0]).parent.name if image_paths else ""
        _hitl_preset = load_hitl_preset(_test_name)
        _hitl_pipeline_state: dict = {}
        if _hitl_preset is not None:
            _hitl_pipeline_state = apply_hitl_preset(_hitl_pipeline_state, _hitl_preset)
            if _hitl_pipeline_state.get("force_scans"):
                logger.info(
                    f"[Stitch] §3.16B: HITL preset '{_test_name}' → force SCANS fallback."
                )
                frames_early = _load_frames(image_paths)
                return _scan_stitch_fallback(frames_early, output_path)
            if _hitl_pipeline_state.get("scroll_axis"):
                logger.info(
                    f"[Stitch] §3.16B: HITL preset '{_test_name}' → "
                    f"scroll_axis={_hitl_pipeline_state['scroll_axis']}."
                )

        # ── Stage 1: Load & trim ─────────────────────────────────────────────
        frames = _load_frames(image_paths)
        N = len(frames)
        if N < 2:
            raise PipelineError("Need at least 2 valid frames to stitch.")
        logger.info(f"[Stitch] Stage 1 complete: {N} frames loaded.")

        # ── Stage 1.5: §1.29 Static input detection gate ─────────────────────
        if _STATIC_INPUT_MAX_MAD > 0.0 and _detect_static_input(
            frames, _STATIC_INPUT_MAX_MAD
        ):
            logger.warning(
                f"[Stitch] Stage 1.5: static-input gate — all {N} frames are near-identical "
                f"(MAD < {_STATIC_INPUT_MAX_MAD:.1f}).  Copying frame 0 to output."
            )
            cv2.imwrite(output_path, frames[0])
            return output_path

        # ── Stage 2: Width normalisation ─────────────────────────────────────
        frames = _normalise_widths(frames)
        H, W = frames[0].shape[:2]
        scans_frames = (
            [] if _SCANS_RELOAD else list(frames)
        )  # §1.9C: omit snapshot when reload-on-demand is enabled
        logger.info(f"[Stitch] Stage 2 complete: all frames at {W}×{H}.")

        # ── Stage 3: BaSiC photometric correction ────────────────────────────
        if self.use_basic:
            if self._basic is None:
                self._basic = BaSiCWrapper()
            frames, baselines = _apply_basic(frames, self._basic)
            self._baselines = baselines
            frames = _correct_vignetting(frames)
            logger.info(
                "[Stitch] Stage 3 complete: BaSiC + Vignette correction applied."
            )
        else:
            logger.info("[Stitch] Stage 3 skipped (use_basic=False).")

        # ── Stage 4: Foreground masking ──────────────────────────────────────
        if self.use_birefnet and self._birefnet is None:
            from backend.src.models.wrappers.birefnet_wrapper import (
                BiRefNetWrapper,
            )  # §3.14 lazy

            self._birefnet = BiRefNetWrapper()
        bg_masks = _compute_fg_masks(
            frames,
            self._birefnet,
            use_birefnet=self.use_birefnet,
        )
        if self._birefnet is not None:
            try:
                self._birefnet.unload()
            except Exception:
                pass
            self._birefnet = None
        logger.debug(
            f"[Stitch] Stage 4 complete: foreground masks ready "
            f"({'BiRefNet' if self.use_birefnet else 'None'})."
        )

        # ── §1.37: Background pixel coverage fraction gate ───────────────────
        if _MIN_BG_FRACTION > 0.0:
            _bg_frac = _compute_bg_coverage_fraction(bg_masks)
            if _bg_frac < _MIN_BG_FRACTION:
                logger.info(
                    "[Stitch] §1.37: bg coverage fraction %.3f < %.3f — "
                    "fg-dominant scene, bg normalisation unreliable → SCANS fallback.",
                    _bg_frac,
                    _MIN_BG_FRACTION,
                )
                _sf = scans_frames or _reload_scans_frames(image_paths)
                return _scan_stitch_fallback(_sf, output_path)

        # ── Stage 4.5: Background-based photometric normalisation ────────────
        # Compute the per-frame mean background color (bg_mask > 127) and normalise
        # every frame to the same median background level.  This eliminates
        # frame-to-frame ambient lighting variation (anime cel flicker) which
        # would otherwise appear as horizontal color seams in the temporal median.
        bg_frame_means: List[Optional[np.ndarray]] = []
        for _i, (_frame, _mask) in enumerate(zip(frames, bg_masks)):
            if _mask is not None:
                _bg_px = _frame[_mask > 127].astype(np.float32)
                if len(_bg_px) >= 1000:
                    bg_frame_means.append(_bg_px.mean(axis=0))
                    continue
            bg_frame_means.append(None)

        _valid_means = [m for m in bg_frame_means if m is not None]
        if len(_valid_means) >= 3:
            _ref_mean = np.median(_valid_means, axis=0)  # (3,) BGR reference
            for _i in range(N):
                if bg_frame_means[_i] is None:
                    continue
                _gain = _ref_mean / np.maximum(bg_frame_means[_i], 1.0)
                _ref_lum_scalar = float(np.dot(_ref_mean, [0.114, 0.587, 0.299]))
                _gain_lo, _gain_hi = (
                    (0.80, 1.25) if _ref_lum_scalar < 80.0 else (0.88, 1.14)
                )
                _gain = np.clip(_gain, _gain_lo, _gain_hi)
                if not np.allclose(_gain, 1.0, atol=0.01):
                    frames[_i] = np.clip(
                        frames[_i].astype(np.float32) * _gain, 0, 255
                    ).astype(np.uint8)
            logger.debug(
                f"[Stitch] Stage 4.5 complete: background photometric normalisation "
                f"({len(_valid_means)}/{N} frames had sufficient background)."
            )

        # P2.6 — Per-segment photometric correction.
        # The global gain above applies one scalar per frame.  Anime assigns
        # different exposure levels to different colour regions (sky vs costume
        # vs background props), so a single gain is a poor approximation.
        # This pass refines correction at the connected-component level,
        # matching each background segment to the reference (frame 0) segment
        # with the closest colour, removing per-region flicker independently.
        _n_seg_corrected = 0
        for _i in range(1, N):
            if bg_masks[_i] is None:
                continue
            bm = bg_masks[_i] > 127
            if bm.sum() < 1000:
                continue
            # Quick color-region segmentation via quantization (no SAM needed)
            img_small = cv2.resize(
                frames[_i],
                (frames[_i].shape[1] // 4, frames[_i].shape[0] // 4),
                cv2.INTER_AREA,
            )
            flat = img_small.reshape(-1, 3).astype(np.float32)
            _, labels_flat, centers = cv2.kmeans(
                flat,
                min(8, len(np.unique(flat.reshape(-1)))),
                None,
                (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0),
                2,
                cv2.KMEANS_PP_CENTERS,
            )
            seg_map = labels_flat.reshape(img_small.shape[:2])
            seg_map_full = cv2.resize(
                seg_map.astype(np.uint8),
                (frames[_i].shape[1], frames[_i].shape[0]),
                cv2.INTER_NEAREST,
            )
            # Reference: frame 0 colour clusters
            img0_small = cv2.resize(
                frames[0], img_small.shape[:2][::-1], cv2.INTER_AREA
            )
            flat0 = img0_small.reshape(-1, 3).astype(np.float32)
            ref_centers = cv2.kmeans(
                flat0,
                min(8, len(np.unique(flat0.reshape(-1)))),
                None,
                (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0),
                2,
                cv2.KMEANS_PP_CENTERS,
            )[2]

            gain_map = np.ones(frames[_i].shape[:2], dtype=np.float32)
            for _k in range(int(seg_map_full.max()) + 1):
                _seg_px = (seg_map_full == _k) & bm
                if _seg_px.sum() < 200:
                    continue
                _seg_mean = frames[_i][_seg_px].astype(np.float32).mean(axis=0)  # (3,)
                # Find closest reference cluster by colour distance
                _dists = np.linalg.norm(ref_centers - _seg_mean[np.newaxis], axis=1)
                _ref_seg = ref_centers[int(np.argmin(_dists))]
                _gain_seg = np.clip(_ref_seg / np.maximum(_seg_mean, 1.0), 0.88, 1.12)
                gain_map[_seg_px] = _gain_seg.mean()

            frames[_i] = np.clip(
                frames[_i].astype(np.float32) * gain_map[..., np.newaxis], 0, 255
            ).astype(np.uint8)
            _n_seg_corrected += 1
        if _n_seg_corrected > 0:
            logger.debug(
                f"[Stitch] Stage 4.5b: per-segment photometric correction applied to {_n_seg_corrected} frames."
            )

        # ── Stage 4.7: §3.13 ProPainter background completion ───────────────
        # Replaces fg-masked pixels in every selected frame with a temporally
        # coherent background estimate.  Completed frames give Stage 5
        # (phase correlation) clean bg-only signal and give the Stage 10
        # temporal median complete bg coverage in every row.
        if _PROPAINTER:
            logger.info(
                "[Stitch] Stage 4.7: §3.13 ProPainter background completion — %d frames.",
                N,
            )
            _pp_device = os.environ.get("ASP_PROPAINTER_DEVICE", "cpu")
            frames = _propainter_complete_frames(frames, bg_masks, device=_pp_device)
            logger.debug(
                "[Stitch] Stage 4.7 complete: ProPainter background completion done."
            )

        # ── Pre-stage 5: Deduplicate near-static consecutive frames ─────────
        if N >= 3:
            _luma_cache = [
                cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.float32) for f in frames
            ]
            keep = [True] * N
            _prev_kept = 0
            for _fi in range(1, N):
                _la, _lb = _luma_cache[_fi], _luma_cache[_prev_kept]
                if _la.shape != _lb.shape:
                    # Different heights — cannot be duplicates; keep both
                    _prev_kept = _fi
                    continue
                diff = float(np.abs(_la - _lb).mean())
                if diff < NEAR_DUP_LUMA_THRESH:
                    keep[_fi] = False
                    logger.debug(
                        f"[Stitch]   Dedup: frame {_fi} ≈ frame {_prev_kept} "
                        f"(luma_diff={diff:.2f}) — dropped."
                    )
                else:
                    _prev_kept = _fi
            if not all(keep):
                keep_idx = [i for i, k in enumerate(keep) if k]
                frames = [frames[i] for i in keep_idx]
                scans_frames = (
                    [scans_frames[i] for i in keep_idx] if scans_frames else []
                )  # §1.9C
                bg_masks = [bg_masks[i] for i in keep_idx]
                image_paths = [image_paths[i] for i in keep_idx]
                N = len(frames)
                logger.debug(
                    f"[Stitch]   Dedup complete: {sum(not k for k in keep)} "
                    f"removed, {N} remain."
                )
                if N < 2:
                    _sf = scans_frames or _reload_scans_frames(image_paths)
                    return _scan_stitch_fallback(_sf, output_path)

        # ── Stage 5-6: Pairwise matching (+ skip-pair edges) ────────────────
        # ── Matcher selection (P1.4 EfficientLoFTR / P3.2 JamMa) ───────────────
        # Priority: JamMa (4K only) → EfficientLoFTR → kornia LoFTR → None.
        _is_4k = H * W > 3000 * 2000
        _active_loftr = None

        if self.use_jamma and _is_4k:
            try:
                from backend.src.models.wrappers.jamma_wrapper import JamMaWrapper  # §3.14 lazy

                _jamma_inst = JamMaWrapper()
                _jamma_inst.load_model()
                _active_loftr = _jamma_inst
                logger.info(f"[Stitch]   4K frame ({W}×{H}): using JamMa (O(N) Mamba).")
            except Exception as _jm_e:
                logger.info(
                    f"[Stitch]   JamMa unavailable ({_jm_e}); using EfficientLoFTR."
                )

        # P1.4 — Use EfficientLoFTR (2.5× faster) when available; fall back to
        # kornia LoFTR.  Both expose the same .match() interface.
        if _active_loftr is None and self.use_efficient_loftr:
            if self._eloftr is None:
                try:
                    from backend.src.models.wrappers.efficient_loftr_wrapper import (
                        EfficientLoFTRWrapper,
                    )  # §3.14 lazy

                    self._eloftr = EfficientLoFTRWrapper()
                    self._eloftr.load_model()
                    _active_loftr = self._eloftr
                    logger.info(
                        "[Stitch]   Using EfficientLoFTR (2.5× faster than LoFTR)."
                    )
                except Exception as _e:
                    logger.debug(
                        f"[Stitch]   EfficientLoFTR init failed ({_e}); falling back to LoFTR."
                    )
                    self.use_efficient_loftr = False
                    self._eloftr = None
            else:
                self._eloftr.load_model()
                _active_loftr = self._eloftr
        if _active_loftr is None and self.use_loftr:
            if self._loftr is None:
                from backend.src.models.wrappers.loftr_wrapper import LoFTRWrapper  # §3.14 lazy

                self._loftr = LoFTRWrapper()
            _active_loftr = self._loftr

        if self.use_aliked and self._aliked is None:
            try:
                from backend.src.models.wrappers.aliked_lg_wrapper import (
                    ALIKEDLightGlueWrapper,
                )  # §3.14 lazy

                self._aliked = ALIKEDLightGlueWrapper()
            except Exception as _e:
                logger.info(
                    f"[Stitch]   ALIKED+LightGlue init failed ({_e}); disabling."
                )
                self.use_aliked = False
                self._aliked = None
        if self.use_roma and self._roma is None:
            try:
                self._roma = RoMaWrapper()
            except Exception as _e:
                logger.info(f"[Stitch]   RoMa init failed ({_e}); disabling.")
                self.use_roma = False
                self._roma = None
        edges = _pairwise_match(
            frames,
            bg_masks,
            loftr_wrapper=_active_loftr,
            use_loftr=_active_loftr is not None,
            motion_model=self.motion_model,
            aliked_wrapper=self._aliked if self.use_aliked else None,
            roma_wrapper=self._roma if self.use_roma else None,
        )

        # ── Post-match: Spatial dedup of near-static consecutive frames ──────
        # Frames whose measured adj displacement is < SPATIAL_DEDUP_PX add no
        # meaningful new content and confuse BA (effective gap ≈ 0).  Run in a
        # loop so chains (A≈B≈C) are resolved in successive passes after
        # re-indexing turns a former skip-edge into an adj-edge.

        _total_spa_dropped = 0
        _spa_changed = True
        while _spa_changed:
            frames, scans_frames, bg_masks, image_paths, edges, _n_dropped = (
                _spatial_dedup_frames(
                    frames,
                    scans_frames,
                    bg_masks,
                    image_paths,
                    edges,
                    SPATIAL_DEDUP_PX,
                )
            )
            _spa_changed = _n_dropped > 0
            if _n_dropped:
                _total_spa_dropped += _n_dropped
                logger.debug(
                    f"[Stitch]   Spatial dedup pass: {_n_dropped} frame(s) dropped, "
                    f"{len(frames)} remain."
                )
                N = len(frames)
                if N < 2:
                    _sf = scans_frames or _reload_scans_frames(image_paths)
                    return _scan_stitch_fallback(_sf, output_path)
        if _total_spa_dropped:
            logger.debug(
                f"[Stitch]   Spatial dedup complete: {_total_spa_dropped} frames "
                f"removed, {N} remain."
            )

        edges = self._filter_edges(edges, image_paths, H, W, frames, bg_masks)

        # §3.16B: apply HITL drop_edges after filter
        if _hitl_pipeline_state.get("boundaries"):
            logger.info(
                f"[Stitch] §3.16B: HITL preset '{_test_name}' — "
                f"forced_boundaries={_hitl_pipeline_state['boundaries']}."
            )
        _preset_edges_state: dict = {}
        if _hitl_preset is not None and _hitl_preset.drop_edges:
            _preset_edges_state["edges"] = edges
            apply_hitl_preset(_preset_edges_state, _hitl_preset)
            edges = _preset_edges_state.get("edges", edges)
            logger.info(
                f"[Stitch] §3.16B: HITL preset '{_test_name}' — "
                f"dropped {len(_hitl_preset.drop_edges)} edges, {len(edges)} remain."
            )

        for _mdl in [self._loftr, self._eloftr, self._aliked, self._roma]:
            if _mdl is not None:
                try:
                    _mdl.unload()
                except Exception:
                    try:
                        _mdl.offload()
                    except Exception:
                        pass
        self._loftr = None
        self._eloftr = None
        self._aliked = None
        self._roma = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()
        logger.info(f"[Stitch] Stages 5-6 complete: {len(edges)} valid edges found.")
        if not edges:
            warnings.warn("[Stitch] No valid edges — falling back to scan stitch.")
            _sf = scans_frames or _reload_scans_frames(image_paths)
            return _scan_stitch_fallback(_sf, output_path)

        # ── §1.15: Edge graph connectivity gate ───────────────────────────────
        # A disconnected edge graph means BA will assign wrong translations to
        # isolated frames.  Detect and fall back to SCANS before the bad solve.
        if not _check_edge_graph_connectivity(edges, N):
            logger.info(
                "[Stitch] §1.15: Edge graph is disconnected (%d edges, %d frames) "
                "→ SCANS fallback.",
                len(edges),
                N,
            )
            _sf = scans_frames or _reload_scans_frames(image_paths)
            return _scan_stitch_fallback(_sf, output_path)

        # ── §1.16: MST weight gate ────────────────────────────────────────────
        # When the spanning tree is dominated by low-confidence TM/PC fallback
        # edges, BA is unlikely to produce reliable translations.  The check is
        # O(E log E) and free for N ≤ 40.
        if _MST_MIN_WEIGHT > 0.0:
            _mst_w = _compute_mst_weight(edges, N)
            if _mst_w < _MST_MIN_WEIGHT:
                logger.info(
                    "[Stitch] §1.16: MST mean weight %.3f < %.3f threshold "
                    "→ SCANS fallback (low-confidence edge graph).",
                    _mst_w,
                    _MST_MIN_WEIGHT,
                )
                _sf = scans_frames or _reload_scans_frames(image_paths)
                return _scan_stitch_fallback(_sf, output_path)

        # ── §1.67: Frame canvas spread validation ─────────────────────────────
        # Verifies that the raw pairwise translations span at least
        # _CANVAS_SPREAD_MIN of the expected full-canvas range before BA runs.
        # Catches clustered frame sets that cannot produce good coverage.
        if _CANVAS_SPREAD_MIN > 0.0:
            if not _check_canvas_spread(edges, _CANVAS_SPREAD_MIN):
                logger.info(
                    "[Stitch] §1.67: canvas spread < %.0f%% of expected range "
                    "— selected frames cluster at one end of scroll → SCANS fallback.",
                    _CANVAS_SPREAD_MIN * 100,
                )
                _sf = scans_frames or _reload_scans_frames(image_paths)
                return _scan_stitch_fallback(_sf, output_path)

        # ── §1.43: Adjacent edge coverage ratio gate ──────────────────────────
        if _ADJ_COVERAGE_MIN > 0.0:
            _adj_cov = _compute_adj_edge_coverage(edges, N)
            if _adj_cov < _ADJ_COVERAGE_MIN:
                logger.info(
                    "[Stitch] §1.43: adjacent edge coverage %.2f < %.2f "
                    "(%d of %d adjacent pairs have edges) → SCANS fallback.",
                    _adj_cov,
                    _ADJ_COVERAGE_MIN,
                    round(_adj_cov * max(1, N - 1)),
                    max(1, N - 1),
                )
                _sf = scans_frames or _reload_scans_frames(image_paths)
                return _scan_stitch_fallback(_sf, output_path)

        # ── §1.49: Adjacent edge minimum weight gate ──────────────────────────
        if _ADJ_MIN_WEIGHT > 0.0:
            _adj_min_w = _compute_adj_min_weight(edges)
            if _adj_min_w < _ADJ_MIN_WEIGHT:
                logger.info(
                    "[Stitch] §1.49: adjacent edge min weight %.3f < %.3f "
                    "— at least one adjacent pair has near-zero confidence "
                    "(compositing seam would be ill-placed) → SCANS fallback.",
                    _adj_min_w,
                    _ADJ_MIN_WEIGHT,
                )
                _sf = scans_frames or _reload_scans_frames(image_paths)
                return _scan_stitch_fallback(_sf, output_path)

        # ── §1.47: Adjacent displacement sign consistency gate ────────────────
        if _SIGN_INCONSISTENCY_MAX > 0.0:
            _sign_rate = _compute_sign_inconsistency_rate(edges)
            if _sign_rate > _SIGN_INCONSISTENCY_MAX:
                logger.info(
                    "[Stitch] §1.47: sign inconsistency rate %.2f > %.2f "
                    "— %.0f%% of adjacent edges oppose the majority scroll direction "
                    "→ SCANS fallback.",
                    _sign_rate,
                    _SIGN_INCONSISTENCY_MAX,
                    _sign_rate * 100,
                )
                _sf = scans_frames or _reload_scans_frames(image_paths)
                return _scan_stitch_fallback(_sf, output_path)

        # ── §1.48: Adjacent displacement magnitude CV gate ────────────────────
        if _ADJ_DISP_CV_MAX > 0.0:
            _disp_cv = _compute_adj_disp_cv(edges)
            if _disp_cv > _ADJ_DISP_CV_MAX:
                logger.info(
                    "[Stitch] §1.48: adjacent displacement CV %.3f > %.3f "
                    "— dominant-axis magnitudes have high spread (possible "
                    "wrong-harmonic or non-adjacent PC/TM match) → SCANS fallback.",
                    _disp_cv,
                    _ADJ_DISP_CV_MAX,
                )
                _sf = scans_frames or _reload_scans_frames(image_paths)
                return _scan_stitch_fallback(_sf, output_path)

        # ── Stage 7: Global bundle adjustment ────────────────────────────────
        use_affine_ba = getattr(self, "motion_model", "affine") == "affine"
        affines = _bundle_adjust_affine(edges, N, use_affine=use_affine_ba)
        logger.debug(
            f"[Stitch] Stage 7 complete: bundle adjustment done "
            f"(mode={'affine' if use_affine_ba else 'translation'})."
        )

        # ── §1.50: BA max residual gate ───────────────────────────────────────
        if _BA_RESIDUAL_MAX > 0.0:
            _ba_res = _compute_ba_max_residual(edges, affines)
            if _ba_res > _BA_RESIDUAL_MAX:
                logger.info(
                    "[Stitch] §1.50: BA max residual %.1f px > %.1f px threshold "
                    "— at least one edge is wildly inconsistent with the solved "
                    "frame placement (Category B outlier) → SCANS fallback.",
                    _ba_res,
                    _BA_RESIDUAL_MAX,
                )
                _sf = scans_frames or _reload_scans_frames(image_paths)
                return _scan_stitch_fallback(_sf, output_path)

        # ── §1.52: BA weighted mean residual gate ─────────────────────────────
        if _BA_WMEAN_RESIDUAL_MAX > 0.0:
            _ba_wmean = _compute_ba_weighted_mean_residual(edges, affines)
            if _ba_wmean > _BA_WMEAN_RESIDUAL_MAX:
                logger.info(
                    "[Stitch] §1.52: BA weighted mean residual %.1f px > %.1f px threshold "
                    "— systematic drift across all edges (biased BA solution) "
                    "→ SCANS fallback.",
                    _ba_wmean,
                    _BA_WMEAN_RESIDUAL_MAX,
                )
                _sf = scans_frames or _reload_scans_frames(image_paths)
                return _scan_stitch_fallback(_sf, output_path)

        # ── §1.55: BA affine rotation gate ───────────────────────────────────
        if _MAX_AFFINE_ROTATION_DEG > 0.0:
            _max_rot_deg = _compute_max_affine_rotation_deg(affines)
            if _max_rot_deg > _MAX_AFFINE_ROTATION_DEG:
                logger.info(
                    "[Stitch] §1.55: max affine rotation %.2f° > %.2f° threshold "
                    "— a BA-solved affine contains a significant rotation component, "
                    "indicating the feature matcher latched onto a rotationally-"
                    "similar texture patch → SCANS fallback.",
                    _max_rot_deg,
                    _MAX_AFFINE_ROTATION_DEG,
                )
                _sf = scans_frames or _reload_scans_frames(image_paths)
                return _scan_stitch_fallback(_sf, output_path)

        # ── §3.16: Trajectory smoother (StabStitch++ simplified) ─────────────
        # Gaussian 1D smooth on tx/ty sequences to suppress phase-correlation
        # jitter in non-linear or multi-axis scroll captures.  Fires only when
        # the IQR of adjacent-step magnitudes exceeds _TRAJ_SMOOTH_IQR_THRESH.
        if _TRAJ_SMOOTH_SIGMA > 0.0:
            affines, _traj_smoothed = _smooth_affine_trajectory(
                affines,
                sigma=_TRAJ_SMOOTH_SIGMA,
                iqr_threshold=_TRAJ_SMOOTH_IQR_THRESH,
            )
            if _traj_smoothed:
                logger.info(
                    "[Stitch] §3.16: trajectory smoother applied (σ=%.1f frames, "
                    "IQR threshold=%.1f px) — tx/ty sequences Gaussian-smoothed "
                    "to suppress phase-correlation jitter.",
                    _TRAJ_SMOOTH_SIGMA,
                    _TRAJ_SMOOTH_IQR_THRESH,
                )

        # ── §4.3: Wave correction (post-BA cross-axis drift removal) ─────────
        if _WAVE_CORRECT:
            affines = _wave_correct_affines(affines, axis=_WAVE_CORRECT)
            logger.info(
                "[Stitch] §4.3: wave correction applied (axis=%s) — "
                "linear tx/ty drift removed from BA affines.",
                _WAVE_CORRECT,
            )

        # ── Stage 7b: Affine validation gate ─────────────────────────────────
        # §0.5C: adaptive min_gap — scales with canvas span so fast-scroll
        # (4K, >400 px/frame) applies a proportionally higher floor than the
        # fixed 25 px default, while slow-scroll sequences use 20 px.
        _adaptive_min_gap = _compute_adaptive_min_gap(affines)
        _adaptive_rot, _adaptive_sc = _compute_adaptive_rot_scale(affines)
        health = _validate_affines(
            affines,
            min_step=_adaptive_min_gap,
            max_rotation=_adaptive_rot,
            max_scale_dev=_adaptive_sc,
        )
        logger.debug(
            f"[Stitch]   Affine health: valid={health.valid}, "
            f"ratio={health.ratio:.1f}×, min_gap={health.min_gap:.0f}px "
            f"(adaptive_floor={_adaptive_min_gap:.1f}px), "
            f"max_rot={health.max_rotation:.4f} (thresh={_adaptive_rot:.2f}), "
            f"scale_dev={health.max_scale_dev:.4f} (thresh={_adaptive_sc:.2f})"
        )
        if not health.valid:
            logger.debug(
                f"[Stitch]   Affine health FAILED ({health.reason}); attempting recovery..."
            )
            # Retry 0: §2.9C — high-confidence-only re-solve (ratio failures only).
            # Low-confidence TM/PC fallback edges (weight 0.15–0.55) can corrupt BA
            # when a single bad edge pulls two frames together → inflated ratio.
            # Filter to LoFTR-quality edges (weight ≥ HIGH_CONF_EDGE_THRESH) and
            # re-solve if enough survive.  Falls through to Retry 1 if not.
            if health.reason.startswith("ratio="):
                _hc_edges = _filter_high_conf_edges(edges)
                if len(_hc_edges) >= N - 1:
                    _affines_r0 = _bundle_adjust_affine(
                        _hc_edges, N, use_affine=use_affine_ba
                    )
                    _health_r0 = _validate_affines(
                        _affines_r0,
                        min_step=_adaptive_min_gap,
                        max_rotation=_adaptive_rot,
                        max_scale_dev=_adaptive_sc,
                    )
                    logger.debug(
                        f"[Stitch]   Retry 0 (high-conf edges, {len(_hc_edges)} edges): "
                        f"valid={_health_r0.valid}, {_health_r0.reason}"
                    )
                    if _health_r0.valid:
                        affines, health = _affines_r0, _health_r0

            # Retry 1: consecutive-only bundle — skip edges sometimes corrupt the solution
            _adj_only = [e for e in edges if e["j"] == e["i"] + 1]
            if len(_adj_only) >= N - 1:
                affines_r1 = _bundle_adjust_affine(
                    _adj_only, N, use_affine=use_affine_ba
                )
                health_r1 = _validate_affines(affines_r1)
                logger.debug(
                    f"[Stitch]   Retry 1 (adj-only bundle): "
                    f"valid={health_r1.valid}, {health_r1.reason}"
                )
                if health_r1.valid:
                    affines, health = affines_r1, health_r1
            # Retry 2: smart sequential integration with gap-filling
            if not health.valid:
                _adj_only_r2 = [e for e in edges if e["j"] == e["i"] + 1]
                # Consensus step for interpolation/extrapolation of isolated frames
                _step_dx = (
                    float(np.median([float(e["M"][0, 2]) for e in _adj_only_r2]))
                    if _adj_only_r2
                    else 0.0
                )
                _step_dy = (
                    float(np.median([float(e["M"][1, 2]) for e in _adj_only_r2]))
                    if _adj_only_r2
                    else 0.0
                )
                # Frames that have an adj edge pointing to them
                _has_adj_src = {e["j"] for e in _adj_only_r2}

                _seq = [np.eye(2, 3, dtype=np.float32) for _ in range(N)]
                _anchored: set = {0}

                # Pass 1: greedy — for each frame use the shortest-span edge from an anchored frame
                for _f in range(1, N):
                    _best_e, _best_span = None, float("inf")
                    for _e in edges:
                        if _e["j"] == _f and _e["i"] in _anchored:
                            if _f - _e["i"] < _best_span:
                                _best_span = _f - _e["i"]
                                _best_e = _e
                    if _best_e is not None:
                        _seq[_f][0, 2] = _seq[_best_e["i"]][0, 2] - float(
                            _best_e["M"][0, 2]
                        )
                        _seq[_f][1, 2] = _seq[_best_e["i"]][1, 2] - float(
                            _best_e["M"][1, 2]
                        )
                        _anchored.add(_f)

                # Pass 2: fill frames with no adj edge via interpolation or velocity extrapolation
                for _uf in sorted(i for i in range(N) if i not in _anchored):
                    if _uf in _has_adj_src:
                        continue  # will be chained in Pass 3
                    _lft = max((a for a in _anchored if a < _uf), default=None)
                    _rgt = min((a for a in _anchored if a > _uf), default=None)
                    if _lft is not None and _rgt is not None:
                        _t = (_uf - _lft) / (_rgt - _lft)
                        _seq[_uf][0, 2] = (
                            _seq[_lft][0, 2] * (1 - _t) + _seq[_rgt][0, 2] * _t
                        )
                        _seq[_uf][1, 2] = (
                            _seq[_lft][1, 2] * (1 - _t) + _seq[_rgt][1, 2] * _t
                        )
                    elif _lft is not None:
                        _n = _uf - _lft
                        _seq[_uf][0, 2] = _seq[_lft][0, 2] - _n * _step_dx
                        _seq[_uf][1, 2] = _seq[_lft][1, 2] - _n * _step_dy
                    _anchored.add(_uf)

                # Pass 3: propagate through adj/skip edges from newly-anchored gap frames
                _chg = True
                while _chg:
                    _chg = False
                    for _f in range(1, N):
                        if _f in _anchored:
                            continue
                        _best_e, _best_span = None, float("inf")
                        for _e in edges:
                            if _e["j"] == _f and _e["i"] in _anchored:
                                if _f - _e["i"] < _best_span:
                                    _best_span = _f - _e["i"]
                                    _best_e = _e
                        if _best_e is not None:
                            _seq[_f][0, 2] = _seq[_best_e["i"]][0, 2] - float(
                                _best_e["M"][0, 2]
                            )
                            _seq[_f][1, 2] = _seq[_best_e["i"]][1, 2] - float(
                                _best_e["M"][1, 2]
                            )
                            _anchored.add(_f)
                            _chg = True

                health_r2 = _validate_affines(_seq)
                logger.debug(
                    f"[Stitch]   Retry 2 (sequential+fill): "
                    f"valid={health_r2.valid}, {health_r2.reason}"
                )
                if health_r2.valid:
                    affines, health = _seq, health_r2
                else:
                    # Retry 3: accept with relaxed min_gap when ratio is still healthy
                    health_r3 = _validate_affines(_seq, min_step=20.0)
                    if health_r3.valid:
                        logger.debug(
                            f"[Stitch]   Retry 3 (relaxed min_gap=20px): "
                            f"valid={health_r3.valid}, {health_r3.reason}"
                        )
                        affines, health = _seq, health_r3
            if not health.valid:
                # §1.3B: PANORAMA stitcher handles scale/rotation that
                # translation-only validation rejects; try before SCANS.
                try:
                    _sf = scans_frames or _reload_scans_frames(image_paths)
                    return _panorama_stitch_fallback(_sf, output_path)
                except Exception as _pano_e:
                    logger.info(
                        f"[Stitch]   PANORAMA fallback failed ({_pano_e}); using SCANS."
                    )
                warnings.warn(
                    f"[Stitch] Affine validation FAILED ({health.reason}) after retries. "
                    f"Falling back to SCANS stitch."
                )
                _sf = scans_frames or _reload_scans_frames(image_paths)
                return _scan_stitch_fallback(_sf, output_path)

        # ── Stage 8: Sub-pixel refinement ────────────────────────────────────
        # P2.1 — SEA-RAFT replaces ECC when available.  ECC fails on flat anime
        # cells (near-zero gradients → singular Hessian).  SEA-RAFT uses learned
        # cost volumes that remain informative over uniform colour regions.
        if self.use_sea_raft:
            try:
                if self._sea_raft is None:
                    _dev = "cuda" if torch.cuda.is_available() else "cpu"
                    self._sea_raft = _load_sea_raft(device=_dev)
                    logger.info("[Stitch]   SEA-RAFT model loaded.")
                affines = _flow_refine(
                    frames,
                    affines,
                    bg_masks,
                    device="cuda" if torch.cuda.is_available() else "cpu",
                    raft_model=self._sea_raft,
                )
                logger.info("[Stitch] Stage 8 complete: SEA-RAFT flow refinement done.")
                # Offload SEA-RAFT after use
                if torch.cuda.is_available():
                    try:
                        self._sea_raft.cpu()
                    except Exception:
                        pass
                    torch.cuda.empty_cache()
                    self._sea_raft = None
            except Exception as _ecc_e:
                logger.info(
                    f"[Stitch]   SEA-RAFT failed ({_ecc_e}); falling back to ECC."
                )
                if self.use_ecc:
                    affines = _ecc_refine(frames, affines, bg_masks)
                    logger.info(
                        "[Stitch] Stage 8 complete: ECC refinement done (fallback)."
                    )
        elif self.use_ecc:
            affines = _ecc_refine(frames, affines, bg_masks)
            logger.info("[Stitch] Stage 8 complete: ECC refinement done.")
        else:
            logger.info("[Stitch] Stage 8 skipped (use_ecc=False, use_sea_raft=False).")

        # ── Stage 8.8: Hires keyframe substitution (§9C — Sprint 8) ────────
        # All heavy computation above ran on proxy (1080p) frames. If the caller
        # provided hires_keyframes, swap in the full-resolution images now and
        # scale the locked affines so Stage 9 (canvas) operates at hires resolution.
        if hires_keyframes:
            _n_hires, frames, affines, bg_masks = _apply_hires_keyframes(
                frames, affines, bg_masks, hires_keyframes
            )
            if _n_hires > 0:
                logger.info(
                    f"[Stitch] Stage 8.8: substituted {_n_hires} hires frame(s); "
                    f"canvas will render at {frames[0].shape[1]}×{frames[0].shape[0]} px."
                )
            else:
                logger.warning(
                    "[Stitch] Stage 8.8: hires_keyframes provided but no valid paths "
                    "could be loaded — continuing at proxy resolution."
                )

        # ── Stage 9: Canvas construction ────────────────────────────────────
        canvas_h, canvas_w, T_global = _compute_canvas(frames, affines)
        logger.info(f"[Stitch] Stage 9: canvas size {canvas_w}×{canvas_h}.")
        if canvas_h <= 0 or canvas_w <= 0:
            raise CanvasError("Computed canvas has zero size.")

        for i in range(N):
            affines[i][0, 2] += T_global[0]
            affines[i][1, 2] += T_global[1]

        # P1.9 — Bidirectional midplane projection (StabStitch++).
        # Centres the affine coordinate system on the temporal midplane rather
        # than anchoring everything to frame 0.  For long pans (e.g. 14 frames,
        # 150px/step) this halves the maximum per-frame distortion distance,
        # reducing warp artefacts symmetrically across the sequence.
        T_mid_x = float(np.mean([a[0, 2] for a in affines]))
        T_mid_y = float(np.mean([a[1, 2] for a in affines]))
        for i in range(N):
            affines[i][0, 2] -= T_mid_x
            affines[i][1, 2] -= T_mid_y
        # Recompute canvas after midplane shift so T_global absorbs the offset.
        canvas_h, canvas_w, T_global2 = _compute_canvas(frames, affines)
        for i in range(N):
            affines[i][0, 2] += T_global2[0]
            affines[i][1, 2] += T_global2[1]
        logger.debug(
            f"[Stitch] Stage 9 complete: midplane shift ({T_mid_x:.1f}, {T_mid_y:.1f}), "
            f"canvas {canvas_w}×{canvas_h}."
        )

        # ── §1.53: Canvas memory size gate ───────────────────────────────────
        if _CANVAS_MAX_MEMORY_MB > 0.0:
            _canvas_mb = _compute_canvas_memory_mb(canvas_h, canvas_w)
            if _canvas_mb > _CANVAS_MAX_MEMORY_MB:
                logger.info(
                    "[Stitch] §1.53: canvas %dx%d would require ~%.0f MB (float32 RGB) "
                    "> %.0f MB limit — pre-empting OOM → SCANS fallback.",
                    canvas_w,
                    canvas_h,
                    _canvas_mb,
                    _CANVAS_MAX_MEMORY_MB,
                )
                _sf = scans_frames or _reload_scans_frames(image_paths)
                return _scan_stitch_fallback(_sf, output_path)

        # §3.14 — Scroll axis classification (logged; horizontal → SCANS fallback).
        # Compositing assumes vertical strips; horizontal scroll produces garbled output
        # without a full horizontal-strip compositing mode (not yet implemented).
        scroll_axis = _detect_scroll_axis(affines)
        logger.info(f"[Stitch] Stage 9.5: scroll axis = '{scroll_axis}'.")
        if scroll_axis == "horizontal":
            if _HORIZONTAL_COMPOSITE:
                logger.info(
                    "[Stitch] §3.14B: Horizontal scroll — horizontal-composite mode enabled; "
                    "continuing pipeline (temporal median + canvas-return composite)."
                )
            else:
                logger.info(
                    "[Stitch] Horizontal scroll (tx_range >> ty_range) — vertical-strip "
                    "compositing not applicable; falling back to SCANS."
                )
                return _scan_stitch_fallback(scans_frames, output_path)

        # ── §4.7: dy_cv pre-detection gate ───────────────────────────────────
        # When step-size CV is high the scroll is too irregular for ARAP/seam
        # compositing — SCANS trivially handles these sequences.
        if _DY_CV_MAX > 0.0:
            _dy_cv_gate = _compute_dy_cv(affines)
            _dy_cv_adaptive_max = _compute_adaptive_dy_cv_max(N, _DY_CV_MAX)
            if _dy_cv_gate >= _dy_cv_adaptive_max:
                logger.info(
                    "[Stitch] §4.7/§5.8: dy_cv=%.3f ≥ %.2f (irregular scroll, N=%d) "
                    "→ SCANS fallback (ASP seam routing degrades severely at high dy_cv).",
                    _dy_cv_gate,
                    _dy_cv_adaptive_max,
                    N,
                )
                _sf = scans_frames or _reload_scans_frames(image_paths)
                return _scan_stitch_fallback(_sf, output_path)

        # ── §1.17: Canvas span utilisation gate ──────────────────────────────
        if _CANVAS_SPAN_MIN_UTIL > 0.0:
            _span_util = _compute_canvas_span_utilization(affines)
            if _span_util < _CANVAS_SPAN_MIN_UTIL:
                logger.info(
                    "[Stitch] §1.17: Canvas span utilisation %.2f < %.2f threshold "
                    "→ SCANS fallback (BA collapsed canvas).",
                    _span_util,
                    _CANVAS_SPAN_MIN_UTIL,
                )
                _sf = scans_frames or _reload_scans_frames(image_paths)
                return _scan_stitch_fallback(_sf, output_path)

        # ── §1.44: Maximum adjacent frame gap gate ────────────────────────────
        if _MAX_ADJACENT_GAP_PX > 0.0:
            _max_adj_gap = _compute_max_adjacent_gap(affines, frames)
            if _max_adj_gap > _MAX_ADJACENT_GAP_PX:
                logger.info(
                    "[Stitch] §1.44: max adjacent frame gap %.1f px > %.1f px threshold "
                    "— BA stretched consecutive frames apart → SCANS fallback.",
                    _max_adj_gap,
                    _MAX_ADJACENT_GAP_PX,
                )
                _sf = scans_frames or _reload_scans_frames(image_paths)
                return _scan_stitch_fallback(_sf, output_path)

        # ── §1.51: Minimum adjacent frame overlap gate ───────────────────────
        if _MIN_ADJACENT_OVERLAP_PX > 0.0:
            _min_ovlp = _compute_min_adjacent_overlap(affines, frames)
            if _min_ovlp < _MIN_ADJACENT_OVERLAP_PX:
                logger.info(
                    "[Stitch] §1.51: min adjacent frame overlap %.1f px < %.1f px floor "
                    "— at least one consecutive pair has too narrow a blend zone "
                    "for reliable DP seam cutting → SCANS fallback.",
                    _min_ovlp,
                    _MIN_ADJACENT_OVERLAP_PX,
                )
                _sf = scans_frames or _reload_scans_frames(image_paths)
                return _scan_stitch_fallback(_sf, output_path)

        # ── §1.45: Canvas width ratio gate ───────────────────────────────────
        if _MAX_CANVAS_WIDTH_RATIO > 0.0:
            _cw_ratio = _compute_canvas_width_ratio(canvas_w, frames)
            if _cw_ratio > _MAX_CANVAS_WIDTH_RATIO:
                logger.info(
                    "[Stitch] §1.45: canvas width %.0fpx is %.2f× median frame width "
                    "(threshold %.2f×) — BA tx drift produced oversized canvas "
                    "→ SCANS fallback.",
                    canvas_w,
                    _cw_ratio,
                    _MAX_CANVAS_WIDTH_RATIO,
                )
                _sf = scans_frames or _reload_scans_frames(image_paths)
                return _scan_stitch_fallback(_sf, output_path)

        # ── §1.62: Canvas aspect-ratio sanity gate ────────────────────────────
        if _MIN_CANVAS_ASPECT > 0.0:
            _aspect = _compute_canvas_aspect_ratio(canvas_h, canvas_w)
            # Only fire for nominally vertical-scroll sequences (ty_span > tx_span)
            # to avoid false-positives on mixed-scroll or short sequences.
            _tys_asp = [float(affines[_i][1, 2]) for _i in range(N)]
            _txs_asp = [float(affines[_i][0, 2]) for _i in range(N)]
            _ty_span_asp = max(_tys_asp) - min(_tys_asp)
            _tx_span_asp = max(_txs_asp) - min(_txs_asp)
            if _ty_span_asp > _tx_span_asp and _aspect < _MIN_CANVAS_ASPECT:
                logger.info(
                    "[Stitch] §1.62: canvas aspect ratio %.2f (h=%d, w=%d) "
                    "< %.2f floor — BA drift produced landscape-orientation canvas "
                    "for a vertical-scroll sequence → SCANS fallback.",
                    _aspect,
                    canvas_h,
                    canvas_w,
                    _MIN_CANVAS_ASPECT,
                )
                _sf = scans_frames or _reload_scans_frames(image_paths)
                return _scan_stitch_fallback(_sf, output_path)

        # P1.3 — Compute per-frame matching confidence for weighted median (W3).
        # Each frame's confidence = the maximum edge weight of its adjacent edges.
        # LoFTR edges have weight ~0.9; TM/PC fallbacks have 0.15–0.55.
        # Frame 0 is always the anchor (confidence 1.0 by convention).
        _frame_confs = np.ones(N, dtype=np.float32)
        for _e in edges:
            _fi, _fj, _w = _e["i"], _e["j"], float(_e.get("weight", 1.0))
            if _e["j"] == _e["i"] + 1:  # only adjacent edges for per-frame confidence
                _frame_confs[_fi] = max(_frame_confs[_fi], _w)
                _frame_confs[_fj] = max(_frame_confs[_fj], _w)
        _frame_confs = np.clip(_frame_confs, 0.0, 1.0)

        # ── Stage 9.5: Alignment stability gate ─────────────────────────────
        # Log severe 2D motion but only abort at a very high threshold — the
        # render gate (in the calling benchmark) uses a SCANS-relative comparison
        # and catches genuinely degraded composites regardless of motion pattern.
        # Hard-abort threshold raised to 200px (was 50px); scenes with horizontal
        # drift up to ~2 frame-widths can still produce acceptable composites.
        # Override: ASP_ALIGN_GATE_DX env var (default 200; set to 50 to restore
        # the old strict behaviour; set to 9999 to disable entirely).
        try:
            _align_dx_limit = float(os.environ.get("ASP_ALIGN_GATE_DX", "200"))
        except ValueError:
            _align_dx_limit = 200.0
        _txs_gate = [float(affines[i][0, 2]) for i in range(N)]
        _dx_gate = [abs(_txs_gate[i + 1] - _txs_gate[i]) for i in range(N - 1)]
        if _dx_gate:
            _dx_p75 = float(np.percentile(_dx_gate, 75))
            if _dx_p75 > _align_dx_limit:
                logger.info(
                    f"[Stitch] Alignment stability gate: 75th-pct |dx|={_dx_p75:.1f}px "
                    f"> {_align_dx_limit:.0f}px limit — extreme 2D motion, "
                    f"falling back to SCANS."
                )
                return _scan_stitch_fallback(scans_frames, output_path)

        # ── Stage 10: Temporal renderer ─────────────────────────────────────
        # P1.2 — Variable-step renderer switch (W2 fix for test16).
        # When step-size variance is high (dy_cv > 0.20), the temporal median
        # blurs in proportion to overlap inconsistency across frames.  Switching
        # to 'first' (first-frame-wins per canvas pixel) avoids cross-frame
        # averaging at boundary zones and matches what SCANS naturally produces.
        effective_renderer = self.renderer
        if self.renderer == "median" and N >= 3:
            _dy_steps = [
                abs(float(affines[k][1, 2]) - float(affines[k - 1][1, 2]))
                for k in range(1, N)
            ]
            _mean_dy = float(np.mean(_dy_steps)) if _dy_steps else 1.0
            _dy_cv = float(np.std(_dy_steps)) / max(_mean_dy, 1.0) if _dy_steps else 0.0
            if _dy_cv > 0.20:
                effective_renderer = "first"
                logger.debug(
                    f"[Stitch]   High step variance (dy_cv={_dy_cv:.3f} > 0.20) — "
                    f"switching renderer to 'first'."
                )

        canvas, valid_mask, warped_corr, warped_fgs = _render(
            frames,
            affines,
            bg_masks,
            canvas_h,
            canvas_w,
            renderer=effective_renderer,
            baselines=self._baselines,
            confidence_weights=_frame_confs,
        )
        logger.info("[Stitch] Stage 10 complete: temporal render done.")

        # ── Stage 10.2: Background zero-coverage fill (§5A/C) ────────────────
        # Pixels where valid_mask==0 were never covered by a background sample.
        # When ASP_BG_COMPLETE=1, fill with nearest-neighbour column propagation.
        # When ASP_BG_COMPLETE=2, attempt ProPainter inpainting first.
        if _BG_COMPLETE > 0:
            canvas = complete_background(
                canvas, valid_mask, use_propainter=(_BG_COMPLETE >= 2)
            )
            logger.info("[Stitch] Stage 10.2: background zero-coverage fill applied.")

        # ── §1.39: Render canvas coverage fraction gate ───────────────────────
        if _RENDER_MIN_COVERAGE > 0.0:
            _render_cov = _compute_render_coverage(valid_mask)
            if _render_cov < _RENDER_MIN_COVERAGE:
                logger.info(
                    "[Stitch] §1.39: render coverage %.3f < %.3f — "
                    "affines placed frames in too small a canvas region → SCANS fallback.",
                    _render_cov,
                    _RENDER_MIN_COVERAGE,
                )
                _sf = scans_frames or _reload_scans_frames(image_paths)
                return _scan_stitch_fallback(_sf, output_path)

        # ── §1.54: Render luminance std gate ─────────────────────────────────
        if _RENDER_LUMA_STD_MIN > 0.0:
            _luma_std = _compute_render_luma_std(canvas, valid_mask)
            if _luma_std < _RENDER_LUMA_STD_MIN:
                logger.info(
                    "[Stitch] §1.54: render luminance std %.2f < %.2f — "
                    "valid pixels have near-uniform luminance (degenerate render: "
                    "BaSiC over-correction, warp collapse, or hold-block leakage) "
                    "→ SCANS fallback.",
                    _luma_std,
                    _RENDER_LUMA_STD_MIN,
                )
                _sf = scans_frames or _reload_scans_frames(image_paths)
                return _scan_stitch_fallback(_sf, output_path)

        # ── Stage 10.5: Multi-frame canvas coverage gate (§0 item 2) ─────────
        # For each canvas row count how many frames contribute content.
        # If < ASP_COV_MIN_MULTI_PCT (default 30%) of content rows have ≥2-frame
        # coverage, the temporal median is effectively "first-frame-wins" across
        # the entire canvas — it cannot suppress animation ghosting.  Composite
        # on such a canvas would amplify ghosting rather than remove it.
        # Conservative default (30%) avoids false positives while catching truly
        # degenerate selections (e.g., 2 widely-spaced frames in a tall canvas).
        _row_cov, _pct_cov_multi, _cov_median = _compute_row_coverage(
            affines, frames, canvas_h
        )
        _n_cov_total = int((_row_cov > 0).sum())
        _n_cov_multi = (
            int((_row_cov[_row_cov > 0] >= 2).sum()) if _n_cov_total > 0 else 0
        )
        logger.info(
            f"[Stitch] Stage 10.5: coverage — "
            f"{_n_cov_multi}/{_n_cov_total} rows ({_pct_cov_multi:.0%}) "
            f"have ≥2-frame coverage; median={_cov_median:.1f}"
        )
        if _n_cov_total > 0:
            try:
                _cov_min_pct = float(os.environ.get("ASP_COV_MIN_MULTI_PCT", "0.30"))
            except ValueError:
                _cov_min_pct = 0.30
            if _pct_cov_multi < _cov_min_pct:
                logger.info(
                    f"[Stitch] Stage 10.5: coverage gate — {_pct_cov_multi:.0%} < "
                    f"{_cov_min_pct:.0%} threshold, temporal median insufficient "
                    f"for deghosting → SCANS fallback."
                )
                return _scan_stitch_fallback(scans_frames, output_path)

        # ── Stage 10.8: §1.71 pre-composite background luminance spread gate ───
        # Fires when the per-frame background luma range is so large that the
        # sequential gain normalisation in Stage 11 would require >2× corrections
        # on some frames, producing a brightness staircase across the composite.
        if _BG_LUM_SPREAD_MAX > 0.0:
            _bg_spread = _compute_bg_lum_spread(frames, bg_masks)
            if _bg_spread > _BG_LUM_SPREAD_MAX:
                logger.info(
                    "[Stitch] Stage 10.8: §1.71 bg-luma spread %.1f > %.1f "
                    "→ gain normalisation unreliable → SCANS fallback.",
                    _bg_spread,
                    _BG_LUM_SPREAD_MAX,
                )
                _sf = scans_frames or _reload_scans_frames(image_paths)
                return _scan_stitch_fallback(_sf, output_path)

        # ── Stage 10.9: §1.73 bg-gain monotonicity drift gate ───────────────
        # A gradual monotonic luma drift (every frame slightly darker/brighter
        # than the previous) produces a brightness staircase in the composite
        # even when the total spread is within §1.71's threshold.  Kendall-τ
        # ≈ 1 indicates a perfectly sorted sequence — SCANS is cleaner.
        if _BG_GAIN_MONOTONE_THRESH > 0.0:
            _bg_mono = _compute_bg_lum_monotonicity(frames, bg_masks)
            if _bg_mono > _BG_GAIN_MONOTONE_THRESH:
                logger.info(
                    "[Stitch] Stage 10.9: §1.73 bg-gain monotonicity |τ|=%.3f "
                    "> %.2f → brightness staircase risk → SCANS fallback.",
                    _bg_mono,
                    _BG_GAIN_MONOTONE_THRESH,
                )
                _sf = scans_frames or _reload_scans_frames(image_paths)
                return _scan_stitch_fallback(_sf, output_path)

        # ── Optional: MFSR super-resolution pass ─────────────────────────────
        # P1.7 — Auto-activate MFSR for low-sharpness canvas (W1 fix).
        # Tests 2, 3, 19, 20 produce Laplacian variance 12–16 from inherently
        # blurry/dark sources.  If the canvas is below threshold and MFSR is
        # not already requested, trigger it automatically.
        _lap_var: float = float(
            cv2.Laplacian(cv2.cvtColor(canvas, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
        )
        _mfsr_active = self.mfsr_mode
        if not _mfsr_active and _lap_var < 20.0:
            logger.debug(
                f"[Stitch]   Low sharpness detected (Laplacian var={_lap_var:.1f} < 20); "
                f"auto-activating MFSR."
            )
            _mfsr_active = True

        if _mfsr_active:
            try:
                # relocated: from backend.src.animation.mfsr import run_mfsr

                canvas = run_mfsr(
                    frames,
                    affines,
                    canvas_h,
                    canvas_w,
                    quality=75,
                    use_prior=self.mfsr_use_prior,
                    use_diffusion_inpaint=self.mfsr_use_diffusion,
                    n_dct_iter=self.mfsr_n_dct_iter,
                )
                # Refresh the valid mask to the new canvas's non-zero pixels.
                valid_mask = (canvas.max(axis=2) > 0).astype(np.uint8) * 255
                logger.info("[Stitch]   MFSR refinement complete.")
            except Exception as e:
                logger.debug(
                    f"[Stitch]   MFSR refinement failed ({e}); keeping median canvas."
                )

        # P3.3 — ToonCrafter ghost fill (after temporal render, before fg composite).
        # Uses _cluster_animation_phases output (already computed inside _render_median)
        # to replace ghosted animation pixels with a ToonCrafter canonical cel.
        if self.use_tooncrafter and N >= 4:
            try:
                # relocated: from backend.src.animation.rendering.rendering import _cluster_animation_phases

                _dev_tc = "cuda" if torch.cuda.is_available() else "cpu"
                _tc_anim_mask, _tc_phase_groups = _cluster_animation_phases(
                    frames, affines, canvas_h, canvas_w
                )
                if _tc_anim_mask is not None and _tc_phase_groups is not None:
                    canvas = tooncrafter_ghost_fill(
                        canvas,
                        _tc_anim_mask,
                        _tc_phase_groups,
                        frames,
                        affines,
                        device=_dev_tc,
                    )
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
            except Exception as _tc_e:
                logger.info(
                    f"[Stitch]   ToonCrafter ghost fill failed ({_tc_e}); skipping."
                )

        # ── Stage 11: Foreground composite ──────────────────────────────────
        if self.composite_fg and self.use_birefnet:
            canvas = _composite_foreground(
                [],
                [],
                canvas,
                canvas_h,
                canvas_w,
                frames,
                affines,
                bg_masks,
                frame_keys=tuple(image_paths),
                seam_path_cache=self._seam_path_cache,
                exclusion_masks=self.exclusion_masks or None,
            )
            logger.info("[Stitch] Stage 11 complete: foreground composited.")

        # ── Stage 11.2: §1.14B/C seam colour-similarity gate ────────────────
        if _SEAM_COLOR_GATE_THRESH > 0.0 and N > 1:
            _worst_color_seam = _check_seam_color_gate(
                canvas,
                N,
                thresh=_SEAM_COLOR_GATE_THRESH,
                use_bgr=_SEAM_COLOR_GATE_BGR,
            )
            if _worst_color_seam is not None:
                logger.info(
                    f"[Stitch] Stage 11.2: colour gate — seam {_worst_color_seam} "
                    f"below similarity {_SEAM_COLOR_GATE_THRESH:.2f} → SCANS fallback."
                )
                _sf = scans_frames or _reload_scans_frames(image_paths)
                return _scan_stitch_fallback(_sf, output_path)

        # ── Stage 11.3: §1.24 post-composite seam-step gate ─────────────────
        if _SEAM_STEP_GATE > 0.0 and N > 1:
            _max_step = _measure_max_seam_step(canvas, N)
            if _max_step > _SEAM_STEP_GATE:
                logger.info(
                    f"[Stitch] Stage 11.3: seam-step gate — max step {_max_step:.1f} lum "
                    f"> {_SEAM_STEP_GATE:.1f} → SCANS fallback."
                )
                _sf = scans_frames or _reload_scans_frames(image_paths)
                return _scan_stitch_fallback(_sf, output_path)

        # ── Stage 11.4: §1.66 NCC structural coherence gate ──────────────────
        # Measures normalised cross-correlation between texture bands above
        # and below each seam boundary.  Low NCC = line-art / pose discontinuity
        # that Bhattacharyya and luma-step gates cannot detect.
        if _SEAM_NCC_GATE > 0.0 and N > 1:
            _worst_ncc_seam = _check_seam_ncc_gate(canvas, N, thresh=_SEAM_NCC_GATE)
            if _worst_ncc_seam is not None:
                logger.info(
                    "[Stitch] Stage 11.4: NCC gate — seam %d NCC < %.2f "
                    "(structural discontinuity) → SCANS fallback.",
                    _worst_ncc_seam,
                    _SEAM_NCC_GATE,
                )
                _sf = scans_frames or _reload_scans_frames(image_paths)
                return _scan_stitch_fallback(_sf, output_path)

        # ── Stage 11.5: §1.72 seam entropy asymmetry gate ───────────────────
        # Fires when one side of a seam has rich texture and the other is
        # flat-colour — the perceptible texture density discontinuity is missed
        # by NCC (structural coherence) and Bhattacharyya (colour distribution).
        if _SEAM_ENTROPY_GATE > 0.0 and N > 1:
            _worst_entropy_seam = _check_seam_entropy_gate(
                canvas, N, thresh=_SEAM_ENTROPY_GATE
            )
            if _worst_entropy_seam is not None:
                logger.info(
                    "[Stitch] Stage 11.5: entropy asymmetry gate — seam %d "
                    "asymmetry > %.2f bits → SCANS fallback.",
                    _worst_entropy_seam,
                    _SEAM_ENTROPY_GATE,
                )
                _sf = scans_frames or _reload_scans_frames(image_paths)
                return _scan_stitch_fallback(_sf, output_path)

        # ── Stage 11.7: §1.74 canvas fill ratio gate ─────────────────────────
        # After compositing, pixels that remain zero (never covered by any
        # warped frame) indicate geometric gaps or a catastrophic warp failure.
        # All seam-quality gates above operate on strip boundaries and miss
        # large empty canvas regions, which look visually defective.
        if _CANVAS_FILL_MIN > 0.0:
            _fill_ratio = _compute_canvas_fill_ratio(
                canvas, pix_thresh=_CANVAS_FILL_PIX_THRESH
            )
            if _fill_ratio < _CANVAS_FILL_MIN:
                logger.info(
                    "[Stitch] Stage 11.7: §1.74 canvas fill ratio %.3f "
                    "< %.2f → empty canvas regions → SCANS fallback.",
                    _fill_ratio,
                    _CANVAS_FILL_MIN,
                )
                _sf = scans_frames or _reload_scans_frames(image_paths)
                return _scan_stitch_fallback(_sf, output_path)

        # ── Stage 11.8: §1.75 strip Laplacian variance ratio gate ───────────
        # Detects structural incompatibility between adjacent strips: when one
        # strip is flat-colour (low Laplacian variance) and the next is richly
        # textured (high variance), the composite shows a hard texture-level
        # discontinuity that none of the seam-boundary gates above can catch
        # (those gates sample only ±50px at the boundary, not the full strip).
        if _STRIP_VARIANCE_RATIO_MAX > 0.0 and N > 1:
            _var_ratio = _compute_strip_variance_ratio(canvas, N)
            if _var_ratio > _STRIP_VARIANCE_RATIO_MAX:
                logger.info(
                    "[Stitch] Stage 11.8: §1.75 strip variance ratio %.1f× "
                    "> %.1f× → texture incompatibility → SCANS fallback.",
                    _var_ratio,
                    _STRIP_VARIANCE_RATIO_MAX,
                )
                _sf = scans_frames or _reload_scans_frames(image_paths)
                return _scan_stitch_fallback(_sf, output_path)

        # ── Stage 11.9: §1.76 per-column luma-step gate ──────────────────────
        # Complements Stage 11.3 (§1.24 mean seam step): §1.24 returns the mean
        # luma across the full strip width; §1.76 reports the worst single column,
        # catching localised hot-spots that the band mean smooths away.  A
        # character edge crossing the seam at a single column produces a
        # column-max step of 50+ lum but a band-mean step of only ~3 lum.
        if _SEAM_MAX_COL_GATE > 0.0 and N > 1:
            _worst_col_seam = _check_seam_max_col_gate(
                canvas, N, thresh=_SEAM_MAX_COL_GATE
            )
            if _worst_col_seam is not None:
                logger.info(
                    "[Stitch] Stage 11.9: §1.76 per-column luma-step gate — seam %d "
                    "worst-col step > %.1f lum → SCANS fallback.",
                    _worst_col_seam,
                    _SEAM_MAX_COL_GATE,
                )
                _sf = scans_frames or _reload_scans_frames(image_paths)
                return _scan_stitch_fallback(_sf, output_path)

        # ── Stage 11.10: §1.77 seam saturation jump gate ─────────────────────
        # Complements Stage 11.9 (§1.76 per-column luma step): two strips can
        # have equal brightness yet completely different colour vibrancy — e.g.,
        # a muted pastel background abutting a vividly coloured character outfit.
        # In HSV space, saturation captures this vibrancy; a mean jump ≥ 40 at
        # the seam band is perceptible as a colour-saturation discontinuity.
        if _SEAM_SAT_GATE > 0.0 and N > 1:
            _worst_sat_seam = _check_seam_saturation_gate(
                canvas, N, thresh=_SEAM_SAT_GATE
            )
            if _worst_sat_seam is not None:
                logger.info(
                    "[Stitch] Stage 11.10: §1.77 saturation jump gate — seam %d "
                    "mean sat jump > %.1f → SCANS fallback.",
                    _worst_sat_seam,
                    _SEAM_SAT_GATE,
                )
                _sf = scans_frames or _reload_scans_frames(image_paths)
                return _scan_stitch_fallback(_sf, output_path)

        # ── Stage 11.11: §1.78 seam hue shift gate ───────────────────────────
        # Complements §1.77 (saturation) and §1.24 (luma): two strips can have
        # matching brightness and saturation but opposite colour temperatures —
        # e.g., a warm orange sunset background abutting a cool blue sky strip.
        # Hue is circular (0–180 OpenCV scale); circular distance > 30° is
        # perceptible as a colour-temperature jump.  Near-achromatic pixels
        # (sat ≤ 15) are excluded to prevent grey regions from biasing the mean.
        if _SEAM_HUE_GATE > 0.0 and N > 1:
            _worst_hue_seam = _check_seam_hue_gate(canvas, N, thresh=_SEAM_HUE_GATE)
            if _worst_hue_seam is not None:
                logger.info(
                    "[Stitch] Stage 11.11: §1.78 hue shift gate — seam %d "
                    "circular hue shift > %.1f° → SCANS fallback.",
                    _worst_hue_seam,
                    _SEAM_HUE_GATE,
                )
                _sf = scans_frames or _reload_scans_frames(image_paths)
                return _scan_stitch_fallback(_sf, output_path)

        # ── Stage 11.12: §1.79 seam sharpness mismatch gate ─────────────────
        # Complements §1.76–§1.78 (luma, saturation, hue): two strips can have
        # identical colour profiles yet differ visibly in sharpness/blur — e.g.,
        # a source frame that was upscaled or MPEG-compressed at a different
        # quality level.  Laplacian variance is the standard focus measure;
        # |log₂(var_top / var_bot)| > 3.0 means one strip is 8× sharper than
        # the other, which is clearly perceptible.  Near-flat regions with tiny
        # variance are clamped to 1.0 to prevent log singularities.
        if _SEAM_SHARP_GATE > 0.0 and N > 1:
            _worst_sharp_seam = _check_seam_sharpness_gate(
                canvas, N, thresh=_SEAM_SHARP_GATE
            )
            if _worst_sharp_seam is not None:
                logger.info(
                    "[Stitch] Stage 11.12: §1.79 sharpness mismatch gate — seam %d "
                    "|log₂(var_top/var_bot)| > %.2f → SCANS fallback.",
                    _worst_sharp_seam,
                    _SEAM_SHARP_GATE,
                )
                _sf = scans_frames or _reload_scans_frames(image_paths)
                return _scan_stitch_fallback(_sf, output_path)

        # ── Stage 11.13: §1.80 seam gradient direction coherence gate ────────
        # Complements §1.76–§1.79 (luma, saturation, hue, sharpness): two strips
        # can have identical photometric profiles yet produce a visually jarring
        # seam when their dominant edge orientations differ — e.g., diagonal
        # speed-lines above joined to horizontal cloud-layer below.  This gate
        # measures the circular distance between mean undirected Sobel orientations
        # in bands above and below each seam.  A score of 45° (orthogonal content)
        # indicates severe structural incompatibility that colour-space gates miss.
        if _SEAM_GRAD_DIR_GATE > 0.0 and N > 1:
            _worst_grad_seam = _check_seam_grad_direction_gate(
                canvas, N, thresh=_SEAM_GRAD_DIR_GATE
            )
            if _worst_grad_seam is not None:
                logger.info(
                    "[Stitch] Stage 11.13: §1.80 gradient direction gate — seam %d "
                    "orientation mismatch > %.1f° → SCANS fallback.",
                    _worst_grad_seam,
                    _SEAM_GRAD_DIR_GATE,
                )
                _sf = scans_frames or _reload_scans_frames(image_paths)
                return _scan_stitch_fallback(_sf, output_path)

        # ── Stage 11.14: §1.81 seam band SSIM gate ──────────────────────────
        # Complements §1.76–§1.80 by measuring perceptual similarity holistically:
        # SSIM jointly evaluates luminance, contrast, and structure in a single
        # [0,1] score.  A seam between two perceptually incompatible bands will
        # score well below 0.85 even when each individual §1.76–§1.80 gate passes
        # (e.g., bands with matching mean-luma but different contrast and texture
        # pattern).  Gate fires when ANY seam's SSIM score is *below* the threshold
        # (inverted polarity vs §1.76–§1.80 which fire *above* their thresholds).
        if _SEAM_SSIM_GATE > 0.0 and N > 1:
            _worst_ssim_seam = _check_seam_ssim_gate(canvas, N, thresh=_SEAM_SSIM_GATE)
            if _worst_ssim_seam is not None:
                logger.info(
                    "[Stitch] Stage 11.14: §1.81 band-SSIM gate — seam %d "
                    "SSIM < %.3f → SCANS fallback.",
                    _worst_ssim_seam,
                    _SEAM_SSIM_GATE,
                )
                _sf = scans_frames or _reload_scans_frames(image_paths)
                return _scan_stitch_fallback(_sf, output_path)

        # ── Stage 11.15: §1.82 seam spatial-frequency profile gate ──────────
        # Complements §1.79 (sharpness: blur/focus level) and §1.81 (SSIM): two
        # strips can have identical mean sharpness and similar SSIM yet completely
        # different dominant spatial frequencies — e.g., a high-frequency noise
        # texture above a smooth low-frequency gradient below.  The metric is
        # 1 − Pearson-r between the column-averaged FFT magnitude spectra of each
        # band.  A score of 0 = spectrally identical (compatible); 1 = orthogonal
        # spectra (severe spectral discontinuity at the seam).
        if _SEAM_FREQ_GATE > 0.0 and N > 1:
            _worst_freq_seam = _check_seam_freq_gate(canvas, N, thresh=_SEAM_FREQ_GATE)
            if _worst_freq_seam is not None:
                logger.info(
                    "[Stitch] Stage 11.15: §1.82 frequency-profile gate — seam %d "
                    "spectral mismatch (1−r) > %.2f → SCANS fallback.",
                    _worst_freq_seam,
                    _SEAM_FREQ_GATE,
                )
                _sf = scans_frames or _reload_scans_frames(image_paths)
                return _scan_stitch_fallback(_sf, output_path)

        # ── Stage 11.16: §1.83 seam noise-level asymmetry gate ──────────────
        # Complements §1.82 (spectral): two strips can have identical spectral
        # profiles yet different per-pixel noise amplitudes — e.g., one strip
        # from a heavily compressed panel and the adjacent strip from a cleaner
        # encode.  The Laplacian-std estimator captures this per-pixel noise
        # level directly.  Score = |σ_top−σ_bot| / mean(σ); fires > threshold.
        if _SEAM_NOISE_GATE > 0.0 and N > 1:
            _worst_noise_seam = _check_seam_noise_gate(
                canvas, N, thresh=_SEAM_NOISE_GATE
            )
            if _worst_noise_seam is not None:
                logger.info(
                    "[Stitch] Stage 11.16: §1.83 noise-asymmetry gate — seam %d "
                    "noise mismatch > %.2f → SCANS fallback.",
                    _worst_noise_seam,
                    _SEAM_NOISE_GATE,
                )
                _sf = scans_frames or _reload_scans_frames(image_paths)
                return _scan_stitch_fallback(_sf, output_path)

        # ── Stage 11.17: §1.84 seam RMS contrast ratio gate ─────────────────
        # Complements §1.79 (sharpness: fine-detail Laplacian intensity) and
        # §1.82 (spectral profile): §1.84 measures the broad-range coefficient
        # of variation c=std/mean, catching a smooth low-dynamic-range strip
        # abutting a high-contrast strip even when their Laplacian variance and
        # spectral content match.  Score = max(c)/min(c); fires > threshold.
        if _SEAM_CONTRAST_GATE > 0.0 and N > 1:
            _worst_contrast_seam = _check_seam_rms_contrast_gate(
                canvas, N, thresh=_SEAM_CONTRAST_GATE
            )
            if _worst_contrast_seam is not None:
                logger.info(
                    "[Stitch] Stage 11.17: §1.84 RMS-contrast-ratio gate — seam %d "
                    "contrast ratio > %.1f → SCANS fallback.",
                    _worst_contrast_seam,
                    _SEAM_CONTRAST_GATE,
                )
                _sf = scans_frames or _reload_scans_frames(image_paths)
                return _scan_stitch_fallback(_sf, output_path)

        # ── Stage 11.18: §1.85 multi-gate ensemble combiner ─────────────────
        # Fires when a seam accumulates votes from ≥ _SEAM_ENSEMBLE_VOTES active
        # gates.  Acts as a catch-all for corner cases where no individual gate
        # fires but multiple metrics are simultaneously near-threshold — a seam
        # that is systematically degraded across all dimensions without being
        # catastrophically bad in any single one.
        if _SEAM_ENSEMBLE_VOTES > 0 and N > 1:
            _worst_ensemble_seam = _check_seam_ensemble_gate(
                canvas,
                N,
                min_votes=_SEAM_ENSEMBLE_VOTES,
                thresh_color=float(os.environ.get("ASP_SEAM_COLOR_GATE", "0.0")),
                thresh_ncc=float(os.environ.get("ASP_SEAM_NCC_GATE", "0.0")),
                thresh_entropy=float(os.environ.get("ASP_SEAM_ENTROPY_GATE", "0.0")),
                thresh_col_step=float(os.environ.get("ASP_SEAM_MAX_COL_GATE", "0.0")),
                thresh_sat=float(os.environ.get("ASP_SEAM_SAT_GATE", "0.0")),
                thresh_hue=float(os.environ.get("ASP_SEAM_HUE_GATE", "0.0")),
                thresh_sharp=float(os.environ.get("ASP_SEAM_SHARP_GATE", "0.0")),
                thresh_grad_dir=float(os.environ.get("ASP_SEAM_GRAD_DIR_GATE", "0.0")),
                thresh_ssim=float(os.environ.get("ASP_SEAM_SSIM_GATE", "0.0")),
                thresh_freq=float(os.environ.get("ASP_SEAM_FREQ_GATE", "0.0")),
                thresh_noise=_SEAM_NOISE_GATE,
                thresh_contrast=_SEAM_CONTRAST_GATE,
            )
            if _worst_ensemble_seam is not None:
                logger.info(
                    "[Stitch] Stage 11.18: §1.85 ensemble gate — seam %d "
                    "accumulated ≥ %d gate votes → SCANS fallback.",
                    _worst_ensemble_seam,
                    _SEAM_ENSEMBLE_VOTES,
                )
                _sf = scans_frames or _reload_scans_frames(image_paths)
                return _scan_stitch_fallback(_sf, output_path)

        # ── Stage 11.19: §4.9/§5.11 Adaptive post-composite seam Gaussian blur ──
        # §5.11 scales the half-width by seam_coherence: high-coherence canvas
        # (gradual luma banding) → wider blur; sharp-content canvas → narrower.
        if _SEAM_SMOOTH_PX > 0 and N > 1:
            try:
                _tys_sm = [float(affines[k][1, 2]) for k in range(N)]
                _ctrs_sm = [_tys_sm[k] + frames[k].shape[0] / 2.0 for k in range(N)]
                _ord_sm = list(np.argsort(_ctrs_sm))
                _sc_sm = [_ctrs_sm[_ord_sm[k]] for k in range(N)]
                _seam_ys_sm = [int((_sc_sm[k] + _sc_sm[k + 1]) / 2.0) for k in range(N - 1)]
                _smooth_px = _SEAM_SMOOTH_PX
                if _SEAM_SMOOTH_ADAPTIVE and _smooth_px > 0:
                    _smooth_px = _compute_adaptive_seam_smooth_px(
                        canvas, base_px=_smooth_px, min_px=2, max_px=12
                    )
                    logger.debug(
                        "[Stitch] Stage 11.19: §5.11 adaptive seam_smooth_px=%d (sc-driven).",
                        _smooth_px,
                    )
                canvas = _smooth_seam_bands(canvas, _seam_ys_sm, band_px=_smooth_px)
                logger.debug(
                    "[Stitch] Stage 11.19: seam Gaussian blur at %d seam(s), ±%dpx.",
                    len(_seam_ys_sm), _smooth_px,
                )
            except Exception as _sm_e:
                logger.debug("[Stitch] Stage 11.19 seam band smoothing skipped (%s).", _sm_e)

        # ── Stage 11.20: §5.1/§5.9 Seam luminance step correction ──────────
        # Fires when: (a) user explicitly set ASP_SEAM_LUM_STEP > 0, OR
        # (b) auto mode: CGU check shows banding and auto threshold is enabled.
        # Computes the per-column mean luminance just above and below each seam,
        # then applies a linear ramp (±band_px) to bridge the difference.
        _lum_step_px = _SEAM_LUM_STEP_PX
        if _lum_step_px == 0 and _CGU_AUTO_LUM_STEP < 1.0 and N > 1:
            try:
                _auto_cgu = _canvas_gain_uniformity(canvas, n_strips=8)
                if _auto_cgu > _CGU_AUTO_LUM_STEP:
                    _lum_step_px = 20  # default auto half-band
                    logger.debug(
                        "[Stitch] Stage 11.20: auto-enabling seam lum-step (cgu=%.3f > %.2f).",
                        _auto_cgu, _CGU_AUTO_LUM_STEP,
                    )
            except Exception:
                pass
        if _lum_step_px > 0 and N > 1:
            try:
                _tys_lum = [float(affines[k][1, 2]) for k in range(N)]
                _ctrs_lum = [_tys_lum[k] + frames[k].shape[0] / 2.0 for k in range(N)]
                _ord_lum = list(np.argsort(_ctrs_lum))
                _sc_lum = [_ctrs_lum[_ord_lum[k]] for k in range(N)]
                _seam_ys_lum = [
                    int((_sc_lum[k] + _sc_lum[k + 1]) / 2.0) for k in range(N - 1)
                ]
                if _SEAM_LUM_STEP_ADAPTIVE:
                    _per_seam_band = _per_seam_lum_step_px(canvas, _seam_ys_lum)
                    canvas = _correct_seam_lum_steps(canvas, _seam_ys_lum, band_px=_per_seam_band)
                    logger.debug(
                        "[Stitch] Stage 11.20: §5.20 adaptive seam lum-step at %d seam(s), widths=%s.",
                        len(_seam_ys_lum), _per_seam_band,
                    )
                else:
                    canvas = _correct_seam_lum_steps(canvas, _seam_ys_lum, band_px=_lum_step_px)
                    logger.debug(
                        "[Stitch] Stage 11.20: §5.1 seam lum-step correction at %d seam(s), ±%dpx.",
                        len(_seam_ys_lum), _lum_step_px,
                    )
            except Exception as _lum_e:
                logger.debug(
                    "[Stitch] Stage 11.20 seam lum-step correction skipped (%s).", _lum_e
                )

        # ── Stage 11.21: §5.3 Canvas Gain Uniformity gate ───────────────────
        # Measures strip-level luminance banding on the finished canvas.
        # Falls back to SCANS if CGU > _CGU_GATE_FLOOR (absolute; default 0.20).
        if _CGU_GATE_FLOOR < 1.0 and N > 1:
            try:
                _cgu_val = _canvas_gain_uniformity(canvas, n_strips=8)
                logger.debug("[Stitch] Stage 11.21: canvas_gain_uniformity=%.3f (floor=%.2f).",
                             _cgu_val, _CGU_GATE_FLOOR)
                if _cgu_val > _CGU_GATE_FLOOR:
                    logger.info(
                        "[Stitch] Stage 11.21: CGUGate FAILED (cgu=%.3f > floor=%.2f) "
                        "→ SCANS fallback.", _cgu_val, _CGU_GATE_FLOOR
                    )
                    _sf = scans_frames or _reload_scans_frames(image_paths)
                    return _scan_stitch_fallback(_sf, output_path,
                                                 reason=f"cgu_gate:{_cgu_val:.3f}")
            except Exception as _cgu_e:
                logger.debug("[Stitch] Stage 11.21 CGU gate skipped (%s).", _cgu_e)

        # ── Stage 11.22: §5.19 Seam Coherence Gate ──────────────────────────
        if _SC_GATE_ENABLED and N > 1:
            try:
                _sc_val = _seam_coherence_score(canvas)
                logger.debug("[Stitch] Stage 11.22: seam_coherence=%.3f (floor=%.2f).", _sc_val, _SC_GATE_FLOOR)
                if _sc_val > _SC_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.22: SCGate FAILED (sc=%.3f > floor=%.2f) → SCANS fallback.",
                        _sc_val, _SC_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"sc_gate:{_sc_val:.3f}",
                    )
            except Exception as _sc_e:
                logger.debug("[Stitch] Stage 11.22: SCGate skipped (%s).", _sc_e)

        # ── Stage 11.23: §5.21 FFT Banding Gate ──────────────────────────────
        if _FFT_BAND_GATE_ENABLED and N > 1:
            try:
                _fft_val = _horizontal_fft_banding(canvas, n_strips=8)
                logger.debug("[Stitch] Stage 11.23: fft_banding=%.4f (floor=%.3f).",
                             _fft_val, _FFT_BAND_GATE_FLOOR)
                if _fft_val > _FFT_BAND_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.23: FFTBandGate FAILED (fft=%.4f > floor=%.3f) "
                        "→ SCANS fallback.",
                        _fft_val, _FFT_BAND_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"fft_band_gate:{_fft_val:.4f}",
                    )
            except Exception as _fft_e:
                logger.debug("[Stitch] Stage 11.23: FFTBandGate skipped (%s).", _fft_e)

        # ── Stage 11.24: §5.22 Strip Luma Monotonicity Gate ─────────────────
        if _MONO_GATE_ENABLED and N > 1:
            try:
                _mono_val = _strip_luma_monotonicity(canvas, n_strips=8)
                logger.debug("[Stitch] Stage 11.24: strip_mono=%.3f (floor=%.2f).", _mono_val, _MONO_GATE_FLOOR)
                if _mono_val > _MONO_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.24: MonoGate FAILED (mono=%.3f > floor=%.2f) → SCANS fallback.",
                        _mono_val, _MONO_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"mono_gate:{_mono_val:.3f}",
                    )
            except Exception as _mono_e:
                logger.debug("[Stitch] Stage 11.24: MonoGate skipped (%s).", _mono_e)

        # ── Stage 11.25: §5.23 Seam Visibility Gate ──────────────────────────
        if _SV_GATE_ENABLED and N > 1:
            try:
                _sv_val = _seam_visibility_score(canvas)
                logger.debug("[Stitch] Stage 11.25: seam_vis=%.2f (floor=%.2f).", _sv_val, _SV_GATE_FLOOR)
                if _sv_val > _SV_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.25: SVGate FAILED (sv=%.2f > floor=%.2f) → SCANS fallback.",
                        _sv_val, _SV_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"sv_gate:{_sv_val:.2f}",
                    )
            except Exception as _sv_e:
                logger.debug("[Stitch] Stage 11.25: SVGate skipped (%s).", _sv_e)

        # ── Stage 11.26: §5.24 Chroma Seam Coherence Gate ───────────────────
        if _CHROMA_COH_GATE_ENABLED and N > 1:
            try:
                _chroma_val = _chroma_seam_coherence(canvas, n_strips=8)
                logger.debug("[Stitch] Stage 11.26: chroma_coh=%.2f (floor=%.2f).", _chroma_val, _CHROMA_COH_GATE_FLOOR)
                if _chroma_val > _CHROMA_COH_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.26: ChromaCohGate FAILED (chroma=%.2f > floor=%.2f) → SCANS fallback.",
                        _chroma_val, _CHROMA_COH_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"chroma_coh_gate:{_chroma_val:.2f}",
                    )
            except Exception as _chroma_e:
                logger.debug("[Stitch] Stage 11.26: ChromaCohGate skipped (%s).", _chroma_e)

        # ── Stage 11.27: §5.25 Strip Self-SSIM Gate ──────────────────────────
        if _STRIP_SSIM_GATE_ENABLED and N > 1:
            try:
                _sssim_val = _strip_self_ssim(canvas, n_strips=8)
                logger.debug("[Stitch] Stage 11.27: strip_ssim=%.4f (floor=%.3f).", _sssim_val, _STRIP_SSIM_GATE_FLOOR)
                if _sssim_val > _STRIP_SSIM_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.27: StripSSIMGate FAILED (ssim=%.4f > floor=%.3f) → SCANS fallback.",
                        _sssim_val, _STRIP_SSIM_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"strip_ssim_gate:{_sssim_val:.4f}",
                    )
            except Exception as _sssim_e:
                logger.debug("[Stitch] Stage 11.27: StripSSIMGate skipped (%s).", _sssim_e)

        # ── Stage 11.28: §5.29 Ghosting SIQE Gate ────────────────────────────
        if _SIQE_GATE_ENABLED and N > 1:
            try:
                _siqe_val = _canvas_ghosting_siqe(canvas)
                logger.debug("[Stitch] Stage 11.28: ghosting_siqe=%.2f (floor=%.1f).", _siqe_val, _SIQE_GATE_FLOOR)
                if _siqe_val > _SIQE_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.28: SiqeGate FAILED (siqe=%.2f > floor=%.1f) → SCANS fallback.",
                        _siqe_val, _SIQE_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"siqe_gate:{_siqe_val:.2f}",
                    )
            except Exception as _siqe_e:
                logger.debug("[Stitch] Stage 11.28: SiqeGate skipped (%s).", _siqe_e)

        # ── Stage 11.29: §5.31 Seam Band NCC Gate ────────────────────────────
        if _SEAM_BAND_NCC_GATE_ENABLED and N > 1:
            try:
                _sbn_val = _seam_band_ncc_min(canvas, n_strips=8, band_px=10)
                logger.debug("[Stitch] Stage 11.29: seam_band_ncc_min=%.4f (floor=%.3f).", _sbn_val, _SEAM_BAND_NCC_GATE_FLOOR)
                if _sbn_val < _SEAM_BAND_NCC_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.29: SeamBandNccGate FAILED (ncc=%.4f < floor=%.3f) → SCANS fallback.",
                        _sbn_val, _SEAM_BAND_NCC_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"seam_band_ncc_gate:{_sbn_val:.4f}",
                    )
            except Exception as _sbn_e:
                logger.debug("[Stitch] Stage 11.29: SeamBandNccGate skipped (%s).", _sbn_e)

        # ── Stage 11.30: §5.32 Strip Gradient CV Gate ────────────────────────
        if _STRIP_GRAD_CV_GATE_ENABLED and N > 1:
            try:
                _sgcv_val = _strip_gradient_cv(canvas, n_strips=8)
                logger.debug("[Stitch] Stage 11.30: strip_gradient_cv=%.4f (floor=%.3f).", _sgcv_val, _STRIP_GRAD_CV_GATE_FLOOR)
                if _sgcv_val > _STRIP_GRAD_CV_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.30: StripGradCvGate FAILED (cv=%.4f > floor=%.3f) → SCANS fallback.",
                        _sgcv_val, _STRIP_GRAD_CV_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"strip_grad_cv_gate:{_sgcv_val:.4f}",
                    )
            except Exception as _sgcv_e:
                logger.debug("[Stitch] Stage 11.30: StripGradCvGate skipped (%s).", _sgcv_e)

        # ── Stage 11.31: §5.33 Seam Gradient Ratio Gate ──────────────────────
        if _SEAM_GRAD_RATIO_GATE_ENABLED and N > 1:
            try:
                _sgr_val = _strip_seam_gradient_score(canvas, n_strips=8)
                logger.debug("[Stitch] Stage 11.31: seam_grad_ratio=%.3f (floor=%.2f).", _sgr_val, _SEAM_GRAD_RATIO_GATE_FLOOR)
                if _sgr_val > _SEAM_GRAD_RATIO_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.31: SeamGradRatioGate FAILED (ratio=%.3f > floor=%.2f) → SCANS fallback.",
                        _sgr_val, _SEAM_GRAD_RATIO_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"seam_grad_ratio_gate:{_sgr_val:.3f}",
                    )
            except Exception as _sgr_e:
                logger.debug("[Stitch] Stage 11.31: SeamGradRatioGate skipped (%s).", _sgr_e)

        # ── Stage 11.32: §5.34 Canvas Aspect-Ratio Gate ──────────────────────
        if _CANVAS_ASPECT_GATE_ENABLED and N > 1:
            try:
                _car_val = _canvas_aspect_ratio(canvas)
                _car_floor = max(_CANVAS_ASPECT_GATE_FLOOR, N * 0.3)
                logger.debug("[Stitch] Stage 11.32: canvas_aspect_ratio=%.3f (floor=%.2f).", _car_val, _car_floor)
                if _car_val < _car_floor:
                    logger.warning(
                        "[Stitch] Stage 11.32: CanvasAspectGate FAILED (ratio=%.3f < floor=%.2f) → SCANS fallback.",
                        _car_val, _car_floor,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"canvas_aspect_gate:{_car_val:.3f}",
                    )
            except Exception as _car_e:
                logger.debug("[Stitch] Stage 11.32: CanvasAspectGate skipped (%s).", _car_e)

        # ── Stage 11.33: §5.36 Strip Histogram Intersection Gate ────────────
        if _HIST_INTERSECT_GATE_ENABLED and N > 1:
            try:
                _hi_val = _strip_hist_intersection_min(canvas, n_strips=8)
                logger.debug("[Stitch] Stage 11.33: hist_intersect_min=%.4f (floor=%.3f).", _hi_val, _HIST_INTERSECT_GATE_FLOOR)
                if _hi_val < _HIST_INTERSECT_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.33: HistIntersectGate FAILED (intersect=%.4f < floor=%.3f) → SCANS fallback.",
                        _hi_val, _HIST_INTERSECT_GATE_FLOOR,
                    )
                    _sf = scans_frames or _reload_scans_frames(image_paths)
                    return _scan_stitch_fallback(_sf, output_path, reason=f"hist_intersect_gate:{_hi_val:.4f}")
            except Exception as _hi_e:
                logger.debug("[Stitch] Stage 11.33: HistIntersectGate skipped (%s).", _hi_e)

        # ── Stage 11.34: §5.38 Strip Saturation CV Gate ─────────────────────
        if _SAT_CV_GATE_ENABLED and N > 1:
            try:
                _ssat_val = _strip_sat_cv(canvas, n_strips=8)
                logger.debug("[Stitch] Stage 11.34: strip_sat_cv=%.4f (floor=%.3f).", _ssat_val, _SAT_CV_GATE_FLOOR)
                if _ssat_val > _SAT_CV_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.34: SatCvGate FAILED (cv=%.4f > floor=%.3f) → SCANS fallback.",
                        _ssat_val, _SAT_CV_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"sat_cv_gate:{_ssat_val:.4f}",
                    )
            except Exception as _ssat_e:
                logger.debug("[Stitch] Stage 11.34: SatCvGate skipped (%s).", _ssat_e)

        # ── Stage 11.35: §5.39 Canvas Valid-Area Ratio Gate ─────────────────
        if _VALID_AREA_GATE_ENABLED and N > 1:
            try:
                _var_val = _canvas_valid_area_ratio(canvas)
                logger.debug("[Stitch] Stage 11.35: valid_area_ratio=%.4f (floor=%.3f).", _var_val, _VALID_AREA_GATE_FLOOR)
                if _var_val < _VALID_AREA_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.35: ValidAreaGate FAILED (ratio=%.4f < floor=%.3f) → SCANS fallback.",
                        _var_val, _VALID_AREA_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"valid_area_gate:{_var_val:.4f}",
                    )
            except Exception as _var_e:
                logger.debug("[Stitch] Stage 11.35: ValidAreaGate skipped (%s).", _var_e)

        # ── Stage 11.36: §5.41 Strip Hue CV Gate ────────────────────────────
        if _HUE_CV_GATE_ENABLED and N > 1:
            try:
                _hue_cv_val = _strip_hue_cv(canvas, n_strips=8)
                logger.debug("[Stitch] Stage 11.36: strip_hue_cv=%.4f (floor=%.3f).", _hue_cv_val, _HUE_CV_GATE_FLOOR)
                if _hue_cv_val > _HUE_CV_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.36: HueCvGate FAILED (cv=%.4f > floor=%.3f) → SCANS fallback.",
                        _hue_cv_val, _HUE_CV_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"hue_cv_gate:{_hue_cv_val:.4f}",
                    )
            except Exception as _hue_cv_e:
                logger.debug("[Stitch] Stage 11.36: HueCvGate skipped (%s).", _hue_cv_e)

        # ── Stage 11.37: §5.42 Seam Boundary Sharpness Ratio Gate ───────────
        if _SEAM_SHARP_RATIO_GATE_ENABLED and N > 1:
            try:
                _ssr_val = _seam_boundary_sharpness_ratio(canvas, n_strips=8)
                logger.debug("[Stitch] Stage 11.37: seam_sharp_ratio=%.4f (floor=%.3f).", _ssr_val, _SEAM_SHARP_RATIO_GATE_FLOOR)
                if _ssr_val > _SEAM_SHARP_RATIO_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.37: SeamSharpRatioGate FAILED (ratio=%.4f > floor=%.3f) → SCANS fallback.",
                        _ssr_val, _SEAM_SHARP_RATIO_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"seam_sharp_ratio_gate:{_ssr_val:.4f}",
                    )
            except Exception as _ssr_e:
                logger.debug("[Stitch] Stage 11.37: SeamSharpRatioGate skipped (%s).", _ssr_e)

        # ── Stage 11.38: §5.45 Strip Luma Range Gate ─────────────────────────
        if _LUMA_RANGE_GATE_ENABLED and N > 1:
            try:
                _lr_val = _strip_luma_range(canvas, n_strips=8)
                logger.debug("[Stitch] Stage 11.38: strip_luma_range=%.2f (floor=%.1f).", _lr_val, _LUMA_RANGE_GATE_FLOOR)
                if _lr_val > _LUMA_RANGE_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.38: LumaRangeGate FAILED (range=%.2f > floor=%.1f) → SCANS fallback.",
                        _lr_val, _LUMA_RANGE_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"luma_range_gate:{_lr_val:.2f}",
                    )
            except Exception as _lr_e:
                logger.debug("[Stitch] Stage 11.38: LumaRangeGate skipped (%s).", _lr_e)

        # ── Stage 11.39: §5.46 Seam Edge Density Gate ────────────────────────
        if _EDGE_DENSITY_GATE_ENABLED and N > 1:
            try:
                _ed_val = _seam_edge_density(canvas, n_strips=8)
                logger.debug("[Stitch] Stage 11.39: seam_edge_density=%.4f (floor=%.3f).", _ed_val, _EDGE_DENSITY_GATE_FLOOR)
                if _ed_val > _EDGE_DENSITY_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.39: EdgeDensityGate FAILED (density=%.4f > floor=%.3f) → SCANS fallback.",
                        _ed_val, _EDGE_DENSITY_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"edge_density_gate:{_ed_val:.4f}",
                    )
            except Exception as _ed_e:
                logger.debug("[Stitch] Stage 11.39: EdgeDensityGate skipped (%s).", _ed_e)

        # ── Stage 11.40: §5.49 Strip Luma MAD Gate ──────────────────────────
        if _LUMA_MAD_GATE_ENABLED and N > 1:
            try:
                _lmad_val = _strip_luma_mad(canvas, n_strips=8)
                logger.debug("[Stitch] Stage 11.40: strip_luma_mad=%.2f (floor=%.1f).", _lmad_val, _LUMA_MAD_GATE_FLOOR)
                if _lmad_val > _LUMA_MAD_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.40: LumaMadGate FAILED (mad=%.2f > floor=%.1f) → SCANS fallback.",
                        _lmad_val, _LUMA_MAD_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"luma_mad_gate:{_lmad_val:.2f}",
                    )
            except Exception as _lmad_e:
                logger.debug("[Stitch] Stage 11.40: LumaMadGate skipped (%s).", _lmad_e)

        # ── Stage 11.41: §5.50 Strip Sharpness CV Gate ───────────────────────
        if _SHARPNESS_CV_GATE_ENABLED and N > 1:
            try:
                _scv_val = _strip_sharpness_cv(canvas, n_strips=8)
                logger.debug("[Stitch] Stage 11.41: strip_sharpness_cv=%.4f (floor=%.3f).", _scv_val, _SHARPNESS_CV_GATE_FLOOR)
                if _scv_val > _SHARPNESS_CV_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.41: SharpnessCvGate FAILED (cv=%.4f > floor=%.3f) → SCANS fallback.",
                        _scv_val, _SHARPNESS_CV_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"sharpness_cv_gate:{_scv_val:.4f}",
                    )
            except Exception as _scv_e:
                logger.debug("[Stitch] Stage 11.41: SharpnessCvGate skipped (%s).", _scv_e)

        # ── Stage 11.42: §5.53 Strip Contrast CV Gate ────────────────────────
        if _CONTRAST_CV_GATE_ENABLED and N > 1:
            try:
                _ccv_val = _strip_contrast_cv(canvas, n_strips=8)
                logger.debug("[Stitch] Stage 11.42: strip_contrast_cv=%.4f (floor=%.3f).", _ccv_val, _CONTRAST_CV_GATE_FLOOR)
                if _ccv_val > _CONTRAST_CV_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.42: ContrastCvGate FAILED (cv=%.4f > floor=%.3f) → SCANS fallback.",
                        _ccv_val, _CONTRAST_CV_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"contrast_cv_gate:{_ccv_val:.4f}",
                    )
            except Exception as _ccv_e:
                logger.debug("[Stitch] Stage 11.42: ContrastCvGate skipped (%s).", _ccv_e)

        # ── Stage 11.43: §5.54 Seam Chroma Jump Gate ─────────────────────────
        if _CHROMA_JUMP_GATE_ENABLED and N > 1:
            try:
                _scj_val = _seam_chroma_jump(canvas, n_strips=8, boundary_px=3)
                logger.debug("[Stitch] Stage 11.43: seam_chroma_jump=%.2f (floor=%.1f).", _scj_val, _CHROMA_JUMP_GATE_FLOOR)
                if _scj_val > _CHROMA_JUMP_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.43: ChromaJumpGate FAILED (jump=%.2f > floor=%.1f) → SCANS fallback.",
                        _scj_val, _CHROMA_JUMP_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"chroma_jump_gate:{_scj_val:.2f}",
                    )
            except Exception as _scj_e:
                logger.debug("[Stitch] Stage 11.43: ChromaJumpGate skipped (%s).", _scj_e)
        # ── Stage 11.44: §5.57 Strip Noise CV Gate ───────────────────────────
        if _NOISE_CV_GATE_ENABLED and N > 1:
            try:
                _ncv_val = _strip_noise_cv(canvas, n_strips=8)
                logger.debug("[Stitch] Stage 11.44: strip_noise_cv=%.4f (floor=%.3f).", _ncv_val, _NOISE_CV_GATE_FLOOR)
                if _ncv_val > _NOISE_CV_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.44: NoiseCvGate FAILED (cv=%.4f > floor=%.3f) → SCANS fallback.",
                        _ncv_val, _NOISE_CV_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"noise_cv_gate:{_ncv_val:.4f}",
                    )
            except Exception as _ncv_e:
                logger.debug("[Stitch] Stage 11.44: NoiseCvGate skipped (%s).", _ncv_e)

        # ── Stage 11.45: §5.58 Seam Luma Step CV Gate ────────────────────────
        if _LUMA_STEP_CV_GATE_ENABLED and N > 1:
            try:
                _lscv_val = _seam_luma_step_cv(canvas, n_strips=8, boundary_px=3)
                logger.debug("[Stitch] Stage 11.45: seam_luma_step_cv=%.4f (floor=%.3f).", _lscv_val, _LUMA_STEP_CV_GATE_FLOOR)
                if _lscv_val > _LUMA_STEP_CV_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.45: LumaStepCvGate FAILED (cv=%.4f > floor=%.3f) → SCANS fallback.",
                        _lscv_val, _LUMA_STEP_CV_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"luma_step_cv_gate:{_lscv_val:.4f}",
                    )
            except Exception as _lscv_e:
                logger.debug("[Stitch] Stage 11.45: LumaStepCvGate skipped (%s).", _lscv_e)

        # ── Stage 11.46: §5.61 Strip Entropy CV Gate ─────────────────────────
        if _ENTROPY_CV_GATE_ENABLED and N > 1:
            try:
                _ecv_val = _strip_entropy_cv(canvas, n_strips=8)
                logger.debug("[Stitch] Stage 11.46: strip_entropy_cv=%.4f (floor=%.3f).", _ecv_val, _ENTROPY_CV_GATE_FLOOR)
                if _ecv_val > _ENTROPY_CV_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.46: EntropyCvGate FAILED (cv=%.4f > floor=%.3f) → SCANS fallback.",
                        _ecv_val, _ENTROPY_CV_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"entropy_cv_gate:{_ecv_val:.4f}",
                    )
            except Exception as _ecv_e:
                logger.debug("[Stitch] Stage 11.46: EntropyCvGate skipped (%s).", _ecv_e)

        # ── Stage 11.47: §5.62 Seam Chroma Step CV Gate ──────────────────────
        if _CHROMA_STEP_CV_GATE_ENABLED and N > 1:
            try:
                _cscv_val = _seam_chroma_step_cv(canvas, n_strips=8, boundary_px=3)
                logger.debug("[Stitch] Stage 11.47: seam_chroma_step_cv=%.4f (floor=%.3f).", _cscv_val, _CHROMA_STEP_CV_GATE_FLOOR)
                if _cscv_val > _CHROMA_STEP_CV_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.47: ChromaStepCvGate FAILED (cv=%.4f > floor=%.3f) → SCANS fallback.",
                        _cscv_val, _CHROMA_STEP_CV_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"chroma_step_cv_gate:{_cscv_val:.4f}",
                    )
            except Exception as _cscv_e:
                logger.debug("[Stitch] Stage 11.47: ChromaStepCvGate skipped (%s).", _cscv_e)

        # ── Stage 11.48: §5.65 Strip Chroma Energy CV Gate ───────────────────
        if _CHROMA_ENERGY_CV_GATE_ENABLED and N > 1:
            try:
                _cecv_val = _strip_chroma_energy_cv(canvas, n_strips=8)
                logger.debug("[Stitch] Stage 11.48: strip_chroma_energy_cv=%.4f (floor=%.3f).", _cecv_val, _CHROMA_ENERGY_CV_GATE_FLOOR)
                if _cecv_val > _CHROMA_ENERGY_CV_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.48: ChromaEnergyCvGate FAILED (cv=%.4f > floor=%.3f) → SCANS fallback.",
                        _cecv_val, _CHROMA_ENERGY_CV_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"chroma_energy_cv_gate:{_cecv_val:.4f}",
                    )
            except Exception as _cecv_e:
                logger.debug("[Stitch] Stage 11.48: ChromaEnergyCvGate skipped (%s).", _cecv_e)

        # ── Stage 11.49: §5.66 Seam Gradient CV Gate ─────────────────────────
        if _SEAM_GRADIENT_CV_GATE_ENABLED and N > 1:
            try:
                _sgcv_val = _seam_gradient_cv(canvas, n_strips=8, band_px=5)
                logger.debug("[Stitch] Stage 11.49: seam_gradient_cv=%.4f (floor=%.3f).", _sgcv_val, _SEAM_GRADIENT_CV_GATE_FLOOR)
                if _sgcv_val > _SEAM_GRADIENT_CV_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.49: SeamGradientCvGate FAILED (cv=%.4f > floor=%.3f) → SCANS fallback.",
                        _sgcv_val, _SEAM_GRADIENT_CV_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"seam_gradient_cv_gate:{_sgcv_val:.4f}",
                    )
            except Exception as _sgcv_e:
                logger.debug("[Stitch] Stage 11.49: SeamGradientCvGate skipped (%s).", _sgcv_e)

        # ── Stage 11.50: §5.69 Strip Luma IQR CV Gate ────────────────────────
        if _LUMA_IQR_CV_GATE_ENABLED and N > 1:
            try:
                _iqr_val = _strip_luma_iqr_cv(canvas, n_strips=8)
                logger.debug("[Stitch] Stage 11.50: strip_luma_iqr_cv=%.4f (floor=%.3f).", _iqr_val, _LUMA_IQR_CV_GATE_FLOOR)
                if _iqr_val > _LUMA_IQR_CV_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.50: LumaIqrCvGate FAILED (cv=%.4f > floor=%.3f) → SCANS fallback.",
                        _iqr_val, _LUMA_IQR_CV_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"luma_iqr_cv_gate:{_iqr_val:.4f}",
                    )
            except Exception as _iqr_e:
                logger.debug("[Stitch] Stage 11.50: LumaIqrCvGate skipped (%s).", _iqr_e)

        # ── Stage 11.51: §5.70 Seam Column Variance CV Gate ──────────────────
        if _SEAM_COL_VAR_CV_GATE_ENABLED and N > 1:
            try:
                _scvarcv_val = _seam_column_variance_cv(canvas, n_strips=8, boundary_px=3)
                logger.debug("[Stitch] Stage 11.51: seam_column_variance_cv=%.4f (floor=%.3f).", _scvarcv_val, _SEAM_COL_VAR_CV_GATE_FLOOR)
                if _scvarcv_val > _SEAM_COL_VAR_CV_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.51: SeamColVarCvGate FAILED (cv=%.4f > floor=%.3f) → SCANS fallback.",
                        _scvarcv_val, _SEAM_COL_VAR_CV_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"seam_col_var_cv_gate:{_scvarcv_val:.4f}",
                    )
            except Exception as _scvarcv_e:
                logger.debug("[Stitch] Stage 11.51: SeamColVarCvGate skipped (%s).", _scvarcv_e)

        # ── Stage 11.52: §5.73 Strip Luma Skewness CV Gate ──────────────────
        if _LUMA_SKEW_CV_GATE_ENABLED and N > 1:
            try:
                _lskew_val = _strip_luma_skewness_cv(canvas, n_strips=8)
                logger.debug("[Stitch] Stage 11.52: strip_luma_skewness_cv=%.4f (floor=%.3f).", _lskew_val, _LUMA_SKEW_CV_GATE_FLOOR)
                if _lskew_val > _LUMA_SKEW_CV_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.52: LumaSkewCvGate FAILED (cv=%.4f > floor=%.3f) → SCANS fallback.",
                        _lskew_val, _LUMA_SKEW_CV_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"luma_skew_cv_gate:{_lskew_val:.4f}",
                    )
            except Exception as _lskew_e:
                logger.debug("[Stitch] Stage 11.52: LumaSkewCvGate skipped (%s).", _lskew_e)

        # ── Stage 11.53: §5.74 Seam Signed Step CV Gate ──────────────────────
        if _SEAM_SIGNED_STEP_CV_GATE_ENABLED and N > 1:
            try:
                _sssv_val = _seam_signed_step_cv(canvas, n_strips=8, boundary_px=3)
                logger.debug("[Stitch] Stage 11.53: seam_signed_step_cv=%.4f (floor=%.3f).", _sssv_val, _SEAM_SIGNED_STEP_CV_GATE_FLOOR)
                if _sssv_val > _SEAM_SIGNED_STEP_CV_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.53: SeamSignedStepCvGate FAILED (cv=%.4f > floor=%.3f) → SCANS fallback.",
                        _sssv_val, _SEAM_SIGNED_STEP_CV_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"seam_signed_step_cv_gate:{_sssv_val:.4f}",
                    )
            except Exception as _sssv_e:
                logger.debug("[Stitch] Stage 11.53: SeamSignedStepCvGate skipped (%s).", _sssv_e)
        # ── Stage 11.54: §5.77 Strip Luma Kurtosis CV Gate ──────────────────
        if _LUMA_KURTOSIS_CV_GATE_ENABLED and N > 1:
            try:
                _lkurt_val = _strip_luma_kurtosis_cv(canvas, n_strips=8)
                logger.debug("[Stitch] Stage 11.54: strip_luma_kurtosis_cv=%.4f (floor=%.3f).", _lkurt_val, _LUMA_KURTOSIS_CV_GATE_FLOOR)
                if _lkurt_val > _LUMA_KURTOSIS_CV_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.54: LumaKurtosisCvGate FAILED (cv=%.4f > floor=%.3f) → SCANS fallback.",
                        _lkurt_val, _LUMA_KURTOSIS_CV_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"luma_kurtosis_cv_gate:{_lkurt_val:.4f}",
                    )
            except Exception as _lkurt_e:
                logger.debug("[Stitch] Stage 11.54: LumaKurtosisCvGate skipped (%s).", _lkurt_e)
        # ── Stage 11.55: §5.78 Seam Texture Ratio CV Gate ────────────────────
        if _SEAM_TEXTURE_RATIO_CV_GATE_ENABLED and N > 1:
            try:
                _stxr_val = _seam_texture_ratio_cv(canvas, n_strips=8, band_px=5)
                logger.debug("[Stitch] Stage 11.55: seam_texture_ratio_cv=%.4f (floor=%.3f).", _stxr_val, _SEAM_TEXTURE_RATIO_CV_GATE_FLOOR)
                if _stxr_val > _SEAM_TEXTURE_RATIO_CV_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.55: SeamTextureRatioCvGate FAILED (cv=%.4f > floor=%.3f) → SCANS fallback.",
                        _stxr_val, _SEAM_TEXTURE_RATIO_CV_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"seam_texture_ratio_cv_gate:{_stxr_val:.4f}",
                    )
            except Exception as _stxr_e:
                logger.debug("[Stitch] Stage 11.55: SeamTextureRatioCvGate skipped (%s).", _stxr_e)
        # ── Stage 11.56: §5.81 Strip Edge Density CV Gate ───────────────────
        if _EDGE_DENSITY_CV_GATE_ENABLED and N > 1:
            try:
                _edcv_val = _strip_edge_density_cv(canvas, n_strips=8)
                logger.debug("[Stitch] Stage 11.56: strip_edge_density_cv=%.4f (floor=%.3f).", _edcv_val, _EDGE_DENSITY_CV_GATE_FLOOR)
                if _edcv_val > _EDGE_DENSITY_CV_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.56: EdgeDensityCvGate FAILED (cv=%.4f > floor=%.3f) → SCANS fallback.",
                        _edcv_val, _EDGE_DENSITY_CV_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"edge_density_cv_gate:{_edcv_val:.4f}",
                    )
            except Exception as _edcv_e:
                logger.debug("[Stitch] Stage 11.56: EdgeDensityCvGate skipped (%s).", _edcv_e)
        # ── Stage 11.57: §5.82 Seam Local Contrast CV Gate ───────────────────
        if _SEAM_LOCAL_CONTRAST_CV_GATE_ENABLED and N > 1:
            try:
                _slcc_val = _seam_local_contrast_cv(canvas, n_strips=8, band_px=5)
                logger.debug("[Stitch] Stage 11.57: seam_local_contrast_cv=%.4f (floor=%.3f).", _slcc_val, _SEAM_LOCAL_CONTRAST_CV_GATE_FLOOR)
                if _slcc_val > _SEAM_LOCAL_CONTRAST_CV_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.57: SeamLocalContrastCvGate FAILED (cv=%.4f > floor=%.3f) → SCANS fallback.",
                        _slcc_val, _SEAM_LOCAL_CONTRAST_CV_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"seam_local_contrast_cv_gate:{_slcc_val:.4f}",
                    )
            except Exception as _slcc_e:
                logger.debug("[Stitch] Stage 11.57: SeamLocalContrastCvGate skipped (%s).", _slcc_e)
        # ── Stage 11.58: §5.85 Strip Luma P90–P10 CV Gate ───────────────────
        if _LUMA_P90P10_CV_GATE_ENABLED and N > 1:
            try:
                _p90p10_val = _strip_luma_p90p10_cv(canvas, n_strips=8)
                logger.debug("[Stitch] Stage 11.58: strip_luma_p90p10_cv=%.4f (floor=%.3f).", _p90p10_val, _LUMA_P90P10_CV_GATE_FLOOR)
                if _p90p10_val > _LUMA_P90P10_CV_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.58: LumaP90P10CvGate FAILED (cv=%.4f > floor=%.3f) → SCANS fallback.",
                        _p90p10_val, _LUMA_P90P10_CV_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"luma_p90p10_cv_gate:{_p90p10_val:.4f}",
                    )
            except Exception as _p90p10_e:
                logger.debug("[Stitch] Stage 11.58: LumaP90P10CvGate skipped (%s).", _p90p10_e)
        # ── Stage 11.59: §5.86 Seam Hue Shift CV Gate ────────────────────────
        if _SEAM_HUE_SHIFT_CV_GATE_ENABLED and N > 1:
            try:
                _hshift_val = _seam_hue_shift_cv(canvas, n_strips=8, boundary_px=3)
                logger.debug("[Stitch] Stage 11.59: seam_hue_shift_cv=%.4f (floor=%.3f).", _hshift_val, _SEAM_HUE_SHIFT_CV_GATE_FLOOR)
                if _hshift_val > _SEAM_HUE_SHIFT_CV_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.59: SeamHueShiftCvGate FAILED (cv=%.4f > floor=%.3f) → SCANS fallback.",
                        _hshift_val, _SEAM_HUE_SHIFT_CV_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"seam_hue_shift_cv_gate:{_hshift_val:.4f}",
                    )
            except Exception as _hshift_e:
                logger.debug("[Stitch] Stage 11.59: SeamHueShiftCvGate skipped (%s).", _hshift_e)
        # ── Stage 11.60: §5.89 Strip Dark Pixel Fraction CV Gate ─────────────
        if _DARK_PIXEL_FRAC_CV_GATE_ENABLED and N > 1:
            try:
                _dpfcv_val = _strip_dark_pixel_fraction_cv(canvas, n_strips=8, threshold=64)
                logger.debug("[Stitch] Stage 11.60: strip_dark_pixel_fraction_cv=%.4f (floor=%.3f).", _dpfcv_val, _DARK_PIXEL_FRAC_CV_GATE_FLOOR)
                if _dpfcv_val > _DARK_PIXEL_FRAC_CV_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.60: DarkPixelFracCvGate FAILED (cv=%.4f > floor=%.3f) → SCANS fallback.",
                        _dpfcv_val, _DARK_PIXEL_FRAC_CV_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"dark_pixel_frac_cv_gate:{_dpfcv_val:.4f}",
                    )
            except Exception as _dpfcv_e:
                logger.debug("[Stitch] Stage 11.60: DarkPixelFracCvGate skipped (%s).", _dpfcv_e)
        # ── Stage 11.61: §5.90 Seam Saturation Shift CV Gate ─────────────────
        if _SEAM_SAT_SHIFT_CV_GATE_ENABLED and N > 1:
            try:
                _ssscv_val = _seam_saturation_shift_cv(canvas, n_strips=8, boundary_px=3)
                logger.debug("[Stitch] Stage 11.61: seam_saturation_shift_cv=%.4f (floor=%.3f).", _ssscv_val, _SEAM_SAT_SHIFT_CV_GATE_FLOOR)
                if _ssscv_val > _SEAM_SAT_SHIFT_CV_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.61: SeamSatShiftCvGate FAILED (cv=%.4f > floor=%.3f) → SCANS fallback.",
                        _ssscv_val, _SEAM_SAT_SHIFT_CV_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"seam_sat_shift_cv_gate:{_ssscv_val:.4f}",
                    )
            except Exception as _ssscv_e:
                logger.debug("[Stitch] Stage 11.61: SeamSatShiftCvGate skipped (%s).", _ssscv_e)
        # ── Stage 11.62: §5.93 Strip Sobel Energy CV Gate ────────────────────
        if _SOBEL_ENERGY_CV_GATE_ENABLED and N > 1:
            try:
                _sobel_val = _strip_sobel_energy_cv(canvas, n_strips=8)
                logger.debug("[Stitch] Stage 11.62: strip_sobel_energy_cv=%.4f (floor=%.3f).", _sobel_val, _SOBEL_ENERGY_CV_GATE_FLOOR)
                if _sobel_val > _SOBEL_ENERGY_CV_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.62: SobelEnergyCvGate FAILED (cv=%.4f > floor=%.3f) → SCANS fallback.",
                        _sobel_val, _SOBEL_ENERGY_CV_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"sobel_energy_cv_gate:{_sobel_val:.4f}",
                    )
            except Exception as _sobel_e:
                logger.debug("[Stitch] Stage 11.62: SobelEnergyCvGate skipped (%s).", _sobel_e)
        # ── Stage 11.63: §5.94 Seam Value Shift CV Gate ──────────────────────
        if _SEAM_VALUE_SHIFT_CV_GATE_ENABLED and N > 1:
            try:
                _valsh_val = _seam_value_shift_cv(canvas, n_strips=8, boundary_px=3)
                logger.debug("[Stitch] Stage 11.63: seam_value_shift_cv=%.4f (floor=%.3f).", _valsh_val, _SEAM_VALUE_SHIFT_CV_GATE_FLOOR)
                if _valsh_val > _SEAM_VALUE_SHIFT_CV_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.63: SeamValueShiftCvGate FAILED (cv=%.4f > floor=%.3f) → SCANS fallback.",
                        _valsh_val, _SEAM_VALUE_SHIFT_CV_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"seam_value_shift_cv_gate:{_valsh_val:.4f}",
                    )
            except Exception as _valsh_e:
                logger.debug("[Stitch] Stage 11.63: SeamValueShiftCvGate skipped (%s).", _valsh_e)
        # ── Stage 11.64: §5.97 Strip Median Luma CV Gate ────────────────────
        if _MEDIAN_LUMA_CV_GATE_ENABLED and N > 1:
            try:
                _medlum_val = _strip_median_luma_cv(canvas, n_strips=8)
                logger.debug("[Stitch] Stage 11.64: strip_median_luma_cv=%.4f (floor=%.3f).", _medlum_val, _MEDIAN_LUMA_CV_GATE_FLOOR)
                if _medlum_val > _MEDIAN_LUMA_CV_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.64: MedianLumaCvGate FAILED (cv=%.4f > floor=%.3f) → SCANS fallback.",
                        _medlum_val, _MEDIAN_LUMA_CV_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"median_luma_cv_gate:{_medlum_val:.4f}",
                    )
            except Exception as _medlum_e:
                logger.debug("[Stitch] Stage 11.64: MedianLumaCvGate skipped (%s).", _medlum_e)
        # ── Stage 11.65: §5.98 Seam Entropy Shift CV Gate ────────────────────
        if _SEAM_ENTROPY_SHIFT_CV_GATE_ENABLED and N > 1:
            try:
                _entsh_val = _seam_entropy_shift_cv(canvas, n_strips=8, boundary_px=3)
                logger.debug("[Stitch] Stage 11.65: seam_entropy_shift_cv=%.4f (floor=%.3f).", _entsh_val, _SEAM_ENTROPY_SHIFT_CV_GATE_FLOOR)
                if _entsh_val > _SEAM_ENTROPY_SHIFT_CV_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.65: SeamEntropyShiftCvGate FAILED (cv=%.4f > floor=%.3f) → SCANS fallback.",
                        _entsh_val, _SEAM_ENTROPY_SHIFT_CV_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"seam_entropy_shift_cv_gate:{_entsh_val:.4f}",
                    )
            except Exception as _entsh_e:
                logger.debug("[Stitch] Stage 11.65: SeamEntropyShiftCvGate skipped (%s).", _entsh_e)
        # ── Stage 11.66: §5.101 Strip Red Channel CV Gate ────────────────────
        if _RED_CHANNEL_CV_GATE_ENABLED and N > 1:
            try:
                _redcv_val = _strip_red_channel_cv(canvas, n_strips=8)
                logger.debug("[Stitch] Stage 11.66: strip_red_channel_cv=%.4f (floor=%.3f).", _redcv_val, _RED_CHANNEL_CV_GATE_FLOOR)
                if _redcv_val > _RED_CHANNEL_CV_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.66: RedChannelCvGate FAILED (cv=%.4f > floor=%.3f) → SCANS fallback.",
                        _redcv_val, _RED_CHANNEL_CV_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"red_channel_cv_gate:{_redcv_val:.4f}",
                    )
            except Exception as _redcv_e:
                logger.debug("[Stitch] Stage 11.66: RedChannelCvGate skipped (%s).", _redcv_e)
        # ── Stage 11.67: §5.102 Seam Blue Shift CV Gate ──────────────────────
        if _SEAM_BLUE_SHIFT_CV_GATE_ENABLED and N > 1:
            try:
                _blsh_val = _seam_blue_shift_cv(canvas, n_strips=8, boundary_px=3)
                logger.debug("[Stitch] Stage 11.67: seam_blue_shift_cv=%.4f (floor=%.3f).", _blsh_val, _SEAM_BLUE_SHIFT_CV_GATE_FLOOR)
                if _blsh_val > _SEAM_BLUE_SHIFT_CV_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.67: SeamBlueShiftCvGate FAILED (cv=%.4f > floor=%.3f) → SCANS fallback.",
                        _blsh_val, _SEAM_BLUE_SHIFT_CV_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"seam_blue_shift_cv_gate:{_blsh_val:.4f}",
                    )
            except Exception as _blsh_e:
                logger.debug("[Stitch] Stage 11.67: SeamBlueShiftCvGate skipped (%s).", _blsh_e)
        # ── Stage 11.68: §5.105 Strip Green Channel CV Gate ──────────────────
        if _GREEN_CHANNEL_CV_GATE_ENABLED:
            try:
                _gcv_val = _strip_green_channel_cv(canvas, n_strips=8)
                logger.debug("[Stitch] Stage 11.68: strip_green_channel_cv=%.4f (floor=%.3f).", _gcv_val, _GREEN_CHANNEL_CV_GATE_FLOOR)
                if _gcv_val > _GREEN_CHANNEL_CV_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.68: GreenChannelCvGate FAILED (cv=%.4f > floor=%.3f) → SCANS fallback.",
                        _gcv_val, _GREEN_CHANNEL_CV_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"strip_green_channel_cv_gate:{_gcv_val:.4f}",
                    )
            except Exception as _gcv_e:
                logger.debug("[Stitch] Stage 11.68: GreenChannelCvGate skipped (%s).", _gcv_e)
        # ── Stage 11.69: §5.106 Seam Red Shift CV Gate ───────────────────────
        if _SEAM_RED_SHIFT_CV_GATE_ENABLED and N > 1:
            try:
                _rshcv_val = _seam_red_shift_cv(canvas, n_strips=8, boundary_px=3)
                logger.debug("[Stitch] Stage 11.69: seam_red_shift_cv=%.4f (floor=%.3f).", _rshcv_val, _SEAM_RED_SHIFT_CV_GATE_FLOOR)
                if _rshcv_val > _SEAM_RED_SHIFT_CV_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.69: SeamRedShiftCvGate FAILED (cv=%.4f > floor=%.3f) → SCANS fallback.",
                        _rshcv_val, _SEAM_RED_SHIFT_CV_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"seam_red_shift_cv_gate:{_rshcv_val:.4f}",
                    )
            except Exception as _rshcv_e:
                logger.debug("[Stitch] Stage 11.69: SeamRedShiftCvGate skipped (%s).", _rshcv_e)
        # ── Stage 11.70: §5.109 Strip Blue Channel CV Gate ───────────────────
        if _BLUE_CHANNEL_CV_GATE_ENABLED:
            try:
                _bcv_val = _strip_blue_channel_cv(canvas, n_strips=8)
                logger.debug("[Stitch] Stage 11.70: strip_blue_channel_cv=%.4f (floor=%.3f).", _bcv_val, _BLUE_CHANNEL_CV_GATE_FLOOR)
                if _bcv_val > _BLUE_CHANNEL_CV_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.70: BlueChannelCvGate FAILED (cv=%.4f > floor=%.3f) → SCANS fallback.",
                        _bcv_val, _BLUE_CHANNEL_CV_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"strip_blue_channel_cv_gate:{_bcv_val:.4f}",
                    )
            except Exception as _bcv_e:
                logger.debug("[Stitch] Stage 11.70: BlueChannelCvGate skipped (%s).", _bcv_e)
        # ── Stage 11.71: §5.110 Seam Green Shift CV Gate ─────────────────────
        if _SEAM_GREEN_SHIFT_CV_GATE_ENABLED and N > 1:
            try:
                _gshcv_val = _seam_green_shift_cv(canvas, n_strips=8, boundary_px=3)
                logger.debug("[Stitch] Stage 11.71: seam_green_shift_cv=%.4f (floor=%.3f).", _gshcv_val, _SEAM_GREEN_SHIFT_CV_GATE_FLOOR)
                if _gshcv_val > _SEAM_GREEN_SHIFT_CV_GATE_FLOOR:
                    logger.warning(
                        "[Stitch] Stage 11.71: SeamGreenShiftCvGate FAILED (cv=%.4f > floor=%.3f) → SCANS fallback.",
                        _gshcv_val, _SEAM_GREEN_SHIFT_CV_GATE_FLOOR,
                    )
                    return _scan_stitch_fallback(
                        frames=scans_frames or _reload_scans_frames(image_paths),
                        output_path=output_path,
                        reason=f"seam_green_shift_cv_gate:{_gshcv_val:.4f}",
                    )
            except Exception as _gshcv_e:
                logger.debug("[Stitch] Stage 11.71: SeamGreenShiftCvGate skipped (%s).", _gshcv_e)

        # P3.4 — SRStitcher seam diffusion fusion (Stage 11.6).
        # Inpaints the seam bands using a diffusion model so hard Laplacian
        # transitions are replaced by style-consistent anime content.
        if self.use_srstitcher:
            try:
                _dev_sr2 = "cuda" if torch.cuda.is_available() else "cpu"
                # Compute seam y-positions from affine boundaries
                _tys = [float(affines[k][1, 2]) for k in range(N)]
                _ctrs = [_tys[k] + frames[k].shape[0] / 2.0 for k in range(N)]
                _order = np.argsort(_ctrs)
                _sorted_ctrs = [_ctrs[_order[k]] for k in range(N)]
                _seam_ys = [
                    int((_sorted_ctrs[k] + _sorted_ctrs[k + 1]) / 2.0)
                    for k in range(N - 1)
                ]
                canvas = seam_diffusion_fusion(
                    canvas, _seam_ys, device=_dev_sr2, num_steps=20
                )
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                logger.info(
                    "[Stitch] Stage 11.5 complete: SRStitcher seam diffusion done."
                )
            except Exception as _srs_e:
                logger.info(
                    f"[Stitch]   SRStitcher seam fusion failed ({_srs_e}); skipping."
                )

        # ── Stage 11.20: §5.1/§5.9 Seam luminance step correction ──────────
        # Fires when: (a) user explicitly set ASP_SEAM_LUM_STEP > 0, OR
        # (b) auto mode: CGU check shows banding and auto threshold is enabled.
        # Computes the per-column mean luminance just above and below each seam,
        # then applies a linear ramp (±band_px) to bridge the difference.
        _lum_step_px = _SEAM_LUM_STEP_PX
        if _lum_step_px == 0 and _CGU_AUTO_LUM_STEP < 1.0 and N > 1:
            try:
                _auto_cgu = _canvas_gain_uniformity(canvas, n_strips=8)
                if _auto_cgu > _CGU_AUTO_LUM_STEP:
                    _lum_step_px = 20  # default auto half-band
                    logger.debug(
                        "[Stitch] Stage 11.20: auto-enabling seam lum-step (cgu=%.3f > %.2f).",
                        _auto_cgu, _CGU_AUTO_LUM_STEP,
                    )
            except Exception:
                pass
        if _lum_step_px > 0 and N > 1:
            try:
                _tys_lum = [float(affines[k][1, 2]) for k in range(N)]
                _ctrs_lum = [_tys_lum[k] + frames[k].shape[0] / 2.0 for k in range(N)]
                _ord_lum = list(np.argsort(_ctrs_lum))
                _sc_lum = [_ctrs_lum[_ord_lum[k]] for k in range(N)]
                _seam_ys_lum = [
                    int((_sc_lum[k] + _sc_lum[k + 1]) / 2.0) for k in range(N - 1)
                ]
                # §5.20: per-seam adaptive band widths via list API
                if _SEAM_LUM_STEP_ADAPTIVE:
                    _per_seam_band = _per_seam_lum_step_px(canvas, _seam_ys_lum)
                    canvas = _correct_seam_lum_steps(canvas, _seam_ys_lum, band_px=_per_seam_band)
                    logger.debug(
                        "[Stitch] Stage 11.20: §5.20 adaptive seam lum-step at %d seam(s), widths=%s.",
                        len(_seam_ys_lum), _per_seam_band,
                    )
                else:
                    canvas = _correct_seam_lum_steps(
                        canvas, _seam_ys_lum, band_px=_lum_step_px
                    )
                    logger.debug(
                        "[Stitch] Stage 11.20: §5.1 seam lum-step correction at %d seam(s), ±%dpx.",
                        len(_seam_ys_lum),
                        _lum_step_px,
                    )
            except Exception as _lum_e:
                logger.debug(
                    "[Stitch] Stage 11.20 seam lum-step correction skipped (%s).", _lum_e
                )

        # ── Stage 12: Remaining seam blend (handled inside _render). ────────

        # ── Stage 12.5: Scroll-axis-aware content crop (§2.6) ───────────────
        # After compositing, the canvas may have leading/trailing strips of
        # pure background that contain zero foreground character pixels across
        # all frames.  These pure-bg rows inflate the scale factor relative to
        # GT (GT's panorama starts/ends with the first/last character-containing
        # frame).  Trim them to reduce GT-framing bias.
        #
        # Only trim rows where ALL warped frames have bg-only content (i.e., no
        # character pixels from any frame reach that canvas row).  Rows where
        # even one frame has fg content are kept — they contain mid-scroll
        # character data even if the median/composite shows bg there.
        #
        # Cap: never trim more than 15% of canvas height/width per side.
        # This prevents over-cropping on datasets where the first/last frame
        # is entirely background (static camera opening shot).
        try:
            _trim_cap_frac = 0.15
            # Determine dominant scroll axis from affine translations
            _tys_trim = [float(affines[k][1, 2]) for k in range(N)]
            _txs_trim = [float(affines[k][0, 2]) for k in range(N)]
            _ty_span = max(_tys_trim) - min(_tys_trim)
            _tx_span = max(_txs_trim) - min(_txs_trim)
            _is_vert_scroll = _ty_span >= _tx_span

            if bg_masks and any(m is not None for m in bg_masks):
                # Build a union fg map across all warped frames:
                # any pixel that is foreground in AT LEAST ONE warped frame
                # is protected from trimming.
                _union_fg = np.zeros((canvas_h, canvas_w), dtype=bool)
                for _idx_trim in range(N):
                    if bg_masks[_idx_trim] is None:
                        continue
                    _wfg = cv2.warpAffine(
                        (bg_masks[_idx_trim] < 127).astype(np.uint8),
                        affines[_idx_trim],
                        (canvas_w, canvas_h),
                        flags=cv2.INTER_NEAREST,
                        borderMode=cv2.BORDER_CONSTANT,
                        borderValue=0,
                    )
                    _union_fg |= _wfg > 0

                if _is_vert_scroll:
                    # Find row range with any fg content
                    _row_has_fg = _union_fg.any(axis=1)  # (canvas_h,)
                    _fg_rows = np.where(_row_has_fg)[0]
                    if len(_fg_rows) > 0:
                        _cap_px = int(canvas_h * _trim_cap_frac)
                        _new_top = max(0, min(int(_fg_rows[0]), _cap_px))
                        _new_bot = min(
                            canvas_h, max(int(_fg_rows[-1]) + 1, canvas_h - _cap_px)
                        )
                        if _new_top > 0 or _new_bot < canvas_h:
                            canvas = canvas[_new_top:_new_bot]
                            valid_mask = valid_mask[_new_top:_new_bot]
                            logger.info(
                                f"[Stitch] Stage 12.5: vertical scroll content trim "
                                f"rows [{_new_top}:{_new_bot}] / {canvas_h} "
                                f"(−{_new_top}top, −{canvas_h - _new_bot}bot)"
                            )
                else:
                    # Horizontal scroll: trim pure-bg columns at left/right
                    _col_has_fg = _union_fg.any(axis=0)  # (canvas_w,)
                    _fg_cols = np.where(_col_has_fg)[0]
                    if len(_fg_cols) > 0:
                        _cap_px = int(canvas_w * _trim_cap_frac)
                        _new_lft = max(0, min(int(_fg_cols[0]), _cap_px))
                        _new_rgt = min(
                            canvas_w, max(int(_fg_cols[-1]) + 1, canvas_w - _cap_px)
                        )
                        if _new_lft > 0 or _new_rgt < canvas_w:
                            canvas = canvas[:, _new_lft:_new_rgt]
                            valid_mask = valid_mask[:, _new_lft:_new_rgt]
                            logger.info(
                                f"[Stitch] Stage 12.5: horizontal scroll content trim "
                                f"cols [{_new_lft}:{_new_rgt}] / {canvas_w} "
                                f"(−{_new_lft}left, −{canvas_w - _new_rgt}right)"
                            )
        except Exception as _trim_e:
            logger.debug(f"[Stitch] Stage 12.5 content trim skipped ({_trim_e}).")

        # ── Stage 13: Morphological boundary crop ───────────────────────────
        canvas = _crop_to_valid(canvas, valid_mask)
        if getattr(self, "edge_crop", 0) > 0:
            ec = self.edge_crop
            if ec * 2 < canvas.shape[0] and ec * 2 < canvas.shape[1]:
                canvas = canvas[ec:-ec, ec:-ec]
        logger.info("[Stitch] Stage 13 complete: boundary crop done.")

        # P1.8 — Auto-trigger diffusion inpainting for coverage gaps (W4 fix).
        # test7 (diagonal motion) leaves black corners at 81.5% coverage.
        # After the crop, recalculate the valid-pixel ratio and call the existing
        # inpaint_gaps module when coverage drops below 95%.
        _gap_mask = (canvas.max(axis=2) == 0).astype(np.uint8) * 255
        _coverage = 1.0 - float(_gap_mask.mean()) / 255.0
        if _coverage < 0.95 and _gap_mask.any():
            logger.debug(
                f"[Stitch]   Coverage {_coverage * 100:.1f}% < 95%; "
                f"auto-activating border fill for black corners."
            )
            if self.sr_mode and _SRSTITCHER_OK:
                # §1.7/3.4 Option A — diffusion border fill via sr_stitcher
                try:
                    _dev_bdf = "cuda" if torch.cuda.is_available() else "cpu"
                    canvas = border_diffusion_fill(canvas, device=_dev_bdf)
                    logger.info(
                        "[Stitch]   sr_stitcher diffusion border fill complete."
                    )
                except Exception as _bdf_e:
                    logger.warning(
                        f"[Stitch]   Diffusion border fill failed ({_bdf_e}); TELEA fallback."
                    )
                    try:
                        canvas = _telea_fill_gaps(canvas, _gap_mask)
                        logger.info("[Stitch]   TELEA border fill complete.")
                    except Exception as _telea_e:
                        logger.info(
                            f"[Stitch]   TELEA fallback also failed ({_telea_e}); keeping canvas as-is."
                        )
            else:
                # Default path: MFSR inpaint_gaps → TELEA
                try:
                    # relocated: from backend.src.animation.mfsr import inpaint_gaps

                    canvas = inpaint_gaps(canvas, gap_mask=_gap_mask)
                    logger.info("[Stitch]   Inpainting complete.")
                except Exception as _e:
                    logger.info(
                        f"[Stitch]   Diffusion inpainting failed ({_e}); trying TELEA fallback."
                    )
                    try:
                        canvas = _telea_fill_gaps(canvas, _gap_mask)
                        logger.info(
                            "[Stitch]   TELEA border fill complete (diffusion fallback)."
                        )
                    except Exception as _telea_e:
                        logger.info(
                            f"[Stitch]   TELEA fallback also failed ({_telea_e}); keeping canvas as-is."
                        )

        # ── Optional: Real-ESRGAN anime_6B super-resolution (P2.2) ──────────
        if self.sr_mode and _SR_OK:
            try:
                _dev_sr = "cuda" if torch.cuda.is_available() else "cpu"
                logger.debug(
                    f"[Stitch]   Running Real-ESRGAN anime_6B {self.sr_scale}× SR "
                    f"on {canvas.shape[1]}×{canvas.shape[0]} canvas…"
                )
                canvas = upscale_anime(canvas, scale=self.sr_scale, device=_dev_sr)
                logger.debug(
                    f"[Stitch]   SR complete: output {canvas.shape[1]}×{canvas.shape[0]}."
                )
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception as _sr_e:
                logger.debug(
                    f"[Stitch]   Real-ESRGAN failed ({_sr_e}); keeping original resolution."
                )

        # ── Save ─────────────────────────────────────────────────────────────
        rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
        out = Image.fromarray(rgb)
        out.save(output_path)
        gc.collect()
        logger.info(f"[Stitch] Done. Saved to '{output_path}'.")

        # §2.8 — HybridStitch export
        if _HYBRID_EXPORT_PATH:
            try:
                from backend.src.animation.rendering.hybrid_export import build_hybrid_export, save_hybrid_export

                _he_state = {
                    "image_paths": image_paths,
                    "affines": affines,
                    "photometric_gains": [],
                    "photometric_biases": [],
                    "canvas_w": canvas.shape[1],
                    "canvas_h": canvas.shape[0],
                    "seam_boundaries": [],
                    "seam_post_diffs": {},
                }
                _he_data = build_hybrid_export(_he_state)
                save_hybrid_export(_he_data, _HYBRID_EXPORT_PATH)
                logger.info(
                    f"[Stitch] §2.8 Hybrid export saved to '{_HYBRID_EXPORT_PATH}'."
                )
            except Exception as _he_e:
                logger.warning(
                    f"[Stitch] §2.8 Hybrid export failed ({_he_e}); continuing."
                )

        return out

    # ------------------------------------------------------------- thin wrappers
    # The original class exposed several stage methods (as bound or static).
    # We keep them as thin wrappers so external callers (tests, helpers) still
    # work.

    def _load_frames(self, paths: List[str]) -> List[np.ndarray]:
        return _load_frames(paths)

    @staticmethod
    def _normalise_widths(frames: List[np.ndarray]) -> List[np.ndarray]:
        return _normalise_widths(frames)

    def _apply_basic(self, frames: List[np.ndarray]) -> List[np.ndarray]:
        if self._basic is None:
            self._basic = BaSiCWrapper()
        corrected, baselines = _apply_basic(frames, self._basic)
        self._baselines = baselines
        return corrected

    def _correct_vignetting(self, frames: List[np.ndarray]) -> List[np.ndarray]:
        return _correct_vignetting(frames)

    def _compute_fg_masks(self, frames: List[np.ndarray]) -> List[Optional[np.ndarray]]:
        if self.use_birefnet and self._birefnet is None:
            from backend.src.models.wrappers.birefnet_wrapper import (
                BiRefNetWrapper,
            )  # §3.14 lazy

            self._birefnet = BiRefNetWrapper()
        if _USE_SAM2:
            masks, pred, state, tmp, fh, fw = _compute_fg_masks_sam2_stateful(
                frames, self._birefnet, use_birefnet=self.use_birefnet
            )
            self._sam2_predictor = pred
            self._sam2_inference_state = state
            self._sam2_tmp_dir = tmp
            self._sam2_frame_h = fh
            self._sam2_frame_w = fw
            return masks
        return _compute_fg_masks(frames, self._birefnet, use_birefnet=self.use_birefnet)

    def _cleanup_sam2_state(self) -> None:
        """Free the live SAM-2 predictor state stored by _compute_fg_masks."""
        _cleanup_sam2_state(
            self._sam2_predictor, self._sam2_inference_state, self._sam2_tmp_dir
        )
        self._sam2_predictor = None
        self._sam2_inference_state = None
        self._sam2_tmp_dir = None
        self._sam2_frame_h = 0
        self._sam2_frame_w = 0

    def _pairwise_match(
        self,
        frames: List[np.ndarray],
        bg_masks: List[Optional[np.ndarray]],
    ) -> List[Dict]:
        if self.use_loftr and self._loftr is None:
            from backend.src.models.wrappers.loftr_wrapper import LoFTRWrapper  # §3.14 lazy

            self._loftr = LoFTRWrapper()
        return _pairwise_match(
            frames,
            bg_masks,
            loftr_wrapper=self._loftr,
            use_loftr=self.use_loftr,
            motion_model=self.motion_model,
            aliked_wrapper=self._aliked if self.use_aliked else None,
        )

    def _match_pair(
        self,
        frames: List[np.ndarray],
        bg_masks: List[Optional[np.ndarray]],
        i: int,
        j: int,
        H: int,
        W: int,
    ) -> Optional[Dict]:
        return _match_pair(
            frames,
            bg_masks,
            i,
            j,
            H,
            W,
            loftr_wrapper=self._loftr,
            use_loftr=self.use_loftr,
            motion_model=self.motion_model,
            aliked_wrapper=self._aliked if self.use_aliked else None,
        )

    @staticmethod
    def _template_match(
        img_i: np.ndarray,
        img_j: np.ndarray,
        m_i: Optional[np.ndarray],
        m_j: Optional[np.ndarray],
        H: int,
        slice_h: int = 256,
        max_search_frac: float = 0.8,
        direction_sign: int = 0,
        max_dy_frac: float = 0.70,
    ) -> Tuple[Optional[np.ndarray], float]:
        return _template_match(
            img_i,
            img_j,
            m_i,
            m_j,
            H,
            slice_h=slice_h,
            max_search_frac=max_search_frac,
            direction_sign=direction_sign,
            max_dy_frac=max_dy_frac,
        )

    @staticmethod
    def _phase_correlate(
        img_i: np.ndarray,
        img_j: np.ndarray,
        m_i: Optional[np.ndarray],
        m_j: Optional[np.ndarray],
        use_mask: bool = True,
    ) -> Tuple[Optional[np.ndarray], float]:
        return _phase_correlate(img_i, img_j, m_i, m_j, use_mask=use_mask)

    @staticmethod
    def _sample_bg_points(
        mask: Optional[np.ndarray], H: int, W: int, n: int = 200
    ) -> np.ndarray:
        return _sample_bg_points(mask, H, W, n=n)

    def _ecc_refine(
        self,
        frames: List[np.ndarray],
        affines: List[np.ndarray],
        bg_masks: List[Optional[np.ndarray]],
    ) -> List[np.ndarray]:
        return _ecc_refine(frames, affines, bg_masks)

    @staticmethod
    def _compute_canvas(
        frames: List[np.ndarray],
        affines: List[np.ndarray],
    ) -> Tuple[int, int, np.ndarray]:
        return _compute_canvas(frames, affines)

    def _render(
        self,
        frames: List[np.ndarray],
        affines: List[np.ndarray],
        bg_masks: List[Optional[np.ndarray]],
        canvas_h: int,
        canvas_w: int,
    ) -> Tuple[np.ndarray, np.ndarray, List[np.ndarray], List[np.ndarray]]:
        return _render(
            frames,
            affines,
            bg_masks,
            canvas_h,
            canvas_w,
            renderer=self.renderer,
            baselines=self._baselines,
        )

    def _render_median(self, *args, **kwargs):
        return _render_median(*args, **kwargs)

    def _render_first(self, frames, affines, H, W):
        return _render_first(frames, affines, H, W)

    def _render_laplacian(self, *args, **kwargs):
        return _render_laplacian(*args, **kwargs)

    @staticmethod
    def _cluster_animation_phases(
        frames: List[np.ndarray],
        affines: List[np.ndarray],
        H: int,
        W: int,
        target_w: int = 320,
        ac_threshold: float = 0.25,
        min_anim_pixels: int = 500,
    ):
        return _cluster_animation_phases(
            frames,
            affines,
            H,
            W,
            target_w=target_w,
            ac_threshold=ac_threshold,
            min_anim_pixels=min_anim_pixels,
        )

    def _composite_foreground(
        self,
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
        return _composite_foreground(
            warped_corr,
            warped_fgs,
            canvas,
            H,
            W,
            frames,
            affines,
            bg_masks,
            frame_keys=frame_keys,
            seam_path_cache=seam_path_cache,
            exclusion_masks=exclusion_masks,
            preset_boundaries=preset_boundaries,
            paint_mask=paint_mask,
            seam_meta_out=seam_meta_out,
            seam_overrides=seam_overrides,
        )

    def _crop_to_valid(self, canvas: np.ndarray, valid_mask: np.ndarray) -> np.ndarray:
        return _crop_to_valid(canvas, valid_mask)

    @staticmethod
    def _scan_stitch_fallback(
        frames: List[np.ndarray],
        output_path: str,
    ) -> Image.Image:
        return _scan_stitch_fallback(frames, output_path)

    @staticmethod
    def find_optimal_sequence(
        ref_path: str,
        candidates: List[str],
        min_inliers: int = 30,
        max_overlap: float = 0.85,
    ) -> List[str]:
        return find_optimal_sequence(
            ref_path,
            candidates,
            min_inliers=min_inliers,
            max_overlap=max_overlap,
        )


def _build_manual_edge(
    i: int,
    j: int,
    dx: float,
    dy: float,
    weight: float = 0.9,
) -> Dict:
    """§S89: Construct a pipeline-compatible edge dict from a user-supplied displacement.

    The affine M is a pure translation: [[1, 0, dx], [0, 1, dy]].
    pts_i / pts_j are set to a single centroid-estimate point so Bundle Adjust
    can process the edge without matched feature points.

    Args:
        i: Source frame index.
        j: Target frame index.
        dx: Horizontal pixel displacement (j relative to i).
        dy: Vertical pixel displacement (j relative to i).
        weight: Edge confidence weight in [0, 1]; default 0.9 (high confidence
                for manual edges since the user deliberately chose the value).

    Returns:
        Edge dict compatible with ``_bundle_adjust_affine`` and the HITL edge
        override path in ``StitchWorker``.
    """
    M = np.array([[1.0, 0.0, dx], [0.0, 1.0, dy]], dtype=np.float64)
    pts_i = np.array([[0.0, 0.0]], dtype=np.float32)
    pts_j = np.array([[dx, dy]], dtype=np.float32)
    return {
        "i": i,
        "j": j,
        "M": M,
        "pts_i": pts_i,
        "pts_j": pts_j,
        "weight": float(np.clip(weight, 0.0, 1.0)),
        "method": "manual",
    }


def _build_landmark_affine(
    i: int,
    j: int,
    landmark_pairs: "List[Tuple[Tuple[float, float], Tuple[float, float]]]",
    weight: float = 0.95,
) -> Dict:
    """§2.9A: Build a pipeline edge dict from user-placed landmark point pairs.

    Constructs a least-squares affine (or partial-affine / translation) from
    the N landmark correspondences provided by the BigWarp landmark editor
    dialog and returns an edge dict compatible with ``_bundle_adjust_affine``.

    ``landmark_pairs`` is a list of ``((xi, yi), (xj, yj))`` tuples where
    ``(xi, yi)`` is the point in frame i and ``(xj, yj)`` is the corresponding
    point in frame j, both in pixel coordinates.

    Estimation strategy (by point count):
    - 1 pair  → pure translation (centroid-to-centroid displacement)
    - 2 pairs → ``cv2.estimateAffinePartial2D`` (4-DOF: tx, ty, rotation, scale)
    - 3+ pairs → ``cv2.estimateAffine2D`` (6-DOF general affine, LMEDS robust)

    Falls back to centroid translation if cv2 estimation returns None/fails.

    Args:
        i: Source frame index.
        j: Target frame index.
        landmark_pairs: At least 1 ``((xi, yi), (xj, yj))`` correspondence.
        weight: Edge confidence weight in [0, 1]; default 0.95.

    Returns:
        Edge dict compatible with ``_bundle_adjust_affine`` and the HITL edge
        override path in ``StitchWorker``.
    """
    if not landmark_pairs:
        raise ValueError("landmark_pairs must contain at least 1 point pair")

    pts_i = np.array([[p[0][0], p[0][1]] for p in landmark_pairs], dtype=np.float32)
    pts_j = np.array([[p[1][0], p[1][1]] for p in landmark_pairs], dtype=np.float32)

    M: Optional[np.ndarray] = None
    n = len(landmark_pairs)
    if n >= 3:
        M_est, inliers = cv2.estimateAffine2D(pts_i, pts_j, method=cv2.LMEDS)
        if M_est is not None:
            M = M_est.astype(np.float64)
    elif n == 2:
        M_est, inliers = cv2.estimateAffinePartial2D(pts_i, pts_j, method=cv2.LMEDS)
        if M_est is not None:
            M = M_est.astype(np.float64)

    if M is None:
        # Centroid translation fallback
        centroid_i = pts_i.mean(axis=0)
        centroid_j = pts_j.mean(axis=0)
        dx = float(centroid_j[0] - centroid_i[0])
        dy = float(centroid_j[1] - centroid_i[1])
        M = np.array([[1.0, 0.0, dx], [0.0, 1.0, dy]], dtype=np.float64)

    return {
        "i": i,
        "j": j,
        "M": M,
        "pts_i": pts_i,
        "pts_j": pts_j,
        "weight": float(np.clip(weight, 0.0, 1.0)),
        "method": "landmark",
    }


__all__ = [
    "AnimeStitchPipeline",
    "_spatial_dedup_frames",
    "_reject_static_edges",
    "_compute_adaptive_min_disp",
    "_filter_high_conf_edges",
    "_reload_scans_frames",
    "_reject_scene_change_edges",
    "_normalize_frame_scales",
    "_check_edge_graph_connectivity",
    "_compute_mst_weight",
    "_compute_canvas_span_utilization",
    "_compute_dy_cv",
    "_compute_adaptive_dy_cv_max",
    "_DY_CV_MAX",
    "_SEAM_SMOOTH_PX",
    "_SEAM_LUM_STEP_PX",
    "_CGU_GATE_FLOOR",
    "_CGU_AUTO_LUM_STEP",
    "_SC_GATE_ENABLED",
    "_SC_GATE_FLOOR",
    "_seam_coherence_score",
    "_FFT_BAND_GATE_ENABLED",
    "_FFT_BAND_GATE_FLOOR",
    "_horizontal_fft_banding",
    "_SV_GATE_ENABLED",
    "_SV_GATE_FLOOR",
    "_seam_visibility_score",
    "_CHROMA_COH_GATE_ENABLED",
    "_CHROMA_COH_GATE_FLOOR",
    "_chroma_seam_coherence",
    "_correct_seam_lum_steps",
    "_measure_max_seam_step",
    "_detect_static_input",
    "_build_manual_edge",
    "_triangular_consistency_filter",
    "_compute_bg_coverage_fraction",
    "_compute_render_coverage",
    "_compute_adj_edge_coverage",
    "_compute_max_adjacent_gap",
    "_compute_canvas_width_ratio",
    "_compute_sign_inconsistency_rate",
    "_compute_adj_disp_cv",
    "_compute_adj_min_weight",
    "_compute_ba_max_residual",
    "_compute_min_adjacent_overlap",
    "_compute_ba_weighted_mean_residual",
    "_compute_canvas_memory_mb",
    "_compute_canvas_aspect_ratio",
    "_compute_render_luma_std",
    "_compute_max_affine_rotation_deg",
    "_smooth_affine_trajectory",
    "_wave_correct_affines",
    "_WAVE_CORRECT",
    "_apply_hires_keyframes",
    "_sort_frames_by_index",
    "_check_canvas_spread",
    "_compute_bg_lum_spread",
    "_compute_bg_lum_monotonicity",
    "_compute_canvas_fill_ratio",
    "_compute_strip_variance_ratio",
    "_build_landmark_affine",
    "_HYBRID_EXPORT_PATH",
    "_SEAM_SMOOTH_PX",
    "_SEAM_SMOOTH_ADAPTIVE",
    "_compute_adaptive_seam_smooth_px",
    "_SEAM_LUM_STEP_PX",
    "_CGU_AUTO_LUM_STEP",
    "_SEAM_LUM_STEP_ADAPTIVE",
    "_per_seam_lum_step_px",
    "_correct_seam_lum_steps",
    "_MONO_GATE_ENABLED",
    "_MONO_GATE_FLOOR",
    "_strip_luma_monotonicity",
    "_STRIP_SSIM_GATE_ENABLED",
    "_STRIP_SSIM_GATE_FLOOR",
    "_strip_self_ssim",
    "_STRIP_GRAD_CV_GATE_ENABLED",
    "_STRIP_GRAD_CV_GATE_FLOOR",
    "_strip_gradient_cv",
    "_SEAM_BAND_NCC_GATE_ENABLED",
    "_SEAM_BAND_NCC_GATE_FLOOR",
    "_seam_band_ncc_min",
    "_SIQE_GATE_ENABLED",
    "_SIQE_GATE_FLOOR",
    "_canvas_ghosting_siqe",
    "_SEAM_GRAD_RATIO_GATE_ENABLED",
    "_SEAM_GRAD_RATIO_GATE_FLOOR",
    "_strip_seam_gradient_score",
    "_CANVAS_ASPECT_GATE_ENABLED",
    "_CANVAS_ASPECT_GATE_FLOOR",
    "_canvas_aspect_ratio",
    "_HIST_INTERSECT_GATE_ENABLED",
    "_HIST_INTERSECT_GATE_FLOOR",
    "_strip_hist_intersection_min",
    "_SAT_CV_GATE_ENABLED",
    "_SAT_CV_GATE_FLOOR",
    "_strip_sat_cv",
    "_VALID_AREA_GATE_ENABLED",
    "_VALID_AREA_GATE_FLOOR",
    "_canvas_valid_area_ratio",
    "_HUE_CV_GATE_ENABLED",
    "_HUE_CV_GATE_FLOOR",
    "_strip_hue_cv",
    "_SEAM_SHARP_RATIO_GATE_ENABLED",
    "_SEAM_SHARP_RATIO_GATE_FLOOR",
    "_seam_boundary_sharpness_ratio",
    "_LUMA_RANGE_GATE_ENABLED",
    "_LUMA_RANGE_GATE_FLOOR",
    "_strip_luma_range",
    "_EDGE_DENSITY_GATE_ENABLED",
    "_EDGE_DENSITY_GATE_FLOOR",
    "_seam_edge_density",
    "_LUMA_MAD_GATE_ENABLED",
    "_LUMA_MAD_GATE_FLOOR",
    "_SHARPNESS_CV_GATE_ENABLED",
    "_SHARPNESS_CV_GATE_FLOOR",
    "_CONTRAST_CV_GATE_ENABLED",
    "_CONTRAST_CV_GATE_FLOOR",
    "_CHROMA_JUMP_GATE_ENABLED",
    "_CHROMA_JUMP_GATE_FLOOR",
    "_NOISE_CV_GATE_ENABLED",
    "_NOISE_CV_GATE_FLOOR",
    "_LUMA_STEP_CV_GATE_ENABLED",
    "_LUMA_STEP_CV_GATE_FLOOR",
    "_ENTROPY_CV_GATE_ENABLED",
    "_ENTROPY_CV_GATE_FLOOR",
    "_CHROMA_STEP_CV_GATE_ENABLED",
    "_CHROMA_STEP_CV_GATE_FLOOR",
    "_CHROMA_ENERGY_CV_GATE_ENABLED",
    "_CHROMA_ENERGY_CV_GATE_FLOOR",
    "_SEAM_GRADIENT_CV_GATE_ENABLED",
    "_SEAM_GRADIENT_CV_GATE_FLOOR",
    "_LUMA_IQR_CV_GATE_ENABLED",
    "_LUMA_IQR_CV_GATE_FLOOR",
    "_SEAM_COL_VAR_CV_GATE_ENABLED",
    "_SEAM_COL_VAR_CV_GATE_FLOOR",
    "_LUMA_SKEW_CV_GATE_ENABLED",
    "_LUMA_SKEW_CV_GATE_FLOOR",
    "_SEAM_SIGNED_STEP_CV_GATE_ENABLED",
    "_SEAM_SIGNED_STEP_CV_GATE_FLOOR",
    "_LUMA_KURTOSIS_CV_GATE_ENABLED",
    "_LUMA_KURTOSIS_CV_GATE_FLOOR",
    "_SEAM_TEXTURE_RATIO_CV_GATE_ENABLED",
    "_SEAM_TEXTURE_RATIO_CV_GATE_FLOOR",
    "_EDGE_DENSITY_CV_GATE_ENABLED",
    "_EDGE_DENSITY_CV_GATE_FLOOR",
    "_SEAM_LOCAL_CONTRAST_CV_GATE_ENABLED",
    "_SEAM_LOCAL_CONTRAST_CV_GATE_FLOOR",
    "_LUMA_P90P10_CV_GATE_ENABLED",
    "_LUMA_P90P10_CV_GATE_FLOOR",
    "_SEAM_HUE_SHIFT_CV_GATE_ENABLED",
    "_SEAM_HUE_SHIFT_CV_GATE_FLOOR",
    "_DARK_PIXEL_FRAC_CV_GATE_ENABLED",
    "_DARK_PIXEL_FRAC_CV_GATE_FLOOR",
    "_SEAM_SAT_SHIFT_CV_GATE_ENABLED",
    "_SEAM_SAT_SHIFT_CV_GATE_FLOOR",
    "_SOBEL_ENERGY_CV_GATE_ENABLED",
    "_SOBEL_ENERGY_CV_GATE_FLOOR",
    "_SEAM_VALUE_SHIFT_CV_GATE_ENABLED",
    "_SEAM_VALUE_SHIFT_CV_GATE_FLOOR",
    "_MEDIAN_LUMA_CV_GATE_ENABLED",
    "_MEDIAN_LUMA_CV_GATE_FLOOR",
    "_SEAM_ENTROPY_SHIFT_CV_GATE_ENABLED",
    "_SEAM_ENTROPY_SHIFT_CV_GATE_FLOOR",
    "_RED_CHANNEL_CV_GATE_ENABLED",
    "_RED_CHANNEL_CV_GATE_FLOOR",
    "_SEAM_BLUE_SHIFT_CV_GATE_ENABLED",
    "_SEAM_BLUE_SHIFT_CV_GATE_FLOOR",
    "_GREEN_CHANNEL_CV_GATE_ENABLED",
    "_GREEN_CHANNEL_CV_GATE_FLOOR",
    "_SEAM_RED_SHIFT_CV_GATE_ENABLED",
    "_SEAM_RED_SHIFT_CV_GATE_FLOOR",
    "_BLUE_CHANNEL_CV_GATE_ENABLED",
    "_BLUE_CHANNEL_CV_GATE_FLOOR",
    "_SEAM_GREEN_SHIFT_CV_GATE_ENABLED",
    "_SEAM_GREEN_SHIFT_CV_GATE_FLOOR",
]

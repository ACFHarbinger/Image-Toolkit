"""
§1.8A: TOML-based ASP pipeline configuration loader.

Loads ``asp_config.toml`` from the current working directory (or a path
supplied by the caller).  Any key present in the TOML file is exported as an
environment variable (via ``os.environ.setdefault``), so all downstream
``os.environ.get`` calls in pipeline modules pick up the value automatically.
Existing env-var values always win over the config file.

Usage::

    from backend.src.anim.config import load_asp_config
    load_asp_config()  # reads asp_config.toml if present in cwd

Example ``asp_config.toml``::

    [frame_selection]
    ASP_NEAR_DUP_LUMA = 5.0
    ASP_HOLD_THRESHOLD = 0.03

    [compositing]
    ASP_SP_SOFT_PX = 6
    ASP_GATE_GHOST_FLOOR = 40.0
    ASP_POISSON_SEAM = 0

    [pipeline]
    ASP_COV_MIN_MULTI_PCT = 0.30

All keys are optional; unrecognised keys are silently accepted (forwarded as
env vars).  Values must be numeric (int/float) or boolean — TOML strings are
forwarded as-is.
"""

from __future__ import annotations

import os
import tomllib
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.src.exceptions import ConfigError

__all__ = ["load_asp_config", "validate_asp_config", "dump_asp_config", "get_asp"]

_DEFAULT_CONFIG_NAME = "asp_config.toml"

# §1.8B — Schema for known ASP env-var keys.
# Tuple: (expected_type, min_val, max_val, description)
# min_val / max_val are None when the bound is open.
_CONFIG_SCHEMA: Dict[str, Tuple] = {
    "ASP_HOLD_THRESHOLD": (float, 0.0, 1.0, "MAD hold-detection threshold [0, 1]"),
    "ASP_NEAR_DUP_LUMA": (float, 0.0, 255.0, "Near-dup luma floor (luma units 0–255)"),
    "ASP_COV_MIN_MULTI_PCT": (
        float,
        0.0,
        1.0,
        "Min multi-frame canvas coverage [0, 1]",
    ),
    "ASP_SP_SOFT_PX": (int, 0, None, "Single-pose feather half-width (px, 0=off)"),
    "ASP_GATE_GHOST_FLOOR": (
        float,
        0.0,
        None,
        "Ghost gate absolute floor (luma units)",
    ),
    "ASP_POISSON_SEAM": (int, 0, 1, "Enable Poisson seam blend (0 or 1)"),
    "ASP_TOONCRAFTER_SEAM": (int, 0, 1, "Enable ToonCrafter seam fill (0 or 1)"),
    "ASP_SCANS_RELOAD": (int, 0, 1, "Reload SCANS frames on demand (0 or 1)"),
    "ASP_TEMPORAL_VAR_THRESH": (
        float,
        0.0,
        None,
        "Temporal variance pre-filter threshold",
    ),
    "ASP_HIGH_HOLD_RESPONSE": (
        float,
        0.0,
        1.0,
        "Phase-corr response floor for hold merge",
    ),
    "ASP_BA_F_SCALE": (float, 0.01, None, "GNC Cauchy f_scale for bundle adjustment"),
    "ASP_POSE_WINDOW_PX": (int, 0, None, "DINOv2 pose-selection window (px, 0=off)"),
    "ASP_SGM_PROXY": (int, 0, 1, "Enable SLIC SGM flow proxy (0 or 1)"),
    "ASP_TWO_CHANNEL_SELECT": (
        int,
        0,
        1,
        "Enable BiRefNet two-channel selection (0/1)",
    ),
    "ASP_HOLD_DHASH_THRESH": (
        int,
        0,
        64,
        "dHash Hamming threshold for hold detection (0=off)",
    ),
    "ASP_MULTISCALE_GAIN": (int, 0, 1, "Enable multi-scale spatial gain map (0 or 1)"),
    "ASP_SIMILARITY_MODE": (
        int,
        0,
        1,
        "Use similarity (scale+rot+tx) instead of translation-only matching (0 or 1)",
    ),
    "ASP_HISTOGRAM_MATCH": (
        int,
        0,
        1,
        "Enable CDF histogram matching for bg normalisation (0 or 1)",
    ),
    "ASP_EXPOSURE_OUTLIER_THRESH": (
        float,
        0.0,
        255.0,
        "Max bg-lum deviation from median before norm skip (0=off)",
    ),
    "ASP_SCENE_CHANGE_LUMA_THRESH": (
        float,
        0.0,
        255.0,
        "Max mean-luma diff between frames before edge rejection (0=off)",
    ),
    "ASP_SCENE_CHANGE_BGR_THRESH": (
        float,
        0.0,
        255.0,
        "Max per-channel (BGR) mean diff between frames before edge rejection (0=off)",
    ),
    "ASP_SEAM_COLOR_GATE": (
        float,
        0.0,
        1.0,
        "Min Bhattacharyya colour similarity across seam to pass composite gate (0=off)",
    ),
    "ASP_SEAM_COLOR_GATE_BGR": (
        int,
        0,
        1,
        "Use per-channel BGR Bhattacharyya instead of greyscale in seam colour gate (0 or 1)",
    ),
    "ASP_MST_MIN_WEIGHT": (
        float,
        0.0,
        1.0,
        "Min mean MST edge weight before pre-BA SCANS fallback (0=off)",
    ),
    "ASP_CANVAS_SPAN_MIN_UTIL": (
        float,
        0.0,
        1.0,
        "Min canvas-span/expected-span utilisation ratio after BA (0=off)",
    ),
    "ASP_ADAPTIVE_SP_THRESH": (
        int,
        0,
        1,
        "Enable adaptive single-pose escalation threshold scaled by feather width (0 or 1)",
    ),
    "ASP_FG_FEATHER_CAP": (
        int,
        0,
        300,
        "Cap feather (px) in fg-dominated seam zones (0=off)",
    ),
    "ASP_FG_FEATHER_THRESH": (
        float,
        0.0,
        1.0,
        "Fg fraction threshold above which feather cap fires (default 0.60)",
    ),
    "ASP_TIGHT_STEP_PX": (
        int,
        0,
        500,
        "Dominant-axis step (px) below which seam is preemptively single-posed (0=off)",
    ),
    "ASP_SEAM_LUM_EQ": (
        int,
        0,
        1,
        "Enable post-composite seam luminance equalisation pass (0 or 1)",
    ),
    "ASP_SEAM_CHROMA_EQ": (
        int,
        0,
        1,
        "Enable post-composite chroma seam correction in LAB colour space (0 or 1)",
    ),
    "ASP_ADAPTIVE_SP_SOFT": (
        int,
        0,
        1,
        "Enable adaptive single-pose soft-edge width scaled by feather (0 or 1)",
    ),
    "ASP_SEAM_HARD_BARRIER": (
        int,
        0,
        1,
        "Upgrade fg-column barrier from soft (2.0) to hard (1e6) when corridor exists (0 or 1)",
    ),
    "ASP_SEAM_HARD_BARRIER_COST": (
        float,
        0.0,
        None,
        "Hard barrier cost for fg-dominated seam columns (default 1e6)",
    ),
    "ASP_SEAM_STEP_GATE": (
        float,
        0.0,
        255.0,
        "Max luma step at seam boundary before SCANS fallback (0=off, recommend 25.0)",
    ),
    "ASP_SEAM_SMOOTH_WINDOW": (
        int,
        0,
        51,
        "Median-filter window for seam path jitter removal (0 or 1 = off, recommend 5)",
    ),
    "ASP_SEAM_MARGIN": (
        int,
        0,
        50,
        "Min rows between seam path and zone top/bottom edge (0 = off, recommend 3)",
    ),
    "ASP_BG_NORM_MIN_PX": (
        int,
        0,
        10000,
        "Min background pixels for gain normalisation (0 = use built-in 200-px floor)",
    ),
    "ASP_SEAM_INSTABILITY_THRESH": (
        float,
        0.0,
        500.0,
        "Max seam path std (rows) before single-pose escalation (0=off, recommend 20.0)",
    ),
    "ASP_STATIC_INPUT_MAX_MAD": (
        float,
        0.0,
        255.0,
        "MAD ceiling for static-input detection (0=off, recommend 2.0; exits early with frame-0 copy)",
    ),
    "ASP_ZONE_MIN_HEIGHT": (
        int,
        0,
        500,
        "Min blend-zone rows before single-pose escalation without DP (0=off, recommend 20)",
    ),
    "ASP_SEAM_FG_PENETRATION_MAX": (
        float,
        0.0,
        1.0,
        "Max fraction of seam columns through fg before single-pose escalation (0=off, recommend 0.7)",
    ),
    "ASP_GNC_OUTER": (
        int,
        0,
        20,
        "GNC-TLS outer iterations (0=Cauchy only, default 8)",
    ),
    "ASP_USE_SAM2": (
        int,
        0,
        1,
        "Use SAM-2 video predictor for temporally consistent fg masking (0=off, 1=on)",
    ),
    "ASP_OTSU_BG_CORR": (
        int,
        0,
        1,
        "Per-pair Otsu bg mask for phase correlation §1A (0=off, 1=on; no new deps)",
    ),
    "ASP_BG_COMPLETE": (
        int,
        0,
        1,
        "Background zero-coverage fill after temporal median §5A (0=off, 1=NN fill, 2=ProPainter)",
    ),
    "ASP_BG_COMPLETE_MIN_ROWS": (
        int,
        0,
        10000,
        "Minimum empty-pixel rows before bg completion runs (0=always, default 20)",
    ),
    "ASP_TRI_CONSISTENCY": (
        float,
        0.0,
        10000.0,
        "§2.14: Triangular consistency residual threshold (px); penalises weakest edge in bad triangles (0=off, recommended 80.0)",
    ),
    "ASP_SEAM_OVERLAY": (
        int,
        0,
        1,
        "§2.4B: Draw coloured seam-quality diagnostic lines on composite output (0=off, 1=on)",
    ),
    "ASP_BLUR_REJECT_THRESH": (
        float,
        0.0,
        None,
        "§1.2E: Laplacian variance floor (uint8 scale) for blur pre-rejection (0=off, suggest 50.0)",
    ),
    "ASP_SEAM_LOW_TEXTURE_THRESH": (
        float,
        0.0,
        None,
        "§1.34: Laplacian variance floor (uint8 scale) for flat-zone seam pre-escalation (0=off, suggest 5.0)",
    ),
    "ASP_LINE_GRAD_WEIGHT": (
        float,
        0.0,
        None,
        "§1.35: Additive cost weight [0, weight] for fg-interior gradient penalty in seam DP (0=off, suggest 1.0)",
    ),
    "ASP_MATCH_SPREAD_CEIL": (
        float,
        0.0,
        None,
        "§1.36: Max allowed MAD of LoFTR per-match dx/dy displacements (px) before rejecting edge (0=off, suggest 30.0)",
    ),
    "ASP_MIN_BG_FRACTION": (
        float,
        0.0,
        1.0,
        "§1.37: Minimum mean bg-pixel fraction across frames after Stage 4; below → SCANS fallback (0=off, suggest 0.05)",
    ),
    "ASP_LOFTR_BG_RATIO_MIN": (
        float,
        0.0,
        1.0,
        "§1.38: Minimum fraction of LoFTR matches on background pixels before rejecting LoFTR edge (0=off, suggest 0.15)",
    ),
    "ASP_RENDER_MIN_COVERAGE": (
        float,
        0.0,
        1.0,
        "§1.39: Minimum fraction of canvas pixels covered by ≥1 warped frame after Stage 10; below → SCANS fallback (0=off, suggest 0.30)",
    ),
    "ASP_ADAPTIVE_RENDER_GAIN": (
        int,
        0,
        1,
        "§1.40: Enable luminance-adaptive gain clamp in sequential colour correction (0=off fixed ±12%, 1=adaptive ±14–26%)",
    ),
    "ASP_GAIN_DRIFT_MAX": (
        float,
        0.0,
        None,
        "§1.41: Maximum cumulative gain fold-change across all frames before resetting sequential gains to identity (0=off, suggest 2.0)",
    ),
    "ASP_INTERP_BG_FILL": (
        int,
        0,
        1,
        "§1.42: Use linear interpolation instead of nearest-neighbour copy for zero-coverage bg fill (0=off, 1=linear interp)",
    ),
    "ASP_ADJ_COVERAGE_MIN": (
        float,
        0.0,
        1.0,
        "§1.43: Minimum fraction of adjacent frame pairs (|i-j|=1) that must have ≥1 matching edge before BA; below threshold → SCANS fallback (0=off, suggest 0.60)",
    ),
    "ASP_MAX_ADJACENT_GAP_PX": (
        float,
        0.0,
        None,
        "§1.44: Maximum pixel gap between adjacent frames in the dominant scroll axis after Stage 9; BA 'stretch' artefact — gap > threshold → SCANS fallback (0=off, suggest 100.0)",
    ),
    "ASP_MAX_CANVAS_WIDTH_RATIO": (
        float,
        0.0,
        None,
        "§1.45: Maximum canvas_w / median_frame_w ratio after Stage 9; catches BA tx-drift that widens the canvas far beyond frame width in a nominally vertical-scroll sequence — ratio > threshold → SCANS fallback (0=off, suggest 1.5)",
    ),
    "ASP_CONTRAST_THRESH": (
        float,
        0.0,
        None,
        "§1.46: Pixel std floor (0–255 scale) for low-contrast frame pre-rejection; interior frames with std below threshold dropped before hold detection — catches flash/whiteout frames that offer no LoFTR/PC texture (0=off, suggest 15.0)",
    ),
    "ASP_SIGN_INCONSISTENCY_MAX": (
        float,
        0.0,
        0.5,
        "§1.47: Maximum minority-sign fraction of adjacent-edge dominant-axis displacements before BA; high rate means some edges report opposite scroll direction to the majority — sign of matching confusion → SCANS fallback (0=off, suggest 0.20)",
    ),
    "ASP_ADJ_DISP_CV_MAX": (
        float,
        0.0,
        None,
        "§1.48: Maximum coefficient of variation (std/mean) of adjacent-edge dominant-axis displacement magnitudes before BA; high CV means one or more adjacent edges report wildly different step sizes (wrong-harmonic PC peak, non-adjacent TM match) → SCANS fallback (0=off, suggest 0.50)",
    ),
    "ASP_ADJ_MIN_WEIGHT": (
        float,
        0.0,
        1.0,
        "§1.49: Minimum allowed match-confidence weight for any single adjacent edge (|i-j|=1) before BA; a near-zero weight means that pair has no reliable displacement, making its compositing seam ill-placed even if BA solves cleanly → SCANS fallback (0=off, suggest 0.20)",
    ),
    "ASP_BA_RESIDUAL_MAX": (
        float,
        0.0,
        None,
        "§1.50: Maximum per-edge BA residual (L2, pixels) after Stage 7 bundle adjustment; residual = |observed_disp − (affine[j].t − affine[i].t)|; outlier edges that survive GNC/Cauchy weighting still produce large residuals in the solved frame placement (Category B failure) → SCANS fallback (0=off, suggest 200.0)",
    ),
    "ASP_MIN_ADJACENT_OVERLAP_PX": (
        float,
        0.0,
        None,
        "§1.51: Minimum canvas-space overlap (pixels) between each consecutive frame pair after BA; overlap < floor means the blend zone is too narrow for reliable DP seam cutting or FEATHER_MIN=80 feathering — complementary to §1.44 (gap gate) which fires for negative overlap → SCANS fallback (0=off, suggest 20.0)",
    ),
    "ASP_BA_WMEAN_RESIDUAL_MAX": (
        float,
        0.0,
        None,
        "§1.52: Maximum confidence-weighted mean per-edge BA residual (L2, pixels); Σ(w_i×r_i)/Σ(w_i) where r_i=‖observed−predicted‖; catches systematic BA drift where all edges are moderately wrong (40–60px), passing §1.50 max-residual gate but indicating unreliable global frame placement → SCANS fallback (0=off, suggest 30.0)",
    ),
    "ASP_CANVAS_MAX_MEMORY_MB": (
        float,
        0.0,
        None,
        "§1.53: Maximum estimated float32 RGB canvas array footprint (canvas_h × canvas_w × 3 × 4 / 1024²) in megabytes; CANVAS_MAX_DIM=32768 prevents individual extreme dimensions but not extreme products (e.g. 32768×1920≈720 MB); fires before OOM-prone allocation → SCANS fallback (0=off, suggest 2048.0)",
    ),
    "ASP_RENDER_LUMA_STD_MIN": (
        float,
        0.0,
        None,
        "§1.54: Minimum luminance std (0–255 scale, simple BGR mean per pixel) across valid canvas pixels after Stage 10 temporal render; std near zero indicates degenerate output — BaSiC over-correction fusing all frames to same mean luma, silent warp failure, or hold-block leakage; distinct from §1.39 (coverage quantity) → SCANS fallback (0=off, suggest 5.0)",
    ),
    "ASP_MAX_AFFINE_ROTATION_DEG": (
        float,
        0.0,
        90.0,
        "§1.55: Maximum absolute rotation angle (degrees) allowed in any BA-solved affine; any affine exceeding this threshold signals a corrupted feature match — LoFTR latched onto a rotationally-similar texture patch; fires between Stage 7 BA and Stage 7b validation → SCANS fallback (0=off, suggest 5.0)",
    ),
    "ASP_TRAJ_SMOOTH_SIGMA": (
        float,
        0.0,
        None,
        "§3.16: Gaussian σ (frames) for StabStitch++ simplified trajectory smoother applied to BA-solved tx/ty sequences; corrects phase-correlation jitter in non-linear or multi-axis scroll; IQR-gated (fires only when adjacent-step IQR > ASP_TRAJ_SMOOTH_IQR_THRESH); 0=off, suggest 1.5",
    ),
    "ASP_TRAJ_SMOOTH_IQR_THRESH": (
        float,
        0.0,
        None,
        "§3.16: IQR threshold (px) below which trajectory smoother is skipped — clean linear-scroll sequences have near-zero IQR and are not modified; default 10.0",
    ),
    "ASP_FG_POSE_GAP_THRESH": (
        float,
        0.0,
        255.0,
        "§1.60: Mean absolute fg-pixel luminance diff (luma units) between adjacent warped frames in blend zone; exceeds → single-pose escalation before DP (0=off, suggest 35.0)",
    ),
    "ASP_MIN_CANVAS_ASPECT": (
        float,
        0.0,
        None,
        "§1.62: Minimum canvas height/width aspect ratio for vertical-scroll sequences after Stage 9 BA; aspect below floor → SCANS fallback (0=off, suggest 0.5)",
    ),
    "ASP_FG_SEAM_EROSION_PX": (
        int,
        0,
        20,
        "§1.65: Erode fg mask by this many pixels before Tier-1 cost assignment; converts outline ring from cost=1.0 to cost=0.5, nudging DP seam one ring outward (0=off, suggest 2)",
    ),
    "ASP_DHASH_EXACT_DROP": (
        int,
        0,
        1,
        "§1.64: Drop consecutive frames whose 64-bit dHash is bit-identical before all other filters; set to 1 to enable (0=off)",
    ),
    "ASP_SEAM_NCC_GATE": (
        float,
        0.0,
        1.0,
        "§1.66: Post-composite NCC structural coherence gate; seams with NCC < threshold trigger SCANS fallback (0=off, suggest 0.45)",
    ),
    "ASP_CANVAS_SPREAD_MIN": (
        float,
        0.0,
        1.0,
        "§1.67: Minimum fraction of expected canvas range that selected frames must span before BA; catches clustered frame sets (0=off, suggest 0.5)",
    ),
    "ASP_FEATHER_RATIO_MAX": (
        float,
        0.0,
        None,
        "§1.68: Maximum fold-change ratio between adjacent seam feather widths; enforced via forward+backward pass clamping after all §1.6B/§1.19 feather adjustments; prevents visible tonal rhythm discontinuity from 80px-next-to-300px seam pairs (0=off, suggest 3.0)",
    ),
    "ASP_SEAM_DP_BG_MIN": (
        float,
        0.0,
        1.0,
        "§1.69: Minimum fraction of DP seam path columns where BOTH adjacent frame bg_masks classify the pixel as background; below threshold → seam was forced through character pixels despite cost-map steering → single-pose escalation (0=off, suggest 0.30)",
    ),
    "ASP_SEAM_ZONE_FG_MAX": (
        float,
        0.0,
        1.0,
        "§1.70: Maximum fraction of blend-zone pixels classified as fg in EITHER adjacent warped frame; when the entire zone is fg-dominated no background corridor exists for the DP seam → single-pose escalation before DP (0=off, suggest 0.85)",
    ),
    "ASP_BG_LUM_SPREAD_MAX": (
        float,
        0.0,
        255.0,
        "§1.71: Maximum per-frame background median luminance range (max−min, luma units 0–255) across all frames before Stage 11 compositing; extreme spread means gain normalisation would require >2× corrections, producing a brightness staircase → SCANS fallback (0=off, suggest 80.0)",
    ),
    "ASP_SEAM_ENTROPY_GATE": (
        float,
        0.0,
        None,
        "§1.72: Maximum per-seam Shannon entropy asymmetry (|H_top − H_bot|, bits) across a 50-row band at each seam boundary; high asymmetry indicates one side is flat-colour (character body) and the other is rich-texture (background) → SCANS fallback (0=off, suggest 1.5)",
    ),
    "ASP_BG_GAIN_MONOTONE_THRESH": (
        float,
        0.0,
        1.0,
        "§1.73: Maximum absolute Kendall-τ correlation between frame order and per-frame background median luminance; |τ| close to 1.0 means luma is perfectly monotone (brightness staircase) even when total spread is within ASP_BG_LUM_SPREAD_MAX → SCANS fallback (0=off, suggest 0.85)",
    ),
    "ASP_CANVAS_FILL_MIN": (
        float,
        0.0,
        1.0,
        "§1.74: Minimum fraction of canvas pixels with max(B,G,R) > ASP_CANVAS_FILL_PIX_THRESH; below threshold indicates large empty canvas regions from failed frame warps → SCANS fallback (0=off, suggest 0.60)",
    ),
    "ASP_CANVAS_FILL_PIX_THRESH": (
        int,
        0,
        255,
        "§1.74: Per-channel intensity floor used by the canvas fill ratio gate; pixels at or below this value in all channels are counted as empty (default 10 avoids classifying dark-background anime as unfilled)",
    ),
    "ASP_STRIP_VARIANCE_RATIO_MAX": (
        float,
        0.0,
        None,
        "§1.75: Maximum ratio of most-textured to least-textured strip Laplacian variance; a high ratio signals structural content incompatibility (one strip flat-colour, another richly detailed) that seam-boundary gates miss → SCANS fallback (0=off, suggest 10.0)",
    ),
    "ASP_SEAM_MAX_COL_GATE": (
        float,
        0.0,
        255.0,
        "§1.76: Maximum allowed worst-column luma step across any seam band; catches localised hot-spots (character edges, shadow lines) that the §1.24 band-mean gate smooths away → SCANS fallback (0=off, suggest 40.0)",
    ),
    "ASP_SEAM_SAT_GATE": (
        float,
        0.0,
        255.0,
        "§1.77: Maximum allowed mean HSV saturation jump between bands above/below a seam; catches colour-vibrancy discontinuities (muted background vs vivid character) that luma and entropy gates miss → SCANS fallback (0=off, suggest 40.0)",
    ),
    "ASP_SEAM_HUE_GATE": (
        float,
        0.0,
        90.0,
        "§1.78: Maximum allowed circular mean hue shift between bands above/below a seam; catches colour-temperature discontinuities (warm vs cool strips) that saturation and luma gates miss; near-achromatic pixels excluded → SCANS fallback (0=off, suggest 30.0)",
    ),
    "ASP_SEAM_SHARP_GATE": (
        float,
        0.0,
        20.0,
        "§1.79: Maximum allowed |log₂(Laplacian-variance-top / Laplacian-variance-bottom)| across a seam; catches blur/sharpness discontinuities caused by different MPEG compression or upscaling applied to source frames; a score of 3.0 means one strip is 8× sharper → SCANS fallback (0=off, suggest 3.0)",
    ),
    "ASP_SEAM_GRAD_DIR_GATE": (
        float,
        0.0,
        90.0,
        "§1.80: Maximum allowed circular distance (degrees) between mean undirected Sobel gradient orientations above and below a seam; catches structural orientation discontinuities (diagonal speed-lines above vs horizontal horizon below) that all colour-space gates miss; 45°=orthogonal content, 90°=maximum → SCANS fallback (0=off, suggest 45.0)",
    ),
    "ASP_SEAM_SSIM_GATE": (
        float,
        0.0,
        1.0,
        "§1.81: Minimum allowed band-SSIM between the strip immediately above and below a seam (gate fires when score FALLS BELOW threshold); SSIM jointly captures luma, contrast, and structure — a catch-all perceptual gate complementing the targeted §1.76–§1.80 single-dimension gates; 1.0=identical, 0.85=clear discontinuity → SCANS fallback (0=off, suggest 0.85)",
    ),
    "ASP_SEAM_FREQ_GATE": (
        float,
        0.0,
        1.0,
        "§1.82: Maximum allowed spatial-frequency profile mismatch (1 − Pearson-r of column-averaged FFT magnitude spectra) between bands above and below a seam; catches spectral content discontinuities (fine noise texture vs smooth gradient) invisible to all §1.76–§1.81 gates; 0=identical spectra, 1=orthogonal spectra → SCANS fallback (0=off, suggest 0.6)",
    ),
}


def validate_asp_config(
    config: Dict[str, Any],
    *,
    strict: bool = False,
) -> List[str]:
    """§1.8B: Validate a flat ASP config dict against ``_CONFIG_SCHEMA``.

    Parameters
    ----------
    config:
        Flat mapping of ASP key → value (as returned by :func:`load_asp_config`).
    strict:
        When *True*, raises :exc:`ValueError` listing all violations instead of
        returning them.  Use in CI/scripting contexts where a misconfigured
        experiment should abort immediately.

    Returns
    -------
    list[str]
        Violation messages.  Empty list means the config is valid.

    Notes
    -----
    *Unknown* keys (not in ``_CONFIG_SCHEMA``) emit a :class:`UserWarning` but
    are not counted as violations — forward-compatibility is preserved so that
    configs written for a newer pipeline version still load on an older one.

    TOML integers are accepted where *float* is expected (TOML does not
    distinguish ``0`` from ``0.0`` at the application level).
    """
    violations: List[str] = []

    for key, val in config.items():
        if key not in _CONFIG_SCHEMA:
            warnings.warn(
                f"[ASP config] Unknown key {key!r} — not in schema; forwarded as-is.",
                UserWarning,
                stacklevel=2,
            )
            continue

        expected_type, lo, hi, desc = _CONFIG_SCHEMA[key]

        # Allow int where float is expected (TOML integers → Python int)
        is_type_ok = isinstance(val, expected_type) or (
            expected_type is float and isinstance(val, int)
        )
        if not is_type_ok:
            violations.append(
                f"{key}: expected {expected_type.__name__}, "
                f"got {type(val).__name__} ({val!r}). Hint: {desc}"
            )
            continue

        numeric_val = float(val) if expected_type is float else int(val)
        if lo is not None and numeric_val < lo:
            violations.append(f"{key}={val!r} is below minimum {lo}. Hint: {desc}")
        if hi is not None and numeric_val > hi:
            violations.append(f"{key}={val!r} exceeds maximum {hi}. Hint: {desc}")

    if strict and violations:
        raise ConfigError(
            "ASP config validation failed:\n"
            + "\n".join(f"  • {v}" for v in violations)
        )

    return violations


def load_asp_config(
    path: Optional[str] = None,
    *,
    override_env: bool = True,
    validate: bool = False,
    strict: bool = False,
) -> Dict[str, Any]:
    """Load ASP pipeline configuration from a TOML file.

    Parameters
    ----------
    path:
        Path to the TOML file.  Defaults to ``asp_config.toml`` in the
        current working directory.  If the file does not exist the function
        returns an empty dict without error.
    override_env:
        When *True* (default), each loaded key is written to ``os.environ``
        via ``setdefault`` so downstream modules see it.  Set to *False* to
        load values for inspection only, without touching the environment.
    validate:
        When *True*, run :func:`validate_asp_config` on the loaded dict before
        writing env vars.  Invalid keys emit warnings (or raise, if *strict*).
    strict:
        Passed to :func:`validate_asp_config` when *validate* is *True*.
        Raises :exc:`ValueError` on the first batch of violations.

    Returns
    -------
    dict
        Flat mapping of all keys found in the TOML file (sections merged).
        Empty if the file is absent or contains no section data.
    """
    config_path = Path(path) if path is not None else Path(_DEFAULT_CONFIG_NAME)
    if not config_path.exists():
        return {}

    with open(config_path, "rb") as fh:
        raw: Dict[str, Any] = tomllib.load(fh)

    flat: Dict[str, Any] = {}
    for value in raw.values():
        if isinstance(value, dict):
            flat.update(value)

    if not flat:
        return {}

    if validate:
        validate_asp_config(flat, strict=strict)

    if override_env:
        for key, val in flat.items():
            if isinstance(val, bool):
                os.environ.setdefault(key, "1" if val else "0")
            else:
                os.environ.setdefault(key, str(val))

    return flat


def get_asp(key: str, default: str = "") -> str:
    """Return an ASP pipeline env-var, falling back to *default*.

    Prefer this over bare ``os.environ.get("ASP_*")`` calls because it
    guarantees the default is consistent with the schema and makes call-sites
    greppable via a single name.

    Parameters
    ----------
    key:
        The ``ASP_*`` environment variable name (e.g. ``"ASP_HOLD_THRESHOLD"``).
    default:
        String default returned when the key is absent from the environment.
        Callers that need a non-string type should cast the return value::

            threshold = float(get_asp("ASP_HOLD_THRESHOLD", "0.025"))
            enabled   = get_asp("ASP_POISSON_SEAM", "0") != "0"

    Returns
    -------
    str
        The env-var value or *default*.
    """
    return os.environ.get(key, default)


# Logical section groupings for the TOML dump (§1.8C).
# Maps section header → list of ASP env-var key prefixes belonging to it.
_DUMP_SECTIONS: Dict[str, List[str]] = {
    "frame_selection": [
        "ASP_HOLD_THRESHOLD",
        "ASP_HOLD_DHASH_THRESH",
        "ASP_DHASH_EXACT_DROP",
        "ASP_NEAR_DUP_LUMA",
        "ASP_HIGH_HOLD_RESPONSE",
        "ASP_TEMPORAL_VAR_THRESH",
        "ASP_BLUR_REJECT_THRESH",
        "ASP_CONTRAST_THRESH",
        "ASP_TWO_CHANNEL_SELECT",
        "ASP_OTSU_BG_CORR",
        "ASP_POSE_WINDOW_PX",
        "ASP_SGM_PROXY",
    ],
    "compositing": [
        "ASP_SP_SOFT_PX",
        "ASP_GATE_GHOST_FLOOR",
        "ASP_POISSON_SEAM",
        "ASP_TOONCRAFTER_SEAM",
        "ASP_MULTISCALE_GAIN",
        "ASP_HISTOGRAM_MATCH",
        "ASP_EXPOSURE_OUTLIER_THRESH",
        "ASP_SEAM_COLOR_GATE",
        "ASP_SEAM_COLOR_GATE_BGR",
        "ASP_ADAPTIVE_SP_THRESH",
        "ASP_FG_FEATHER_CAP",
        "ASP_FG_FEATHER_THRESH",
        "ASP_TIGHT_STEP_PX",
        "ASP_SEAM_LUM_EQ",
        "ASP_SEAM_CHROMA_EQ",
        "ASP_ADAPTIVE_SP_SOFT",
        "ASP_SEAM_HARD_BARRIER",
        "ASP_SEAM_HARD_BARRIER_COST",
        "ASP_SEAM_SMOOTH_WINDOW",
        "ASP_SEAM_MARGIN",
        "ASP_BG_NORM_MIN_PX",
        "ASP_SEAM_INSTABILITY_THRESH",
        "ASP_ZONE_MIN_HEIGHT",
        "ASP_SEAM_FG_PENETRATION_MAX",
        "ASP_SEAM_OVERLAY",
        "ASP_SEAM_LOW_TEXTURE_THRESH",
        "ASP_LINE_GRAD_WEIGHT",
        "ASP_FG_POSE_GAP_THRESH",
        "ASP_FG_SEAM_EROSION_PX",
        "ASP_SEAM_NCC_GATE",
        "ASP_SEAM_ENTROPY_GATE",
        "ASP_FEATHER_RATIO_MAX",
        "ASP_SEAM_DP_BG_MIN",
        "ASP_SEAM_ZONE_FG_MAX",
        "ASP_SEAM_MAX_COL_GATE",
        "ASP_SEAM_SAT_GATE",
        "ASP_SEAM_HUE_GATE",
        "ASP_SEAM_SHARP_GATE",
        "ASP_SEAM_GRAD_DIR_GATE",
        "ASP_SEAM_SSIM_GATE",
        "ASP_SEAM_FREQ_GATE",
    ],
    "bundle_adjust": [
        "ASP_BA_F_SCALE",
        "ASP_GNC_OUTER",
        "ASP_MATCH_SPREAD_CEIL",
        "ASP_LOFTR_BG_RATIO_MIN",
    ],
    "pipeline": [
        "ASP_COV_MIN_MULTI_PCT",
        "ASP_SCANS_RELOAD",
        "ASP_USE_SAM2",
        "ASP_BG_COMPLETE",
        "ASP_BG_COMPLETE_MIN_ROWS",
        "ASP_TRI_CONSISTENCY",
        "ASP_MIN_BG_FRACTION",
        "ASP_RENDER_MIN_COVERAGE",
        "ASP_ADJ_COVERAGE_MIN",
        "ASP_MAX_ADJACENT_GAP_PX",
        "ASP_MAX_CANVAS_WIDTH_RATIO",
        "ASP_MIN_CANVAS_ASPECT",
        "ASP_MIN_ADJACENT_OVERLAP_PX",
        "ASP_CANVAS_MAX_MEMORY_MB",
        "ASP_RENDER_LUMA_STD_MIN",
        "ASP_MAX_AFFINE_ROTATION_DEG",
        "ASP_CANVAS_SPAN_MIN_UTIL",
        "ASP_SEAM_STEP_GATE",
        "ASP_STATIC_INPUT_MAX_MAD",
        "ASP_SIGN_INCONSISTENCY_MAX",
        "ASP_ADJ_DISP_CV_MAX",
        "ASP_ADJ_MIN_WEIGHT",
        "ASP_BA_RESIDUAL_MAX",
        "ASP_BA_WMEAN_RESIDUAL_MAX",
        "ASP_TRAJ_SMOOTH_SIGMA",
        "ASP_TRAJ_SMOOTH_IQR_THRESH",
        "ASP_SCENE_CHANGE_LUMA_THRESH",
        "ASP_SCENE_CHANGE_BGR_THRESH",
        "ASP_ADAPTIVE_RENDER_GAIN",
        "ASP_GAIN_DRIFT_MAX",
        "ASP_INTERP_BG_FILL",
        "ASP_CANVAS_SPREAD_MIN",
        "ASP_BG_LUM_SPREAD_MAX",
        "ASP_BG_GAIN_MONOTONE_THRESH",
        "ASP_CANVAS_FILL_MIN",
        "ASP_CANVAS_FILL_PIX_THRESH",
        "ASP_STRIP_VARIANCE_RATIO_MAX",
    ],
}


def dump_asp_config(
    path: Optional[str] = None,
    *,
    include_defaults: bool = False,
) -> str:
    """§1.8C/D: Serialize the current ASP env-var state to a TOML file (S126/S131).

    Reads all known ``ASP_*`` env-var keys from ``os.environ`` and writes them
    to a TOML file grouped into logical sections (frame_selection, compositing,
    bundle_adjust, pipeline).  Only keys that are currently set in the environment
    are written by default; pass ``include_defaults=True`` to emit all schema keys
    with their default values (``"0"`` for most flags, or the built-in default).

    §1.8D enhancement (S131): each key is preceded by two comment lines:
    *   ``# type: <typename>  range: [min, max]`` — machine-readable constraint
        annotation (``min``/``max`` are ``None`` when unbounded).
    *   ``# <description>`` — human-readable explanation from ``_CONFIG_SCHEMA``.

    These comments survive round-trip through a TOML editor and let tools
    validate the file against the schema without having to import the Python module.

    This is the inverse of :func:`load_asp_config`: it lets you capture the
    current tuning state of a successful run and save it as a reproducible config
    file for future experiments.

    Parameters
    ----------
    path:
        Destination TOML file path.  Defaults to ``asp_config.toml`` in the
        current working directory.  Parent directories are created if needed.
    include_defaults:
        When *True*, all schema keys are emitted (with ``"0"`` as the fallback
        default for unset keys).  When *False* (default), only keys that are
        explicitly set in the environment are written.

    Returns
    -------
    str
        Absolute path to the written file.
    """
    out_path = Path(path) if path is not None else Path(_DEFAULT_CONFIG_NAME)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    lines: List[str] = [
        "# ASP pipeline configuration — generated by dump_asp_config()",
        f"# Generated at: {__import__('datetime').datetime.now().isoformat(timespec='seconds')}",
        "",
    ]

    written_keys: set = set()

    for section, keys in _DUMP_SECTIONS.items():
        section_lines: List[str] = []
        for key in keys:
            env_val = os.environ.get(key)
            if env_val is None and not include_defaults:
                continue
            val_str = env_val if env_val is not None else "0"
            # Preserve numeric type: if the value looks like a float with decimal
            # point keep it; if it looks like a plain integer, omit quotes.
            try:
                if "." in val_str:
                    toml_val = str(float(val_str))
                else:
                    toml_val = str(int(val_str))
            except ValueError:
                toml_val = f'"{val_str}"'
            schema_entry = _CONFIG_SCHEMA.get(key)
            if schema_entry is not None:
                _typ, _lo, _hi, hint = schema_entry
                # §1.8D: emit machine-readable type/range annotation first.
                _type_name = getattr(_typ, "__name__", str(_typ)) if _typ is not None else "str"
                _range_str = f"[{_lo}, {_hi}]"
                section_lines.append(f"# type: {_type_name}  range: {_range_str}")
                if hint:
                    section_lines.append(f"# {hint}")
            section_lines.append(f"{key} = {toml_val}")
            written_keys.add(key)

        if section_lines:
            lines.append(f"[{section}]")
            lines.extend(section_lines)
            lines.append("")

    # Emit any env-set ASP_* keys not covered by _DUMP_SECTIONS under [extra].
    extra_lines: List[str] = []
    for key, val in os.environ.items():
        if key.startswith("ASP_") and key not in written_keys:
            try:
                if "." in val:
                    toml_val = str(float(val))
                else:
                    toml_val = str(int(val))
            except ValueError:
                toml_val = f'"{val}"'
            extra_lines.append(f"{key} = {toml_val}")
    if extra_lines:
        lines.append("[extra]")
        lines.extend(extra_lines)
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return str(out_path.resolve())

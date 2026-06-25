"""
§1.8A: TOML-based ASP pipeline configuration loader.

Loads ``asp_config.toml`` from the current working directory (or a path
supplied by the caller).  Any key present in the TOML file is exported as an
environment variable (via ``os.environ.setdefault``), so all downstream
``os.environ.get`` calls in pipeline modules pick up the value automatically.
Existing env-var values always win over the config file.

Usage::

    from backend.src.animation.core.config import load_asp_config
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
    "ASP_FLOW_ENGINE": (
        str,
        None,
        None,
        "§3.1A: Flow engine — 'dis' | 'searaft' | 'animeinterp'",
    ),
    "ASP_ANIMEINTERP_WEIGHTS": (
        str,
        None,
        None,
        "§3.1A: Path to ConvGRU .pth weights (empty=ImageNet VGG-19 init)",
    ),
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
    "ASP_ZONE_PRE_SSIM_THRESH": (
        float,
        0.0,
        1.0,
        "§1.86: Zone-SSIM floor (post-ARAP) for single-pose escalation (0=off, suggest 0.35)",
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
    "ASP_SEAM_NOISE_GATE": (
        float,
        0.0,
        None,
        "§1.83: Maximum allowed normalised noise-level asymmetry |σ_top−σ_bot|/mean(σ) between bands above and below a seam (Laplacian-std estimator, Immerkær 1996); catches codec/exposure bitrate discontinuities invisible to all §1.76–§1.82 luma/chroma/spectral gates; 0=identical noise, >1=substantial mismatch → SCANS fallback (0=off, suggest 1.0)",
    ),
    "ASP_SEAM_CONTRAST_GATE": (
        float,
        0.0,
        None,
        "§1.84: Maximum allowed RMS contrast ratio max(c_top,c_bot)/min(c_top,c_bot) where c=std/max(1,mean) is the coefficient of variation; catches broad dynamic-range discontinuities distinct from §1.79 sharpness (fine-detail) and §1.82 spectral content; 1=identical contrast, >4=substantial mismatch → SCANS fallback (0=off, suggest 4.0)",
    ),
    "ASP_SEAM_ENSEMBLE_VOTES": (
        int,
        0,
        None,
        "§1.85: Minimum number of active quality gates that must simultaneously flag the same seam to trigger the multi-gate ensemble fallback; each gate uses its own threshold (0 disables the gate from voting); catches corner cases where no single gate fires but multiple metrics are simultaneously near-threshold; suggest 3 when several §1.76–§1.84 gate thresholds are enabled",
    ),
    "ASP_GATE_STRIP_GRAD_CV": (int, 0, 1, "§5.32: Enable pipeline strip gradient CV gate (0 or 1, default 1)"),
    "ASP_GATE_STRIP_GRAD_CV_FLOOR": (float, 0.0, 5.0, "§5.32: Strip gradient CV gate floor (default 0.50)"),
    "ASP_GATE_HIST_INTERSECT_RATIO": (
        float,
        0.0,
        1.0,
        "§5.37: Bench histogram intersection ratio limit (default 0.5); gate fires when ASP intersection < ratio × SIM intersection",
    ),
    "ASP_GATE_SAT_CV": (
        int,
        0,
        1,
        "§5.38: Enable pipeline strip saturation CV gate (0 or 1, default 1)",
    ),
    "ASP_GATE_SAT_CV_FLOOR": (
        float,
        0.0,
        2.0,
        "§5.38: Strip saturation CV gate floor (default 0.40; high CV = color mismatch)",
    ),
    "ASP_PROPAINTER": (
        int,
        0,
        1,
        "§3.13: Enable ProPainter Stage 4.7 multi-frame background completion; runs ProPainter inpainting on all selected frames after BiRefNet masking to replace foreground-occupied pixels with temporally coherent background before phase correlation and temporal median render; requires 'pip install propainter'; falls back to NN fill when unavailable (0=off, 1=on)",
    ),
    "ASP_PROPAINTER_DEVICE": (
        str,
        None,
        None,
        "§3.13: Torch device string for ProPainter inference (e.g. 'cpu', 'cuda', 'cuda:0'); default 'cpu'",
    ),
    "ASP_MASKED_MEDIAN": (
        int,
        0,
        1,
        "§1.87: Masked-median background plate (Overmix AnimRender approach); pixels where every frame has foreground are left as zero instead of ghost-averaging different animation poses; pairs with ASP_BG_COMPLETE>=1 to fill the zero-coverage holes; eliminates temporal-median ghosting root cause without GPU deps (0=off, 1=on)",
    ),
    "ASP_HORIZONTAL_COMPOSITE": (
        int,
        0,
        1,
        "§3.14B: Horizontal-strip compositing; when scroll_axis='horizontal' detected, uses vertical seam cuts (transposed compositing) instead of falling back to SCANS; unlocks horizontal-scroll test sequences (0=off; when off, horizontal scroll still triggers SCANS fallback)",
    ),
    "ASP_MLLM_SCORER": (
        int,
        0,
        1,
        "§3.10: Enable MLLM semantic quality scoring via ollama (Qwen2-VL-7B); adds body_coherence/seam_quality/bg_consistency/overall fields to benchmark output; requires ollama running locally with ASP_MLLM_MODEL (default 'qwen2-vl:7b') pulled (0=off)",
    ),
    "ASP_HOLD_AVERAGE": (
        int,
        0,
        1,
        "§3.12A: Overmix-style hold-block sub-pixel averaging; ECC-aligns all frames within each animation hold block and stack-averages them to recover √N SNR; requires ASP_HOLD_THRESHOLD>0 or ASP_HOLD_DHASH_THRESH>0 to detect hold blocks (0=off, 1=on)",
    ),
    "ASP_SI_FID": (
        int,
        0,
        1,
        "§3.9: Self-Inception FID proxy (SI-FID); patch Laplacian sharpness ratio computed from ASP output vs simple_stitch; added as si_fid field in benchmark result dicts; zero new GPU/FID deps (0=off, 1=on)",
    ),
    "ASP_MESH_BARRIER": (
        int,
        0,
        1,
        "§3.15B: Triangular mesh barrier — Delaunay triangulation of fg contour points rasterized as 1e6 hard barrier in seam cost map, forcing DP seam into bg-only corridors (0=off, 1=on)",
    ),
    "ASP_HYBRID_EXPORT_PATH": (
        str,
        None,
        None,
        "§2.8: Path to write HybridStitch JSON export (pipeline state: frame paths, affines, photometric corrections, seam boundaries); empty=disabled",
    ),
    "ASP_HITL_PRESET_DIR": (
        str,
        None,
        None,
        "§3.16B: Directory for per-test HITL preset JSON files (empty=~/.image-toolkit/hitl_presets/)",
    ),
    "ASP_CAMFLOW": (
        str,
        None,
        None,
        "§3.5B: Camera displacement method — '' (whole-frame phase-corr) | 'bg_masked' (background-only phase-corr)",
    ),
    "ASP_HIST_MATCH_SEAM": (
        bool,
        None,
        None,
        "§1.88: ECDF histogram matching in seam blend band after mean-shift (default off)",
    ),
    "ASP_SEAM_ORDER": (
        str,
        None,
        None,
        "§1.89: Seam processing order — '' (linear) | 'residual' (ascending post_warp_diff)",
    ),
    "ASP_BILATERAL_SEAM": (
        bool,
        None,
        None,
        "§1.90: Post-compositing bilateral filter pass in ±5px around seam paths (default off)",
    ),
    "ASP_HF_SEAM_COST": (
        bool,
        None,
        None,
        "§3.17: Laplacian-energy-per-column additive cost in seam cost map (default off)",
    ),
    "ASP_SEAM_LUM_CONVERGE": (
        bool,
        None,
        None,
        "§1.91: Iterative seam color match until band delta < target (default off)",
    ),
    "ASP_SEAM_LUM_CONVERGE_TARGET": (
        float,
        0.0,
        50.0,
        "§1.91: Target mean lum delta for convergence (default 5.0 lum units)",
    ),
    "ASP_SMOOTH_FEATHER": (
        bool,
        None,
        None,
        "§1.92: Gaussian smooth on feather widths between adjacent seams (default off)",
    ),
    "ASP_SMOOTH_FEATHER_SIGMA": (
        float,
        0.1,
        5.0,
        "§1.92: Gaussian sigma for feather smoothing in seam units (default 1.0)",
    ),
    "ASP_SP_THRESH_FG_SCALE": (
        bool,
        None,
        None,
        "§1.95: Scale SP threshold down for fg-heavy zones",
    ),
    "ASP_SP_THRESH_FG_FACTOR": (
        float,
        0.1,
        1.0,
        "§1.95: SP threshold scale factor (default 0.7)",
    ),
    "ASP_SP_FG_FRAC_THRESH": (
        float,
        0.0,
        1.0,
        "§1.95: Fg fraction above which threshold is scaled",
    ),
    "ASP_ZONE_CHROMA_ALIGN": (
        bool,
        None,
        None,
        "§3.19: Per-zone pre-blend LAB a/b mean alignment",
    ),
    "ASP_ENTROPY_GAP_THRESH": (
        float,
        0.0,
        10.0,
        "§1.97: Entropy gap threshold for single-pose escalation (bits)",
    ),
    "ASP_SMOOTH_GAIN": (
        bool,
        None,
        None,
        "§1.98: Gaussian smooth per-frame gain corrections",
    ),
    "ASP_SMOOTH_GAIN_SIGMA": (
        float,
        0.1,
        5.0,
        "§1.98: Gain smoothing sigma in frames",
    ),
    "ASP_EXTRA_FG_DILATION": (
        float,
        0.0,
        50.0,
        "§3.20: Extra outer fg dilation ring in seam cost map (0=off)",
    ),
    "ASP_SEAM_PIN_ROWS": (
        float,
        0.0,
        20.0,
        "§1.99: Rows at zone top/bottom with amplified fg cost (0=off)",
    ),
    "ASP_ZONE_MAD_THRESH": (
        float,
        0.0,
        255.0,
        "§1.101: Full zone MAD threshold for single-pose escalation (0=off)",
    ),
    "ASP_WARP_MOMENTUM_DAMP": (
        bool,
        None,
        None,
        "§1.102: Lower SP threshold after adjacent single-pose fallback",
    ),
    "ASP_WARP_MOMENTUM_FACTOR": (
        float,
        0.1,
        1.0,
        "§1.102: Momentum damping multiplier for SP threshold",
    ),
    "ASP_SP_REF_PROX": (
        bool,
        None,
        None,
        "§1.103: Use reference-proximity for dominant frame in single-pose",
    ),
    "ASP_ZONE_LUM_NORM": (
        bool,
        None,
        None,
        "§1.104: Per-zone luminance normalization before blend",
    ),
    "ASP_FG_OVERLAP_BLEND_CAP": (
        float,
        0.0,
        0.5,
        "§1.105: Blend weight cap for fg-overlap pixels with high lum diff",
    ),
    "ASP_POST_SEAM_WARN_THRESH": (
        float,
        0.0,
        100.0,
        "§1.106: Post-composite seam lum step warning threshold",
    ),
    "ASP_ADAPTIVE_SEAM_BAND": (
        bool,
        None,
        None,
        "§1.107: Zone-height-aware seam band width in single-pose path",
    ),
    "ASP_ADAPTIVE_SEAM_BAND_MAX": (
        float,
        4.0,
        100.0,
        "§1.107: Max seam band width for adaptive mode",
    ),
    "ASP_LAPLACIAN_ALPHA_SCHEDULE": (
        bool,
        None,
        None,
        "§1.108: Sharpen blend mask for fine Laplacian levels",
    ),
    "ASP_COST_MAP_NORM": (
        bool,
        None,
        None,
        "§1.109: L-inf normalize seam cost map (excludes hard barriers)",
    ),
    "ASP_COST_MAP_BLUR_SIGMA": (
        float,
        0.0,
        20.0,
        "§1.110: Gaussian blur sigma for seam cost map soft region (0=off)",
    ),
    "ASP_ZONE_SAT_NORM": (
        bool,
        None,
        None,
        "§1.111: Zone background HSV saturation normalization",
    ),
    "ASP_SEAM_DRIFT_THRESH": (
        float,
        0.0,
        None,
        "§1.112: Max seam path column-to-column jump before single-pose escalation (0=off)",
    ),
    "ASP_COST_COL_SMOOTH_SIGMA": (
        float,
        0.0,
        10.0,
        "§1.113: Column-wise Gaussian smooth sigma for seam cost map (0=off)",
    ),
    "ASP_ZONE_CONTRAST_EQ": (
        bool,
        None,
        None,
        "§1.114: Zone RMS contrast equalization before Laplacian blend",
    ),
    "ASP_FEATHER_JUMP_MAX": (
        float,
        0.0,
        500.0,
        "§1.115: Absolute feather jump cap between adjacent seams (0=off)",
    ),
    "ASP_ZONE_BG_FRAC_DIAG": (
        bool,
        None,
        None,
        "§1.116: Record per-seam blend zone bg fraction in debug context",
    ),
    "ASP_ZONE_FAST_NCC_THRESH": (
        float,
        0.0,
        1.0,
        "§1.117: Fast thumbnail NCC threshold for single-pose pre-escalation (0=off)",
    ),
    "ASP_SEAM_SHARP_MIN": (
        float,
        0.0,
        1000.0,
        "§1.118: Seam band Laplacian variance floor — logs blur warning when below",
    ),
    "ASP_ZONE_WIDTH_CV_MAX": (
        float,
        0.0,
        None,
        "§1.119: Zone width CV gate — pre-escalates narrowest seam when layout is uneven (0=off)",
    ),
    "ASP_SEAM_SAT_WARN_THRESH": (
        float,
        0.0,
        255.0,
        "§1.120: Saturation step warn threshold — logs warning when sat diff exceeds (0=off)",
    ),
    "ASP_ZONE_HIST_THRESH": (
        float,
        0.0,
        1.0,
        "§1.121: Zone histogram intersection pre-gate threshold (0=off)",
    ),
    "ASP_HIGH_PATH_COST_THRESH": (
        float,
        0.0,
        10.0,
        "§1.122: Mean DP path cost threshold for single-pose escalation (0=off)",
    ),
    "ASP_SCATTER_COST": (
        bool,
        None,
        None,
        "§1.123: Local pixel variance penalty in seam cost map",
    ),
    "ASP_SCATTER_COST_WEIGHT": (
        float,
        0.0,
        2.0,
        "§1.123: Scatter cost additive weight",
    ),
    "ASP_ADAPTIVE_SP_SOFT_MIN": (
        float,
        1.0,
        20.0,
        "§1.124: Minimum soft-edge px for high-residual seams",
    ),
    "ASP_ADAPTIVE_SP_SOFT_MAX": (
        float,
        1.0,
        30.0,
        "§1.124: Maximum soft-edge px for low-residual seams",
    ),
    "ASP_SEAM_TRANSITION_PEN": (
        float,
        0.0,
        100.0,
        "§1.125: Seam straightness prior — row-distance-from-midline energy penalty",
    ),
    "ASP_FG_MAJORITY_FLOOR": (
        float,
        0.0,
        10.0,
        "§1.126: Cost floor applied to >80%-fg columns when zone is >60% fg",
    ),
    "ASP_ZONE_HUE_EQ": (
        float,
        0.0,
        1.0,
        "§1.127: Enable per-zone HSV hue equalization (0=off, 1=on)",
    ),
    "ASP_BLOCKS_GAIN_COMP": (
        float,
        0.0,
        1.0,
        "§4.1: Enable spatial 32×32 blocks BGR gain compensation (0=off, 1=on)",
    ),
    "ASP_BLOCKS_LUM_COMP": (
        float,
        0.0,
        1.0,
        "§4.4: Enable spatial 32×32 blocks LAB L-channel gain compensation (0=off, 1=on)",
    ),
    "ASP_WAVE_CORRECT": (
        str,
        None,
        None,
        "§4.3: Post-BA wave correction axis — '' (off), 'vertical', or 'horizontal'",
    ),
    "ASP_GATE_SEAM_VIS": (
        float,
        0.0,
        90.0,
        "§4.8: SeamVisGate ratio limit — ASP seam_visibility must not exceed ratio×SCANS; ≥90=disabled (default 3.0)",
    ),
    "ASP_GATE_SEAM_VIS_FLOOR": (
        float,
        0.0,
        200.0,
        "§4.8: SeamVisGate absolute floor (seam_vis units); gate only fires when ASP seam_vis exceeds this value (default 20.0)",
    ),
    "ASP_SEAM_SMOOTH_PX": (
        int,
        0,
        32,
        "§4.9: Post-composite seam band smoothing half-width (px); narrow vertical Gaussian blur at each seam row; default 4 (S166); 0=disabled",
    ),
    "ASP_SEAM_LUM_STEP": (
        int,
        0,
        80,
        "§5.1: Post-composite seam luminance step correction half-band (px); linear ramp in ±band_px window bridges inter-strip lum gap; 0=disabled (default); suggest 20",
    ),
    "ASP_GATE_CGU": (
        float,
        0.0,
        90.0,
        "§5.3: CGUGate ratio limit — ASP canvas_gain_uniformity must not exceed ratio×SCANS CGU; ≥90=disabled (default 2.0)",
    ),
    "ASP_GATE_CGU_FLOOR": (
        float,
        0.0,
        1.0,
        "§5.3: CGUGate absolute floor (CGU units); gate only fires when ASP CGU exceeds this value (default 0.15)",
    ),
    "ASP_GATE_SEAM_COH": (
        float,
        0.0,
        90.0,
        "§5.2: SCGate ratio limit — ASP seam_coherence must not exceed ratio×SCANS; ≥90=disabled (default 2.5)",
    ),
    "ASP_GATE_SEAM_COH_FLOOR": (
        float,
        0.0,
        200.0,
        "§5.2: SCGate absolute floor (seam_coherence units); gate only fires when ASP seam_coherence exceeds this value (default 15.0)",
    ),
    "ASP_GATE_FFT_BAND": (
        float,
        0.0,
        90.0,
        "§5.13/§5.21: FFTBandGate — bench ratio limit (≥90=disabled, default 3.0); pipeline gate uses 0=disable/1=enable (default 1)",
    ),
    "ASP_GATE_FFT_BAND_FLOOR": (
        float,
        0.0,
        1.0,
        "§5.13/§5.21: FFTBandGate absolute floor (banding score [0,1]); bench gate: ASP score floor (default 0.30); pipeline gate: canvas fft_banding floor (default 0.35)",
    ),
    "ASP_GATE_MONO": (
        float,
        0.0,
        90.0,
        "§5.14: MonotonGate ratio limit — ASP strip_luma_monotonicity must not exceed ratio×SCANS; ≥90=disabled (default 3.0)",
    ),
    "ASP_GATE_MONO_FLOOR": (
        float,
        0.0,
        1.0,
        "§5.14: MonotonGate absolute floor (monotonicity score [0,1]); gate only fires when ASP score exceeds this value (default 0.50)",
    ),
    "ASP_GATE_MONO_PIPE": (
        int,
        0,
        1,
        "§5.22: Enable pipeline strip luma monotonicity gate (0 or 1, default 1)",
    ),
    "ASP_GATE_MONO_PIPE_FLOOR": (
        float,
        0.0,
        1.0,
        "§5.22: Pipeline mono gate floor (reversal fraction, default 0.60)",
    ),
    "ASP_GATE_ENTROPY": (
        float,
        0.0,
        90.0,
        "§5.15: EntropyGate ratio limit — ASP seam_ownership_entropy must not exceed ratio×SCANS; ≥90=disabled (default 2.5)",
    ),
    "ASP_GATE_ENTROPY_FLOOR": (
        float,
        0.0,
        100.0,
        "§5.15: EntropyGate absolute floor (entropy score); gate only fires when ASP entropy exceeds this value (default 3.0)",
    ),
    "ASP_GATE_STRIP_SSIM": (
        float,
        0.0,
        1.0,
        "§5.17: StripSSIMGate ratio limit — ASP strip_self_ssim must not be below ratio×SCANS; 0=disabled (default 0.5)",
    ),
    "ASP_GATE_STRIP_SSIM_FLOOR": (
        float,
        0.0,
        1.0,
        "§5.17: StripSSIMGate absolute floor (strip_self_ssim [0,1]); gate fires when ASP ssim < min(floor, ratio×sim) (default 0.60)",
    ),
    "ASP_GATE_CHROMA_COH": (
        float,
        0.0,
        90.0,
        "§5.18: ChromaSeamGate ratio limit — ASP chroma_seam_coherence must not exceed ratio×SCANS; ≥90=disabled (default 2.5)",
    ),
    "ASP_GATE_CHROMA_COH_FLOOR": (
        float,
        0.0,
        200.0,
        "§5.18: ChromaSeamGate absolute floor (coherence score); gate only fires when ASP chroma_seam_coherence exceeds this value (default 12.0)",
    ),
    "ASP_GATE_SEAM_VIS": (int, 0, 1, "§5.23: Enable pipeline seam visibility gate (0 or 1, default 1)"),
    "ASP_GATE_SEAM_VIS_FLOOR": (float, 0.0, 255.0, "§5.23: Pipeline seam visibility gate floor (luma units, default 30.0)"),
    "ASP_GATE_CHROMA_PIPE": (
        int,
        0,
        1,
        "§5.24: Enable pipeline chroma seam coherence gate (0 or 1, default 1)",
    ),
    "ASP_GATE_CHROMA_PIPE_FLOOR": (
        float,
        0.0,
        255.0,
        "§5.24: Pipeline chroma coh gate floor (luma units per channel, default 20.0)",
    ),
    "ASP_GATE_STRIP_SSIM": (int, 0, 1, "§5.25: Enable pipeline strip self-SSIM gate (0 or 1, default 1)"),
    "ASP_GATE_STRIP_SSIM_FLOOR": (float, 0.0, 1.0, "§5.25: Strip self-SSIM gate floor (default 0.85)"),
    "ASP_GATE_SEAM_BAND_NCC": (
        int,
        0,
        1,
        "§5.31: Enable pipeline seam band NCC gate (0 or 1, default 1)",
    ),
    "ASP_GATE_SEAM_BAND_NCC_FLOOR": (
        float,
        -1.0,
        1.0,
        "§5.31: Seam band NCC gate floor (default 0.30)",
    ),
    "ASP_GATE_GHOSTING_SIQE": (int, 0, 1, "§5.29: Enable pipeline ghosting SIQE gate (0 or 1, default 1)"),
    "ASP_GATE_GHOSTING_SIQE_FLOOR": (float, 0.0, 100.0, "§5.29: Ghosting SIQE gate floor (default 30.0)"),
    "ASP_GATE_GHOST_SIQE_RATIO": (float, 0.0, None, "§5.30: Bench ghosting SIQE comparative ratio limit (default 2.0)"),
    "ASP_GATE_SEAM_GRAD_RATIO": (int, 0, 1, "§5.33: Enable pipeline seam gradient ratio gate (0 or 1, default 1)"),
    "ASP_GATE_SEAM_GRAD_RATIO_FLOOR": (float, 0.0, 20.0, "§5.33: Seam gradient ratio gate floor (default 3.0; higher=more permissive)"),
    "ASP_GATE_CANVAS_ASPECT": (int, 0, 1, "§5.34: Enable pipeline canvas aspect-ratio gate (0 or 1, default 1)"),
    "ASP_GATE_CANVAS_ASPECT_FLOOR": (float, 0.0, 10.0, "§5.34: Minimum H/W ratio for canvas aspect gate (default 1.2)"),
    "ASP_GATE_SEAM_NCC_FLOOR": (float, -1.0, 1.0, "§5.35: Bench seam band NCC absolute floor (default 0.10); gate fires when ASP NCC < floor"),
    "ASP_GATE_SEAM_NCC_RATIO": (float, 0.0, 1.0, "§5.35: Bench seam band NCC ratio limit (default 0.5); gate fires when ASP NCC < ratio × SIM NCC"),
    "ASP_GATE_HIST_INTERSECT": (int, 0, 1, "§5.36: Enable pipeline strip histogram intersection gate (0 or 1, default 1)"),
    "ASP_GATE_HIST_INTERSECT_FLOOR": (float, 0.0, 1.0, "§5.36: Strip histogram intersection gate floor (default 0.35; low intersection = color mismatch)"),
}


def validate_asp_config(
    config: Dict[str, Any],
    *,
    strict: bool = False,
) -> List[str]:
    """§1.8B: Validate a flat ASP config dict against ``_CONFIG_SCHEMA``.

    Args:
        config: Flat mapping of ASP key → value (as returned by `load_asp_config`).
        strict: When True, raises `ConfigError` listing all violations instead of
            returning them. Use in CI/scripting contexts where a misconfigured
            experiment should abort immediately.

    Returns:
        Violation messages as a list of strings. Empty list means the config is valid.

    Note:
        Unknown keys (not in ``_CONFIG_SCHEMA``) emit a `UserWarning` but are not
        counted as violations — forward-compatibility is preserved so that configs
        written for a newer pipeline version still load on an older one. TOML
        integers are accepted where float is expected.

    Example:
        >>> cfg = {"ASP_HOLD_THRESHOLD": 0.03, "ASP_SP_SOFT_PX": 6}
        >>> validate_asp_config(cfg)
        []
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

    Reads ``asp_config.toml`` (or the file at *path*) and merges all sections
    into a flat dict. Each key is written to ``os.environ`` via ``setdefault``
    so that all downstream ``os.environ.get("ASP_*")`` calls pick it up
    automatically. Existing environment variables always take precedence.

    Args:
        path: Path to the TOML file. Defaults to ``asp_config.toml`` in the
            current working directory. Returns an empty dict silently if the
            file does not exist.
        override_env: When True (default), write each loaded key to
            ``os.environ`` via ``setdefault``. Set to False to dry-run the
            load without touching the environment (useful for testing).
        validate: When True, run `validate_asp_config` on the loaded dict
            before writing env vars. Invalid keys emit warnings (or raise if
            *strict* is also True).
        strict: Passed to `validate_asp_config` when *validate* is True.
            Raises `ConfigError` on the first batch of violations.

    Returns:
        Flat mapping of all keys found in the TOML file (sections merged).
        Empty dict if the file is absent or contains no section data.

    Example:
        >>> import os, tempfile, pathlib
        >>> toml = b"[frame_selection]\\nASP_HOLD_THRESHOLD = 0.03\\n"
        >>> with tempfile.NamedTemporaryFile(suffix='.toml', delete=False) as f:
        ...     _ = f.write(toml); name = f.name
        >>> cfg = load_asp_config(name, override_env=False)
        >>> cfg['ASP_HOLD_THRESHOLD']
        0.03
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

    Args:
        key: The ``ASP_*`` environment variable name (e.g. ``"ASP_HOLD_THRESHOLD"``).
        default: String default returned when the key is absent from the environment.
            Callers that need a non-string type should cast the return value::

                threshold = float(get_asp("ASP_HOLD_THRESHOLD", "0.025"))
                enabled   = get_asp("ASP_POISSON_SEAM", "0") != "0"

    Returns:
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
        "ASP_ZONE_PRE_SSIM_THRESH",
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
        "ASP_SEAM_NOISE_GATE",
        "ASP_SEAM_CONTRAST_GATE",
        "ASP_SEAM_ENSEMBLE_VOTES",
        "ASP_BLOCKS_GAIN_COMP",
        "ASP_BLOCKS_LUM_COMP",
        "ASP_GATE_SEAM_VIS",
        "ASP_GATE_SEAM_VIS_FLOOR",
        "ASP_SEAM_SMOOTH_PX",
        "ASP_SEAM_LUM_STEP",
        "ASP_GATE_CGU",
        "ASP_GATE_CGU_FLOOR",
        "ASP_GATE_SEAM_COH",
        "ASP_GATE_SEAM_COH_FLOOR",
        "ASP_GATE_FFT_BAND",
        "ASP_GATE_FFT_BAND_FLOOR",
        "ASP_GATE_MONO",
        "ASP_GATE_MONO_FLOOR",
        "ASP_GATE_MONO_PIPE",
        "ASP_GATE_MONO_PIPE_FLOOR",
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
        "ASP_WAVE_CORRECT",
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
        "ASP_PROPAINTER",
        "ASP_PROPAINTER_DEVICE",
        "ASP_MASKED_MEDIAN",
        "ASP_HORIZONTAL_COMPOSITE",
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

    Args:
        path: Destination TOML file path. Defaults to ``asp_config.toml`` in the
            current working directory. Parent directories are created if needed.
        include_defaults: When True, all schema keys are emitted (with ``"0"`` as
            the fallback default for unset keys). When False (default), only keys
            that are explicitly set in the environment are written.

    Returns:
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
                _type_name = (
                    getattr(_typ, "__name__", str(_typ)) if _typ is not None else "str"
                )
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

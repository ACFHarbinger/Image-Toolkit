"""
Anime Stitching and MFSR Constants.
Centralized from backend/src/animation/*
"""

from pathlib import Path
import numpy as np

# Core stitching constants
LAPLACIAN_BANDS = 5
ECC_MAX_ITER = 80
ECC_EPS = 1e-4
ECC_PYRAMID_LEVELS = 4
MIN_LOFTR_INLIERS = 20
MAX_DX_DRIFT_RATIO = 0.01
MATCH_EDGE_CROP = 0.05
MIN_TEMPLATE_SCORE = 0.85
PC_CONF_THRESHOLD = 0.05
CANVAS_MAX_DIM = 32768
MEDIAN_MIN_SAMPLES = 3
FOREGROUND_DILATION = 16
FOREGROUND_EROSION = 8
SMOOTHSTEP_BLEND_PX = 96

# Luminance weights (BT.601 for BGR)
LUMINANCE_WEIGHTS = np.array([0.114, 0.587, 0.299], dtype=np.float32)

# Compositing
FEATHER_MAX = 300
FEATHER_MIN = 80
SEARCH_RANGE = 250
SEARCH_SLAB = 20
FEATHER_TABLE = [
    (5.0, 300),
    (10.0, 250),
    (20.0, 200),
    (35.0, 150),
    (50.0, 100),
    (float("inf"), 80),  # FEATHER_MIN
]

# Bundle Adjustment
DY_RATIO_THRESH = 2.5
DY_ABS_THRESH = 100.0

# ECC
ECC_MAX_DRIFT = 80.0

# Flow Refinement
FLOW_MAX_DRIFT = 80.0
FLOW_PATCH_SIZE = 512

# Foreground pose registration (Stage 8.5 — flow-guided fg re-posing)
# See reports/ASP_Foreground_Assembly_Research.md §5.
FG_REG_TAPER_PX = 220  # half-width (px) over which the seam warp tapers to zero
FG_REG_MAX_RESIDUAL = (
    90.0  # max per-pixel animation residual (px) to warp; above → no-warp
)
FG_REG_MIN_FG_PIXELS = (
    150  # min foreground pixels in the seam zone to attempt registration
)
FG_REG_FLOW_ENGINE = "dis"  # "dis" (OpenCV DISOpticalFlow, no extra dep) or "searaft"
FG_REG_SMOOTH_SIGMA = 9.0  # Gaussian sigma to smooth the residual flow before warping

# Rendering
RENDERING_FADE_ROWS = 40
LANCZOS_BLEED = 8
MAX_SAFE_GAIN_DEV = 0.15

# MFSR - Particle Swarm Optimization (PSO)
PSO_SWARM_SIZE = 40
PSO_MAX_ITER = 150
PSO_INERTIA = 0.729
PSO_C1 = 1.494
PSO_C2 = 1.494
PSO_VEL_CLAMP = 0.2

# MFSR - Differential Evolution (DE)
DE_POP_SIZE = 30
DE_MAX_GEN = 100
DE_F = 0.8
DE_CR = 0.9

# MFSR - DCT restoration
DCT_BLOCK_SIZE = 8
DCT_ITERATIONS = 20
DCT_QUANT_TABLE_LUMINANCE = [
    16,
    11,
    10,
    16,
    24,
    40,
    51,
    61,
    12,
    12,
    14,
    19,
    26,
    58,
    60,
    55,
    14,
    13,
    16,
    24,
    40,
    57,
    69,
    56,
    14,
    17,
    22,
    29,
    51,
    87,
    80,
    62,
    18,
    22,
    37,
    56,
    68,
    109,
    103,
    77,
    24,
    35,
    55,
    64,
    81,
    104,
    113,
    92,
    49,
    64,
    78,
    87,
    103,
    121,
    120,
    101,
    72,
    92,
    95,
    98,
    112,
    100,
    103,
    99,
]

# MFSR - Deep Reinforcement Learning (DRL)
DRL_STATE_SIZE = 256
DRL_ACTION_DIM = 4
DRL_GAMMA = 0.99
DRL_LR = 1e-4
DRL_MEMORY_SIZE = 10000
DRL_BATCH_SIZE = 64
DRL_AXIS_STEPS = [
    (0, +1.0),
    (0, -1.0),
    (0, +8.0),
    (0, -8.0),
    (1, +1.0),
    (1, -1.0),
    (1, +8.0),
    (1, -8.0),
    (2, +0.01),
    (2, -0.01),
    (2, +0.05),
    (2, -0.05),
    (3, +0.01),
    (3, -0.01),
    (3, +0.05),
    (3, -0.05),
]
NUM_ACTIONS = len(DRL_AXIS_STEPS)

# RLHF
RLHF_FLAW_TYPES = [
    "seam",
    "blur",
    "misalignment",
    "color_mismatch",
    "dark_border",
    "compression",
    "ghosting",
]
RLHF_STORE_PATH = Path.home() / ".config" / "image-toolkit" / "rlhf_feedback.jsonl"
REWARD_MODEL_INPUT_SIZE = 224
REWARD_MODEL_DEFAULT_PATH = (
    Path.home() / ".config" / "image-toolkit" / "stitch_reward_model.pt"
)

# Pipeline
MIN_EXPECTED_STEP = 25
SPATIAL_DEDUP_PX = 25
NEAR_DUP_LUMA_THRESH = 3.0  # §1.2B: pre-stage-5 luma dedup ceiling (luma units, 0–255)
STATIC_EDGE_MIN_DISP_PX = (
    50  # §1.2A: minimum per-axis displacement to keep an edge before BA
)
ADAPTIVE_MIN_DISP_FRAC = (
    0.10  # §1.2C: adaptive threshold = max(floor, frac * expected_step)
)
HIGH_CONF_EDGE_THRESH = (
    0.65  # §2.9C: minimum edge weight to keep on high-confidence re-solve
)
HIGH_HOLD_RESPONSE_THRESH = (
    0.85  # §1.11C: phaseCorrelate response floor for post-hoc hold merge
)
TEMPORAL_VAR_THRESH = (
    1e-3  # §1.2D: mean per-pixel variance [0,1] for static-frame rejection
)
HOLD_DHASH_THRESHOLD = (
    4  # §3.4A: dHash Hamming-distance floor for hold detection (0=disabled)
)
MULTISCALE_GAIN_SIGMA = (
    30.0  # §1.4D: Gaussian sigma (px) for low-freq gain map computation
)
EXPOSURE_OUTLIER_THRESH = (
    60.0  # §1.4F: max allowed bg-lum deviation from median before skip (0=off)
)
SCENE_CHANGE_LUMA_THRESH = (
    60.0  # §1.13: max mean-luma diff between two frames before edge rejection (0=off)
)
SCENE_CHANGE_BGR_THRESH = (
    60.0  # §1.13B: max per-channel mean diff (BGR) before edge rejection (0=off)
)
SCALE_NORM_THRESH = (
    0.05  # §1.3C: min max/min scale ratio deviation before normalisation is applied
)
SEAM_COLOR_GATE_THRESH = 0.55  # §1.14B: min Bhattacharyya colour similarity (0–1) to pass post-composite gate (0=off)
MST_MIN_WEIGHT = (
    0.35  # §1.16: minimum mean MST edge weight before pre-BA SCANS fallback (0=off)
)
ADJ_COVERAGE_MIN = 0.60  # §1.43: minimum fraction of adjacent frame pairs that must have ≥1 edge (0=off)
MAX_ADJACENT_GAP_PX = (
    100.0  # §1.44: max pixel gap between adjacent frames before SCANS fallback (0=off)
)
MAX_CANVAS_WIDTH_RATIO = (
    1.5  # §1.45: max canvas_w / median_frame_w ratio before SCANS fallback (0=off)
)
CONTRAST_THRESH = (
    15.0  # §1.46: pixel std floor (0–255 scale) for low-contrast frame rejection
)
SIGN_INCONSISTENCY_MAX = (
    0.20  # §1.47: max minority-sign fraction of adjacent displacements (0=off)
)
ADJ_DISP_CV_MAX = 0.50  # §1.48: max coefficient of variation of adjacent displacement magnitudes (0=off)
ADJ_MIN_WEIGHT = 0.20  # §1.49: minimum match confidence weight for any adjacent edge before BA (0=off)
BA_RESIDUAL_MAX = (
    200.0  # §1.50: maximum per-edge BA residual (px) before SCANS fallback (0=off)
)
MIN_ADJACENT_OVERLAP_PX = 20.0  # §1.51: minimum canvas-space overlap (px) between consecutive frame pairs (0=off)
BA_WMEAN_RESIDUAL_MAX = 30.0  # §1.52: maximum confidence-weighted mean BA residual (px) before SCANS fallback (0=off)
CANVAS_MAX_MEMORY_MB = 2048.0  # §1.53: max estimated float32 RGB canvas footprint in MB before SCANS fallback (0=off)
RENDER_LUMA_STD_MIN = (
    5.0  # §1.54: minimum luminance std of valid canvas pixels after render (0=off)
)
MAX_AFFINE_ROTATION_DEG = 5.0  # §1.55: max absolute rotation (degrees) in any BA-solved affine before SCANS fallback (0=off)
TRAJ_SMOOTH_SIGMA = 1.5  # §3.16: Gaussian σ (frames) for trajectory smoother (0=off)
TRAJ_SMOOTH_IQR_THRESH = (
    10.0  # §3.16: IQR threshold (px) below which trajectory smoother is skipped
)
GNC_C_PX = 10.0  # §1.17: Geman-McClure c parameter (px); rᵢ ≈ c → 50% weight
GNC_MU_ANNEAL = (
    1.4  # §1.17: GNC μ annealing divisor per outer iteration (Yang et al. 2020)
)
GNC_MAX_OUTER = 8  # §1.17: default max GNC outer continuation iterations
CANVAS_SPAN_MIN_UTIL = 0.3  # §1.17: minimum canvas-span/expected-span ratio before post-BA SCANS fallback (0=off)
ADAPTIVE_SP_THRESH_BASE = 22.0  # §1.18: baseline post_warp_diff threshold for single-pose escalation (lum units)
ADAPTIVE_SP_THRESH_MIN = 12.0  # §1.18: floor threshold applied for wide feathers
ADAPTIVE_SP_THRESH_REF = (
    80  # §1.18: feather reference width (px) at which threshold = base
)
FG_FEATHER_CAP = (
    60  # §1.19: cap feather to this px when seam zone is fg-dominated (0=off)
)
FG_FEATHER_THRESH = 0.60  # §1.19: fg fraction above which feather cap fires
TIGHT_STEP_PX = 30  # §1.20: dominant-axis step below which seam is preemptively single-posed (0=off)
SEAM_LUM_EQ_BAND_PX = 20  # §1.21: post-composite lum equalisation ramp width (rows)
SEAM_LUM_EQ_MIN_STEP = (
    5.0  # §1.21: minimum lum step (lum units) to trigger equalisation
)
SP_SOFT_BASE_PX = 6  # §1.22: baseline single-pose soft-edge half-width (px)
SP_SOFT_MAX_PX = (
    30  # §1.22: maximum single-pose soft-edge half-width after scaling (px)
)
SP_SOFT_REF_PX = (
    80  # §1.22: feather reference width at which base_px is returned unchanged (px)
)
SEAM_HARD_BARRIER_COST = (
    1e6  # §1.23: hard corridor barrier cost for fg-dominated seam columns (0=off)
)
SEAM_STEP_GATE_THRESH = (
    25.0  # §1.24: max allowed luma step at seam boundary before SCANS fallback (0=off)
)
SEAM_SMOOTH_WINDOW = (
    5  # §1.25: median-filter window for seam path jitter removal (0 or 1 = off)
)
SEAM_MARGIN = 3  # §1.26: min rows between seam path and zone top/bottom edge (0 = off)
BG_NORM_MIN_PX = (
    200  # §1.27: minimum background pixels for reliable normalisation gain estimate
)
SEAM_INSTABILITY_THRESH = (
    20.0  # §1.28: max seam path std (rows) before single-pose escalation (0=off)
)
STATIC_INPUT_MAX_MAD = 2.0  # §1.29: MAD ceiling (0–255) for static-input detection gate
ZONE_MIN_HEIGHT = 20  # §1.30: min blend-zone rows before single-pose escalation (0=off)
ZONE_PRE_SSIM_THRESH = (
    0.35  # §1.86: zone-SSIM floor before single-pose escalation (0=off)
)
SEAM_FG_PENETRATION_MAX = (
    0.7  # §1.31: max fraction of seam columns through fg before escalation (0=off)
)

# §1A: Otsu bg-only phase correlation (frame_selection.py)
OTSU_BG_CORR_MIN_BG_FRAC = 0.10  # minimum bg fraction for valid Otsu mask

# §5A/C: Background zero-coverage fill (bg_complete.py)
BG_COMPLETE_MIN_ROWS = 20  # min zero-coverage rows before fill runs

# §3.13: ProPainter Stage 4.7 background completion (pipeline.py / bg_complete.py)
PROPAINTER_DEVICE = (
    "cpu"  # default inference device; override with ASP_PROPAINTER_DEVICE
)

# §2.14: Triangular consistency filter (pipeline.py)
TRI_CONSISTENCY_MAX_RESIDUAL = (
    80.0  # L2 residual (px) above which triangle is inconsistent; 0=off
)
TRI_CONSISTENCY_PENALTY = (
    0.5  # weight multiplier applied to weakest edge in inconsistent triangle
)

# §2.4B: Seam overlay annotation thresholds (compositing.py)
SEAM_OVERLAY_AMBER_THRESH = 10.0  # post_warp_diff below this → green annotation
SEAM_OVERLAY_RED_THRESH = 22.0  # post_warp_diff at or above this → red annotation

# §2.4C: Seam zone crop band (compositing.py _extract_seam_crops)
SEAM_CROP_BAND_PX = 50  # rows above+below each boundary to include in crop thumbnail

# §1.2E: Blur/artifact frame pre-rejection (frame_selection.py _reject_blurry_frames)
BLUR_REJECT_THRESH = 50.0  # Laplacian variance floor (uint8 scale); 0=off

# §1.34: Seam zone texture-energy pre-escalation (compositing.py _seam_zone_texture_energy)
SEAM_LOW_TEXTURE_THRESH = (
    5.0  # Laplacian variance floor (uint8 scale) for flat-color pre-escalation; 0=off
)

# §1.35: Line-art gradient penalty in seam cost map (compositing.py _fg_gradient_cost)
LINE_GRAD_WEIGHT = 1.0  # Additive cost per fg-interior pixel, scaled by normalized Laplacian magnitude; 0=off

# §1.36: LoFTR translation consensus spread filter (matching.py _compute_translation_spread)
MATCH_SPREAD_CEIL = 30.0  # Max allowed MAD of per-match dx/dy displacements (px); 0=off

# §1.37: Background pixel coverage fraction gate (pipeline.py _compute_bg_coverage_fraction)
MIN_BG_FRACTION = (
    0.05  # Minimum mean bg-pixel fraction across frames; below → SCANS fallback (0=off)
)

# §1.38: LoFTR background match ratio gate (matching.py _compute_bg_match_ratio)
LOFTR_BG_RATIO_MIN = 0.15  # Minimum fraction of LoFTR matches that must fall on bg; below → reject LoFTR edge (0=off)

# §1.39: Render canvas coverage fraction gate (pipeline.py _compute_render_coverage)
RENDER_MIN_COVERAGE = 0.30  # Minimum fraction of canvas pixels covered by ≥1 warped frame; below → SCANS fallback (0=off)

# §1.40: Adaptive gain clamp for sequential colour correction (rendering.py _adaptive_render_gain_clamp)
# Formula: clamp_width = 0.26 - 0.12 * (ref_lum / 255) → ±26% at black, ±14% at white
RENDER_GAIN_CLAMP_DARK = 0.26  # clamp_width at ref_lum=0 (pure black)
RENDER_GAIN_CLAMP_BRIGHT = 0.14  # clamp_width at ref_lum=255 (pure white)

# §1.41: Sequential gain chain-drift guard (rendering.py _check_gain_chain_drift)
GAIN_DRIFT_MAX = (
    2.0  # Maximum cumulative gain fold-change before resetting to identity (0=off)
)

# §1.42: Linear interpolation bg fill (bg_complete.py _linear_interp_zero_bg)
# When ASP_INTERP_BG_FILL=1, blends between above/below known pixels instead of hard NN copy

# §1.56: Post-composite chroma seam correction (compositing.py _seam_chroma_equalize)
SEAM_CHROMA_EQ_BAND_PX = (
    20  # row-band width (above/below boundary) used for sampling and correction
)
SEAM_CHROMA_EQ_MIN_SHIFT = 3.0  # min LAB ab-channel shift (units) to trigger correction

# §1.83: Seam band noise-level asymmetry gate (compositing.py _seam_noise_mismatch)
SEAM_NOISE_GATE_THRESH = (
    1.0  # normalised |σ_top−σ_bot| / mean(σ) asymmetry threshold (0=off)
)

# §1.84: Seam band RMS contrast ratio gate (compositing.py _seam_rms_contrast_ratio)
SEAM_CONTRAST_GATE_THRESH = (
    4.0  # max(c_top,c_bot)/min(c_top,c_bot) ratio threshold (0=off)
)

# §1.85: Multi-gate ensemble combiner (compositing.py _check_seam_ensemble_gate)
SEAM_ENSEMBLE_MIN_VOTES = (
    3  # minimum number of gate votes required to trigger fallback (0=off)
)

# §1.87: Masked-Median Background Plate (rendering.py _render_median / bg_complete.py _masked_median_bg)
# When ASP_MASKED_MEDIAN=1, pixels where every frame has foreground are left as zero
# (no ghost-average of different animation poses); pairs with ASP_BG_COMPLETE for hole fill.
MASKED_MEDIAN_MIN_AGREE_FRAC = (
    0.4  # min fraction of frames agreeing on bg value for stability vote
)

# §3.14B: Horizontal-strip compositing (compositing.py _composite_foreground)
# When scroll_axis='horizontal', vertical seam cuts are used instead of SCANS fallback.
HORIZONTAL_FEATHER_PX = (
    120  # default feather band width (px) for horizontal-scroll seams
)

# §3.15B: OBJ-GSP triangular mesh seam barrier (compositing.py)
MESH_BARRIER_MIN_AREA_PX = 100

# §3.10: MLLM semantic quality scoring (mllm_scorer.py)
MLLM_TIMEOUT_SEC = 30
MLLM_MAX_IMAGE_DIM = 1024
MLLM_MODEL = "qwen2-vl:7b"

# §3.1A: AnimeInterp SGM + §3.2A ConvGRU flow engine (animeinterp_flow.py)
ANIMEINTERP_SPATIAL_SIGMA = 50.0
ANIMEINTERP_GRU_ITERS = 4
ANIMEINTERP_TRAPPED_BALL_MIN_R = 2
ANIMEINTERP_TRAPPED_BALL_MAX_R = 8

# §3.12A: Hold-block sub-pixel averaging
HOLD_AVERAGE_ECC_ITERS = 20
HOLD_AVERAGE_ECC_EPS = 1e-3

# §3.9: SI-FID proxy metric
SI_FID_PATCH_SIZE = 128
SI_FID_N_PATCHES = 32

# ToonCrafter
TOONCRAFTER_REPO = "Doubiiu/ToonCrafter"

# §3.16B: HITL preset system
HITL_PRESET_DIR_DEFAULT: str = str(Path.home() / ".image-toolkit" / "hitl_presets")

# §3.5B: CamFlow background-masked phase correlation
CAM_FLOW_MIN_BG_PIXELS: int = 500

# §1.88: Seam band histogram matching
HIST_MATCH_SEAM_BAND_PX: int = 20

# §1.89: Seam processing order
SEAM_ORDER_RESIDUAL: str = "residual"

# §1.90: Post-seam bilateral smoothing
BILATERAL_SEAM_BAND_PX: int = 5
BILATERAL_SEAM_SIGMA_SPACE: float = 3.0
BILATERAL_SEAM_SIGMA_COLOR: float = 20.0

# §3.17: High-frequency column seam cost
HF_SEAM_COST_THRESHOLD: float = 50.0
HF_SEAM_COST_BOOST: float = 0.5

# §1.91: Iterative seam luminance convergence
SEAM_LUM_CONVERGE_TARGET: float = 5.0
SEAM_LUM_CONVERGE_MAX_ITERS: int = 2

# §1.92: Gaussian feather smoothing
SMOOTH_FEATHER_SIGMA: float = 1.0

# §3.18: CQAS ghosting reference (above → score=0)
CQAS_GHOSTING_REF: float = 60.0
# §1.94: Background consistency (per-strip row-mean lum std)
BG_CONSISTENCY_REF: float = 10.0

# §1.95: Fg-zone single-pose threshold scaling
SP_THRESH_FG_FACTOR: float = 0.7
SP_FG_FRAC_THRESH: float = 0.5

# §3.19: Per-zone pre-blend chroma alignment min shift threshold
ZONE_CHROMA_ALIGN_MIN_SHIFT: float = 2.0

# §1.97: Seam zone entropy asymmetry gate
ENTROPY_GAP_THRESH_DEFAULT: float = 1.5

# §1.98: Per-frame gain smoothing
SMOOTH_GAIN_SIGMA: float = 1.0

# §3.20: Extra fg-boundary outer dilation ring
EXTRA_FG_DILATION_DEFAULT: int = 8

# §1.99: Seam endpoint bg-preference
SEAM_PIN_ROWS_DEFAULT: int = 3

# §1.101: Full blend-zone MAD pre-escalation
ZONE_MAD_THRESH_DEFAULT: float = 30.0

# §1.102: Warp residual momentum damping
WARP_MOMENTUM_FACTOR: float = 0.85

# §1.103: Reference-proximity dominant frame selection
SP_REF_PROX_DEFAULT: bool = False

# §1.104: Per-zone luminance normalization
ZONE_LUM_NORM_GAIN_CLAMP: float = 2.0

# §1.105: Fg-overlap blend weight cap
FG_OVERLAP_BLEND_CAP_DEFAULT: float = 0.3

# §1.106: Post-composite seam lum step audit
POST_SEAM_WARN_THRESH: float = 8.0

# §1.107: Adaptive seam band width
ADAPTIVE_SEAM_BAND_MAX: int = 40

# §1.108: Laplacian blend alpha schedule
LAPLACIAN_ALPHA_FINE_WEIGHT: float = 0.3

# §1.109: Seam cost map normalization
COST_MAP_NORM_BARRIER: float = 1e5

# §1.110: Seam cost map Gaussian blur sigma
COST_MAP_BLUR_SIGMA: float = 2.0

# §1.111: Zone background saturation normalization gain clamp
ZONE_SAT_NORM_GAIN_CLAMP: float = 2.0

# §1.112: Seam path vertical drift gate
SEAM_DRIFT_THRESH: float = 15.0

# §3.25: Seam boundary entropy band width
SEAM_BOUNDARY_ENTROPY_BAND_PX: int = 15

# §1.113: Seam cost map column-wise smooth sigma
COST_COL_SMOOTH_SIGMA: float = 1.5

# §1.114: Zone RMS contrast equalization clamp
ZONE_CONTRAST_EQ_CLAMP: float = 2.0

# §1.115: Absolute feather jump cap
FEATHER_JUMP_MAX_DEFAULT: int = 150

# §1.116: Blend zone bg-fraction diagnostic
ZONE_BG_FRAC_DIAG_KEY: str = "zone_bg_fracs"

# §1.117: Fast zone NCC pre-gate thumbnail size
ZONE_FAST_NCC_THUMB_SIZE: int = 32

# §1.118: Post-composite seam sharpness guard
SEAM_SHARP_BAND_PX: int = 5

# §1.119: Seam zone width variance gate
ZONE_WIDTH_CV_MAX_DEFAULT: float = 0.5

# §1.120: Post-composite saturation step audit
SEAM_SAT_WARN_THRESH_DEFAULT: float = 15.0
SEAM_SAT_BAND_PX: int = 5

# §1.121: Zone histogram intersection pre-gate
ZONE_HIST_THRESH_DEFAULT: float = 0.4
ZONE_HIST_BINS: int = 32

# §3.28: Seam boundary gradient direction coherence metric
SEAM_GRAD_COHERENCE_BAND_PX: int = 8

# §1.122: High seam path cost escalation
HIGH_PATH_COST_THRESH_DEFAULT: float = 0.6

# §1.123: Local scatter penalty in seam cost
SCATTER_COST_WEIGHT_DEFAULT: float = 0.3

# §1.124: Adaptive single-pose soft-edge width from seam residual
ADAPTIVE_SP_SOFT_MIN: int = 3
ADAPTIVE_SP_SOFT_MAX: int = 10

# §3.29: Blend zone coverage fraction metric
ZONE_COVERAGE_N_STRIPS: int = 8

# §1.125: Seam transition straightness penalty default
SEAM_TRANSITION_PEN_DEFAULT: float = 0.0

# §1.126: Fg-majority column floor in seam cost map
FG_MAJORITY_FLOOR_DEFAULT: float = 0.0

# §1.127: Minimum hue difference (degrees) for zone hue equalization to fire
ZONE_HUE_EQ_MIN_DIFF_DEG: float = 5.0

# §4.1 / §4.4: Block size (pixels) for spatial gain compensation
BLOCKS_GAIN_COMP_BLOCK_SIZE: int = 32

# §4.3: Minimum tx/ty range (pixels) required before wave correction fires
WAVE_CORRECT_MIN_TX_RANGE: float = 5.0

# §4.7: dy_cv pre-detection gate — SCANS fallback when step-size CV exceeds threshold.
# dy_cv is the coefficient of variation of adjacent vertical frame steps.
# 97-test benchmark shows dy_cv ≥ 1.5 → catastrophic ASP failure (AlSSIM −22 to −37%,
# seam_vis 60–120 vs SCANS 2–3) while SCANS trivially handles these sequences.
# 0.0 = disabled.
DY_CV_MAX: float = 1.5
DY_CV_ADAPTIVE_FLOOR: float = 0.8  # §5.8: minimum adaptive dy_cv ceiling for large-N sequences

# §4.9/§5.11 — Seam band smoothing half-width (px).  After Stage 11 compositing, a narrow
# Gaussian blur (±SEAM_SMOOTH_PX rows) is applied at each inter-frame seam row.
# 0 = disabled.  Default: 4 px (safe; below double-image ghost threshold).
SEAM_SMOOTH_PX: int = 4
# §5.11: adaptive seam-smooth enabled by default when SEAM_SMOOTH_PX > 0
SEAM_SMOOTH_ADAPTIVE: bool = True
# §5.1: Post-composite seam luminance step correction half-band (px); 0=disabled
SEAM_LUM_STEP_PX: int = 0
# §5.9: auto-enable seam lum-step when CGU exceeds this threshold; 1.0=disabled
CGU_AUTO_LUM_STEP: float = 0.08
# §5.16: per-seam adaptive lum-step correction width; True=adapt per seam
SEAM_LUM_STEP_ADAPTIVE: bool = True
# §5.19: pipeline seam coherence gate floor
SC_GATE_FLOOR: float = 25.0
# §5.21: pipeline FFT banding gate floor (energy fraction [0,1])
FFT_BAND_GATE_FLOOR: float = 0.35

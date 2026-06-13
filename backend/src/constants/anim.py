"""
Anime Stitching and MFSR Constants.
Centralized from backend/src/anim/*
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
SEAM_FG_PENETRATION_MAX = (
    0.7  # §1.31: max fraction of seam columns through fg before escalation (0=off)
)

# §1A: Otsu bg-only phase correlation (frame_selection.py)
OTSU_BG_CORR_MIN_BG_FRAC = 0.10  # minimum bg fraction for valid Otsu mask

# §5A/C: Background zero-coverage fill (bg_complete.py)
BG_COMPLETE_MIN_ROWS = 20  # min zero-coverage rows before fill runs

# ToonCrafter
TOONCRAFTER_REPO = "Doubiiu/ToonCrafter"

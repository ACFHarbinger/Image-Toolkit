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
FG_REG_TAPER_PX = 220        # half-width (px) over which the seam warp tapers to zero
FG_REG_MAX_RESIDUAL = 90.0   # max per-pixel animation residual (px) to warp; above → no-warp
FG_REG_MIN_FG_PIXELS = 150   # min foreground pixels in the seam zone to attempt registration
FG_REG_FLOW_ENGINE = "dis"   # "dis" (OpenCV DISOpticalFlow, no extra dep) or "searaft"
FG_REG_SMOOTH_SIGMA = 9.0    # Gaussian sigma to smooth the residual flow before warping

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
STATIC_EDGE_MIN_DISP_PX = 50  # §1.2A: minimum per-axis displacement to keep an edge before BA
ADAPTIVE_MIN_DISP_FRAC = 0.10  # §1.2C: adaptive threshold = max(floor, frac * expected_step)
HIGH_CONF_EDGE_THRESH = 0.65  # §2.9C: minimum edge weight to keep on high-confidence re-solve
HIGH_HOLD_RESPONSE_THRESH = 0.85  # §1.11C: phaseCorrelate response floor for post-hoc hold merge
TEMPORAL_VAR_THRESH = 1e-3  # §1.2D: mean per-pixel variance [0,1] for static-frame rejection
HOLD_DHASH_THRESHOLD = 4  # §3.4A: dHash Hamming-distance floor for hold detection (0=disabled)
MULTISCALE_GAIN_SIGMA = 30.0  # §1.4D: Gaussian sigma (px) for low-freq gain map computation

# ToonCrafter
TOONCRAFTER_REPO = "Doubiiu/ToonCrafter"

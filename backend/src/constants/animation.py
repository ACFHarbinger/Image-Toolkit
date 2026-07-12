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
MAX_DX_DRIFT_RATIO = 0.01
MATCH_EDGE_CROP = 0.05
MIN_TEMPLATE_SCORE = 0.85
PC_CONF_THRESHOLD = 0.05
CANVAS_MAX_DIM = 32768
MEDIAN_MIN_SAMPLES = 3
FOREGROUND_DILATION = 16
FOREGROUND_EROSION = 8

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
# See research/ASP_Foreground_Assembly_Research.md §5.
FG_REG_TAPER_PX = 220  # half-width (px) over which the seam warp tapers to zero
FG_REG_MAX_RESIDUAL = (
    90.0  # max per-pixel animation residual (px) to warp; above → no-warp
)
FG_REG_MIN_FG_PIXELS = (
    150  # min foreground pixels in the seam zone to attempt registration
)
FG_REG_SMOOTH_SIGMA = 9.0  # Gaussian sigma to smooth the residual flow before warping

# Rendering
RENDERING_FADE_ROWS = 40
LANCZOS_BLEED = 8
MAX_SAFE_GAIN_DEV = 0.15
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
GNC_C_PX = 10.0  # §1.17: Geman-McClure c parameter (px); rᵢ ≈ c → 50% weight
GNC_MU_ANNEAL = (
    1.4  # §1.17: GNC μ annealing divisor per outer iteration (Yang et al. 2020)
)

# §2.4B: Seam overlay annotation thresholds (compositing.py)
SEAM_OVERLAY_AMBER_THRESH = 10.0  # post_warp_diff below this → green annotation
SEAM_OVERLAY_RED_THRESH = 22.0  # post_warp_diff at or above this → red annotation

# §2.4C: Seam zone crop band (compositing.py _extract_seam_crops)
SEAM_CROP_BAND_PX = 50  # rows above+below each boundary to include in crop thumbnail

# §4.9/§5.11 — Seam band smoothing half-width (px).  After Stage 11 compositing, a narrow
# Gaussian blur (±SEAM_SMOOTH_PX rows) is applied at each inter-frame seam row.
# 0 = disabled.  Default: 4 px (safe; below double-image ghost threshold).
SEAM_SMOOTH_PX: int = 4

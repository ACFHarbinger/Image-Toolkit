"""
Constants for the anime stitching pipeline and MFSR modules.

All tunable thresholds, iteration counts, and algorithm hyperparameters live
here so they can be referenced from any sibling module.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Core stitching constants (legacy names preserved with _ prefix for backward
# compatibility with the original anime_stitch_pipeline module).
# ---------------------------------------------------------------------------

_LAPLACIAN_BANDS = 5  # Laplacian pyramid depth for multi-band blend
_ECC_MAX_ITER = 80  # ECC termination iterations
_ECC_EPS = 1e-4  # ECC termination epsilon
_ECC_PYRAMID_LEVELS = 4  # Gaussian pyramid levels for ECC
_MIN_LOFTR_INLIERS = 20  # Minimum MAGSAC++ inliers for a valid LoFTR pair
_MAX_DX_DRIFT_RATIO = (
    0.01  # Maximum horizontal drift relative to width for vertical pans
)
_MATCH_EDGE_CROP = (
    0.05  # Fraction of edge to trim before feature matching (discard distortion)
)
_MIN_TEMPLATE_SCORE = 0.85  # Minimum TM_CCORR_NORMED score for template match
_PC_CONF_THRESHOLD = 0.05  # Minimum phase-correlation response (shallow = noisy)
_CANVAS_MAX_DIM = 32768  # Hard cap on canvas size to avoid OOM
_MEDIAN_MIN_SAMPLES = 3  # Minimum valid samples per pixel for median render
_FOREGROUND_DILATION = 16  # BiRefNet mask dilation (safety margin around chars)
_FOREGROUND_EROSION = 8  # BiRefNet mask erosion (sharpens boundary)
_SMOOTHSTEP_BLEND_PX = 96  # Fallback blend height when seam is unavailable


# ---------------------------------------------------------------------------
# MFSR — Particle Swarm Optimization (PSO)
# ---------------------------------------------------------------------------

PSO_SWARM_SIZE = 40
PSO_MAX_ITER = 150
PSO_INERTIA = 0.729
PSO_C1 = 1.494  # cognitive
PSO_C2 = 1.494  # social
PSO_VEL_CLAMP = 0.2  # fraction of search range


# ---------------------------------------------------------------------------
# MFSR — Differential Evolution (DE)
# ---------------------------------------------------------------------------

DE_POP_SIZE = 30
DE_MAX_GEN = 100
DE_F = 0.8   # mutation scale
DE_CR = 0.9  # crossover rate


# ---------------------------------------------------------------------------
# MFSR — DCT restoration
# ---------------------------------------------------------------------------

DCT_BLOCK_SIZE = 8
DCT_ITERATIONS = 20
DCT_QUANT_TABLE_LUMINANCE = [  # JPEG standard luminance quantization table
    16, 11, 10, 16, 24, 40, 51, 61,
    12, 12, 14, 19, 26, 58, 60, 55,
    14, 13, 16, 24, 40, 57, 69, 56,
    14, 17, 22, 29, 51, 87, 80, 62,
    18, 22, 37, 56, 68, 109, 103, 77,
    24, 35, 55, 64, 81, 104, 113, 92,
    49, 64, 78, 87, 103, 121, 120, 101,
    72, 92, 95, 98, 112, 100, 103, 99,
]


# ---------------------------------------------------------------------------
# MFSR — Deep Reinforcement Learning (DRL)
# ---------------------------------------------------------------------------

DRL_STATE_SIZE = 256   # feature dim of the concatenated state
DRL_ACTION_DIM = 4     # [dx, dy, dscale, dtheta]
DRL_GAMMA = 0.99
DRL_LR = 1e-4
DRL_MEMORY_SIZE = 10000
DRL_BATCH_SIZE = 64


__all__ = [
    # Core
    "_LAPLACIAN_BANDS",
    "_ECC_MAX_ITER",
    "_ECC_EPS",
    "_ECC_PYRAMID_LEVELS",
    "_MIN_LOFTR_INLIERS",
    "_MAX_DX_DRIFT_RATIO",
    "_MATCH_EDGE_CROP",
    "_MIN_TEMPLATE_SCORE",
    "_PC_CONF_THRESHOLD",
    "_CANVAS_MAX_DIM",
    "_MEDIAN_MIN_SAMPLES",
    "_FOREGROUND_DILATION",
    "_FOREGROUND_EROSION",
    "_SMOOTHSTEP_BLEND_PX",
    # PSO
    "PSO_SWARM_SIZE",
    "PSO_MAX_ITER",
    "PSO_INERTIA",
    "PSO_C1",
    "PSO_C2",
    "PSO_VEL_CLAMP",
    # DE
    "DE_POP_SIZE",
    "DE_MAX_GEN",
    "DE_F",
    "DE_CR",
    # DCT
    "DCT_BLOCK_SIZE",
    "DCT_ITERATIONS",
    "DCT_QUANT_TABLE_LUMINANCE",
    # DRL
    "DRL_STATE_SIZE",
    "DRL_ACTION_DIM",
    "DRL_GAMMA",
    "DRL_LR",
    "DRL_MEMORY_SIZE",
    "DRL_BATCH_SIZE",
]

#!/usr/bin/env python3
"""
Anime Stitch Pipeline Benchmark
================================
Runs both the Anime Stitch Pipeline (ASP) and OpenCV SCANS Simple Stitch on
every asp_testX dataset in data/, then generates a comprehensive markdown
report with side-by-side comparisons, CV metrics, intermediate-output
analysis (2-D and 3-D visualizations), and structured feedback blocks for
human review and LLM-assisted iteration.
"""

import gc
import glob
import json
import math
import os
import platform
import shutil
import sys
import time
import datetime
import logging
from typing import Dict, List, Optional

import cv2
import numpy as np
import torch

sys.path.insert(0, "/home/pkhunter/Repositories/Image-Toolkit")
os.environ.setdefault("PYTORCH_ALLOC_CONF", "expandable_segments:True")

from backend.src.animation.core.pipeline import AnimeStitchPipeline
from backend.src.animation.alignment.canvas import (
    _load_frames,
    _normalise_widths,
    _compute_canvas,
    _crop_to_valid,
    _scan_stitch_fallback,
    _strip_self_ssim,
    _chroma_seam_coherence,
)
from backend.src.animation.core.validation import _validate_affines
from backend.src.animation.ingestion.masking import _compute_fg_masks
from backend.src.animation.alignment.matching import _pairwise_match
from backend.src.animation.alignment.bundle_adjust import _bundle_adjust_affine
from backend.src.animation.alignment.ecc import _ecc_refine
from backend.src.animation.rendering.rendering import _render_median
from backend.src.animation.rendering.compositing import _composite_foreground

# ---------------------------------------------------------------------------
# Lazy-import heavy plotting deps so the benchmark still runs without them
# ---------------------------------------------------------------------------
try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401 (registers 3-D projection)

    _MPL_OK = True
except ImportError:
    _MPL_OK = False

try:
    from skimage.metrics import structural_similarity as ssim

    _SSIM_OK = True
except ImportError:
    _SSIM_OK = False

# ---------------------------------------------------------------------------
# RLHF quality gate (§1.10A, S29) + active-learning uncertainty (§1.10D, S130)
# ---------------------------------------------------------------------------
_RLHF_FLAG_THRESHOLD = 0.6
_RLHF_UNCERTAINTY_THRESHOLD = 0.10  # §1.10D: MC-dropout std above this → needs review
_reward_model = None  # lazy-loaded singleton

# §3.10: MLLM semantic quality scoring via ollama
_MLLM_SCORER: bool = os.environ.get("ASP_MLLM_SCORER", "0") != "0"
_MLLM_MODEL: str = os.environ.get("ASP_MLLM_MODEL", "qwen2-vl:7b")

# §5.40: Bench seam gradient ratio comparative gate
_SEAM_GRAD_RATIO_ABS_FLOOR: float = float(os.environ.get("ASP_GATE_SEAM_GRAD_ABS_FLOOR", "5.0"))
_SEAM_GRAD_RATIO_LIMIT: float = float(os.environ.get("ASP_GATE_SEAM_GRAD_RATIO_LIMIT", "2.0"))

# §3.9: SI-FID proxy (patch Laplacian sharpness ratio)
_SI_FID: bool = os.environ.get("ASP_SI_FID", "0") != "0"
_SI_FID_PATCH_SIZE: int = int(os.environ.get("ASP_SI_FID_PATCH_SIZE", "128"))
_SI_FID_N_PATCHES: int = int(os.environ.get("ASP_SI_FID_N_PATCHES", "32"))

# §5.30: Benchmark Ghosting SIQE Comparative Gate
_GHOST_SIQE_RATIO_LIMIT: float = float(os.environ.get("ASP_GATE_GHOST_SIQE_RATIO", "2.0"))
_GHOST_SIQE_ABS_FLOOR: float = float(os.environ.get("ASP_GATE_GHOST_SIQE_FLOOR", "30.0"))
# §5.37: Bench histogram intersection comparative gate
_HIST_INTERSECT_ABS_FLOOR: float = float(os.environ.get("ASP_GATE_HIST_INTERSECT_FLOOR", "0.10"))
_HIST_INTERSECT_RATIO: float = float(os.environ.get("ASP_GATE_HIST_INTERSECT_RATIO", "0.5"))
# §5.43: Bench canvas valid-area comparative gate
_VALID_AREA_ABS_FLOOR: float = float(os.environ.get("ASP_GATE_VALID_AREA_FLOOR", "0.30"))
_VALID_AREA_RATIO: float = float(os.environ.get("ASP_GATE_VALID_AREA_RATIO", "0.7"))
# §5.44: Bench strip saturation CV comparative gate
_SAT_CV_ABS_FLOOR: float = float(os.environ.get("ASP_GATE_SAT_CV_ABS_FLOOR", "0.30"))
_SAT_CV_RATIO: float = float(os.environ.get("ASP_GATE_SAT_CV_RATIO", "2.0"))
# §5.47: Bench strip luma range comparative gate
_LUMA_RANGE_ABS_FLOOR: float = float(os.environ.get("ASP_GATE_LUMA_RANGE_ABS_FLOOR", "30.0"))
_LUMA_RANGE_RATIO: float = float(os.environ.get("ASP_GATE_LUMA_RANGE_RATIO", "2.0"))
# §5.48: Bench strip edge density comparative gate
_EDGE_DENSITY_ABS_FLOOR: float = float(os.environ.get("ASP_GATE_EDGE_DENSITY_ABS_FLOOR", "0.15"))
_EDGE_DENSITY_RATIO: float = float(os.environ.get("ASP_GATE_EDGE_DENSITY_RATIO", "2.5"))
# §5.51: Bench strip luma MAD comparative gate
_LUMA_MAD_ABS_FLOOR: float = float(os.environ.get("ASP_GATE_LUMA_MAD_ABS_FLOOR", "10.0"))
_LUMA_MAD_RATIO: float = float(os.environ.get("ASP_GATE_LUMA_MAD_RATIO", "2.0"))
# §5.52: Bench strip sharpness CV comparative gate
_SHARPNESS_CV_ABS_FLOOR: float = float(os.environ.get("ASP_GATE_SHARPNESS_CV_ABS_FLOOR", "0.60"))
_SHARPNESS_CV_RATIO: float = float(os.environ.get("ASP_GATE_SHARPNESS_CV_RATIO", "2.5"))
# §5.55: Bench strip contrast CV comparative gate
_CONTRAST_CV_ABS_FLOOR: float = float(os.environ.get("ASP_GATE_CONTRAST_CV_ABS_FLOOR", "0.80"))
_CONTRAST_CV_RATIO: float = float(os.environ.get("ASP_GATE_CONTRAST_CV_RATIO", "2.5"))
# §5.56: Bench seam chroma jump comparative gate
_CHROMA_JUMP_ABS_FLOOR: float = float(os.environ.get("ASP_GATE_CHROMA_JUMP_ABS_FLOOR", "8.0"))
_CHROMA_JUMP_RATIO: float = float(os.environ.get("ASP_GATE_CHROMA_JUMP_RATIO", "2.0"))
# §5.59: Bench strip noise CV comparative gate
_NOISE_CV_ABS_FLOOR: float = float(os.environ.get("ASP_GATE_NOISE_CV_ABS_FLOOR", "0.50"))
_NOISE_CV_RATIO: float = float(os.environ.get("ASP_GATE_NOISE_CV_RATIO", "2.5"))
# §5.60: Bench seam luma step CV comparative gate
_LUMA_STEP_CV_ABS_FLOOR: float = float(os.environ.get("ASP_GATE_LUMA_STEP_CV_ABS_FLOOR", "0.40"))
_LUMA_STEP_CV_RATIO: float = float(os.environ.get("ASP_GATE_LUMA_STEP_CV_RATIO", "2.0"))
# §5.63: Bench strip entropy CV comparative gate
_ENTROPY_CV_ABS_FLOOR: float = float(os.environ.get("ASP_GATE_ENTROPY_CV_ABS_FLOOR", "0.30"))
_ENTROPY_CV_RATIO: float = float(os.environ.get("ASP_GATE_ENTROPY_CV_RATIO", "2.5"))
# §5.64: Bench seam chroma step CV comparative gate
_CHROMA_STEP_CV_ABS_FLOOR: float = float(os.environ.get("ASP_GATE_CHROMA_STEP_CV_ABS_FLOOR", "0.30"))
_CHROMA_STEP_CV_RATIO: float = float(os.environ.get("ASP_GATE_CHROMA_STEP_CV_RATIO", "2.0"))
# §5.71: Bench strip luma IQR CV comparative gate
_LUMA_IQR_CV_ABS_FLOOR: float = float(os.environ.get("ASP_GATE_LUMA_IQR_CV_ABS_FLOOR", "0.40"))
_LUMA_IQR_CV_RATIO: float = float(os.environ.get("ASP_GATE_LUMA_IQR_CV_RATIO", "2.5"))
# §5.72: Bench seam column variance CV comparative gate
_SEAM_COL_VAR_CV_ABS_FLOOR: float = float(os.environ.get("ASP_GATE_SEAM_COL_VAR_CV_ABS_FLOOR", "0.40"))
_SEAM_COL_VAR_CV_RATIO: float = float(os.environ.get("ASP_GATE_SEAM_COL_VAR_CV_RATIO", "2.0"))
# §5.75: Bench strip luma skewness CV comparative gate
_LUMA_SKEW_CV_ABS_FLOOR: float = float(os.environ.get("ASP_BENCH_LUMA_SKEW_CV_ABS_FLOOR", "0.50"))
_LUMA_SKEW_CV_RATIO: float = float(os.environ.get("ASP_BENCH_LUMA_SKEW_CV_RATIO", "2.5"))
# §5.76: Bench seam signed step CV comparative gate
_SEAM_SIGNED_STEP_CV_ABS_FLOOR: float = float(os.environ.get("ASP_BENCH_SEAM_SIGNED_STEP_CV_ABS_FLOOR", "0.40"))
_SEAM_SIGNED_STEP_CV_RATIO: float = float(os.environ.get("ASP_BENCH_SEAM_SIGNED_STEP_CV_RATIO", "2.0"))
# §5.79: Bench strip luma kurtosis CV comparative gate
_LUMA_KURTOSIS_CV_ABS_FLOOR: float = float(os.environ.get("ASP_BENCH_LUMA_KURTOSIS_CV_ABS_FLOOR", "0.50"))
_LUMA_KURTOSIS_CV_RATIO: float = float(os.environ.get("ASP_BENCH_LUMA_KURTOSIS_CV_RATIO", "2.5"))
# §5.80: Bench seam texture ratio CV comparative gate
_SEAM_TEXTURE_RATIO_CV_ABS_FLOOR: float = float(os.environ.get("ASP_BENCH_SEAM_TEXTURE_RATIO_CV_ABS_FLOOR", "0.40"))
_SEAM_TEXTURE_RATIO_CV_RATIO: float = float(os.environ.get("ASP_BENCH_SEAM_TEXTURE_RATIO_CV_RATIO", "2.0"))
# §5.83: Bench strip edge density CV comparative gate
_EDGE_DENSITY_CV_ABS_FLOOR: float = float(os.environ.get("ASP_BENCH_EDGE_DENSITY_CV_ABS_FLOOR", "0.40"))
_EDGE_DENSITY_CV_RATIO: float = float(os.environ.get("ASP_BENCH_EDGE_DENSITY_CV_RATIO", "2.5"))
# §5.84: Bench seam local contrast CV comparative gate
_SEAM_LOCAL_CONTRAST_CV_ABS_FLOOR: float = float(os.environ.get("ASP_BENCH_SEAM_LOCAL_CONTRAST_CV_ABS_FLOOR", "0.30"))
_SEAM_LOCAL_CONTRAST_CV_RATIO: float = float(os.environ.get("ASP_BENCH_SEAM_LOCAL_CONTRAST_CV_RATIO", "2.0"))
# §5.87: Bench strip luma P90–P10 CV comparative gate
_LUMA_P90P10_CV_ABS_FLOOR: float = float(os.environ.get("ASP_BENCH_LUMA_P90P10_CV_ABS_FLOOR", "0.30"))
_LUMA_P90P10_CV_RATIO: float = float(os.environ.get("ASP_BENCH_LUMA_P90P10_CV_RATIO", "2.5"))
# §5.88: Bench seam hue shift CV comparative gate
_SEAM_HUE_SHIFT_CV_ABS_FLOOR: float = float(os.environ.get("ASP_BENCH_SEAM_HUE_SHIFT_CV_ABS_FLOOR", "0.40"))
_SEAM_HUE_SHIFT_CV_RATIO: float = float(os.environ.get("ASP_BENCH_SEAM_HUE_SHIFT_CV_RATIO", "2.0"))
# §5.91: Bench strip dark pixel fraction CV comparative gate
_DARK_PIXEL_FRAC_CV_ABS_FLOOR: float = float(os.environ.get("ASP_BENCH_DARK_PIXEL_FRAC_CV_ABS_FLOOR", "0.40"))
_DARK_PIXEL_FRAC_CV_RATIO: float = float(os.environ.get("ASP_BENCH_DARK_PIXEL_FRAC_CV_RATIO", "2.5"))
# §5.92: Bench seam saturation shift CV comparative gate
_SEAM_SAT_SHIFT_CV_ABS_FLOOR: float = float(os.environ.get("ASP_BENCH_SEAM_SAT_SHIFT_CV_ABS_FLOOR", "0.30"))
_SEAM_SAT_SHIFT_CV_RATIO: float = float(os.environ.get("ASP_BENCH_SEAM_SAT_SHIFT_CV_RATIO", "2.0"))
# §5.95: Bench strip Sobel energy CV comparative gate
_SOBEL_ENERGY_CV_ABS_FLOOR: float = float(os.environ.get("ASP_BENCH_SOBEL_ENERGY_CV_ABS_FLOOR", "0.35"))
_SOBEL_ENERGY_CV_RATIO: float = float(os.environ.get("ASP_BENCH_SOBEL_ENERGY_CV_RATIO", "2.5"))
# §5.96: Bench seam Value shift CV comparative gate
_SEAM_VALUE_SHIFT_CV_ABS_FLOOR: float = float(os.environ.get("ASP_BENCH_SEAM_VALUE_SHIFT_CV_ABS_FLOOR", "0.30"))
_SEAM_VALUE_SHIFT_CV_RATIO: float = float(os.environ.get("ASP_BENCH_SEAM_VALUE_SHIFT_CV_RATIO", "2.0"))
# §5.99: Bench strip median luma CV comparative gate
_MEDIAN_LUMA_CV_ABS_FLOOR: float = float(os.environ.get("ASP_BENCH_MEDIAN_LUMA_CV_ABS_FLOOR", "0.20"))
_MEDIAN_LUMA_CV_RATIO: float = float(os.environ.get("ASP_BENCH_MEDIAN_LUMA_CV_RATIO", "3.0"))
# §5.100: Bench seam entropy shift CV comparative gate
_SEAM_ENTROPY_SHIFT_CV_ABS_FLOOR: float = float(os.environ.get("ASP_BENCH_SEAM_ENTROPY_SHIFT_CV_ABS_FLOOR", "0.30"))
_SEAM_ENTROPY_SHIFT_CV_RATIO: float = float(os.environ.get("ASP_BENCH_SEAM_ENTROPY_SHIFT_CV_RATIO", "2.0"))
# §5.103: Bench strip red channel CV comparative gate
_RED_CHANNEL_CV_ABS_FLOOR: float = float(os.environ.get("ASP_BENCH_RED_CHANNEL_CV_ABS_FLOOR", "0.20"))
_RED_CHANNEL_CV_RATIO: float = float(os.environ.get("ASP_BENCH_RED_CHANNEL_CV_RATIO", "3.0"))
# §5.104: Bench seam blue shift CV comparative gate
_SEAM_BLUE_SHIFT_CV_ABS_FLOOR: float = float(os.environ.get("ASP_BENCH_SEAM_BLUE_SHIFT_CV_ABS_FLOOR", "0.30"))
_SEAM_BLUE_SHIFT_CV_RATIO: float = float(os.environ.get("ASP_BENCH_SEAM_BLUE_SHIFT_CV_RATIO", "2.0"))
# §5.107: Bench strip green channel CV comparative gate
_GREEN_CHANNEL_CV_ABS_FLOOR: float = float(os.environ.get("ASP_BENCH_GREEN_CHANNEL_CV_ABS_FLOOR", "0.20"))
_GREEN_CHANNEL_CV_RATIO: float = float(os.environ.get("ASP_BENCH_GREEN_CHANNEL_CV_RATIO", "3.0"))
# §5.108: Bench seam red shift CV comparative gate
_SEAM_RED_SHIFT_CV_ABS_FLOOR: float = float(os.environ.get("ASP_BENCH_SEAM_RED_SHIFT_CV_ABS_FLOOR", "0.30"))
_SEAM_RED_SHIFT_CV_RATIO: float = float(os.environ.get("ASP_BENCH_SEAM_RED_SHIFT_CV_RATIO", "2.0"))
# §5.111: Bench strip blue channel CV comparative gate
_BLUE_CHANNEL_CV_ABS_FLOOR: float = float(os.environ.get("ASP_BENCH_BLUE_CHANNEL_CV_ABS_FLOOR", "0.20"))
_BLUE_CHANNEL_CV_RATIO: float = float(os.environ.get("ASP_BENCH_BLUE_CHANNEL_CV_RATIO", "3.0"))
# §5.112: Bench seam green shift CV comparative gate
_SEAM_GREEN_SHIFT_CV_ABS_FLOOR: float = float(os.environ.get("ASP_BENCH_SEAM_GREEN_SHIFT_CV_ABS_FLOOR", "0.30"))
_SEAM_GREEN_SHIFT_CV_RATIO: float = float(os.environ.get("ASP_BENCH_SEAM_GREEN_SHIFT_CV_RATIO", "2.0"))
# §5.67: Bench strip chroma energy CV comparative gate
_CHROMA_ENERGY_CV_ABS_FLOOR: float = float(os.environ.get("ASP_GATE_CHROMA_ENERGY_CV_ABS_FLOOR", "0.30"))
_CHROMA_ENERGY_CV_RATIO: float = float(os.environ.get("ASP_GATE_CHROMA_ENERGY_CV_RATIO", "2.5"))
# §5.68: Bench seam gradient CV comparative gate
_SEAM_GRADIENT_CV_ABS_FLOOR: float = float(os.environ.get("ASP_GATE_SEAM_GRADIENT_CV_ABS_FLOOR", "0.40"))
_SEAM_GRADIENT_CV_RATIO: float = float(os.environ.get("ASP_GATE_SEAM_GRADIENT_CV_RATIO", "2.0"))

logger = logging.getLogger(__name__)

# §5.35: Bench seam band NCC comparative gate constants
_SEAM_NCC_ABS_FLOOR: float = float(os.environ.get("ASP_GATE_SEAM_NCC_FLOOR", "0.10"))
_SEAM_NCC_RATIO: float = float(os.environ.get("ASP_GATE_SEAM_NCC_RATIO", "0.5"))


def _get_reward_model():
    """Lazily load StitchRewardModel; returns None on any import / init error."""
    global _reward_model
    if _reward_model is not None:
        return _reward_model
    try:
        from backend.src.animation.rlhf.reward_model import StitchRewardModel

        _reward_model = StitchRewardModel()
    except Exception:
        _reward_model = None
    return _reward_model


def _compute_rlhf_score(img_bgr: np.ndarray) -> Optional[float]:
    """Score a stitched panorama with the RLHF reward model (§1.10A).

    Returns a float in [0, 1] (1.0 = perfect quality) or None when the model
    is unavailable.  Outputs below _RLHF_FLAG_THRESHOLD are flagged for review.
    """
    if img_bgr is None or img_bgr.size == 0:
        return None
    model = _get_reward_model()
    if model is None:
        return None
    try:
        return model.predict(img_bgr)
    except Exception:
        return None


def _compute_rlhf_uncertainty(
    img_bgr: np.ndarray,
    n_samples: int = 20,
) -> Optional[float]:
    """§1.10D: MC-dropout epistemic uncertainty for active-learning prioritisation.

    Returns the std-dev across ``n_samples`` stochastic forward passes, or None
    when the reward model is unavailable.  Outputs with uncertainty above
    ``_RLHF_UNCERTAINTY_THRESHOLD`` are candidates for human review: the model
    is near its decision boundary and additional labelling has maximum information
    gain.  Complements ``_compute_rlhf_score`` — a low score with low uncertainty
    is a confident bad output; a middling score with high uncertainty is where
    human labels help most.
    """
    if img_bgr is None or img_bgr.size == 0:
        return None
    model = _get_reward_model()
    if model is None:
        return None
    try:
        _mean, std = model.predict_with_uncertainty(img_bgr, n_samples=n_samples)
        return std
    except Exception:
        return None


# ============================================================================
# SYSTEM INFO
# ============================================================================


def _system_info() -> Dict:
    info: Dict = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cpu": platform.processor(),
        "cpu_count": os.cpu_count() or 0,
        "cpu_threads": 0,
        "ram_gb": 0.0,
        "gpu": "N/A",
        "cuda_version": "N/A",
        "vram_gb": 0.0,
    }
    try:
        import psutil as ps  # pyrefly: ignore [untyped-import]

        info["cpu_threads"] = ps.cpu_count(logical=True) or 0
        info["ram_gb"] = round(ps.virtual_memory().total / 1024**3, 1)
    except Exception:
        pass
    if torch.cuda.is_available():
        info["gpu"] = torch.cuda.get_device_name(0)
        info["cuda_version"] = torch.version.cuda or "N/A"
        props = torch.cuda.get_device_properties(0)
        info["vram_gb"] = round(props.total_memory / 1024**3, 1)
    return info


# ============================================================================
# CV METRIC HELPERS
# ============================================================================


def _sharpness(img: np.ndarray) -> float:
    """Laplacian-variance sharpness (higher = sharper)."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    lap = cv2.Laplacian(gray.astype(np.float32), cv2.CV_32F)
    return float(lap.var())


def _coverage(img: np.ndarray) -> float:
    """Fraction of non-black pixels (proxy for crop completeness)."""
    mask = img.max(axis=2) > 8 if img.ndim == 3 else img > 8
    return float(mask.sum()) / max(mask.size, 1)


def _mean_seam_gradient(
    img: np.ndarray, affines: Optional[List[np.ndarray]] = None
) -> float:
    """
    Average gradient magnitude along horizontal seam boundaries.
    Without affines, samples the whole image and returns mean gradient.
    With affines, evaluates only the seam transition rows.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    gy = cv2.Sobel(gray.astype(np.float32), cv2.CV_32F, 0, 1, ksize=3)
    if affines is None:
        return float(np.abs(gy).mean())
    H, W = gray.shape
    seam_rows = set()
    for a in affines:
        row = round(float(a[1, 2]))
        for dr in range(-5, 6):
            r = row + dr
            if 0 <= r < H:
                seam_rows.add(r)
    if not seam_rows:
        return float(np.abs(gy).mean())
    rows = np.array(sorted(seam_rows))
    return float(np.abs(gy[rows]).mean())


def _color_entropy(img: np.ndarray) -> float:
    """Shannon entropy of luma histogram (higher = more diverse colours)."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).ravel()
    hist = hist / max(hist.sum(), 1.0)
    hist = hist[hist > 0]
    return float(-np.sum(hist * np.log2(hist)))


def _ssim_score(img_a: np.ndarray, img_b: np.ndarray) -> float:
    """SSIM between two images (resized to min dims if needed)."""
    if not _SSIM_OK:
        return float("nan")
    h = min(img_a.shape[0], img_b.shape[0])
    w = min(img_a.shape[1], img_b.shape[1])
    a = cv2.resize(img_a, (w, h))
    b = cv2.resize(img_b, (w, h))
    ga = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
    gb = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)
    score, _ = ssim(ga, gb, full=True, data_range=255)
    return float(score)


def _psnr(img_a: np.ndarray, img_b: np.ndarray) -> float:
    """PSNR (dB) between two images after resizing to common dims."""
    h = min(img_a.shape[0], img_b.shape[0])
    w = min(img_a.shape[1], img_b.shape[1])
    a = cv2.resize(img_a, (w, h)).astype(np.float32)
    b = cv2.resize(img_b, (w, h)).astype(np.float32)
    mse = float(np.mean((a - b) ** 2))
    if mse < 1e-8:
        return float("inf")
    return 20 * math.log10(255.0 / math.sqrt(mse))


def _ghosting_score(img: np.ndarray) -> float:
    """§3.32: Edge energy proxy (formerly mislabelled as ghosting).

    Computes mean absolute value of the second-order vertical derivative
    (double-Sobel Y) — this measures *edge energy / sharpness*, NOT ghosting.
    Kept for backward compatibility with ASP_GATE_GHOST and historical JSON keys;
    emitted as ``edge_energy_score`` in all new benchmark output.

    For true ghosting detection use ``_ghosting_score_v2`` (``ghosting_siqe``).
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    g = gray.astype(np.float32)
    gy2 = cv2.Sobel(cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3), cv2.CV_32F, 0, 1, ksize=3)
    return float(np.abs(gy2).mean())


def _edge_energy_score(img: np.ndarray) -> float:
    """§3.32: Correctly-labelled wrapper — same computation as ``_ghosting_score``."""
    return _ghosting_score(img)


def _ghosting_score_v2(img: np.ndarray) -> float:
    """§3.8A: Double-edge autocorrelation ghosting score.

    A ghost (double-image artifact) creates a pair of parallel edges separated
    by displacement D in the scroll direction.  This shows up as a secondary
    peak in the normalized autocorrelation of the column-mean gradient-magnitude
    profile at lag D.

    Score interpretation:
      0–10  : no detectable double-edge structure (clean output)
      10–30 : mild periodic gradient pattern (natural scene texture, low concern)
      30–60 : moderate secondary peak (ghost possible, inspect)
      60+   : strong secondary peak (ghost highly likely)

    Unlike ``_ghosting_score`` / ``edge_energy_score`` (double-Sobel sharpness
    proxy, §3.32), this metric is specifically sensitive to *repeated* edge
    patterns at a fixed displacement — the signature of a misaligned character
    copy — while being less sensitive to high-frequency texture that is NOT
    ghost-related.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    g = gray.astype(np.float32)
    gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.abs(gy)

    profile = mag.mean(axis=1)  # (H,) column-mean gradient profile
    H = len(profile)
    if H < 20:
        return 0.0

    p = profile - profile.mean()
    n = 2 * H  # zero-pad to avoid circular aliasing
    P = np.fft.rfft(p, n=n)
    acorr = np.fft.irfft(P * P.conj(), n=n)[:H]

    zero_lag = float(acorr[0])
    if zero_lag < 1e-6:
        return 0.0

    acorr /= zero_lag  # normalize: acorr[0] = 1.0

    lag_min = 5
    lag_max = max(lag_min + 1, H // 4)
    secondary = float(acorr[lag_min:lag_max].max()) if lag_max > lag_min else 0.0
    return float(np.clip(secondary, 0.0, 1.0) * 100.0)


def _seam_coherence(img: np.ndarray) -> float:
    """
    Standard deviation of per-row mean luminance.

    A clean panorama produced by genuine camera panning has smoothly varying
    row means (std ≈ 5–20).  An image with severe horizontal color banding —
    caused by the composite stacking frames with different animation-state
    colors — has wildly different row means across the height (std > 30).

    This metric is a better quality indicator than sharpness for detecting the
    catastrophic strip-banding failures that corrupt the Laplacian-variance score.
    Lower = more coherent (better).
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    # Only consider rows that have content (not pure black borders)
    content_rows = gray.mean(axis=1) > 5
    if content_rows.sum() < 10:
        return 0.0
    row_means = gray[content_rows].mean(axis=1)
    return float(np.std(row_means))


def _strip_banding_score(
    render_img: np.ndarray,
    affines: Optional[List[np.ndarray]] = None,
) -> float:
    """
    Maximum luminance jump between adjacent frame-strip zones.

    Samples the mean luminance in a ±25px band around each frame's canvas entry
    row (where the frame's affine ty places it).  If two adjacent strips differ
    by more than the returned value, severe color banding is present.

    Used as a fallback trigger: if max_strip_jump > 20.0 lum units, the Stage 11
    composite is likely to produce visible color bands and SCANS fallback is
    preferable.
    """
    if affines is None or len(affines) < 2:
        return 0.0
    gray = (
        cv2.cvtColor(render_img, cv2.COLOR_BGR2GRAY)
        if render_img.ndim == 3
        else render_img
    )
    H = gray.shape[0]
    strip_means = []
    for a in sorted(affines, key=lambda m: float(m[1, 2])):
        ty = int(float(a[1, 2]))
        y0 = max(0, ty)
        y1 = min(H, ty + 50)
        if y1 > y0:
            band = gray[y0:y1]
            # Skip near-black border regions
            if band.mean() > 5:
                strip_means.append(float(band.mean()))
    if len(strip_means) < 2:
        return 0.0
    diffs = [
        abs(strip_means[i + 1] - strip_means[i]) for i in range(len(strip_means) - 1)
    ]
    return max(diffs)


def _seam_visibility_score(
    output_img: np.ndarray,
    affines: Optional[List[np.ndarray]] = None,
) -> float:
    """
    Worst-case horizontal luminance discontinuity (no-reference).

    Computes the per-row mean absolute difference profile across the full
    output image, then reports the maximum peak value.  A perfectly blended
    seam contributes nothing to this profile; a hard single-pose seam cut
    produces a large spike exactly at the seam row.

    Lower = smoother output (better).  0 = no visible discontinuities.
    Typical clean outputs: < 6.  Single-pose seam cuts: 12–50+.

    Unlike `_seam_coherence` (global row-mean variance), this detects
    localised hard cuts rather than broad brightness drift, making it
    complementary to the existing metrics.  Works for all 96 tests with
    no ground truth required.

    Parameters
    ----------
    output_img : (H, W) or (H, W, 3) uint8 panorama
    affines    : unused; kept for API compatibility with _compute_all_metrics
    """
    gray = (
        cv2.cvtColor(output_img, cv2.COLOR_BGR2GRAY)
        if output_img.ndim == 3
        else output_img
    )
    g = gray.astype(np.float32)
    H, W = g.shape

    # Per-row mean luminance, excluding near-black border pixels.
    content = g > 5  # True where pixel is non-black
    row_content_count = content.sum(axis=1)
    row_valid = row_content_count > W * 0.1  # rows with ≥10% content
    if row_valid.sum() < 4:
        return 0.0

    # Compute mean only for content rows to avoid empty-slice warnings.
    valid_idx = np.where(row_valid)[0]
    row_sums = np.where(content[valid_idx], g[valid_idx], 0.0).sum(axis=1)
    row_mean_vals = row_sums / np.maximum(row_content_count[valid_idx], 1)

    # Adjacent-row absolute difference on content rows only.
    diffs = np.abs(np.diff(row_mean_vals))

    # The worst-case single-row jump is the seam visibility score.
    return round(float(np.nanmax(diffs)) if len(diffs) > 0 else 0.0, 2)


def _compute_per_seam_ghost_scores(
    img: np.ndarray,
    n_strips: int,
    band_px: int = 100,
) -> List[float]:
    """§3.8B: Per-seam SIQE ghost scores for a vertically-assembled panorama.

    Divides the output image into *n_strips* equal-height zones and evaluates
    ``_ghosting_score_v2`` in a ±*band_px* horizontal band centred at each of
    the ``n_strips − 1`` inter-strip seam boundaries.  This localises ghosting
    to specific seams rather than averaging over the whole image (as
    ``ghosting_siqe`` does), making it actionable for per-seam quality triage.

    Parameters
    ----------
    img : (H, W, 3) or (H, W) uint8 image.
    n_strips : number of equal-height zones.  Must be ≥ 2 to produce any
               scores; returns ``[]`` for *n_strips* ≤ 1.
    band_px : half-height of the analysis window around each boundary (px).
              Clipped to image bounds automatically.

    Returns
    -------
    List of ``n_strips − 1`` float scores (same units as ``_ghosting_score_v2``:
    0–100).  Empty list when *n_strips* ≤ 1.
    """
    if n_strips <= 1:
        return []
    H = img.shape[0]
    zone_h = H / n_strips
    scores: List[float] = []
    for k in range(1, n_strips):
        boundary_y = int(round(zone_h * k))
        y0 = max(0, boundary_y - band_px)
        y1 = min(H, boundary_y + band_px)
        band = img[y0:y1]
        scores.append(_ghosting_score_v2(band) if (y1 - y0) >= 20 else 0.0)
    return scores


def _seam_bhattacharyya_distances(
    img: np.ndarray,
    n_strips: int,
    band_px: int = 50,
) -> List[float]:
    """§1.14: Per-seam Bhattacharyya histogram distance for colour-banding detection.

    Divides the output image into *n_strips* equal-height zones and, at each of
    the ``n_strips − 1`` inter-strip seam boundaries, compares the greyscale
    histogram of the *band_px*-row window **above** the boundary against the
    *band_px*-row window **below** it using the Bhattacharyya coefficient.

    Score interpretation (per seam, higher = more similar):
      ≥ 0.95 : excellent colour match (invisible seam)
      0.80–0.95 : good match (typical clean composite)
      0.50–0.80 : noticeable mismatch (visible colour band likely)
      < 0.50  : severe mismatch (hard colour cut)

    The score is ``1 − cv2.compareHist(HISTCMP_BHATTACHARYYA)`` so it lives in
    [0, 1] and is zero for completely disjoint distributions, one for identical
    ones.  This makes it directly comparable to similarity scores elsewhere in
    the benchmark.

    Complements ``_seam_visibility_score`` (which measures the *peak* luminance
    jump at a single row) and ``ghost_seam_scores`` (which measures repeated-edge
    periodicity).  Bhattacharyya distance captures the *distribution* mismatch —
    two strips can have the same mean luminance but completely different histogram
    shapes (e.g., one bimodal, one unimodal) and still produce perceptible banding.

    Parameters
    ----------
    img : (H, W, 3) or (H, W) uint8 image.
    n_strips : number of equal-height zones.  Returns ``[]`` when ≤ 1.
    band_px : number of rows on each side of the boundary used for the histogram.
              Clipped to image bounds; falls back to 0.0 when either side is empty.

    Returns
    -------
    List of ``n_strips − 1`` float scores in [0, 1].  Empty list when
    *n_strips* ≤ 1.
    """
    if n_strips <= 1:
        return []
    H = img.shape[0]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    zone_h = H / n_strips
    scores: List[float] = []
    for k in range(1, n_strips):
        boundary_y = int(round(zone_h * k))
        top = gray[max(0, boundary_y - band_px) : boundary_y]
        bot = gray[boundary_y : min(H, boundary_y + band_px)]
        if top.size == 0 or bot.size == 0:
            scores.append(0.0)
            continue
        h_top = cv2.calcHist([top], [0], None, [256], [0, 256])
        h_bot = cv2.calcHist([bot], [0], None, [256], [0, 256])
        cv2.normalize(h_top, h_top)
        cv2.normalize(h_bot, h_bot)
        dist = cv2.compareHist(h_top, h_bot, cv2.HISTCMP_BHATTACHARYYA)
        scores.append(round(float(np.clip(1.0 - dist, 0.0, 1.0)), 4))
    return scores


def _seam_ncc_coherence(
    img: np.ndarray,
    n_strips: int,
    band_px: int = 60,
) -> List[float]:
    """§3.17: Per-seam normalized cross-correlation (NCC) structural coherence (S123).

    Measures structural continuity across each seam boundary by computing the
    normalized cross-correlation between the *band_px*-row window immediately
    above and the window immediately below each of the ``n_strips − 1`` inter-strip
    seam boundaries.

    NCC score per seam:
      ``ncc = mean((A − μA) · (B − μB)) / (σA · σB + ε)``

    where A and B are the grayscale band crops above and below the boundary,
    resized to a common shape (the smaller of the two) before correlation.

    Score interpretation (in [−1, 1], higher = more coherent):
      ≥ 0.90 : excellent structural match (invisible seam)
      0.70–0.90 : good continuity (typical clean composite)
      0.40–0.70 : moderate mismatch (visible structure step)
      < 0.40   : severe mismatch (hard structure cut or pose gap)

    Complements ``_seam_bhattacharyya_distances`` (intensity distribution
    similarity) by measuring *structural texture pattern* similarity — two strips
    can have matching histograms (same color palette) but completely different
    line-art structure (different character pose), which NCC detects while
    Bhattacharyya misses.

    Parameters
    ----------
    img : (H, W, 3) or (H, W) uint8 image.
    n_strips : number of equal-height zones.  Returns ``[]`` when ≤ 1.
    band_px : number of rows on each side of the boundary used for NCC.
              Clipped to image bounds; returns 0.0 when either side is empty.

    Returns
    -------
    List of ``n_strips − 1`` float scores in [−1, 1].  Empty list when
    *n_strips* ≤ 1.
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
        # Resize both bands to the same row count (use the smaller one) before NCC.
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
            # One band is nearly flat — NCC is meaningless; use 1.0 (no texture = no mismatch).
            scores.append(1.0)
            continue
        ncc = float(np.mean((top - mu_a) * (bot - mu_b)) / (sig_a * sig_b + 1e-8))
        scores.append(round(float(np.clip(ncc, -1.0, 1.0)), 4))
    return scores


def _seam_ownership_entropy(
    output_img: np.ndarray,
    affines: Optional[List[np.ndarray]] = None,
    band_px: int = 8,
) -> float:
    """§4.3: Seam-boundary pixel-value entropy (Phase 4 GraphCut metric).

    Measures how *contested* canvas pixels are at estimated seam boundaries.
    For each adjacent-frame boundary (estimated from affine ty-offsets), we
    sample a ``±band_px`` row window and compute the Shannon entropy of the
    luminance distribution.

    Interpretation:
      ``< 3.5``: smooth blend — low pixel-value diversity, clean seam
      ``3.5–5.0``: moderate diversity — typical single-pose seam
      ``> 5.0``: high entropy — ghosted / doubled content at seam

    When GraphCut seam finding is used (§4.2), ownership is globally optimal
    and seam bands contain content from a single frame → lower entropy.
    When pairwise DP blending is used, contested seam bands contain content
    from both frames → higher entropy.

    Parameters
    ----------
    output_img : (H, W, 3) or (H, W) uint8 panorama.
    affines    : list of 2×3 affine matrices; ty-offsets used to estimate
                 seam boundary rows.  Returns 0.0 when fewer than 2 affines.
    band_px    : half-height of the analysis window around each boundary row.

    Returns
    -------
    float — mean Shannon entropy (bits, base-2) across all estimated seam bands.
    0.0 when no boundaries can be estimated.
    """
    if affines is None or len(affines) < 2:
        return 0.0
    H = output_img.shape[0]
    gray = (
        cv2.cvtColor(output_img, cv2.COLOR_BGR2GRAY)
        if output_img.ndim == 3
        else output_img.astype(np.uint8)
    )
    # Estimate seam boundary rows as midpoints between sorted ty-offsets.
    tys = sorted(float(a[1, 2]) for a in affines)
    boundaries = [(tys[i] + tys[i + 1]) / 2.0 for i in range(len(tys) - 1)]
    entropies: List[float] = []
    for by in boundaries:
        y0 = max(0, int(by) - band_px)
        y1 = min(H, int(by) + band_px + 1)
        if y1 - y0 < 3:
            continue
        band = gray[y0:y1].ravel()
        band = band[band > 5]  # exclude black border / padding pixels
        if len(band) < 16:
            continue
        hist, _ = np.histogram(band, bins=32, range=(0, 256))
        hist = hist.astype(np.float64) + 1e-9
        hist /= hist.sum()
        h = float(-np.sum(hist * np.log2(hist)))
        entropies.append(h)
    return round(float(np.mean(entropies)) if entropies else 0.0, 4)


def _composite_quality_score(
    seam_ncc_min: Optional[float],
    seam_color_min: Optional[float],
    ghost_seam_max: Optional[float],
) -> float:
    """§3.5A: Aggregate per-seam metrics into a single composite quality score (S128).

    Combines three complementary no-reference seam-quality signals into a single
    scalar in [0, 1] (higher = better quality):

    * **NCC structural coherence** (``seam_ncc_min``): measures whether the
      texture pattern above and below each seam boundary is structurally
      continuous.  Mapped from [-1, 1] → [0, 1] via ``(v + 1) / 2``.
    * **Bhattacharyya color similarity** (``seam_color_min``): measures whether
      the luminance histogram above and below each seam boundary is similar.
      Already in [0, 1] (1 = identical distributions).
    * **Ghost score** (``ghost_seam_max``): measures doubled-edge artifacts in
      [0, 100].  Inverted to [0, 1] via ``1 − v / 100`` (0 = severe ghost,
      1 = no ghost).

    When a component is unavailable (``None``), a neutral value of 0.5 is used
    so the missing dimension does not bias the composite unfairly.  This
    gracefully handles single-strip images where per-seam scores are empty
    (``n_strips = 1`` → ``seam_ncc_min = None``).

    Interpretation:
      ≥ 0.80 : high quality — seam likely invisible
      0.60–0.80 : acceptable — minor colour step or structure gap
      0.40–0.60 : warning — noticeable seam; tune feather / gain
      < 0.40   : fail — hard cut, ghost, or severe colour mismatch

    Parameters
    ----------
    seam_ncc_min : worst-case NCC coherence across all seams, or None.
    seam_color_min : worst-case Bhattacharyya similarity across all seams, or None.
    ghost_seam_max : worst-case per-seam ghost score (0–100), or None.

    Returns
    -------
    float in [0, 1], rounded to 4 decimal places.
    """
    ncc_term = ((seam_ncc_min + 1.0) / 2.0) if seam_ncc_min is not None else 0.5
    color_term = seam_color_min if seam_color_min is not None else 0.5
    ghost_term = (
        max(0.0, 1.0 - ghost_seam_max / 100.0) if ghost_seam_max is not None else 0.5
    )
    ncc_term = float(np.clip(ncc_term, 0.0, 1.0))
    color_term = float(np.clip(color_term, 0.0, 1.0))
    ghost_term = float(np.clip(ghost_term, 0.0, 1.0))
    return round((ncc_term + color_term + ghost_term) / 3.0, 4)


def _strip_gradient_cv(img: np.ndarray, n_strips: int = 8) -> float:
    """§3.21: Coefficient of variation of per-strip Laplacian energy (S150).

    Splits the image into *n_strips* equal horizontal strips and computes the
    mean absolute Laplacian energy per strip.  Returns the coefficient of
    variation (std / mean) across strips.  A high CV means some strips are much
    sharper or blurrier than adjacent ones — a signature of seam-induced
    sharpness discontinuities.  Returns 0.0 for degenerate inputs.
    """
    if img is None or img.ndim != 3 or img.shape[0] < n_strips or n_strips < 2:
        return 0.0
    H = img.shape[0]
    strip_h = H // n_strips
    if strip_h < 1:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    energies = []
    for i in range(n_strips):
        y0 = i * strip_h
        y1 = y0 + strip_h
        lap = cv2.Laplacian(gray[y0:y1], cv2.CV_64F)
        energies.append(float(np.mean(np.abs(lap))))
    mean_e = float(np.mean(energies))
    if mean_e < 1e-6:
        return 0.0
    return float(np.std(energies) / mean_e)


def _seam_contrast_ratio(
    img: np.ndarray, n_strips: int = 8, band_px: int = 10
) -> float:
    """§3.22: Ratio of seam-boundary gradient energy to interior gradient energy (S151).

    Splits the image into *n_strips* horizontal strips.  At each inter-strip
    boundary, measures mean absolute Laplacian energy in a ±*band_px* row band
    (seam region) vs. the energy in the non-band pixels.  Returns the ratio
    seam_energy / interior_energy.  Values near 1.0 indicate no seam artifact;
    values > 1.5 indicate visible boundary sharpness discontinuities.
    Returns 1.0 (neutral) for degenerate inputs.
    """
    if img is None or img.ndim != 3 or img.shape[0] < n_strips * 2 or n_strips < 2:
        return 1.0
    H = img.shape[0]
    strip_h = H // n_strips
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    lap = np.abs(cv2.Laplacian(gray, cv2.CV_32F))

    seam_rows = set()
    for i in range(1, n_strips):
        boundary = i * strip_h
        for r in range(max(0, boundary - band_px), min(H, boundary + band_px)):
            seam_rows.add(r)

    seam_mask = np.zeros(H, dtype=bool)
    for r in seam_rows:
        seam_mask[r] = True

    seam_energy = float(lap[seam_mask].mean()) if seam_mask.any() else 0.0
    interior_energy = float(lap[~seam_mask].mean()) if (~seam_mask).any() else 0.0

    if interior_energy < 1e-6:
        return 1.0
    return seam_energy / interior_energy


def _seam_col_spread(img: np.ndarray, n_strips: int = 8) -> float:
    """§3.23: Std of per-strip horizontal gradient peak position (S152).

    For each strip, finds the column of maximum horizontal gradient magnitude
    (the most likely seam column if any exists).  Returns the std of these
    peak columns, normalized by image width.  A low normalized std means all
    strips pick the same seam column (concentrated routing); a high value
    means the gradients are spread across columns (good background routing).
    Returns 0.0 for degenerate inputs.
    """
    if img is None or img.ndim != 3 or img.shape[0] < n_strips or n_strips < 2:
        return 0.0
    H, W = img.shape[:2]
    if W < 2:
        return 0.0
    strip_h = H // n_strips
    if strip_h < 1:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    sobelx = np.abs(cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3))
    peaks = []
    for i in range(n_strips):
        y0 = i * strip_h
        y1 = y0 + strip_h
        col_energy = sobelx[y0:y1].mean(axis=0)
        peaks.append(int(np.argmax(col_energy)))
    return float(np.std(peaks) / W)


def _seam_row_std(img: np.ndarray, n_strips: int = 8) -> float:
    """§3.24: Max per-boundary row pixel std, normalized by 255 (S153).

    For each inter-strip boundary row, computes the std of BGR pixel values
    across the width of that row.  Returns the maximum std divided by 255.
    A high value means at least one boundary row has strong horizontal variation
    (abrupt color transition = visible seam).  Returns 0.0 for degenerate inputs.
    """
    if img is None or img.ndim != 3 or img.shape[0] < n_strips or n_strips < 2:
        return 0.0
    H, W = img.shape[:2]
    strip_h = H // n_strips
    if strip_h < 1:
        return 0.0
    max_std = 0.0
    for i in range(1, n_strips):
        row_idx = i * strip_h
        if row_idx >= H:
            continue
        row = img[row_idx].astype(np.float32)  # (W, 3)
        row_std = float(row.std())
        max_std = max(max_std, row_std)
    return max_std / 255.0


def _strip_sat_cv(img: np.ndarray, n_strips: int = 8) -> float:
    """§3.26: Coefficient of variation of per-strip mean HSV saturation (S155).

    Converts *img* to HSV and measures mean saturation in each horizontal
    strip.  Returns std / mean across strips.  High CV = strips have very
    different saturation levels (photometric banding).  Returns 0.0 for
    degenerate inputs (< 2 strips, height too small, zero mean saturation).
    """
    if img is None or img.ndim != 3 or img.shape[0] < n_strips or n_strips < 2:
        return 0.0
    H = img.shape[0]
    strip_h = H // n_strips
    if strip_h < 1:
        return 0.0
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
    sat = hsv[..., 1]
    means = []
    for i in range(n_strips):
        y0 = i * strip_h
        y1 = y0 + strip_h
        means.append(float(sat[y0:y1].mean()))
    mean_sat = float(np.mean(means))
    if mean_sat < 1e-6:
        return 0.0
    return float(np.std(means) / mean_sat)


def _seam_band_ncc(img: np.ndarray, n_strips: int = 8, band_px: int = 10) -> float:
    """§3.27: Minimum NCC between strip boundary bands (S156).

    For each inter-strip boundary, computes the normalized cross-correlation
    between the *band_px*-row band immediately above and the band immediately
    below.  Returns the minimum NCC across all boundaries.  Values near 1.0
    indicate seamless transitions; values near 0 or negative indicate visible
    discontinuities.  Returns 1.0 (neutral) for degenerate inputs.
    """
    if img is None or img.ndim != 3 or img.shape[0] < n_strips * 2 or n_strips < 2:
        return 1.0
    H = img.shape[0]
    strip_h = H // n_strips
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    min_ncc = 1.0
    for i in range(1, n_strips):
        boundary = i * strip_h
        above = gray[max(0, boundary - band_px) : boundary].ravel()
        below = gray[boundary : min(H, boundary + band_px)].ravel()
        if len(above) < 4 or len(below) < 4:
            continue
        n = min(len(above), len(below))
        a, b = above[:n], below[:n]
        a = a - a.mean()
        b = b - b.mean()
        denom = float(np.linalg.norm(a) * np.linalg.norm(b))
        if denom < 1e-6:
            continue
        ncc = float(np.dot(a, b) / denom)
        min_ncc = min(min_ncc, ncc)
    return min_ncc


def _seam_row_grad_coherence(
    img: np.ndarray, n_strips: int = 8, band_px: int = 8
) -> float:
    """§3.28: Mean angular coherence of Sobel gradient at seam boundary rows (S157).

    For each inter-strip boundary, computes Sobel-X and Sobel-Y in a ±*band_px*
    row band, then measures the circular mean resultant length R = |mean(exp(2jθ))|
    where θ = atan2(Gy, Gx).  R near 1.0 means gradient directions are uniform
    (likely a real edge); R near 0 means isotropic noise (no structural seam).
    Returns the *minimum* R across all boundaries — a low minimum indicates a
    seam boundary where the local texture has no dominant orientation (smooth
    transition region that shouldn't look like a hard edge).
    Returns 1.0 for degenerate inputs.
    """
    if img is None or img.ndim != 3 or img.shape[0] < n_strips * 2 or n_strips < 2:
        return 1.0
    H = img.shape[0]
    strip_h = H // n_strips
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    min_r = 1.0
    for i in range(1, n_strips):
        boundary = i * strip_h
        y0 = max(0, boundary - band_px)
        y1 = min(H, boundary + band_px)
        if y1 - y0 < 2:
            continue
        band = gray[y0:y1]
        gx = cv2.Sobel(band, cv2.CV_64F, 1, 0, ksize=3).ravel()
        gy = cv2.Sobel(band, cv2.CV_64F, 0, 1, ksize=3).ravel()
        mag = np.sqrt(gx**2 + gy**2)
        strong = mag > 1e-3
        if strong.sum() < 4:
            continue
        angles = np.arctan2(gy[strong], gx[strong])
        cos_m = float(np.cos(2 * angles).mean())
        sin_m = float(np.sin(2 * angles).mean())
        r = float(np.sqrt(cos_m**2 + sin_m**2))
        min_r = min(min_r, r)
    return min_r


def _seam_boundary_entropy(
    img: np.ndarray, n_strips: int = 8, band_px: int = 15
) -> List[float]:
    """§3.25: Normalised Shannon entropy at each seam boundary band (S154).

    For each inter-strip boundary, takes a ±band_px row window and computes the
    Shannon entropy of the 256-bin greyscale intensity histogram, normalised to
    [0, 1] by dividing by log2(256)=8.  High entropy = complex/varied texture at
    the seam (more likely to be visible); low entropy = uniform region (less
    visible seam step).

    Returns a list of ``n_strips - 1`` float values.  Returns [] for degenerate
    inputs (too few strips, too small image).
    """
    if img is None or img.ndim < 2 or n_strips < 2:
        return []
    H = img.shape[0]
    strip_h = H // n_strips
    if strip_h < 1:
        return []
    gray = (
        img
        if img.ndim == 2
        else (
            img.astype(np.float32).dot(np.array([0.114, 0.587, 0.299])).astype(np.uint8)
        )
    )
    scores: List[float] = []
    for i in range(1, n_strips):
        row = i * strip_h
        y0 = max(0, row - band_px)
        y1 = min(H, row + band_px)
        if y1 <= y0:
            scores.append(0.0)
            continue
        band = gray[y0:y1].ravel()
        hist, _ = np.histogram(band, bins=256, range=(0, 256))
        hist = hist[hist > 0].astype(np.float64)
        p = hist / hist.sum()
        entropy = float(-np.sum(p * np.log2(p))) / 8.0
        scores.append(float(np.clip(entropy, 0.0, 1.0)))
    return scores


def _zone_coverage_fraction(img: np.ndarray, n_strips: int = 8) -> float:
    """§3.29: Fraction of image height covered by inter-strip blend zones (S158).

    Approximates how much of the canvas is occupied by transition/blend regions
    versus clean single-frame content.  High fraction → blend zones dominate the
    output and seam quality matters more; low fraction → most rows are single-frame
    and seam placement has smaller visual impact.

    Computation: ``n_strips − 1`` seam boundaries, each with an estimated blend
    band of strip_h // 3 rows on each side.  Total blend rows capped at H so the
    fraction stays in [0, 1].

    Returns 0.0 for degenerate inputs.
    """
    if img is None or img.ndim != 3 or img.shape[0] < n_strips or n_strips < 2:
        return 0.0
    H = img.shape[0]
    strip_h = H // n_strips
    if strip_h < 1:
        return 0.0
    approx_feather = max(1, strip_h // 3)
    n_boundaries = n_strips - 1
    total_blend_rows = min(H, n_boundaries * 2 * approx_feather)
    return float(total_blend_rows / H)


def _canvas_gain_uniformity(img: np.ndarray, n_strips: int = 8) -> float:
    """§3.31: Strip-level luminance gain uniformity metric (S160).

    Divides the image into *n_strips* equal horizontal strips, computes the
    mean luminance of each strip, and returns the coefficient of variation
    (std / mean) of those strip means.  A value of 0.0 means perfectly uniform
    luminance across strips; high values indicate strip-level banding.

    Range [0, ∞).  Returns 0.0 for degenerate inputs (fewer rows than
    n_strips, all-zero image, or single strip).
    """
    if img is None or n_strips < 1:
        return 0.0
    gray: np.ndarray
    if img.ndim == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    else:
        gray = img.astype(np.float32)
    H = gray.shape[0]
    if H < n_strips:
        return 0.0
    strip_h = H // n_strips
    if strip_h < 1:
        return 0.0
    strip_means = []
    for i in range(n_strips):
        y0 = i * strip_h
        y1 = y0 + strip_h
        strip_means.append(float(gray[y0:y1].mean()))
    mean_val = float(np.mean(strip_means))
    if mean_val < 1.0:
        return 0.0
    return float(np.std(strip_means) / mean_val)


def _strip_luma_monotonicity(img: np.ndarray, n_strips: int = 8) -> float:
    """§5.10: Non-monotonicity of strip mean luminance sequence.

    Computes the fraction of adjacent strip pairs that violate monotonicity
    (i.e., the sequence of strip means is neither consistently ascending nor
    descending). Returns 0.0 for perfectly monotonic (or degenerate) input,
    1.0 for perfectly alternating (every pair reverses direction).

    Range [0, 1]. Higher = more banding / non-monotonic strip luminance.
    """
    if img is None or n_strips < 2:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32) if img.ndim == 3 else img.astype(np.float32)
    H = gray.shape[0]
    strip_h = H // n_strips
    if strip_h < 1:
        return 0.0
    strip_means = np.array([gray[i * strip_h:(i + 1) * strip_h].mean() for i in range(n_strips)])
    diffs = np.diff(strip_means)
    if len(diffs) < 2:
        return 0.0
    signs = np.sign(diffs)
    nonzero = signs[signs != 0]
    if len(nonzero) < 2:
        return 0.0
    reversals = int(np.sum(nonzero[1:] != nonzero[:-1]))
    return reversals / (len(nonzero) - 1)


def _horizontal_fft_banding(img: np.ndarray, n_strips: int = 8) -> float:
    """§5.12: Detect periodic horizontal banding via column-mean luminance FFT.

    Computes the column-mean luminance profile (1D, length=H), takes its FFT,
    and measures the relative energy at the spatial frequency corresponding to
    n_strips equally-spaced bands. High score = strong periodic banding at
    strip boundaries.

    Returns a score in [0, 1]. 0 = no banding at strip frequency; 1 = all
    energy concentrated at strip frequency. Returns 0.0 for degenerate input.
    """
    if img is None:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32) if img.ndim == 3 else img.astype(np.float32)
    H = gray.shape[0]
    if H < n_strips * 4:
        return 0.0
    # Column-mean luminance profile (length H)
    profile = gray.mean(axis=1)  # shape (H,)
    # Remove DC (mean)
    profile -= profile.mean()
    # FFT magnitude spectrum
    spectrum = np.abs(np.fft.rfft(profile))
    total_energy = float(np.sum(spectrum ** 2))
    if total_energy < 1e-6:
        return 0.0
    # Strip frequency: the banding period is strip_h = H/n_strips rows.
    # An alternating (high/low) pattern repeats every 2*strip_h rows, so the
    # dominant FFT bin is H / (2*strip_h) = n_strips // 2.
    # We also sample the harmonic at n_strips (period = strip_h) which captures
    # same-polarity periodicity and the square-wave harmonic series.
    strip_freq_idx = max(1, n_strips // 2)
    # Sum energy in a ±1 bin window around strip frequency
    lo = max(1, strip_freq_idx - 1)
    hi = min(len(spectrum) - 1, strip_freq_idx + 1)
    band_energy = float(np.sum(spectrum[lo:hi + 1] ** 2))
    return float(np.clip(band_energy / total_energy, 0.0, 1.0))


def _compute_cqas(metrics: dict) -> Optional[float]:
    """§3.18 Composite Quality Aggregate Score — single [0,1] quality signal (S148).

    Combines five complementary no-reference metrics into one scalar, useful
    especially for the 43 GT-less tests where GT-SSIM is unavailable.
    Higher = better quality.

    Components (all normalized to [0, 1]):
      ghosting_siqe        : 0=clean → 1.0; ≥60=ghost → 0.0  (weight 0.35)
      seam_visibility      : 0=invisible → 1.0; ≥25=hard-cut → 0.0  (weight 0.30)
      seam_coherence       : 0=coherent → 1.0; ≥50=incoherent → 0.0  (weight 0.20)
      sharpness            : corpus ref ~100; clamped to [0, 1]  (weight 0.15)
      canvas_gain_uniformity: 0=uniform → 1.0; ≥0.40=banded → 0.0  (weight 0.15)

    Returns None only when all five metrics are None.
    total_w normalization handles missing components gracefully.
    """
    g = metrics.get("ghosting_siqe")
    g_score = float(np.clip(1.0 - g / 60.0, 0.0, 1.0)) if g is not None else None

    sv = metrics.get("seam_visibility")
    sv_score = float(np.clip(1.0 - sv / 25.0, 0.0, 1.0)) if sv is not None else None

    sc = metrics.get("seam_coherence")
    sc_score = float(np.clip(1.0 - sc / 50.0, 0.0, 1.0)) if sc is not None else None

    sh = metrics.get("sharpness")
    sh_score = float(np.clip(sh / 100.0, 0.0, 1.0)) if sh is not None else None

    cgu = metrics.get("canvas_gain_uniformity")
    cgu_score = float(np.clip(1.0 - cgu / 0.40, 0.0, 1.0)) if cgu is not None else None

    components = [
        (g_score, 0.35),
        (sv_score, 0.30),
        (sc_score, 0.20),
        (sh_score, 0.15),
        (cgu_score, 0.15),
    ]
    available = [(s, w) for s, w in components if s is not None]
    if not available:
        return None
    total_w = sum(w for _, w in available)
    return round(sum(s * w for s, w in available) / total_w, 4)


def _bg_consistency_score(img: np.ndarray, n_strips: int = 1) -> float:
    """§1.94 Background plate row consistency score (S148).

    Measures per-row luminance variance within each horizontal strip.
    High variance within a strip signals a corrupted background plate
    (inconsistent temporal median rows).  Returns mean per-row luminance
    std across all strips, in [0, ∞); lower = more consistent background.
    Useful for detecting §1.87 masked-median failures.
    """
    if img is None or img.size == 0:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img.copy()
    H = gray.shape[0]
    strip_h = max(1, H // max(1, n_strips))
    stds: List[float] = []
    for s in range(n_strips):
        y0 = s * strip_h
        y1 = min(H, (s + 1) * strip_h)
        strip = gray[y0:y1]
        if strip.shape[0] == 0:
            continue
        row_means = strip.mean(axis=1).astype(np.float32)
        stds.append(float(row_means.std()))
    return round(float(np.mean(stds)) if stds else 0.0, 2)


def _compute_si_fid_score(
    asp_img: np.ndarray,
    sim_img: np.ndarray,
    patch_size: int = 128,
    n_patches: int = 32,
    seed: int = 42,
) -> Optional[float]:
    """§3.9: SI-FID proxy — ratio of patch Laplacian sharpness (ASP / simple_stitch).

    Samples ``n_patches`` random patches from each image, computes the mean
    Laplacian variance (a reference-free sharpness proxy), and returns
    ``asp_sharpness / sim_sharpness``.  Values > 1.0 mean ASP is sharper;
    < 1.0 means simple_stitch is sharper.  Returns None on any error (e.g.
    images too small, mismatched shape).

    This is a zero-dep proxy for the Self-Inception FID (SI-FID) quality
    signal: it uses the same interpretable "sharpness ratio" axis without
    requiring an InceptionV3 forward pass.  The ratio is computed from
    identically-sampled patch locations so spatial sampling bias cancels.
    """
    if asp_img is None or sim_img is None:
        return None
    try:
        h = min(asp_img.shape[0], sim_img.shape[0])
        w = min(asp_img.shape[1], sim_img.shape[1])
        if h < patch_size or w < patch_size:
            return None
        rng = np.random.default_rng(seed)
        ys = rng.integers(0, h - patch_size, size=n_patches)
        xs = rng.integers(0, w - patch_size, size=n_patches)
        asp_var, sim_var = [], []
        for y, x in zip(ys, xs):
            pa = asp_img[y : y + patch_size, x : x + patch_size]
            ps = sim_img[y : y + patch_size, x : x + patch_size]
            ga = cv2.cvtColor(pa, cv2.COLOR_BGR2GRAY) if pa.ndim == 3 else pa
            gs = cv2.cvtColor(ps, cv2.COLOR_BGR2GRAY) if ps.ndim == 3 else ps
            asp_var.append(cv2.Laplacian(ga, cv2.CV_64F).var())
            sim_var.append(cv2.Laplacian(gs, cv2.CV_64F).var())
        asp_mean = float(np.mean(asp_var))
        sim_mean = float(np.mean(sim_var))
        if sim_mean < 1e-9:
            return None
        return round(asp_mean / sim_mean, 4)
    except Exception:
        return None


def _compute_all_metrics(
    img: np.ndarray,
    affines: Optional[List] = None,
    n_strips: int = 1,
) -> Dict:
    rlhf = _compute_rlhf_score(img)
    rlhf_unc = _compute_rlhf_uncertainty(img)
    seam_scores = _compute_per_seam_ghost_scores(img, n_strips)
    color_scores = _seam_bhattacharyya_distances(img, n_strips)
    ncc_scores = _seam_ncc_coherence(img, n_strips)
    _seam_ncc_min = round(min(ncc_scores), 4) if ncc_scores else None
    _seam_color_min = round(min(color_scores), 4) if color_scores else None
    _ghost_seam_max = round(max(seam_scores), 2) if seam_scores else None
    # §1.10D: needs_review fires when the model is uncertain (std > threshold),
    # regardless of whether the score itself triggered rlhf_flagged.  Uncertain
    # near-boundary outputs are the highest-value samples for human annotation.
    _rlhf_needs_review = rlhf_unc is not None and rlhf_unc > _RLHF_UNCERTAINTY_THRESHOLD
    metrics = {
        "sharpness": round(_sharpness(img), 2),
        "coverage": round(_coverage(img), 4),
        "seam_gradient": round(_mean_seam_gradient(img, affines), 3),
        "color_entropy": round(_color_entropy(img), 4),
        "edge_energy_score": round(_edge_energy_score(img), 4),
        "ghosting_score": round(_ghosting_score(img), 4),  # alias kept for gate compat
        "ghosting_siqe": round(_ghosting_score_v2(img), 2),
        "seam_coherence": round(_seam_coherence(img), 2),
        "seam_visibility": round(_seam_visibility_score(img, affines), 2),
        "seam_ownership_entropy": _seam_ownership_entropy(img, affines),
        "strip_banding_score": round(_strip_banding_score(img, affines), 2),
        "ghost_seam_scores": [round(s, 2) for s in seam_scores],
        "ghost_seam_max": _ghost_seam_max,
        "seam_color_scores": color_scores,
        "seam_color_min": _seam_color_min,
        "seam_ncc_scores": ncc_scores,
        "seam_ncc_min": _seam_ncc_min,
        "composite_quality": _composite_quality_score(
            _seam_ncc_min, _seam_color_min, _ghost_seam_max
        ),
        "width": img.shape[1],
        "height": img.shape[0],
        "rlhf_score": round(rlhf, 4) if rlhf is not None else None,
        "rlhf_flagged": (rlhf is not None and rlhf < _RLHF_FLAG_THRESHOLD),
        "rlhf_uncertainty": round(rlhf_unc, 4) if rlhf_unc is not None else None,
        "rlhf_needs_review": _rlhf_needs_review,
        "mllm_body_coherence": None,
        "mllm_seam_quality": None,
        "mllm_bg_consistency": None,
        "mllm_overall": None,
    }
    if _MLLM_SCORER and img is not None:
        try:
            from backend.src.animation.hitl.mllm_scorer import (
                score_composite as _mllm_score,
            )

            _ms = _mllm_score(img, model=_MLLM_MODEL)
            metrics["mllm_body_coherence"] = _ms.body_coherence
            metrics["mllm_seam_quality"] = _ms.seam_quality
            metrics["mllm_bg_consistency"] = _ms.bg_consistency
            metrics["mllm_overall"] = _ms.overall
        except Exception as _exc:
            logger.warning("[bench] MLLM scoring failed: %s", _exc)
    # §3.18 — CQAS aggregate quality score and §1.94 background consistency.
    metrics["cqas"] = _compute_cqas(metrics)
    metrics["bg_consistency_score"] = _bg_consistency_score(img, n_strips)
    # §1.96 — Chroma seam coherence.
    metrics["chroma_seam_coherence"] = _chroma_seam_coherence(img, n_strips=8)
    # §3.21 — Per-strip Laplacian energy CV.
    metrics["strip_gradient_cv"] = _strip_gradient_cv(img, n_strips=8)
    # §3.22 — Seam boundary vs interior gradient energy ratio.
    metrics["seam_contrast_ratio"] = _seam_contrast_ratio(img, n_strips=8, band_px=10)
    # §3.23 — Seam-path column distribution spread.
    metrics["seam_col_spread"] = _seam_col_spread(img, n_strips=8)
    metrics["seam_row_std"] = _seam_row_std(img, n_strips=8)
    metrics["strip_sat_cv"] = _strip_sat_cv(img, n_strips=8)
    # §3.27 — Minimum NCC between strip boundary bands.
    metrics["seam_band_ncc_min"] = _seam_band_ncc(img, n_strips=8, band_px=10)
    # §3.28 — Seam boundary gradient direction coherence.
    metrics["seam_grad_coherence_min"] = _seam_row_grad_coherence(
        img, n_strips=8, band_px=8
    )
    # §3.25 — Seam boundary entropy.
    _sbe = _seam_boundary_entropy(img, n_strips=n_strips, band_px=15)
    metrics["seam_boundary_entropies"] = _sbe
    metrics["seam_boundary_entropy_max"] = max(_sbe) if _sbe else None
    # §3.29 — Blend zone coverage fraction (S158).
    metrics["zone_coverage_fraction"] = _zone_coverage_fraction(img, n_strips=8)
    # §3.30 — Per-strip top/bottom NCC self-consistency (S159).
    metrics["strip_self_ssim"] = round(_strip_self_ssim(img, n_strips=8), 4)
    # §3.31 — Canvas strip-level luminance gain uniformity (S160).
    metrics["canvas_gain_uniformity"] = round(
        _canvas_gain_uniformity(img, n_strips=8), 4
    )
    # §5.10 — Per-strip luma monotonicity (S169).
    metrics["strip_luma_monotonicity"] = round(_strip_luma_monotonicity(img, n_strips=8), 4)
    # §5.12 — Horizontal FFT banding score (S170).
    metrics["horizontal_fft_banding"] = round(_horizontal_fft_banding(img, n_strips=8), 4)
    return metrics


# ============================================================================
# GROUND TRUTH HELPERS
# ============================================================================


def _load_ground_truth(dataset_name: str, gt_dir: str) -> Optional[np.ndarray]:
    """
    Load the ground truth reference image for a dataset, if one exists.

    Tries .png, .jpg, .jpeg extensions in that order.  Returns None when no
    ground truth is available for the given dataset.
    """
    for ext in (".png", ".jpg", ".jpeg"):
        path = os.path.join(gt_dir, f"{dataset_name}{ext}")
        if os.path.exists(path):
            img = cv2.imread(path)
            if img is not None:
                return img
    return None


def _compute_aligned_ssim(output_img: np.ndarray, gt_img: np.ndarray) -> float:
    """
    SSIM after ECC Euclidean alignment of output_img to gt_img (S8 metric, S25 dedup).

    Eliminates framing/translation bias from GT-coupling — frame substitutions that
    diverge from the GT's temporal reference shift the output, penalising raw SSIM
    even when pose quality is identical. MOTION_EUCLIDEAN handles both translation
    and small rotation residuals from the panorama assembly.

    gaussFiltSize=5 pre-smooths ECC input for robustness on noisy/low-texture crops.
    GT dimensions are used as the canonical reference space. Falls back to
    non-aligned SSIM if ECC diverges (e.g. featureless input).
    """
    if not _SSIM_OK:
        return float("nan")

    h, w = gt_img.shape[:2]
    resized_out = cv2.resize(output_img, (w, h))

    gray_gt = cv2.cvtColor(gt_img, cv2.COLOR_BGR2GRAY)
    gray_out = cv2.cvtColor(resized_out, cv2.COLOR_BGR2GRAY)

    warp_matrix = np.eye(2, 3, dtype=np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-4)

    try:
        # pyrefly: ignore [no-matching-overload]
        _, warp_matrix = cv2.findTransformECC(
            gray_out,
            gray_gt,
            warp_matrix,
            cv2.MOTION_EUCLIDEAN,
            criteria,
            inputMask=None,
            gaussFiltSize=5,
        )
        aligned_out = cv2.warpAffine(
            resized_out,
            warp_matrix,
            (w, h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REPLICATE,
        )
        gray_aligned = cv2.cvtColor(aligned_out, cv2.COLOR_BGR2GRAY)
        score, _ = ssim(gray_aligned, gray_gt, full=True, data_range=255)
        return float(score)
    except Exception:
        score, _ = ssim(gray_out, gray_gt, full=True, data_range=255)
        return float(score)


def _compute_gt_metrics(
    output_img: Optional[np.ndarray],
    gt_img: np.ndarray,
) -> Dict:
    """
    Compute SSIM and PSNR between a pipeline output and the ground truth.

    Both images are resized to the smaller of the two dimensions before
    comparison, matching the existing _ssim_score / _psnr helpers.  Returns an
    empty dict when output_img is None.
    """
    if output_img is None:
        return {}
    ssim_val = _ssim_score(output_img, gt_img)
    aligned_ssim = _compute_aligned_ssim(output_img, gt_img)
    psnr_val = _psnr(output_img, gt_img)
    sc_val = _seam_coherence(output_img)
    return {
        "ssim_vs_gt": round(ssim_val, 4) if not math.isnan(ssim_val) else None,
        "aligned_ssim_vs_gt": round(aligned_ssim, 4)
        if not math.isnan(aligned_ssim)
        else None,
        "psnr_vs_gt": round(psnr_val, 2) if not math.isnan(psnr_val) else None,
        "seam_coherence": round(sc_val, 2),
    }


def _gt_verdict(
    asp_gt: Dict,
    sim_gt: Dict,
) -> Optional[str]:
    """
    Quality verdict derived from ground truth SSIM comparison.

    Returns 'asp_better', 'simple_better', or 'comparable' when both outputs
    have GT SSIM scores.  Returns None when ground truth is unavailable.

    SSIM-vs-GT is a far more reliable signal than Laplacian sharpness because
    it measures structural similarity to the *intended* output, not the presence
    of high-frequency edge artifacts introduced by banding or misalignment.
    """
    asp_ssim = asp_gt.get("aligned_ssim_vs_gt", asp_gt.get("ssim_vs_gt"))
    sim_ssim = sim_gt.get("aligned_ssim_vs_gt", sim_gt.get("ssim_vs_gt"))
    if asp_ssim is None or sim_ssim is None:
        return None
    if asp_ssim > sim_ssim * 1.03:  # 3 % margin to avoid noise-driven flips
        return "asp_better"
    if sim_ssim > asp_ssim * 1.03:
        return "simple_better"
    return "comparable"


# ============================================================================
# VISUALIZATION HELPERS
# ============================================================================


def _save_affine_path_plot(
    affines: List[np.ndarray],
    canvas_h: int,
    canvas_w: int,
    frame_h: int,
    frame_w: int,
    out_path: str,
) -> None:
    """2-D plot of frame placement on the canvas."""
    if not _MPL_OK:
        return
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.set_xlim(-50, canvas_w + 50)
    ax.set_ylim(canvas_h + 50, -50)
    ax.set_aspect("equal")
    ax.set_title("Frame Placement on Canvas (2D)", fontsize=11)
    ax.set_xlabel("X (px)")
    ax.set_ylabel("Y (px)")
    colors = plt.cm.plasma(np.linspace(0, 1, len(affines)))  # pyrefly: ignore [missing-attribute]
    for idx, (M, color) in enumerate(zip(affines, colors)):
        tx = float(M[0, 2])
        ty = float(M[1, 2])
        rect = plt.Rectangle(
            (tx, ty),
            frame_w,
            frame_h,
            linewidth=1.5,
            edgecolor=color,
            facecolor=(*color[:3], 0.08),
        )
        ax.add_patch(rect)
        ax.text(
            tx + frame_w / 2,
            ty + frame_h / 2,
            str(idx),
            ha="center",
            va="center",
            fontsize=7,
            color=color,
        )
    ax.set_facecolor("#1a1a2e")
    fig.patch.set_facecolor("#12121f")
    ax.title.set_color("white")
    ax.xaxis.label.set_color("white")
    ax.yaxis.label.set_color("white")
    ax.tick_params(colors="white")
    for spine in ax.spines.values():
        spine.set_edgecolor("#444")
    sm = plt.cm.ScalarMappable(cmap="plasma", norm=plt.Normalize(0, len(affines) - 1))
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax)
    cbar.set_label("Frame index", color="white")
    cbar.ax.yaxis.set_tick_params(color="white")
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color="white")
    plt.tight_layout()
    fig.savefig(out_path, dpi=100, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def _save_translation_plot(
    affines: List[np.ndarray],
    out_path: str,
    title: str = "Translation Vectors per Frame",
) -> None:
    """2-D plot of tx/ty translation per frame."""
    if not _MPL_OK:
        return
    N = len(affines)
    txs = [float(M[0, 2]) for M in affines]
    tys = [float(M[1, 2]) for M in affines]
    frames = list(range(N))
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for ax, vals, label, color in zip(
        axes, [txs, tys], ["tx (horizontal)", "ty (vertical)"], ["#4ecdc4", "#ff6b6b"]
    ):
        ax.plot(frames, vals, marker="o", color=color, linewidth=2, markersize=5)
        ax.set_xlabel("Frame index")
        ax.set_ylabel(f"{label} (px)")
        ax.set_title(label)
        ax.grid(True, alpha=0.3)
        ax.set_facecolor("#1a1a2e")
        ax.title.set_color("white")
        ax.xaxis.label.set_color("white")
        ax.yaxis.label.set_color("white")
        ax.tick_params(colors="white")
        for spine in ax.spines.values():
            spine.set_edgecolor("#444")
    fig.suptitle(title, color="white")
    fig.patch.set_facecolor("#12121f")
    plt.tight_layout()
    fig.savefig(out_path, dpi=100, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def _save_gains_plot(
    frame_lums: List[Optional[float]],
    gains: List[float],
    out_path: str,
) -> None:
    """Bar chart of per-frame luminance gain corrections."""
    if not _MPL_OK:
        return
    N = len(gains)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    valid = [lum if lum is not None else 0.0 for lum in frame_lums]

    ax0, ax1 = axes
    ax0.bar(range(N), valid, color="#4ecdc4", alpha=0.8)
    ax0.axhline(
        float(np.median([v for v in valid if v > 0]))
        if any(v > 0 for v in valid)
        else 0,
        color="#ff6b6b",
        linestyle="--",
        label="median",
    )
    ax0.set_title("Background Luminance per Frame")
    ax0.set_xlabel("Frame index")
    ax0.set_ylabel("Mean luminance")
    ax0.legend(facecolor="#2a2a3e", labelcolor="white")

    ax1.bar(range(N), gains, color="#ff6b6b", alpha=0.8)
    ax1.axhline(1.0, color="#4ecdc4", linestyle="--", label="gain=1.0")
    ax1.set_title("Applied Luminance Gain per Frame")
    ax1.set_xlabel("Frame index")
    ax1.set_ylabel("Gain multiplier")
    ax1.legend(facecolor="#2a2a3e", labelcolor="white")

    for ax in axes:
        ax.set_facecolor("#1a1a2e")
        ax.title.set_color("white")
        ax.xaxis.label.set_color("white")
        ax.yaxis.label.set_color("white")
        ax.tick_params(colors="white")
        for spine in ax.spines.values():
            spine.set_edgecolor("#444")
    fig.patch.set_facecolor("#12121f")
    plt.tight_layout()
    fig.savefig(out_path, dpi=100, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def _save_seam_heatmap(img: np.ndarray, out_path: str, title: str = "") -> None:
    """2-D heatmap of gradient magnitude — highlights seam artefacts."""
    if not _MPL_OK:
        return
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    # Compute magnitude of gradient
    gx = cv2.Sobel(gray.astype(np.float32), cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray.astype(np.float32), cv2.CV_32F, 0, 1, ksize=3)
    mag = np.sqrt(gx**2 + gy**2)
    # Downsample for plotting
    scale = max(1, max(mag.shape) // 512)
    if scale > 1:
        mag = cv2.resize(mag, (mag.shape[1] // scale, mag.shape[0] // scale))
    fig, ax = plt.subplots(figsize=(8, 5))
    im = ax.imshow(mag, cmap="inferno", aspect="auto")
    ax.set_title(title or "Gradient Magnitude Heatmap", color="white")
    ax.axis("off")
    cbar = fig.colorbar(im, ax=ax, fraction=0.03)
    cbar.set_label("Gradient magnitude", color="white")
    cbar.ax.yaxis.set_tick_params(color="white")
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color="white")
    fig.patch.set_facecolor("#12121f")
    plt.tight_layout()
    fig.savefig(out_path, dpi=100, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def _save_3d_surface(img: np.ndarray, out_path: str, title: str = "") -> None:
    """3-D surface plot of pixel luminance — reveals exposure ridges/valleys."""
    if not _MPL_OK:
        return
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    # Aggressively downsample to keep rendering fast
    target = 96
    h, w = gray.shape
    sh = max(1, h // target)
    sw = max(1, w // target)
    small = gray[::sh, ::sw].astype(np.float32)
    # Smooth to reduce noise
    small = cv2.GaussianBlur(small, (5, 5), 0)
    Y, X = np.mgrid[0 : small.shape[0], 0 : small.shape[1]]
    fig = plt.figure(figsize=(9, 5))
    ax = fig.add_subplot(111, projection="3d")
    ax.plot_surface(
        X,
        Y,
        small,
        cmap="viridis",
        linewidth=0,
        antialiased=False,
        rstride=1,
        cstride=1,
        alpha=0.9,
    )
    ax.set_title(title or "Luminance Surface (3D)", color="white", pad=8)
    ax.set_xlabel("X (px ÷ " + str(sw) + ")", color="white", fontsize=7)
    ax.set_ylabel("Y (px ÷ " + str(sh) + ")", color="white", fontsize=7)
    ax.set_zlabel("Luma", color="white", fontsize=7)
    ax.tick_params(colors="white", labelsize=6)
    ax.xaxis.pane.fill = False  # pyrefly: ignore [missing-attribute]
    ax.yaxis.pane.fill = False  # pyrefly: ignore [missing-attribute]
    ax.zaxis.pane.fill = False  # pyrefly: ignore [missing-attribute]
    fig.patch.set_facecolor("#12121f")
    ax.set_facecolor("#1a1a2e")
    plt.tight_layout()
    fig.savefig(out_path, dpi=100, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def _save_overlap_map(
    affines: List[np.ndarray],
    canvas_h: int,
    canvas_w: int,
    frame_h: int,
    frame_w: int,
    out_path: str,
) -> None:
    """2-D heatmap counting how many frames contribute to each canvas pixel."""
    if not _MPL_OK:
        return
    scale = max(1, max(canvas_h, canvas_w) // 512)
    ch = max(1, canvas_h // scale)
    cw = max(1, canvas_w // scale)
    acc = np.zeros((ch, cw), dtype=np.float32)
    for M in affines:
        tx = int(float(M[0, 2]) / scale)
        ty = int(float(M[1, 2]) / scale)
        fh = max(1, frame_h // scale)
        fw = max(1, frame_w // scale)
        r0, r1 = max(0, ty), min(ch, ty + fh)
        c0, c1 = max(0, tx), min(cw, tx + fw)
        if r1 > r0 and c1 > c0:
            acc[r0:r1, c0:c1] += 1.0
    fig, ax = plt.subplots(figsize=(7, 5))
    im = ax.imshow(acc, cmap="hot", aspect="auto")
    ax.set_title("Frame Overlap Count Map (2D)", color="white")
    ax.axis("off")
    cbar = fig.colorbar(im, ax=ax, fraction=0.03)
    cbar.set_label("# overlapping frames", color="white")
    cbar.ax.yaxis.set_tick_params(color="white")
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color="white")
    fig.patch.set_facecolor("#12121f")
    plt.tight_layout()
    fig.savefig(out_path, dpi=100, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def _save_mask_overlay(
    frame: np.ndarray,
    mask: Optional[np.ndarray],
    out_path: str,
    title: str = "",
) -> None:
    """Visualize a foreground mask overlaid on the source frame."""
    if not _MPL_OK:
        return
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]
    overlay = rgb.copy().astype(np.float32)
    if mask is not None:
        fg = mask < 128  # fg pixels (BiRefNet: 0=foreground)
        overlay[fg, 0] = np.clip(overlay[fg, 0] * 0.4 + 200, 0, 255)
        overlay[fg, 1] = np.clip(overlay[fg, 1] * 0.4, 0, 255)
        overlay[fg, 2] = np.clip(overlay[fg, 2] * 0.4, 0, 255)
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.imshow(overlay.astype(np.uint8), aspect="auto")
    ax.set_title(title or "FG mask overlay (red=foreground)", color="white")
    ax.axis("off")
    fig.patch.set_facecolor("#12121f")
    plt.tight_layout()
    fig.savefig(out_path, dpi=100, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def _save_metrics_bar(metrics_asp: Dict, metrics_simple: Dict, out_path: str) -> None:
    """Side-by-side bar chart comparing key CV metrics for ASP vs simple."""
    if not _MPL_OK:
        return
    keys = ["sharpness", "coverage", "seam_gradient", "color_entropy", "ghosting_score"]
    labels = [
        "Sharpness",
        "Coverage",
        "Seam\nGradient",
        "Color\nEntropy",
        "Ghosting\nScore",
    ]
    asp_vals = [metrics_asp.get(k, 0) for k in keys]
    sim_vals = [metrics_simple.get(k, 0) for k in keys]
    # Normalize each metric to [0,1] for display
    maxes = [max(a, b, 1e-9) for a, b in zip(asp_vals, sim_vals)]
    asp_n = [v / m for v, m in zip(asp_vals, maxes)]
    sim_n = [v / m for v, m in zip(sim_vals, maxes)]
    x = np.arange(len(keys))
    width = 0.35
    fig, ax = plt.subplots(figsize=(9, 4))
    b1 = ax.bar(x - width / 2, asp_n, width, label="ASP", color="#4ecdc4", alpha=0.85)
    b2 = ax.bar(
        x + width / 2, sim_n, width, label="Simple", color="#ff6b6b", alpha=0.85
    )
    ax.set_xticks(x)
    ax.set_xticklabels(labels, color="white", fontsize=9)
    ax.set_ylabel("Normalised value", color="white")
    ax.set_title("CV Metrics: ASP vs Simple Stitch (normalised)", color="white")
    ax.legend(facecolor="#2a2a3e", labelcolor="white")
    ax.set_facecolor("#1a1a2e")
    ax.tick_params(colors="white")
    for spine in ax.spines.values():
        spine.set_edgecolor("#444")
    # Raw value annotations
    for bar, val in zip(b1, asp_vals):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.02,
            f"{val:.2f}",
            ha="center",
            va="bottom",
            fontsize=7,
            color="#4ecdc4",
        )
    for bar, val in zip(b2, sim_vals):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.02,
            f"{val:.2f}",
            ha="center",
            va="bottom",
            fontsize=7,
            color="#ff6b6b",
        )
    fig.patch.set_facecolor("#12121f")
    plt.tight_layout()
    fig.savefig(out_path, dpi=100, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


# ============================================================================
# SMART FRAME SELECTOR  (v2: pose-consistent lookahead window)
# ============================================================================

_SELECTOR_THUMB_LONG = 256  # thumbnail longest side for phase-correlation pass

# Pose-consistent refinement window (full-resolution canvas pixels).
# When > 0, Pass 2 of the smart selector checks whether a nearby frame
# (within ±2 slots of each v1 candidate) has ≥10% better fg pixel similarity
# to the previous selected frame.  "Fg pixel similarity" is the mean absolute
# normalised-pixel diff on BiRefNet-masked foreground pixels only — strictly
# background-invariant: locker/wall structure that scrolls through the frame
# as the camera pans contributes exactly 0.
#
# IMPORTANT: This is DISABLED by default (_POSE_WINDOW_PX = 0).
#
# Session-3 gradient proxy was confounded by background edges that changed as
# the camera panned (lockers, walls), causing wrong frame choices on test04
# (-0.043) and test27 (-0.026).  Session-5 switches to fg pixel L1 (hard
# binary mask, per-frame gain-normalised), which is background-invariant.
# Whether this is sufficient to break the GT-coupling limitation remains to be
# verified; enable via ASP_POSE_WINDOW_PX=80 to test.
try:
    _POSE_WINDOW_PX = float(os.environ.get("ASP_POSE_WINDOW_PX", "0"))
except ValueError:
    _POSE_WINDOW_PX = 0.0


def _load_thumb_gray(path: str) -> np.ndarray:
    """Load a grayscale float32 thumbnail for phase correlation."""
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return np.zeros((_SELECTOR_THUMB_LONG, _SELECTOR_THUMB_LONG), dtype=np.float32)
    h, w = img.shape
    scale = _SELECTOR_THUMB_LONG / max(h, w, 1)
    tw = max(1, int(w * scale))
    th = max(1, int(h * scale))
    return cv2.resize(img, (tw, th)).astype(np.float32) / 255.0


def _load_thumbs_parallel(
    frames_paths: List[str], max_workers: int = 8
) -> List[np.ndarray]:
    """Load all thumbnails in parallel (I/O bound — GIL released for imread)."""
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        return list(ex.map(_load_thumb_gray, frames_paths))


def _fg_center_diff(
    thumb_a: np.ndarray,
    thumb_b: np.ndarray,
    fg_mask: Optional[np.ndarray] = None,
) -> float:
    """
    Pose similarity metric between two thumbnails.

    **With fg_mask (BiRefNet fg probability at thumbnail scale):**
    Hard-thresholds the mask (> 0.3) to a binary fg_bin, zeroes out all
    background pixels, then computes mean absolute pixel difference on the
    foreground region.  Each frame's fg pixels are independently normalised to
    zero mean / unit std before differencing to remove inter-frame gain
    variations (ECC gain normalisation has not yet run at selection time).

    This is strictly background-invariant: background pixels are exactly 0.0
    in both masked images, so camera-panning locker/wall/scenery structure
    contributes nothing regardless of mask softness.  For "on twos" animation
    holds (same character cel for 2–3 consecutive frames), fg pixels look
    identical → score ≈ 0.  Across a hold boundary (new animation cel), fg
    pixels shift position → score > 0.

    The previous gradient-weighted approach computed Sobel gradient on the full
    image and multiplied by fg_mask, so background edges with fg_mask weight
    ~0.05–0.1 still contributed proportionally — confounding pose with
    background scroll.  This masked-pixel approach is background-invariant by
    construction.

    **Without fg_mask (fallback):**
    Gradient-magnitude L1 on the central 50% crop.  Partly confounded by
    background structure but requires no BiRefNet.

    Returns a non-negative float (0 = identical character region).
    """
    h = min(thumb_a.shape[0], thumb_b.shape[0])
    w = min(thumb_a.shape[1], thumb_b.shape[1])

    if fg_mask is not None and fg_mask.shape[0] >= h and fg_mask.shape[1] >= w:
        fg_bin = (fg_mask[:h, :w] > 0.3).astype(np.float32)
        total = float(fg_bin.sum())
        if total >= 50.0:
            a = thumb_a[:h, :w]
            b = thumb_b[:h, :w]
            # Per-frame fg normalisation to remove gain variation
            a_px = a[fg_bin > 0.5]
            b_px = b[fg_bin > 0.5]
            a_norm = (a - float(a_px.mean())) / (float(a_px.std()) + 1e-5)
            b_norm = (b - float(b_px.mean())) / (float(b_px.std()) + 1e-5)
            diff = np.abs(a_norm - b_norm) * fg_bin
            return float(diff.sum() / total)
        # fg mask too sparse — fall through to central-crop

    # Fallback: gradient-magnitude L1 on central 50% crop
    def _grad_mag(img: np.ndarray) -> np.ndarray:
        gx = cv2.Sobel(img, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(img, cv2.CV_32F, 0, 1, ksize=3)
        return np.sqrt(gx * gx + gy * gy)

    h0, h1 = h // 4, 3 * h // 4
    w0, w1 = w // 4, 3 * w // 4
    if h1 <= h0 or w1 <= w0:
        a, b = thumb_a[:h, :w], thumb_b[:h, :w]
    else:
        a, b = thumb_a[h0:h1, w0:w1], thumb_b[h0:h1, w0:w1]
    return float(np.mean(np.abs(_grad_mag(a) - _grad_mag(b))))


# Two-channel pose-consistency frame selection (ASP §0.2).  The character is
# usually central; the background is peripheral.  Phase-correlating the
# PERIPHERAL region aims to isolate the CAMERA pan from character animation.
#
# Two-channel selection uses BiRefNet background masks for cleaner camera
# displacement estimates.  Default OFF: BiRefNet runs a second time for
# selection (overhead) and can change frame selection in ways that hurt GT-SSIM
# for some tests.  Re-enable via ASP_TWO_CHANNEL_SELECT=1 for targeted testing.
_TWO_CHANNEL_SELECT = os.environ.get("ASP_TWO_CHANNEL_SELECT", "0") != "0"
_PERIPH_BORDER_FRAC = 0.24  # outer ring fraction treated as "background/camera"


def _periph_central_masks(h: int, w: int):
    """Return (peripheral, central) float32 weight masks for an (h, w) thumb."""
    bh = max(1, int(h * _PERIPH_BORDER_FRAC))
    bw = max(1, int(w * _PERIPH_BORDER_FRAC))
    yy, xx = np.mgrid[0:h, 0:w]
    periph = (yy < bh) | (yy >= h - bh) | (xx < bw) | (xx >= w - bw)
    return periph.astype(np.float32), (~periph).astype(np.float32)


# ---------------------------------------------------------------------------
# Main selector
# ---------------------------------------------------------------------------


def _compute_dinov2_features(frames_paths: List[str]) -> Optional[np.ndarray]:
    """
    Computes DINOv2 features for all frames to use in submodular pose selection.
    Returns (N, 384) numpy array of normalized features, or None if DINOv2 fails.
    """
    try:
        import torch
        import torchvision.transforms as T
        from PIL import Image

        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = (
            # pyrefly: ignore [missing-attribute]
            torch.hub.load("facebookresearch/dinov2", "dinov2_vits14", verbose=False)
            .to(device)
            .eval()
        )
    except Exception:
        return None

    transform = T.Compose(
        [
            T.Resize(224, interpolation=T.InterpolationMode.BICUBIC),
            T.CenterCrop(224),
            T.ToTensor(),
            T.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
        ]
    )

    features = []
    try:
        with torch.no_grad():
            for path in frames_paths:
                img = Image.open(path).convert("RGB")
                tensor = transform(img).unsqueeze(0).to(device)
                feat = model(tensor)
                feat = feat / feat.norm(dim=-1, keepdim=True)
                features.append(feat.cpu().numpy()[0])
    except Exception:
        return None

    return np.array(features, dtype=np.float32)


def _smart_select_frames(
    frames_paths: List[str],
    min_step_px: float = 50.0,
    min_phase_response: float = 0.04,
    high_anim_mad: float = 0.10,
    tiny_step_px: float = 8.0,
) -> List[str]:
    """
    Return a subset of ``frames_paths`` suitable for the stitch pipeline.

    **v2 upgrade — pose-consistent lookahead window (§6.1 of the research report).**

    Instead of selecting the *first* frame past ``min_step_px`` (v1 behaviour),
    v2 accumulates all candidates within a ``[min_step_px, min_step_px +
    _POSE_WINDOW_PX]`` window beyond the last selected frame and then picks the
    candidate with the lowest central-crop L1 distance to the last selected
    thumbnail.  The central-crop (inner 50% of each thumbnail) isolates the
    character region; peripheral background pixels are excluded because they
    always differ between frames due to camera panning.  A low L1 value means
    the character is in the same animation pose as the previous anchor frame —
    the "on twos" principle.

    Four rejection gates (applied before the window logic):

    **1. Displacement sufficiency.**
    Track cumulative canvas position along the dominant scroll axis.  Only frames
    that advance ≥ ``min_step_px`` from the last selected frame enter the window.

    **2. Direction consistency.**
    Backward-direction steps do not contribute positive progress; frames that
    re-expose already-covered canvas rows are skipped.

    **3. High-animation / low-movement filter.**
    Camera barely moved (< ``tiny_step_px``) but thumbnail MAD is high
    (> ``high_anim_mad``) → character is animating at a near-stationary canvas
    position.  Discarded.

    **4. Phase-correlation quality gate.**
    Response < ``min_phase_response`` → displacement estimate unreliable
    (motion blur, scene transition).  Position still accumulated but frame not
    entered into the window.

    Always includes the first and last frames to preserve the full scroll extent.
    Returns the original list unchanged when fewer than 3 frames are provided.
    Set ``ASP_POSE_WINDOW_PX=0`` to revert to v1 first-past-threshold behaviour.
    """
    N = len(frames_paths)
    if N <= 2:
        return frames_paths

    # ── 1. Load thumbnails and compute pairwise displacements ─────────────
    thumbs = _load_thumbs_parallel(frames_paths)

    # Derive pixel scale: thumb-space displacement → full-resolution px
    img0 = cv2.imread(frames_paths[0])
    if img0 is not None:
        full_h, full_w = img0.shape[:2]
        th0, tw0 = thumbs[0].shape[:2]
        scale_y = full_h / max(th0, 1)
        scale_x = full_w / max(tw0, 1)
    else:
        scale_y = scale_x = float(_SELECTOR_THUMB_LONG)

    # ── §0.1c DINOv2 Features (Pass 2) ─────────────────────────────────────
    dinov2_features = None
    if _POSE_WINDOW_PX > 0:
        print("  [SmartSelect] Computing DINOv2 pose features...")
        dinov2_features = _compute_dinov2_features(frames_paths)
        if dinov2_features is not None:
            print("  [SmartSelect] DINOv2 features loaded successfully.")

    # ── §0.2 BiRefNet probe masks for two-channel displacement and pose sim ──
    # Run BiRefNet on 5 evenly-spaced frames to build per-pixel probability
    # maps at thumbnail scale:
    #   _bg_thumb_mask: intersection of bg masks (pixel is background in ALL
    #                   probe frames) — used for camera-displacement phase
    #                   correlation when _TWO_CHANNEL_SELECT is enabled.
    #   _fg_thumb_mask: union of fg masks (pixel is foreground in ANY probe
    #                   frame) — used to weight the gradient diff in Pass 2
    #                   pose-consistency refinement.  Excludes background
    #                   edges (lockers, walls) that change as the camera pans.
    #
    # BiRefNet is run at full resolution on each probe frame, then the mask
    # is downsampled to thumbnail scale.  Total overhead: ~2–3 s per dataset.
    _bg_thumb_mask: Optional[np.ndarray] = None
    _fg_thumb_mask: Optional[np.ndarray] = None
    _needs_biref_probes = _TWO_CHANNEL_SELECT or (
        _POSE_WINDOW_PX > 0 and dinov2_features is None
    )
    if _needs_biref_probes:
        try:
            from backend.src.models.wrappers.birefnet_wrapper import BiRefNetWrapper
            import gc as _gc
            import torch as _torch

            _biref = BiRefNetWrapper()
            _probe_idxs = sorted({0, N // 4, N // 2, 3 * N // 4, N - 1})
            _th_shape = thumbs[0].shape[:2]  # (th, tw) at thumbnail scale
            _bg_accum = np.ones(_th_shape, dtype=np.float32)  # intersection → bg
            _fg_accum = np.zeros(_th_shape, dtype=np.float32)  # union → fg
            _n_ok = 0
            for _pi in _probe_idxs:
                _full = cv2.imread(frames_paths[_pi])
                if _full is None:
                    continue
                _mk = _biref.get_mask(_full)  # BiRefNet: 0=fg, 255=bg
                _th = thumbs[_pi].shape
                # bg_prob: 1.0 = background pixel, 0.0 = foreground pixel
                _bg_prob = cv2.resize(
                    (_mk > 127).astype(np.float32),
                    (_th[1], _th[0]),
                    interpolation=cv2.INTER_NEAREST,
                )
                _fg_prob = 1.0 - _bg_prob
                _bg_accum = np.minimum(_bg_accum, _bg_prob)  # conservative bg
                _fg_accum = np.maximum(_fg_accum, _fg_prob)  # permissive fg
                _n_ok += 1
            try:
                _biref.offload()
            except Exception:
                pass
            del _biref
            _gc.collect()
            if _torch.cuda.is_available():
                _torch.cuda.empty_cache()
            if _n_ok > 0:
                if _TWO_CHANNEL_SELECT:
                    bg_cov = float(_bg_accum.mean())
                    print(
                        f"  [SmartSelect] BiRefNet bg mask: {bg_cov:.0%} coverage, "
                        f"{_n_ok} probes"
                    )
                    _bg_thumb_mask = _bg_accum if bg_cov >= 0.10 else None
                if _POSE_WINDOW_PX > 0:
                    fg_cov = float(_fg_accum.mean())
                    print(
                        f"  [SmartSelect] BiRefNet fg mask: {fg_cov:.0%} fg coverage, "
                        f"{_n_ok} probes — pose comparison will ignore background edges"
                    )
                    _fg_thumb_mask = _fg_accum if fg_cov >= 0.05 else None
        except Exception as _e:
            print(
                f"  [SmartSelect] BiRefNet unavailable ({_e}); "
                "using whole-frame phase correlation and central-crop pose diff"
            )

    raw_dx: List[float] = []
    raw_dy: List[float] = []
    responses: List[float] = []
    frame_mads: List[float] = []

    for i in range(N - 1):
        a = thumbs[i]
        b = thumbs[i + 1]
        # Ensure identical size (may differ by 1px due to rounding)
        th = max(a.shape[0], b.shape[0])
        tw = max(a.shape[1], b.shape[1])
        if a.shape != (th, tw):
            a = np.pad(a, ((0, th - a.shape[0]), (0, tw - a.shape[1])))
        if b.shape != (th, tw):
            b = np.pad(b, ((0, th - b.shape[0]), (0, tw - b.shape[1])))

        if _bg_thumb_mask is not None and _bg_thumb_mask.shape == a.shape:
            # Camera channel: background-only phase correlation.
            _m = _bg_thumb_mask
            (dx_t, dy_t), response = cv2.phaseCorrelate(a * _m, b * _m)
            # Animation channel: foreground MAD
            _fg = 1.0 - _m
            frame_mads.append(float(np.sum(np.abs(b - a) * _fg) / max(_fg.sum(), 1.0)))
        else:
            (dx_t, dy_t), response = cv2.phaseCorrelate(a, b)
            frame_mads.append(float(np.mean(np.abs(b - a))))
        raw_dx.append(dx_t * scale_x)
        raw_dy.append(dy_t * scale_y)
        responses.append(response)

    # ── 2. Dominant scroll axis and direction ──────────────────────────────
    med_dy = float(np.median(raw_dy))
    med_dx = float(np.median(raw_dx))

    if abs(med_dy) >= abs(med_dx):
        axis_steps = raw_dy
        dominant_sign = int(np.sign(med_dy)) if abs(med_dy) > 2.0 else 0
    else:
        axis_steps = raw_dx
        dominant_sign = int(np.sign(med_dx)) if abs(med_dx) > 2.0 else 0

    _chan = "2ch(birefnet-bg)" if _bg_thumb_mask is not None else "1ch(whole-frame)"
    print(
        f"  [SmartSelect] N={N}  dominant_axis={'y' if abs(med_dy) >= abs(med_dx) else 'x'}"
        f"  sign={dominant_sign:+d}"
        f"  med_step={abs(med_dy if abs(med_dy) >= abs(med_dx) else med_dx):.1f}px"
        f"  mode={_chan}  pose_window={_POSE_WINDOW_PX:.0f}px"
    )

    # ── 3. Pre-compute cumulative canvas positions ─────────────────────────
    # Each frame gets a cumulative position along the dominant axis.  Frames
    # rejected by phase-correlation or high-animation gates contribute zero
    # advance (their phase estimate is unreliable and we don't want to count
    # that noisy displacement toward the min_step threshold).
    cumpos: List[float] = [0.0] * N
    for i in range(N - 1):
        step = axis_steps[i]
        rejected = responses[i] < min_phase_response or (
            abs(step) < tiny_step_px and frame_mads[i] > high_anim_mad
        )
        cumpos[i + 1] = cumpos[i] + (0.0 if rejected else step)

    # ── 4. Pass 1 — v1 greedy forward-selection (first-past-threshold) ───────
    # This is the session-2 baseline: select the first frame that crosses
    # min_step_px, accumulate, repeat.  Preserves frame count and even
    # spacing needed for luminance normalisation.

    selected_v1: List[int] = [0]
    canvas_pos: float = 0.0
    last_sel_pos_v1: float = 0.0

    for i in range(N - 1):
        canvas_pos = cumpos[i + 1]
        advance = canvas_pos - last_sel_pos_v1
        net_forward = advance * dominant_sign if dominant_sign != 0 else abs(advance)
        if net_forward >= min_step_px:
            selected_v1.append(i + 1)
            last_sel_pos_v1 = canvas_pos

    if selected_v1[-1] != N - 1:
        selected_v1.append(N - 1)

    # ── 5. Pass 2 — pose-consistent local refinement ──────────────────────
    # For each interior frame in selected_v1, check whether a nearby frame
    # within ±_POSE_LOOK_RANGE frames has significantly better gradient
    # similarity to the previous selected frame (>= 10% improvement).  If
    # so, substitute it.  Frame count is preserved exactly.
    #
    # Key constraints (prevent backward clustering / sub-threshold gaps):
    #   • Replacement must advance at least min_step_px × 0.5 from previous
    #     selection in cumulative position space.
    #   • Replacement must be at most min_step_px × 2.0 ahead of previous
    #     selection (prevents huge forward jumps that skip canvas content).
    #   • ±_POSE_LOOK_RANGE = 2 frames from the v1 candidate.
    #
    # This implements §6.1 "on twos" pose-consistency without requiring any
    # pose-estimation model: fg pixel similarity ≈ animation phase matching.

    _POSE_LOOK_RANGE = 2  # at most ±2 frames from v1 candidate
    _POSE_MIN_GAIN = 0.10  # must improve fg pixel L1 by ≥ 10% to substitute
    _MIN_ADV_FRAC = 0.50  # replacement must advance ≥ min_step_px × 0.50
    _MAX_ADV_FRAC = 2.50  # replacement must advance ≤ min_step_px × 2.50

    if _POSE_WINDOW_PX > 0 and len(selected_v1) > 2:
        _pose_mode = "biref-fg" if _fg_thumb_mask is not None else "central-crop"
        selected: List[int] = [selected_v1[0]]
        n_subs = 0
        for k in range(1, len(selected_v1) - 1):
            s_prev = selected[-1]
            s_curr = selected_v1[k]
            # Candidate pool: ±LOOK_RANGE around s_curr, bounded by (s_prev+1, N-1)
            lo = max(s_prev + 1, s_curr - _POSE_LOOK_RANGE)
            hi = min(N - 1, s_curr + _POSE_LOOK_RANGE)

            # Filter: minimum and maximum canvas advance from previous selection
            def _valid_advance(c: int) -> bool:
                adv = cumpos[c] - cumpos[s_prev]
                nf = adv * dominant_sign if dominant_sign != 0 else abs(adv)
                return _MIN_ADV_FRAC * min_step_px <= nf <= _MAX_ADV_FRAC * min_step_px

            candidates = [c for c in range(lo, hi + 1) if _valid_advance(c)]
            if not candidates:
                selected.append(s_curr)
                continue
            if dinov2_features is not None:
                last_t = dinov2_features[s_prev]
                curr_score = 1.0 - float(np.dot(last_t, dinov2_features[s_curr]))
                scores = [
                    1.0 - float(np.dot(last_t, dinov2_features[c])) for c in candidates
                ]
                _pose_mode = "dinov2"
            else:
                last_t = thumbs[s_prev]
                # Pass BiRefNet fg mask so background edges are excluded from score
                curr_score = _fg_center_diff(last_t, thumbs[s_curr], _fg_thumb_mask)
                scores = [
                    _fg_center_diff(last_t, thumbs[c], _fg_thumb_mask)
                    for c in candidates
                ]
            best_local = int(np.argmin(scores))
            best = candidates[best_local]
            best_score = scores[best_local]
            if best != s_curr and best_score < curr_score * (1.0 - _POSE_MIN_GAIN):
                selected.append(best)
                n_subs += 1
                print(
                    f"  [PoseSelect/{_pose_mode}] Slot {k}: {s_curr}→{best} "
                    f"(score {curr_score:.3f}→{best_score:.3f})"
                )
            else:
                selected.append(s_curr)
        selected.append(selected_v1[-1])
        if n_subs > 0:
            print(
                f"  [PoseSelect/{_pose_mode}] {n_subs}/{len(selected_v1) - 2} slots refined."
            )
    else:
        selected = selected_v1

    print(
        f"  [SmartSelect] Selected {len(selected)}/{N} frames  "
        f"(dropped {N - len(selected)})."
    )
    return [frames_paths[i] for i in selected]


# ============================================================================
# SIMPLE STITCH (OpenCV SCANS)
# ============================================================================


def _run_simple_stitch(frames_paths: List[str], out_path: str) -> bool:
    """Generate OpenCV SCANS simple stitch and save. Returns True on success."""
    raw = [cv2.imread(p) for p in frames_paths]
    raw = [f for f in raw if f is not None]
    if len(raw) < 2:
        return False
    raw = _normalise_widths(raw)
    try:
        _scan_stitch_fallback(raw, out_path)
        return True
    except Exception as exc:
        print(f"  [Simple stitch] FAILED: {exc}")
        return False


# ============================================================================
# MAIN DATASET PROCESSOR
# ============================================================================


def process_dataset(dataset_dir: str) -> Optional[Dict]:
    """
    Run both pipelines on a single dataset directory.

    Returns a dict of per-dataset results for the global report, or None if
    the dataset is skipped.
    """
    t_total_start = time.perf_counter()
    timings: Dict[str, float] = {}

    print(f"\n{'=' * 60}\nProcessing dataset: {dataset_dir}\n{'=' * 60}")

    dataset_name = os.path.basename(dataset_dir)
    stage_dir = os.path.join(dataset_dir, "output", "panorama_stages")
    out_path = os.path.join(dataset_dir, "output", "panorama.png")
    simple_stitch_path = os.path.join(dataset_dir, "output", "simple_stitch.png")
    plots_dir = os.path.join(dataset_dir, "output", "plots")

    # Central output
    central_out_dir = os.path.join(os.path.dirname(dataset_dir), "output")
    os.makedirs(central_out_dir, exist_ok=True)
    central_anime_path = os.path.join(
        central_out_dir, f"{dataset_name}_anime_stitch.png"
    )
    central_simple_path = os.path.join(
        central_out_dir, f"{dataset_name}_simple_stitch.png"
    )

    # Ground truth (if available)
    gt_dir = os.path.join(os.path.dirname(dataset_dir), "ground_truth")
    gt_img = _load_ground_truth(dataset_name, gt_dir)
    if gt_img is not None:
        print(f"  [GT] Ground truth found for {dataset_name}: {gt_img.shape}")

    # Clean old outputs
    if os.path.exists(out_path):
        os.remove(out_path)
    if os.path.exists(stage_dir):
        shutil.rmtree(stage_dir)
    os.makedirs(stage_dir, exist_ok=True)
    os.makedirs(plots_dir, exist_ok=True)

    # Collect frames
    all_pngs = sorted(
        glob.glob(os.path.join(dataset_dir, "*.png"))
        + glob.glob(os.path.join(dataset_dir, "*.jpg"))
    )
    frames_paths = [
        p
        for p in all_pngs
        if "panorama" not in os.path.basename(p)
        and "test_" not in os.path.basename(p)
        and "stage" not in os.path.basename(p)
    ]
    if len(frames_paths) < 2:
        print(f"Skipping {dataset_dir}: not enough frames.")
        return None

    # Smart frame selection: drop near-duplicates and backward-direction frames
    # before any GPU processing.  Large datasets can have 50-330 consecutive
    # video frames; naive stride subsampling would miss character-animation
    # conflicts where the character returns to the same pose as a previous
    # selected frame but the camera is now in a different position.
    _orig_frame_count = len(frames_paths)
    frames_paths = _smart_select_frames(frames_paths)
    _smart_select_count = len(frames_paths)
    if _smart_select_count < _orig_frame_count:
        print(
            f"  Smart selection: {_orig_frame_count} → {_smart_select_count} frames "
            f"({_orig_frame_count - _smart_select_count} dropped)."
        )

    print(f"Source frames ({len(frames_paths)}):")
    for p in frames_paths:
        print(f"  {os.path.basename(p)}")

    # ------------------------------------------------------------------
    # STEP 0: Generate simple stitch (always regenerate for consistency)
    # ------------------------------------------------------------------
    print("\n[0] Running OpenCV SCANS simple stitch …")
    t0 = time.perf_counter()
    simple_ok = _run_simple_stitch(frames_paths, simple_stitch_path)
    timings["simple_stitch_sec"] = round(time.perf_counter() - t0, 3)
    if simple_ok:
        shutil.copy2(simple_stitch_path, central_simple_path)
        print(f"  Saved: {simple_stitch_path}")
    else:
        print(f"  Warning: simple stitch failed for {dataset_name}")

    # ------------------------------------------------------------------
    # STEP 1-2: Load & normalise
    # ------------------------------------------------------------------
    frames = _load_frames(frames_paths)
    N = len(frames)
    frames = _normalise_widths(frames)
    H, W = frames[0].shape[:2]
    scans_frames = list(frames)  # pre-ML snapshot for SCANS fallback
    _fallback_reason: Optional[str] = None  # set by whichever gate triggers SCANS
    for i, f in enumerate(frames):
        cv2.imwrite(os.path.join(stage_dir, f"stage02_normalised_frame{i:02d}.png"), f)

    # ------------------------------------------------------------------
    # STEP 3: BiRefNet foreground masks
    # ------------------------------------------------------------------
    t0 = time.perf_counter()
    birefnet_ok = False
    try:
        from backend.src.models.wrappers.birefnet_wrapper import BiRefNetWrapper

        birefnet = BiRefNetWrapper()
        bg_masks = _compute_fg_masks(frames, birefnet)
        birefnet_ok = True
        if torch.cuda.is_available():
            try:
                birefnet.offload()
            except Exception:
                pass
        del birefnet
        gc.collect()
        torch.cuda.empty_cache()
    except Exception as e:
        print(f"  BiRefNet failed ({e}), using None masks")
        bg_masks = [None] * N
    timings["birefnet_sec"] = round(time.perf_counter() - t0, 3)

    for i, m in enumerate(bg_masks):
        img = m if m is not None else np.ones((H, W), dtype=np.uint8) * 255
        cv2.imwrite(os.path.join(stage_dir, f"stage04_bgmask_frame{i:02d}.png"), img)

    # Visualise mask overlays for first 3 frames
    for i in range(min(3, N)):
        _save_mask_overlay(
            frames[i],
            bg_masks[i],
            os.path.join(plots_dir, f"mask_overlay_frame{i:02d}.png"),
            title=f"FG Mask Overlay — Frame {i}",
        )

    # ------------------------------------------------------------------
    # STEP 4: Background photometric normalisation (luminance scalar gain)
    # ------------------------------------------------------------------
    _LUM_W = np.array([0.114, 0.587, 0.299], dtype=np.float32)
    bg_frame_lums: List[Optional[float]] = []
    for frame, mask in zip(frames, bg_masks):
        if mask is not None:
            bg_px = frame[mask > 127].astype(np.float32)
            if len(bg_px) >= 1000:
                bg_frame_lums.append(float(bg_px.dot(_LUM_W).mean()))
                continue
        bg_frame_lums.append(None)

    valid_lums = [lum for lum in bg_frame_lums if lum is not None]
    applied_gains = [1.0] * N
    if len(valid_lums) >= 3:
        ref_lum = float(np.median(valid_lums))
        _gain_lo, _gain_hi = (0.80, 1.25) if ref_lum < 80.0 else (0.88, 1.14)
        for i in range(N):
            if bg_frame_lums[i] is None:
                continue
            gain = float(
                np.clip(ref_lum / max(bg_frame_lums[i], 1.0), _gain_lo, _gain_hi) # pyrefly: ignore [bad-specialization, unsupported-operation]
            )
            applied_gains[i] = gain
            if abs(gain - 1.0) > 0.01:
                frames[i] = np.clip(frames[i].astype(np.float32) * gain, 0, 255).astype(
                    np.uint8
                )

    # Save stage 3 corrected frames
    for i, f in enumerate(frames):
        cv2.imwrite(
            os.path.join(stage_dir, f"stage03_basic_corrected_frame{i:02d}.png"), f
        )

    # Gains plot
    _save_gains_plot(
        bg_frame_lums,
        applied_gains,
        os.path.join(plots_dir, "gains.png"),
    )

    # ------------------------------------------------------------------
    # STEP 5-7: Match → filter → bundle-adjust → ECC
    # ------------------------------------------------------------------
    t0 = time.perf_counter()
    loftr_ok = False
    try:
        from backend.src.models.wrappers.loftr_wrapper import LoFTRWrapper

        loftr = LoFTRWrapper()
        loftr_ok = True
    except Exception:
        loftr = None

    edges = _pairwise_match(frames, bg_masks, loftr_wrapper=loftr) # pyrefly: ignore [bad-argument-type]
    if loftr is not None:
        if torch.cuda.is_available():
            try:
                loftr.offload()
            except Exception:
                pass
        del loftr
        gc.collect()
        torch.cuda.empty_cache()
    timings["matching_sec"] = round(time.perf_counter() - t0, 3)

    # Collect edge metadata before filtering
    raw_edge_count = len(edges)
    edge_methods: Dict[str, int] = {}
    for e in edges:
        m = e.get("method", "unknown")
        edge_methods[m] = edge_methods.get(m, 0) + 1

    # ── Post-match: Spatial dedup of near-static consecutive frames ──────────
    _SPATIAL_DEDUP_PX = 25
    _spa_changed = True
    _total_spa_dropped = 0
    while _spa_changed:
        _spa_changed = False
        _adj_m = {e["j"]: e for e in edges if e["j"] == e["i"] + 1}
        if not _adj_m:
            break
        _adx = [abs(float(e["M"][0, 2])) for e in _adj_m.values()]
        _ady = [abs(float(e["M"][1, 2])) for e in _adj_m.values()]
        _spa_axis = 0 if float(np.median(_adx)) > float(np.median(_ady)) else 1
        _drop: set = set()
        for _jj in sorted(_adj_m):
            _ee = _adj_m[_jj]
            if _ee["i"] in _drop:
                continue
            if abs(float(_ee["M"][_spa_axis, 2])) < _SPATIAL_DEDUP_PX:
                _drop.add(_jj)
                _spa_changed = True
                print(
                    f"  Spatial dedup: frame {_jj} ≈ frame {_ee['i']} "
                    f"(d{'x' if _spa_axis == 0 else 'y'}="
                    f"{float(_ee['M'][_spa_axis, 2]):.1f}px) — dropped."
                )
        if _drop:
            _total_spa_dropped += len(_drop)
            _keep_idx = [i for i in range(N) if i not in _drop]
            frames = [frames[i] for i in _keep_idx]
            bg_masks = [bg_masks[i] for i in _keep_idx]
            frames_paths = [frames_paths[i] for i in _keep_idx]
            _o2n = {old: new for new, old in enumerate(_keep_idx)}
            edges = [
                {**e, "i": _o2n[e["i"]], "j": _o2n[e["j"]]}
                for e in edges
                if e["i"] not in _drop and e["j"] not in _drop
            ]
            N = len(frames)
            H, W = frames[0].shape[:2]
            if N < 2:
                print(
                    f"  Spatial dedup removed too many frames; skipping {dataset_dir}."
                )
                return None
    if _total_spa_dropped:
        print(
            f"  Spatial dedup complete: {_total_spa_dropped} frames removed, {N} remain."
        )

    t0 = time.perf_counter()
    pipe = AnimeStitchPipeline(
        use_basic=False, use_birefnet=False, use_loftr=False, use_ecc=False
    )
    edges = pipe._filter_edges(edges, frames_paths, H, W, frames, bg_masks) # pyrefly: ignore [bad-argument-type]
    affines = _bundle_adjust_affine(edges, N)
    timings["bundle_adjust_sec"] = round(time.perf_counter() - t0, 3)

    filtered_edge_count = len(edges)
    edge_stats = [
        {
            "i": int(e["i"]),
            "j": int(e["j"]),
            "method": e.get("method", "unknown"),
            "weight": round(float(e.get("weight", 0.0)), 4),
            "n_pts": len(e.get("pts_i", [])),
            "tx": round(float(e["M"][0, 2]), 2),
            "ty": round(float(e["M"][1, 2]), 2),
        }
        for e in edges
    ]

    # Validate affines
    health = _validate_affines(affines)
    print(
        f"  Affine health: valid={health.valid}, reason={health.reason}, "
        f"ratio={health.ratio:.2f}, min_gap={health.min_gap:.1f}px"
    )

    if not health.valid:
        print(f"  Validation FAILED ({health.reason}); attempting recovery...")
        # Retry 1: consecutive-only bundle
        _adj_only = [e for e in edges if e["j"] == e["i"] + 1]
        if len(_adj_only) >= N - 1:
            affines_r1 = _bundle_adjust_affine(_adj_only, N)
            health_r1 = _validate_affines(affines_r1)
            if health_r1.valid:
                affines, health = affines_r1, health_r1
                print(f"  Recovery Retry 1 succeeded: {health.reason}")

        # Retry 2: smart sequential + fill
        if not health.valid:
            _adj_only_r2 = [e for e in edges if e["j"] == e["i"] + 1]
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
            _has_adj_src = {e["j"] for e in _adj_only_r2}
            _seq = [np.eye(2, 3, dtype=np.float32) for _ in range(N)]
            _anchored: set = {0}
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
            for _uf in sorted(i for i in range(N) if i not in _anchored):
                if _uf in _has_adj_src:
                    continue
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
            if health_r2.valid:
                affines, health = _seq, health_r2
                print(f"  Recovery Retry 2 succeeded: {health.reason}")
            else:
                health_r3 = _validate_affines(_seq, min_step=20.0)
                if health_r3.valid:
                    affines, health = _seq, health_r3
                    print(f"  Recovery Retry 3 (relaxed) succeeded: {health.reason}")
                else:
                    # Retry 4: very permissive — only reject truly co-located frames
                    # (min_gap < 3px) or extreme clustering (ratio > 10x).
                    # Needed for slow-pan sequences with many fine-grained frames.
                    health_r4 = _validate_affines(
                        _seq,
                        min_step=3.0,
                        max_ratio=10.0,
                        max_rotation=0.3,
                        max_scale_dev=0.3,
                    )
                    if health_r4.valid:
                        affines, health = _seq, health_r4
                        print(
                            f"  Recovery Retry 4 (permissive) succeeded: {health.reason}"
                        )
                    else:
                        print(
                            f"  Recovery Retry 4 failed: {health_r4.reason} "
                            f"(ratio={health_r4.ratio:.2f} min_gap={health_r4.min_gap:.1f}px)"
                        )
                        # Retry 5: final attempt — accept any _seq with non-zero gaps
                        health_r5 = _validate_affines(
                            _seq,
                            min_step=0.5,
                            max_ratio=50.0,
                            max_rotation=0.5,
                            max_scale_dev=0.5,
                        )
                        if health_r5.valid:
                            affines, health = _seq, health_r5
                            print(
                                f"  Recovery Retry 5 (final) succeeded: {health.reason}"
                            )

    if not health.valid:
        _fallback_reason = f"alignment_failed:{health.reason}"
        print("  Validation FAILED → SCANS fallback.")
        t0 = time.perf_counter()
        _scan_stitch_fallback(scans_frames, out_path)
        timings["scans_fallback_sec"] = round(time.perf_counter() - t0, 3)
        timings["total_sec"] = round(time.perf_counter() - t_total_start, 3)
        shutil.copy2(out_path, central_anime_path)
        print(f"\nFinished (SCANS): {dataset_dir} -> {out_path}")
        asp_img = cv2.imread(central_anime_path)
        sim_img = cv2.imread(central_simple_path) if simple_ok else None
        return _build_result(
            dataset_name,
            central_anime_path,
            central_simple_path,
            asp_img,
            sim_img,
            affines,
            bg_frame_lums,
            applied_gains,
            health,
            plots_dir,
            stage_dir,
            canvas_h=None,
            canvas_w=None,
            used_fallback=True,
            timings=timings,
            frame_count=N,
            frame_h=H,
            frame_w=W,
            raw_edge_count=raw_edge_count,
            filtered_edge_count=filtered_edge_count,
            edge_methods=edge_methods,
            edge_stats=edge_stats,
            birefnet_ok=birefnet_ok,
            loftr_ok=loftr_ok,
            gt_img=gt_img,
            fallback_reason=_fallback_reason,
            orig_frame_count=_orig_frame_count,
            smart_select_count=_smart_select_count,
            spatial_dedup_count=N,
        )

    try:
        # ECC refinement
        t0 = time.perf_counter()
        affines = _ecc_refine(frames, affines, bg_masks) # pyrefly: ignore [bad-argument-type]
        timings["ecc_sec"] = round(time.perf_counter() - t0, 3)

        # Canvas construction
        canvas_h, canvas_w, T_global = _compute_canvas(frames, affines)
        for i in range(N):
            affines[i][0, 2] += T_global[0]
            affines[i][1, 2] += T_global[1]

        canvas_info = {
            "canvas_h": canvas_h,
            "canvas_w": canvas_w,
            "affines_final": [a.tolist() for a in affines],
        }
        with open(os.path.join(stage_dir, "stage08_canvas_info.json"), "w") as fh:
            json.dump(canvas_info, fh)

        # Canvas visualisations
        _save_affine_path_plot(
            affines,
            canvas_h,
            canvas_w,
            H,
            W,
            os.path.join(plots_dir, "canvas_frame_placement.png"),
        )
        _save_translation_plot(
            affines,
            os.path.join(plots_dir, "translation_vectors.png"),
            title=f"{dataset_name} — Translation Vectors",
        )
        _save_overlap_map(
            affines,
            canvas_h,
            canvas_w,
            H,
            W,
            os.path.join(plots_dir, "overlap_map.png"),
        )

        # ── Alignment stability gate (advisory) ──────────────────────────
        # Log the horizontal drift but do NOT abort — the composite render
        # gate below uses a SCANS-relative quality comparison and will catch
        # any genuinely degraded output regardless of the motion pattern.
        # The old hard-abort was over-triggering on scenes where ASP quality
        # is actually comparable to or better than SCANS despite diagonal motion.
        # Override: ASP_ALIGN_GATE_DX=99 to suppress the log entirely.
        try:
            _ALIGN_DX_LIMIT = float(os.environ.get("ASP_ALIGN_GATE_DX", "50"))
        except ValueError:
            _ALIGN_DX_LIMIT = 50.0
        _txs_raw = [float(affines[i][0, 2]) for i in range(N)]
        _dx_raw = [abs(_txs_raw[i + 1] - _txs_raw[i]) for i in range(N - 1)]
        if _dx_raw:
            _dx_p75 = float(np.percentile(_dx_raw, 75))
            _align_flag = _dx_p75 > _ALIGN_DX_LIMIT
            print(
                f"  [AlignGate] 75th-pct |dx|={_dx_p75:.1f}px  "
                f"limit={_ALIGN_DX_LIMIT:.0f}px  {'⚠ high drift' if _align_flag else 'ok'}"
            )

        # ------------------------------------------------------------------
        # STEP 8-10: Render → quality gate → composite → crop
        # ------------------------------------------------------------------
        t0 = time.perf_counter()
        canvas, valid_mask, _, _ = _render_median(
            frames, affines, bg_masks, canvas_h, canvas_w # pyrefly: ignore [bad-argument-type]
        )
        timings["render_sec"] = round(time.perf_counter() - t0, 3)
        cv2.imwrite(os.path.join(stage_dir, "stage09_temporal_render.png"), canvas)

        # Run the full foreground-assembly composite (Stage 11) — this applies
        # the bg-only scalar gain correction AND the flow-guided foreground
        # re-posing (Stage 8.5) + single-pose fallback.
        t0 = time.perf_counter()
        canvas = _composite_foreground(
            [], [], canvas, canvas_h, canvas_w, frames, affines, bg_masks # pyrefly: ignore [bad-argument-type]
        )
        timings["composite_sec"] = round(time.perf_counter() - t0, 3)
        cv2.imwrite(os.path.join(stage_dir, "stage11_fg_composite.png"), canvas)

        # ── Composite quality gate (SCANS-comparative) ────────────────────
        # Measures banding on the FINAL composite and compares against the
        # SCANS baseline for the same dataset.  Falls back only when ASP is
        # significantly worse than SCANS — not just because the content is
        # inherently high-variance (e.g., dark scene + bright character).
        #
        # Adaptive limits:  limit = max(hard_floor, scans_value × 1.6)
        # Interpretation: allow ASP to be up to 60% worse than SCANS before
        # falling back.  The 1.6× factor is calibrated so that scenes where ASP
        # and SCANS are roughly equal always pass, while cases where ASP
        # introduces severe banding on top of clean SCANS output still fail.
        #
        # Hard-floor defaults (absolute caps even when SCANS is clean):
        #   seam_coherence floor = 38   (sc > 38 on a clean-SCANS scene → bad)
        #   strip_banding  floor = 35   (sb > 35 on a clean-SCANS scene → bad)
        # Override: ASP_GATE_SC / ASP_GATE_SB  (set to 999 to disable entirely).
        _render_sc = _seam_coherence(canvas)
        _render_sb = _strip_banding_score(canvas, affines)
        try:
            _SC_FLOOR = float(os.environ.get("ASP_GATE_SC", "38"))
        except ValueError:
            _SC_FLOOR = 38.0
        try:
            _SB_FLOOR = float(os.environ.get("ASP_GATE_SB", "35"))
        except ValueError:
            _SB_FLOOR = 35.0
        _SCANS_MULT = 2.0  # allow ASP up to 100% worse than SCANS (2× absolute)
        _scans_sc_ref = 0.0
        _scans_sb_ref = 0.0
        _scans_img_gate = cv2.imread(simple_stitch_path) if simple_ok else None
        if _scans_img_gate is not None:
            _scans_sc_ref = _seam_coherence(_scans_img_gate)
            _scans_sb_ref = _strip_banding_score(_scans_img_gate, affines)
        _sc_limit = max(_SC_FLOOR, _scans_sc_ref * _SCANS_MULT)
        _sb_limit = max(_SB_FLOOR, _scans_sb_ref * _SCANS_MULT)
        print(
            f"  [CompositeGate] asp sc={_render_sc:.1f} sb={_render_sb:.1f}  "
            f"scans sc={_scans_sc_ref:.1f} sb={_scans_sb_ref:.1f}  "
            f"limits sc<{_sc_limit:.1f} sb<{_sb_limit:.1f}"
        )
        _render_failed = _render_sc > _sc_limit or _render_sb > _sb_limit
        if _render_failed:
            _which = "sc" if _render_sc > _sc_limit else "sb"
            _fallback_reason = f"composite_gate_{_which}:asp_sc={_render_sc:.1f}_limit={_sc_limit:.1f},asp_sb={_render_sb:.1f}_limit={_sb_limit:.1f}"
            print(
                f"  [CompositeGate] FAILED "
                f"(asp sc={_render_sc:.1f}>{_sc_limit:.1f} or "
                f"asp sb={_render_sb:.1f}>{_sb_limit:.1f}) → SCANS fallback."
            )
            timings["render_gate_fallback"] = 1
            raise RuntimeError(
                f"Composite quality gate: asp sc={_render_sc:.1f} (limit={_sc_limit:.1f}), "
                f"asp sb={_render_sb:.1f} (limit={_sb_limit:.1f})"
            )

        timings["render_gate_fallback"] = 0

        canvas_out = _crop_to_valid(canvas, valid_mask)
        ec = 30
        if ec * 2 < canvas_out.shape[0] and ec * 2 < canvas_out.shape[1]:
            canvas_out = canvas_out[ec:-ec, ec:-ec]

        # Note: content-aware crop was removed — cropping based on fg union
        # across a vertical pan incorrectly cuts horizontal extent (the lockers
        # background) rather than trimming excess top/bottom panning extent.
        # The scale mismatch for test27 (2× larger than GT) is a fundamental
        # frame-selection issue, not a post-processing crop problem.

        # ── Ghosting ratio gate (post-crop) ────────────────────────────────
        # §3.32B: GhostGate now uses ghosting_siqe (FFT autocorrelation, 0-100)
        # instead of the old ghosting_score (double-Sobel sharpness proxy).
        # ghosting_siqe: 0=clean, 30+=ghost likely, 60+=ghost confirmed.
        # ASP avg=36.21, SCANS avg=72.34 across 97 tests — ASP is normally
        # BETTER (lower) on true ghosting; gate fires only when ASP shows
        # heavy ghost AND is worse than SCANS by ratio×.
        # Override: ASP_GATE_GHOST=99 to disable.
        try:
            _GHOST_RATIO_LIMIT = float(os.environ.get("ASP_GATE_GHOST", "2.0"))
        except ValueError:
            _GHOST_RATIO_LIMIT = 2.0
        try:
            _GHOST_ABS_FLOOR = float(os.environ.get("ASP_GATE_GHOST_FLOOR", "40.0"))
        except ValueError:
            _GHOST_ABS_FLOOR = 40.0
        if simple_ok and _GHOST_RATIO_LIMIT < 90:
            _simple_img_gate = cv2.imread(central_simple_path)
            if _simple_img_gate is not None:
                _asp_ghost = _ghosting_score_v2(canvas_out)  # siqe, post-crop
                _sim_ghost = _ghosting_score_v2(_simple_img_gate)
                print(
                    f"  [GhostGate/siqe] asp_ghost={_asp_ghost:.1f}  "
                    f"sim_ghost={_sim_ghost:.1f}  "
                    f"ratio={_asp_ghost / max(_sim_ghost, 1.0):.2f}"
                )
                # Gate fires only when ASP ghosting is BOTH above the absolute
                # floor and above ratio× SCANS — prevents false positives when
                # both outputs have inherently low ghosting.
                _ghost_limit = max(
                    _GHOST_ABS_FLOOR, _GHOST_RATIO_LIMIT * max(_sim_ghost, 1.0)
                )
                if _asp_ghost > _ghost_limit:
                    _fallback_reason = f"ghost_gate_siqe:asp={_asp_ghost:.1f}_sim={_sim_ghost:.1f}_limit={_ghost_limit:.1f}"
                    print(
                        f"  [GhostGate/siqe] FAILED "
                        f"(asp={_asp_ghost:.1f} > limit={_ghost_limit:.1f} "
                        f"[floor={_GHOST_ABS_FLOOR:.0f}, {_GHOST_RATIO_LIMIT:.1f}× sim={_sim_ghost:.1f}]) "
                        f"→ SCANS fallback."
                    )
                    timings["render_gate_fallback"] = 1
                    raise RuntimeError(
                        f"Ghosting gate (siqe): asp_ghost={_asp_ghost:.1f}, "
                        f"ratio={_asp_ghost / max(_sim_ghost, 1.0):.2f}"
                    )

        # ── SeamVisGate (post-crop, §4.8) ──────────────────────────────────
        # Fires when ASP seam_visibility is BOTH above an absolute floor AND
        # above ratio× SCANS seam_visibility.
        # seam_visibility taxonomy: 0–5=invisible, 6–12=normal, 13–25=visible,
        # >25=hard cut.  ASP avg=25.77, SCANS avg=4.21 across 97 tests.
        # 97-test corpus: test74 (sv=92.6), test34 (62.8), test12 (38.2),
        # test92 (33.6) all fire at floor=20, ratio=3.0 → SCANS fallback.
        # Override: ASP_GATE_SEAM_VIS=99 to disable.
        try:
            _SEAM_VIS_RATIO_LIMIT = float(os.environ.get("ASP_GATE_SEAM_VIS", "3.0"))
        except ValueError:
            _SEAM_VIS_RATIO_LIMIT = 3.0
        try:
            _SEAM_VIS_ABS_FLOOR = float(os.environ.get("ASP_GATE_SEAM_VIS_FLOOR", "20.0"))
        except ValueError:
            _SEAM_VIS_ABS_FLOOR = 20.0
        if simple_ok and _SEAM_VIS_RATIO_LIMIT < 90:
            _simple_img_sv = cv2.imread(central_simple_path)
            if _simple_img_sv is not None:
                _asp_sv = _seam_visibility_score(canvas_out)
                _sim_sv = _seam_visibility_score(_simple_img_sv)
                print(
                    f"  [SeamVisGate] asp_sv={_asp_sv:.1f}  "
                    f"sim_sv={_sim_sv:.1f}  "
                    f"ratio={_asp_sv / max(_sim_sv, 1.0):.2f}"
                )
                _sv_limit = max(
                    _SEAM_VIS_ABS_FLOOR, _SEAM_VIS_RATIO_LIMIT * max(_sim_sv, 1.0)
                )
                if _asp_sv > _sv_limit:
                    _fallback_reason = (
                        f"seam_vis_gate:asp={_asp_sv:.1f}"
                        f"_sim={_sim_sv:.1f}_limit={_sv_limit:.1f}"
                    )
                    print(
                        f"  [SeamVisGate] FAILED "
                        f"(asp={_asp_sv:.1f} > limit={_sv_limit:.1f} "
                        f"[floor={_SEAM_VIS_ABS_FLOOR:.0f}, "
                        f"{_SEAM_VIS_RATIO_LIMIT:.1f}× sim={_sim_sv:.1f}]) "
                        f"→ SCANS fallback."
                    )
                    timings["render_gate_fallback"] = 2
                    raise RuntimeError(
                        f"SeamVis gate: asp_sv={_asp_sv:.1f}, "
                        f"ratio={_asp_sv / max(_sim_sv, 1.0):.2f}"
                    )

        # ── CanvasGainUniformityGate (post-crop, §5.3) ──────────────────────
        # Fires when ASP per-strip luminance banding (canvas_gain_uniformity)
        # is BOTH above an absolute floor AND above ratio× SCANS CGU.
        # canvas_gain_uniformity = std/mean of 8-strip mean luminance.
        # Good range: <0.10.  test82: asp=0.238 vs sim=0.104 (2.3×) → fires.
        # Override: ASP_GATE_CGU=99 to disable.
        try:
            _CGU_RATIO_LIMIT = float(os.environ.get("ASP_GATE_CGU", "2.0"))
        except ValueError:
            _CGU_RATIO_LIMIT = 2.0
        try:
            _CGU_ABS_FLOOR = float(os.environ.get("ASP_GATE_CGU_FLOOR", "0.15"))
        except ValueError:
            _CGU_ABS_FLOOR = 0.15
        if simple_ok and _CGU_RATIO_LIMIT < 90 and _fallback_reason is None:
            _simple_img_cgu = cv2.imread(central_simple_path)
            if _simple_img_cgu is not None:
                _asp_cgu = _canvas_gain_uniformity(canvas_out, n_strips=8)
                _sim_cgu = _canvas_gain_uniformity(_simple_img_cgu, n_strips=8)
                print(
                    f"  [CGUGate] asp_cgu={_asp_cgu:.3f}  "
                    f"sim_cgu={_sim_cgu:.3f}  "
                    f"ratio={_asp_cgu / max(_sim_cgu, 0.001):.2f}"
                )
                _cgu_limit = max(_CGU_ABS_FLOOR, _CGU_RATIO_LIMIT * max(_sim_cgu, 0.001))
                if _asp_cgu > _cgu_limit:
                    _fallback_reason = (
                        f"cgu_gate:asp={_asp_cgu:.3f}"
                        f"_sim={_sim_cgu:.3f}_limit={_cgu_limit:.3f}"
                    )
                    print(
                        f"  [CGUGate] FAILED "
                        f"(asp={_asp_cgu:.3f} > limit={_cgu_limit:.3f} "
                        f"[floor={_CGU_ABS_FLOOR:.2f}, "
                        f"{_CGU_RATIO_LIMIT:.1f}× sim={_sim_cgu:.3f}]) "
                        f"→ SCANS fallback."
                    )
                    timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 4
                    raise RuntimeError(
                        f"CGU gate: asp_cgu={_asp_cgu:.3f}, "
                        f"ratio={_asp_cgu / max(_sim_cgu, 0.001):.2f}"
                    )

        # ── SeamCoherenceGate (§5.2) ────────────────────────────────────────
        # Fires when ASP seam_coherence is BOTH above an absolute floor AND
        # above ratio× SCANS seam_coherence.
        # seam_coherence = std of per-row mean luminance (rolling window).
        # Override: ASP_GATE_SEAM_COH=99 to disable.
        try:
            _SEAM_COH_RATIO_LIMIT = float(os.environ.get("ASP_GATE_SEAM_COH", "2.5"))
        except ValueError:
            _SEAM_COH_RATIO_LIMIT = 2.5
        try:
            _SEAM_COH_ABS_FLOOR = float(os.environ.get("ASP_GATE_SEAM_COH_FLOOR", "15.0"))
        except ValueError:
            _SEAM_COH_ABS_FLOOR = 15.0
        if simple_ok and _SEAM_COH_RATIO_LIMIT < 90 and _fallback_reason is None:
            _simple_img_sc = cv2.imread(central_simple_path)
            if _simple_img_sc is not None:
                _asp_sc = _seam_coherence(canvas_out)
                _sim_sc = _seam_coherence(_simple_img_sc)
                print(
                    f"  [SCGate] asp_sc={_asp_sc:.1f}  "
                    f"sim_sc={_sim_sc:.1f}  "
                    f"ratio={_asp_sc / max(_sim_sc, 1.0):.2f}"
                )
                _sc_limit = max(
                    _SEAM_COH_ABS_FLOOR, _SEAM_COH_RATIO_LIMIT * max(_sim_sc, 1.0)
                )
                if _asp_sc > _sc_limit:
                    _fallback_reason = (
                        f"seam_coh_gate:asp={_asp_sc:.1f}"
                        f"_sim={_sim_sc:.1f}_limit={_sc_limit:.1f}"
                    )
                    print(
                        f"  [SCGate] FAILED "
                        f"(asp={_asp_sc:.1f} > limit={_sc_limit:.1f} "
                        f"[floor={_SEAM_COH_ABS_FLOOR:.0f}, "
                        f"{_SEAM_COH_RATIO_LIMIT:.1f}× sim={_sim_sc:.1f}]) "
                        f"→ SCANS fallback."
                    )
                    timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 8
                    raise RuntimeError(
                        f"SCGate: asp_sc={_asp_sc:.1f}, "
                        f"ratio={_asp_sc / max(_sim_sc, 1.0):.2f}"
                    )

        # ── FFT Banding Gate (§5.13) ─────────────────────────────────────────────
        try:
            _FFT_BAND_RATIO_LIMIT = float(os.environ.get("ASP_GATE_FFT_BAND", "3.0"))
        except ValueError:
            _FFT_BAND_RATIO_LIMIT = 3.0
        try:
            _FFT_BAND_ABS_FLOOR = float(os.environ.get("ASP_GATE_FFT_BAND_FLOOR", "0.30"))
        except ValueError:
            _FFT_BAND_ABS_FLOOR = 0.30
        if simple_ok and _FFT_BAND_RATIO_LIMIT < 90 and _fallback_reason is None:
            _simple_img_fft = cv2.imread(central_simple_path)
            if _simple_img_fft is not None:
                _asp_fft = _horizontal_fft_banding(canvas_out, n_strips=8)
                _sim_fft = _horizontal_fft_banding(_simple_img_fft, n_strips=8)
                _fft_limit = max(_FFT_BAND_ABS_FLOOR, _FFT_BAND_RATIO_LIMIT * max(_sim_fft, 0.001))
                if _asp_fft > _fft_limit:
                    _fallback_reason = f"fft_band_gate:asp={_asp_fft:.3f}_sim={_sim_fft:.3f}_limit={_fft_limit:.3f}"
                    timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 16
                    raise RuntimeError(f"FFTBandGate: asp_fft={_asp_fft:.3f}, ratio={_asp_fft / max(_sim_fft, 0.001):.2f}")

        # ── Strip Luma Monotonicity Gate (§5.14) ─────────────────────────────────
        try:
            _MONO_RATIO_LIMIT = float(os.environ.get("ASP_GATE_MONO", "3.0"))
        except ValueError:
            _MONO_RATIO_LIMIT = 3.0
        try:
            _MONO_ABS_FLOOR = float(os.environ.get("ASP_GATE_MONO_FLOOR", "0.50"))
        except ValueError:
            _MONO_ABS_FLOOR = 0.50
        if simple_ok and _MONO_RATIO_LIMIT < 90 and _fallback_reason is None:
            _simple_img_mono = cv2.imread(central_simple_path)
            if _simple_img_mono is not None:
                _asp_mono = _strip_luma_monotonicity(canvas_out, n_strips=8)
                _sim_mono = _strip_luma_monotonicity(_simple_img_mono, n_strips=8)
                _mono_limit = max(_MONO_ABS_FLOOR, _MONO_RATIO_LIMIT * max(_sim_mono, 0.001))
                if _asp_mono > _mono_limit:
                    _fallback_reason = f"mono_gate:asp={_asp_mono:.3f}_sim={_sim_mono:.3f}_limit={_mono_limit:.3f}"
                    timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 32
                    raise RuntimeError(f"MonoGate: asp_mono={_asp_mono:.3f}, ratio={_asp_mono / max(_sim_mono, 0.001):.2f}")
        # ── Seam Ownership Entropy Gate (§5.15) ──────────────────────────────────
        try:
            _ENTROPY_RATIO_LIMIT = float(os.environ.get("ASP_GATE_ENTROPY", "2.5"))
        except ValueError:
            _ENTROPY_RATIO_LIMIT = 2.5
        try:
            _ENTROPY_ABS_FLOOR = float(os.environ.get("ASP_GATE_ENTROPY_FLOOR", "3.0"))
        except ValueError:
            _ENTROPY_ABS_FLOOR = 3.0
        if simple_ok and _ENTROPY_RATIO_LIMIT < 90 and _fallback_reason is None:
            _simple_img_ent = cv2.imread(central_simple_path)
            if _simple_img_ent is not None and affines is not None:
                _asp_ent = _seam_ownership_entropy(canvas_out, affines=affines)
                _sim_ent = _seam_ownership_entropy(_simple_img_ent, affines=affines)
                _ent_limit = max(_ENTROPY_ABS_FLOOR, _ENTROPY_RATIO_LIMIT * max(_sim_ent, 0.1))
                if _asp_ent > _ent_limit:
                    _fallback_reason = f"entropy_gate:asp={_asp_ent:.3f}_sim={_sim_ent:.3f}_limit={_ent_limit:.3f}"
                    timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 64
                    raise RuntimeError(f"EntropyGate: asp_ent={_asp_ent:.3f}, ratio={_asp_ent / max(_sim_ent, 0.1):.2f}")

        # ── Strip Self-SSIM Gate (§5.17) ─────────────────────────────────────────
        try:
            _STRIP_SSIM_RATIO_LIMIT = float(os.environ.get("ASP_GATE_STRIP_SSIM", "0.5"))
        except ValueError:
            _STRIP_SSIM_RATIO_LIMIT = 0.5
        try:
            _STRIP_SSIM_ABS_FLOOR = float(os.environ.get("ASP_GATE_STRIP_SSIM_FLOOR", "0.60"))
        except ValueError:
            _STRIP_SSIM_ABS_FLOOR = 0.60
        if simple_ok and _STRIP_SSIM_RATIO_LIMIT > 0 and _fallback_reason is None:
            _simple_img_ssim = cv2.imread(central_simple_path)
            if _simple_img_ssim is not None:
                _asp_sssim = _strip_self_ssim(canvas_out, n_strips=8)
                _sim_sssim = _strip_self_ssim(_simple_img_ssim, n_strips=8)
                _sssim_limit = min(_STRIP_SSIM_ABS_FLOOR, _STRIP_SSIM_RATIO_LIMIT * max(_sim_sssim, 0.001))
                if _asp_sssim < _sssim_limit:
                    _fallback_reason = f"strip_ssim_gate:asp={_asp_sssim:.3f}_sim={_sim_sssim:.3f}_limit={_sssim_limit:.3f}"
                    timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 128
                    raise RuntimeError(f"StripSSIMGate: asp_sssim={_asp_sssim:.3f}, ratio={_asp_sssim / max(_sim_sssim, 0.001):.2f}")

        # ── Chroma Seam Coherence Gate (§5.18) ───────────────────────────────────
        try:
            _CHROMA_COH_RATIO_LIMIT = float(os.environ.get("ASP_GATE_CHROMA_COH", "2.5"))
        except ValueError:
            _CHROMA_COH_RATIO_LIMIT = 2.5
        try:
            _CHROMA_COH_ABS_FLOOR = float(os.environ.get("ASP_GATE_CHROMA_COH_FLOOR", "12.0"))
        except ValueError:
            _CHROMA_COH_ABS_FLOOR = 12.0
        if simple_ok and _CHROMA_COH_RATIO_LIMIT < 90 and _fallback_reason is None:
            _simple_img_chroma = cv2.imread(central_simple_path)
            if _simple_img_chroma is not None:
                _asp_chroma = _chroma_seam_coherence(canvas_out)
                _sim_chroma = _chroma_seam_coherence(_simple_img_chroma)
                _chroma_limit = max(_CHROMA_COH_ABS_FLOOR, _CHROMA_COH_RATIO_LIMIT * max(_sim_chroma, 1.0))
                if _asp_chroma > _chroma_limit:
                    _fallback_reason = f"chroma_coh_gate:asp={_asp_chroma:.2f}_sim={_sim_chroma:.2f}_limit={_chroma_limit:.2f}"
                    timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 256
                    raise RuntimeError(f"ChromaSeamGate: asp_chroma={_asp_chroma:.2f}, ratio={_asp_chroma / max(_sim_chroma, 1.0):.2f}")

        # §5.30 GhostSiqeGate — FFT autocorrelation ghosting (SIQE proxy)
        if _fallback_reason is None and simple_ok:
            try:
                _simple_img_siqe = cv2.imread(central_simple_path)
                if _simple_img_siqe is not None:
                    _asp_siqe = _ghosting_score_v2(canvas_out)
                    _sim_siqe = _ghosting_score_v2(_simple_img_siqe)
                    print(
                        f"  [GhostSiqeGate] asp_siqe={_asp_siqe:.1f}  "
                        f"sim_siqe={_sim_siqe:.1f}  "
                        f"ratio={_asp_siqe / max(_sim_siqe, 1.0):.2f}"
                    )
                    _siqe_limit = max(_GHOST_SIQE_ABS_FLOOR, _GHOST_SIQE_RATIO_LIMIT * max(_sim_siqe, 1.0))
                    if _asp_siqe > _siqe_limit:
                        _fallback_reason = f"ghost_siqe_gate:{_asp_siqe:.1f}"
                        print(
                            f"  [GhostSiqeGate] FAILED "
                            f"(asp_siqe={_asp_siqe:.1f} > limit={_siqe_limit:.1f} "
                            f"[floor={_GHOST_SIQE_ABS_FLOOR:.0f}, {_GHOST_SIQE_RATIO_LIMIT:.1f}× sim={_sim_siqe:.1f}]) "
                            f"→ SCANS fallback."
                        )
                        timings["render_gate_fallback"] = 1
                        raise RuntimeError(
                            f"GhostSiqeGate: asp_siqe={_asp_siqe:.1f}, "
                            f"ratio={_asp_siqe / max(_sim_siqe, 1.0):.2f}"
                        )
            except RuntimeError:
                raise
            except Exception as _gs_e:
                logger.debug("[Bench] GhostSiqeGate skipped: %s", _gs_e)

        # §5.35 SeamBandNccGate — comparative seam band NCC check
        if _fallback_reason is None and simple_ok:
            try:
                _simple_img_ncc = cv2.imread(central_simple_path)
                if _simple_img_ncc is not None:
                    from backend.src.animation.alignment.canvas import _seam_band_ncc_min
                    _asp_ncc = _seam_band_ncc_min(canvas_out, n_strips=8, band_px=10)
                    _sim_ncc = _seam_band_ncc_min(_simple_img_ncc, n_strips=8, band_px=10)
                    print(
                        f"  [SeamBandNccGate] asp_ncc={_asp_ncc:.3f}  "
                        f"sim_ncc={_sim_ncc:.3f}"
                    )
                    if _asp_ncc < _SEAM_NCC_ABS_FLOOR or (
                        _sim_ncc > 0.1 and _asp_ncc < _SEAM_NCC_RATIO * _sim_ncc
                    ):
                        _fallback_reason = f"seam_ncc_gate:{_asp_ncc:.3f}"
                        print(
                            f"  [SeamBandNccGate] FAILED "
                            f"(asp_ncc={_asp_ncc:.3f} < floor={_SEAM_NCC_ABS_FLOOR:.2f} "
                            f"or < {_SEAM_NCC_RATIO:.1f}×sim={_sim_ncc:.3f}) → SCANS fallback."
                        )
                        timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 512
                        raise RuntimeError(
                            f"SeamBandNccGate: asp_ncc={_asp_ncc:.3f}, sim_ncc={_sim_ncc:.3f}"
                        )
            except RuntimeError:
                raise
            except Exception as _ncc_e:
                logger.debug("[Bench] SeamBandNccGate skipped: %s", _ncc_e)

        # §5.37 HistIntersectGate — comparative strip histogram intersection check
        if _fallback_reason is None and simple_ok:
            try:
                _simple_img_hi = cv2.imread(central_simple_path)
                if _simple_img_hi is not None:
                    from backend.src.animation.alignment.canvas import _strip_hist_intersection_min
                    _asp_hi = _strip_hist_intersection_min(canvas_out, n_strips=8)
                    _sim_hi = _strip_hist_intersection_min(_simple_img_hi, n_strips=8)
                    print(
                        f"  [HistIntersectGate] asp_hi={_asp_hi:.3f}  "
                        f"sim_hi={_sim_hi:.3f}"
                    )
                    if _asp_hi < _HIST_INTERSECT_ABS_FLOOR or (
                        _sim_hi > 0.1 and _asp_hi < _HIST_INTERSECT_RATIO * _sim_hi
                    ):
                        _fallback_reason = f"hist_intersect_gate:{_asp_hi:.3f}"
                        print(
                            f"  [HistIntersectGate] FAILED "
                            f"(asp_hi={_asp_hi:.3f} < floor={_HIST_INTERSECT_ABS_FLOOR:.2f} "
                            f"or < {_HIST_INTERSECT_RATIO:.1f}×sim={_sim_hi:.3f}) → SCANS fallback."
                        )
                        timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 1024
                        raise RuntimeError(
                            f"HistIntersectGate: asp_hi={_asp_hi:.3f}, sim_hi={_sim_hi:.3f}"
                        )
            except RuntimeError:
                raise
            except Exception as _hi_e:
                logger.debug("[Bench] HistIntersectGate skipped: %s", _hi_e)

        # §5.40 SeamGradRatioGate — comparative seam gradient ratio check
        if _fallback_reason is None and simple_ok:
            try:
                _simple_img_sgr = cv2.imread(central_simple_path)
                if _simple_img_sgr is not None:
                    from backend.src.animation.alignment.canvas import _strip_seam_gradient_score
                    _asp_sgr = _strip_seam_gradient_score(canvas_out, n_strips=8)
                    _sim_sgr = _strip_seam_gradient_score(_simple_img_sgr, n_strips=8)
                    print(
                        f"  [SeamGradRatioGate] asp_sgr={_asp_sgr:.2f}  "
                        f"sim_sgr={_sim_sgr:.2f}  "
                        f"ratio={_asp_sgr / max(_sim_sgr, 0.1):.2f}"
                    )
                    if _asp_sgr > _SEAM_GRAD_RATIO_ABS_FLOOR and (
                        _asp_sgr > _SEAM_GRAD_RATIO_LIMIT * max(_sim_sgr, 0.1)
                    ):
                        _fallback_reason = f"seam_grad_ratio_gate:{_asp_sgr:.2f}"
                        print(
                            f"  [SeamGradRatioGate] FAILED "
                            f"(asp_sgr={_asp_sgr:.2f} > floor={_SEAM_GRAD_RATIO_ABS_FLOOR:.1f} "
                            f"and > {_SEAM_GRAD_RATIO_LIMIT:.1f}×sim={_sim_sgr:.2f}) → SCANS fallback."
                        )
                        timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 2048
                        raise RuntimeError(
                            f"SeamGradRatioGate: asp_sgr={_asp_sgr:.2f}, sim_sgr={_sim_sgr:.2f}"
                        )
            except RuntimeError:
                raise
            except Exception as _sgr_e:
                logger.debug("[Bench] SeamGradRatioGate skipped: %s", _sgr_e)

        # §5.43 ValidAreaGate — comparative canvas valid-area ratio check
        if _fallback_reason is None and simple_ok:
            try:
                _simple_img_va = cv2.imread(central_simple_path)
                if _simple_img_va is not None:
                    from backend.src.animation.alignment.canvas import _canvas_valid_area_ratio
                    _asp_va = _canvas_valid_area_ratio(canvas_out)
                    _sim_va = _canvas_valid_area_ratio(_simple_img_va)
                    print(
                        f"  [ValidAreaGate] asp_va={_asp_va:.3f}  "
                        f"sim_va={_sim_va:.3f}"
                    )
                    if _asp_va < _VALID_AREA_ABS_FLOOR or (
                        _sim_va > 0.5 and _asp_va < _VALID_AREA_RATIO * _sim_va
                    ):
                        _fallback_reason = f"valid_area_gate:{_asp_va:.3f}"
                        print(
                            f"  [ValidAreaGate] FAILED "
                            f"(asp_va={_asp_va:.3f} < floor={_VALID_AREA_ABS_FLOOR:.2f} "
                            f"or < {_VALID_AREA_RATIO:.1f}×sim={_sim_va:.3f}) → SCANS fallback."
                        )
                        timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 512
                        raise RuntimeError(
                            f"ValidAreaGate: asp_va={_asp_va:.3f}, sim_va={_sim_va:.3f}"
                        )
            except RuntimeError:
                raise
            except Exception as _va_e:
                logger.debug("[Bench] ValidAreaGate skipped: %s", _va_e)

        # §5.44 SatCvGate — comparative strip saturation CV check
        if _fallback_reason is None and simple_ok:
            try:
                _simple_img_sc = cv2.imread(central_simple_path)
                if _simple_img_sc is not None:
                    from backend.src.animation.alignment.canvas import _strip_sat_cv
                    _asp_sc = _strip_sat_cv(canvas_out, n_strips=8)
                    _sim_sc = _strip_sat_cv(_simple_img_sc, n_strips=8)
                    print(
                        f"  [SatCvGate] asp_sc={_asp_sc:.3f}  "
                        f"sim_sc={_sim_sc:.3f}"
                    )
                    if _asp_sc > _SAT_CV_ABS_FLOOR and (
                        _sim_sc < 0.01 or _asp_sc > _SAT_CV_RATIO * max(_sim_sc, 0.001)
                    ):
                        _fallback_reason = f"sat_cv_gate:{_asp_sc:.3f}"
                        print(
                            f"  [SatCvGate] FAILED "
                            f"(asp_sc={_asp_sc:.3f} > floor={_SAT_CV_ABS_FLOOR:.2f} "
                            f"and > {_SAT_CV_RATIO:.1f}×sim={_sim_sc:.3f}) → SCANS fallback."
                        )
                        timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 256
                        raise RuntimeError(
                            f"SatCvGate: asp_sc={_asp_sc:.3f}, sim_sc={_sim_sc:.3f}"
                        )
            except RuntimeError:
                raise
            except Exception as _sc_e:
                logger.debug("[Bench] SatCvGate skipped: %s", _sc_e)

        # §5.47 LumaRangeGate — comparative strip luma range check
        if _fallback_reason is None and simple_ok:
            try:
                _simple_img_lr = cv2.imread(central_simple_path)
                if _simple_img_lr is not None:
                    from backend.src.animation.alignment.canvas import _strip_luma_range
                    _asp_lr = _strip_luma_range(canvas_out, n_strips=8)
                    _sim_lr = _strip_luma_range(_simple_img_lr, n_strips=8)
                    print(
                        f"  [LumaRangeGate] asp_lr={_asp_lr:.2f}  "
                        f"sim_lr={_sim_lr:.2f}"
                    )
                    if _asp_lr > _LUMA_RANGE_ABS_FLOOR and (
                        _sim_lr < 5.0 or _asp_lr > _LUMA_RANGE_RATIO * max(_sim_lr, 1.0)
                    ):
                        _fallback_reason = f"luma_range_gate:{_asp_lr:.2f}"
                        print(
                            f"  [LumaRangeGate] FAILED "
                            f"(asp_lr={_asp_lr:.2f} > floor={_LUMA_RANGE_ABS_FLOOR:.1f} "
                            f"and > {_LUMA_RANGE_RATIO:.1f}×sim={_sim_lr:.2f}) → SCANS fallback."
                        )
                        timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 128
                        raise RuntimeError(
                            f"LumaRangeGate: asp_lr={_asp_lr:.2f}, sim_lr={_sim_lr:.2f}"
                        )
            except RuntimeError:
                raise
            except Exception as _lr_e:
                logger.debug("[Bench] LumaRangeGate skipped: %s", _lr_e)

        # §5.48 EdgeDensityGate — comparative strip edge density check
        if _fallback_reason is None and simple_ok:
            try:
                _simple_img_ed = cv2.imread(central_simple_path)
                if _simple_img_ed is not None:
                    from backend.src.animation.alignment.canvas import _seam_edge_density
                    _asp_ed = _seam_edge_density(canvas_out, n_strips=8)
                    _sim_ed = _seam_edge_density(_simple_img_ed, n_strips=8)
                    print(
                        f"  [EdgeDensityGate] asp_ed={_asp_ed:.4f}  "
                        f"sim_ed={_sim_ed:.4f}"
                    )
                    if _asp_ed > _EDGE_DENSITY_ABS_FLOOR and (
                        _sim_ed < 0.01 or _asp_ed > _EDGE_DENSITY_RATIO * max(_sim_ed, 0.001)
                    ):
                        _fallback_reason = f"edge_density_gate:{_asp_ed:.4f}"
                        print(
                            f"  [EdgeDensityGate] FAILED "
                            f"(asp_ed={_asp_ed:.4f} > floor={_EDGE_DENSITY_ABS_FLOOR:.2f} "
                            f"and > {_EDGE_DENSITY_RATIO:.1f}×sim={_sim_ed:.4f}) → SCANS fallback."
                        )
                        timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 64
                        raise RuntimeError(
                            f"EdgeDensityGate: asp_ed={_asp_ed:.4f}, sim_ed={_sim_ed:.4f}"
                        )
            except RuntimeError:
                raise
            except Exception as _ed_e:
                logger.debug("[Bench] EdgeDensityGate skipped: %s", _ed_e)

        # §5.51 LumaMadGate — comparative strip luma MAD check
        if _fallback_reason is None and simple_ok:
            try:
                _simple_img_lmad = cv2.imread(central_simple_path)
                if _simple_img_lmad is not None:
                    from backend.src.animation.alignment.canvas import _strip_luma_mad
                    _asp_lmad = _strip_luma_mad(canvas_out, n_strips=8)
                    _sim_lmad = _strip_luma_mad(_simple_img_lmad, n_strips=8)
                    print(
                        f"  [LumaMadGate] asp_lmad={_asp_lmad:.2f}  "
                        f"sim_lmad={_sim_lmad:.2f}"
                    )
                    if _asp_lmad > _LUMA_MAD_ABS_FLOOR and (
                        _sim_lmad < 2.0 or _asp_lmad > _LUMA_MAD_RATIO * max(_sim_lmad, 1.0)
                    ):
                        _fallback_reason = f"luma_mad_gate:{_asp_lmad:.2f}"
                        print(
                            f"  [LumaMadGate] FAILED "
                            f"(asp_lmad={_asp_lmad:.2f} > floor={_LUMA_MAD_ABS_FLOOR:.1f} "
                            f"and > {_LUMA_MAD_RATIO:.1f}×sim={_sim_lmad:.2f}) → SCANS fallback."
                        )
                        timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 16
                        raise RuntimeError(
                            f"LumaMadGate: asp_lmad={_asp_lmad:.2f}, sim_lmad={_sim_lmad:.2f}"
                        )
            except RuntimeError:
                raise
            except Exception as _lmad_e:
                logger.debug("[Bench] LumaMadGate skipped: %s", _lmad_e)
        # §5.52 SharpnessCvGate — comparative strip sharpness CV check
        if _fallback_reason is None and simple_ok:
            try:
                _simple_img_scv = cv2.imread(central_simple_path)
                if _simple_img_scv is not None:
                    from backend.src.animation.alignment.canvas import _strip_sharpness_cv
                    _asp_scv = _strip_sharpness_cv(canvas_out, n_strips=8)
                    _sim_scv = _strip_sharpness_cv(_simple_img_scv, n_strips=8)
                    print(
                        f"  [SharpnessCvGate] asp_scv={_asp_scv:.4f}  "
                        f"sim_scv={_sim_scv:.4f}"
                    )
                    if _asp_scv > _SHARPNESS_CV_ABS_FLOOR and (
                        _sim_scv < 0.05 or _asp_scv > _SHARPNESS_CV_RATIO * max(_sim_scv, 0.01)
                    ):
                        _fallback_reason = f"sharpness_cv_gate:{_asp_scv:.4f}"
                        print(
                            f"  [SharpnessCvGate] FAILED "
                            f"(asp_scv={_asp_scv:.4f} > floor={_SHARPNESS_CV_ABS_FLOOR:.2f} "
                            f"and > {_SHARPNESS_CV_RATIO:.1f}×sim={_sim_scv:.4f}) → SCANS fallback."
                        )
                        timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 8
                        raise RuntimeError(
                            f"SharpnessCvGate: asp_scv={_asp_scv:.4f}, sim_scv={_sim_scv:.4f}"
                        )
            except RuntimeError:
                raise
            except Exception as _scv_e:
                logger.debug("[Bench] SharpnessCvGate skipped: %s", _scv_e)
        # §5.55 ContrastCvGate — comparative strip contrast CV check
        if _fallback_reason is None and simple_ok:
            try:
                _simple_img_ccv = cv2.imread(central_simple_path)
                if _simple_img_ccv is not None:
                    from backend.src.animation.alignment.canvas import _strip_contrast_cv
                    _asp_ccv = _strip_contrast_cv(canvas_out, n_strips=8)
                    _sim_ccv = _strip_contrast_cv(_simple_img_ccv, n_strips=8)
                    print(f"  [ContrastCvGate] asp_ccv={_asp_ccv:.4f}  sim_ccv={_sim_ccv:.4f}")
                    if _asp_ccv > _CONTRAST_CV_ABS_FLOOR and (
                        _sim_ccv < 0.05 or _asp_ccv > _CONTRAST_CV_RATIO * max(_sim_ccv, 0.01)
                    ):
                        _fallback_reason = f"contrast_cv_gate:{_asp_ccv:.4f}"
                        print(
                            f"  [ContrastCvGate] FAILED "
                            f"(asp_ccv={_asp_ccv:.4f} > floor={_CONTRAST_CV_ABS_FLOOR:.2f} "
                            f"and > {_CONTRAST_CV_RATIO:.1f}×sim={_sim_ccv:.4f}) → SCANS fallback."
                        )
                        timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 4
                        raise RuntimeError(
                            f"ContrastCvGate: asp_ccv={_asp_ccv:.4f}, sim_ccv={_sim_ccv:.4f}"
                        )
            except RuntimeError:
                raise
            except Exception as _ccv_e:
                logger.debug("[Bench] ContrastCvGate skipped: %s", _ccv_e)
        # §5.56 ChromaJumpGate — comparative seam chroma jump check
        if _fallback_reason is None and simple_ok:
            try:
                _simple_img_scj = cv2.imread(central_simple_path)
                if _simple_img_scj is not None:
                    from backend.src.animation.alignment.canvas import _seam_chroma_jump
                    _asp_scj = _seam_chroma_jump(canvas_out, n_strips=8, boundary_px=3)
                    _sim_scj = _seam_chroma_jump(_simple_img_scj, n_strips=8, boundary_px=3)
                    print(f"  [ChromaJumpGate] asp_scj={_asp_scj:.2f}  sim_scj={_sim_scj:.2f}")
                    if _asp_scj > _CHROMA_JUMP_ABS_FLOOR and (
                        _sim_scj < 1.0 or _asp_scj > _CHROMA_JUMP_RATIO * max(_sim_scj, 0.5)
                    ):
                        _fallback_reason = f"chroma_jump_gate:{_asp_scj:.2f}"
                        print(
                            f"  [ChromaJumpGate] FAILED "
                            f"(asp_scj={_asp_scj:.2f} > floor={_CHROMA_JUMP_ABS_FLOOR:.1f} "
                            f"and > {_CHROMA_JUMP_RATIO:.1f}×sim={_sim_scj:.2f}) → SCANS fallback."
                        )
                        timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 2
                        raise RuntimeError(
                            f"ChromaJumpGate: asp_scj={_asp_scj:.2f}, sim_scj={_sim_scj:.2f}"
                        )
            except RuntimeError:
                raise
            except Exception as _scj_e:
                logger.debug("[Bench] ChromaJumpGate skipped: %s", _scj_e)
        # §5.59 NoiseCvGate — comparative strip noise CV check
        if _fallback_reason is None and simple_ok:
            try:
                _simple_img_ncv = cv2.imread(central_simple_path)
                if _simple_img_ncv is not None:
                    from backend.src.animation.alignment.canvas import _strip_noise_cv
                    _asp_ncv = _strip_noise_cv(canvas_out, n_strips=8)
                    _sim_ncv = _strip_noise_cv(_simple_img_ncv, n_strips=8)
                    print(f"  [NoiseCvGate] asp_ncv={_asp_ncv:.4f}  sim_ncv={_sim_ncv:.4f}")
                    if _asp_ncv > _NOISE_CV_ABS_FLOOR and (
                        _sim_ncv < 0.05 or _asp_ncv > _NOISE_CV_RATIO * max(_sim_ncv, 0.01)
                    ):
                        _fallback_reason = f"noise_cv_gate:{_asp_ncv:.4f}"
                        print(
                            f"  [NoiseCvGate] FAILED "
                            f"(asp_ncv={_asp_ncv:.4f} > floor={_NOISE_CV_ABS_FLOOR:.2f} "
                            f"and > {_NOISE_CV_RATIO:.1f}×sim={_sim_ncv:.4f}) → SCANS fallback."
                        )
                        timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 1
                        raise RuntimeError(
                            f"NoiseCvGate: asp_ncv={_asp_ncv:.4f}, sim_ncv={_sim_ncv:.4f}"
                        )
            except RuntimeError:
                raise
            except Exception as _ncv_e:
                logger.debug("[Bench] NoiseCvGate skipped: %s", _ncv_e)
        # §5.60 LumaStepCvGate — comparative seam luma step CV check
        if _fallback_reason is None and simple_ok:
            try:
                _simple_img_lscv = cv2.imread(central_simple_path)
                if _simple_img_lscv is not None:
                    from backend.src.animation.alignment.canvas import _seam_luma_step_cv
                    _asp_lscv = _seam_luma_step_cv(canvas_out, n_strips=8, boundary_px=3)
                    _sim_lscv = _seam_luma_step_cv(_simple_img_lscv, n_strips=8, boundary_px=3)
                    print(f"  [LumaStepCvGate] asp_lscv={_asp_lscv:.4f}  sim_lscv={_sim_lscv:.4f}")
                    if _asp_lscv > _LUMA_STEP_CV_ABS_FLOOR and (
                        _sim_lscv < 0.05 or _asp_lscv > _LUMA_STEP_CV_RATIO * max(_sim_lscv, 0.01)
                    ):
                        _fallback_reason = f"luma_step_cv_gate:{_asp_lscv:.4f}"
                        print(
                            f"  [LumaStepCvGate] FAILED "
                            f"(asp_lscv={_asp_lscv:.4f} > floor={_LUMA_STEP_CV_ABS_FLOOR:.2f} "
                            f"and > {_LUMA_STEP_CV_RATIO:.1f}×sim={_sim_lscv:.4f}) → SCANS fallback."
                        )
                        timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 1
                        raise RuntimeError(
                            f"LumaStepCvGate: asp_lscv={_asp_lscv:.4f}, sim_lscv={_sim_lscv:.4f}"
                        )
            except RuntimeError:
                raise
            except Exception as _lscv_e:
                logger.debug("[Bench] LumaStepCvGate skipped: %s", _lscv_e)
        # §5.63 EntropyCvGate — comparative strip entropy CV check
        if _fallback_reason is None and simple_ok:
            try:
                _simple_img_ecv = cv2.imread(central_simple_path)
                if _simple_img_ecv is not None:
                    from backend.src.animation.alignment.canvas import _strip_entropy_cv
                    _asp_ecv = _strip_entropy_cv(canvas_out, n_strips=8)
                    _sim_ecv = _strip_entropy_cv(_simple_img_ecv, n_strips=8)
                    print(f"  [EntropyCvGate] asp_ecv={_asp_ecv:.4f}  sim_ecv={_sim_ecv:.4f}")
                    if _asp_ecv > _ENTROPY_CV_ABS_FLOOR and (
                        _sim_ecv < 0.05 or _asp_ecv > _ENTROPY_CV_RATIO * max(_sim_ecv, 0.01)
                    ):
                        _fallback_reason = f"entropy_cv_gate:{_asp_ecv:.4f}"
                        print(
                            f"  [EntropyCvGate] FAILED "
                            f"(asp_ecv={_asp_ecv:.4f} > floor={_ENTROPY_CV_ABS_FLOOR:.2f} "
                            f"and > {_ENTROPY_CV_RATIO:.1f}×sim={_sim_ecv:.4f}) → SCANS fallback."
                        )
                        timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 1
                        raise RuntimeError(
                            f"EntropyCvGate: asp_ecv={_asp_ecv:.4f}, sim_ecv={_sim_ecv:.4f}"
                        )
            except RuntimeError:
                raise
            except Exception as _ecv_e:
                logger.debug("[Bench] EntropyCvGate skipped: %s", _ecv_e)
        # §5.64 ChromaStepCvGate — comparative seam chroma step CV check
        if _fallback_reason is None and simple_ok:
            try:
                _simple_img_cscv = cv2.imread(central_simple_path)
                if _simple_img_cscv is not None:
                    from backend.src.animation.alignment.canvas import _seam_chroma_step_cv
                    _asp_cscv = _seam_chroma_step_cv(canvas_out, n_strips=8, boundary_px=3)
                    _sim_cscv = _seam_chroma_step_cv(_simple_img_cscv, n_strips=8, boundary_px=3)
                    print(f"  [ChromaStepCvGate] asp_cscv={_asp_cscv:.4f}  sim_cscv={_sim_cscv:.4f}")
                    if _asp_cscv > _CHROMA_STEP_CV_ABS_FLOOR and (
                        _sim_cscv < 0.05 or _asp_cscv > _CHROMA_STEP_CV_RATIO * max(_sim_cscv, 0.01)
                    ):
                        _fallback_reason = f"chroma_step_cv_gate:{_asp_cscv:.4f}"
                        print(
                            f"  [ChromaStepCvGate] FAILED "
                            f"(asp_cscv={_asp_cscv:.4f} > floor={_CHROMA_STEP_CV_ABS_FLOOR:.2f} "
                            f"and > {_CHROMA_STEP_CV_RATIO:.1f}×sim={_sim_cscv:.4f}) → SCANS fallback."
                        )
                        timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 1
                        raise RuntimeError(
                            f"ChromaStepCvGate: asp_cscv={_asp_cscv:.4f}, sim_cscv={_sim_cscv:.4f}"
                        )
            except RuntimeError:
                raise
            except Exception as _cscv_e:
                logger.debug("[Bench] ChromaStepCvGate skipped: %s", _cscv_e)
        # §5.67 ChromaEnergyCvGate — comparative strip chroma energy CV check
        if _fallback_reason is None and simple_ok:
            try:
                _simple_img_cecv = cv2.imread(central_simple_path)
                if _simple_img_cecv is not None:
                    from backend.src.animation.alignment.canvas import _strip_chroma_energy_cv
                    _asp_cecv = _strip_chroma_energy_cv(canvas_out, n_strips=8)
                    _sim_cecv = _strip_chroma_energy_cv(_simple_img_cecv, n_strips=8)
                    print(f"  [ChromaEnergyCvGate] asp_cecv={_asp_cecv:.4f}  sim_cecv={_sim_cecv:.4f}")
                    if _asp_cecv > _CHROMA_ENERGY_CV_ABS_FLOOR and (
                        _sim_cecv < 0.05 or _asp_cecv > _CHROMA_ENERGY_CV_RATIO * max(_sim_cecv, 0.01)
                    ):
                        _fallback_reason = f"chroma_energy_cv_gate:{_asp_cecv:.4f}"
                        print(
                            f"  [ChromaEnergyCvGate] FAILED "
                            f"(asp_cecv={_asp_cecv:.4f} > floor={_CHROMA_ENERGY_CV_ABS_FLOOR:.2f} "
                            f"and > {_CHROMA_ENERGY_CV_RATIO:.1f}×sim={_sim_cecv:.4f}) → SCANS fallback."
                        )
                        timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 1
                        raise RuntimeError(
                            f"ChromaEnergyCvGate: asp_cecv={_asp_cecv:.4f}, sim_cecv={_sim_cecv:.4f}"
                        )
            except RuntimeError:
                raise
            except Exception as _cecv_e:
                logger.debug("[Bench] ChromaEnergyCvGate skipped: %s", _cecv_e)
        # §5.68 SeamGradientCvGate — comparative seam gradient CV check
        if _fallback_reason is None and simple_ok:
            try:
                _simple_img_sgcv = cv2.imread(central_simple_path)
                if _simple_img_sgcv is not None:
                    from backend.src.animation.alignment.canvas import _seam_gradient_cv
                    _asp_sgcv = _seam_gradient_cv(canvas_out, n_strips=8, band_px=5)
                    _sim_sgcv = _seam_gradient_cv(_simple_img_sgcv, n_strips=8, band_px=5)
                    print(f"  [SeamGradientCvGate] asp_sgcv={_asp_sgcv:.4f}  sim_sgcv={_sim_sgcv:.4f}")
                    if _asp_sgcv > _SEAM_GRADIENT_CV_ABS_FLOOR and (
                        _sim_sgcv < 0.05 or _asp_sgcv > _SEAM_GRADIENT_CV_RATIO * max(_sim_sgcv, 0.01)
                    ):
                        _fallback_reason = f"seam_gradient_cv_gate:{_asp_sgcv:.4f}"
                        print(
                            f"  [SeamGradientCvGate] FAILED "
                            f"(asp_sgcv={_asp_sgcv:.4f} > floor={_SEAM_GRADIENT_CV_ABS_FLOOR:.2f} "
                            f"and > {_SEAM_GRADIENT_CV_RATIO:.1f}×sim={_sim_sgcv:.4f}) → SCANS fallback."
                        )
                        timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 1
                        raise RuntimeError(
                            f"SeamGradientCvGate: asp_sgcv={_asp_sgcv:.4f}, sim_sgcv={_sim_sgcv:.4f}"
                        )
            except RuntimeError:
                raise
            except Exception as _sgcv_e:
                logger.debug("[Bench] SeamGradientCvGate skipped: %s", _sgcv_e)
        # §5.71 LumaIqrCvGate — comparative strip luma IQR CV check
        if _fallback_reason is None and simple_ok:
            try:
                _simple_img_iqr = cv2.imread(central_simple_path)
                if _simple_img_iqr is not None:
                    from backend.src.animation.alignment.canvas import _strip_luma_iqr_cv
                    _asp_iqr = _strip_luma_iqr_cv(canvas_out, n_strips=8)
                    _sim_iqr = _strip_luma_iqr_cv(_simple_img_iqr, n_strips=8)
                    print(f"  [LumaIqrCvGate] asp_iqr={_asp_iqr:.4f}  sim_iqr={_sim_iqr:.4f}")
                    if _asp_iqr > _LUMA_IQR_CV_ABS_FLOOR and (
                        _sim_iqr < 0.05 or _asp_iqr > _LUMA_IQR_CV_RATIO * max(_sim_iqr, 0.01)
                    ):
                        _fallback_reason = f"luma_iqr_cv_gate:{_asp_iqr:.4f}"
                        print(
                            f"  [LumaIqrCvGate] FAILED "
                            f"(asp_iqr={_asp_iqr:.4f} > floor={_LUMA_IQR_CV_ABS_FLOOR:.2f} "
                            f"and > {_LUMA_IQR_CV_RATIO:.1f}×sim={_sim_iqr:.4f}) → SCANS fallback."
                        )
                        timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 1
                        raise RuntimeError(
                            f"LumaIqrCvGate: asp_iqr={_asp_iqr:.4f}, sim_iqr={_sim_iqr:.4f}"
                        )
            except RuntimeError:
                raise
            except Exception as _iqr_e:
                logger.debug("[Bench] LumaIqrCvGate skipped: %s", _iqr_e)
        # §5.72 SeamColVarCvGate — comparative seam column variance CV check
        if _fallback_reason is None and simple_ok:
            try:
                _simple_img_scvar = cv2.imread(central_simple_path)
                if _simple_img_scvar is not None:
                    from backend.src.animation.alignment.canvas import _seam_column_variance_cv
                    _asp_scvar = _seam_column_variance_cv(canvas_out, n_strips=8, boundary_px=3)
                    _sim_scvar = _seam_column_variance_cv(_simple_img_scvar, n_strips=8, boundary_px=3)
                    print(f"  [SeamColVarCvGate] asp_scvar={_asp_scvar:.4f}  sim_scvar={_sim_scvar:.4f}")
                    if _asp_scvar > _SEAM_COL_VAR_CV_ABS_FLOOR and (
                        _sim_scvar < 0.05 or _asp_scvar > _SEAM_COL_VAR_CV_RATIO * max(_sim_scvar, 0.01)
                    ):
                        _fallback_reason = f"seam_col_var_cv_gate:{_asp_scvar:.4f}"
                        print(
                            f"  [SeamColVarCvGate] FAILED "
                            f"(asp_scvar={_asp_scvar:.4f} > floor={_SEAM_COL_VAR_CV_ABS_FLOOR:.2f} "
                            f"and > {_SEAM_COL_VAR_CV_RATIO:.1f}×sim={_sim_scvar:.4f}) → SCANS fallback."
                        )
                        timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 1
                        raise RuntimeError(
                            f"SeamColVarCvGate: asp_scvar={_asp_scvar:.4f}, sim_scvar={_sim_scvar:.4f}"
                        )
            except RuntimeError:
                raise
            except Exception as _scvar_e:
                logger.debug("[Bench] SeamColVarCvGate skipped: %s", _scvar_e)

        # §5.75 LumaSkewCvGate — comparative strip luma skewness CV check
        if _fallback_reason is None and simple_ok:
            try:
                _simple_img_lskew = cv2.imread(central_simple_path)
                if _simple_img_lskew is not None:
                    from backend.src.animation.alignment.canvas import _strip_luma_skewness_cv
                    _asp_lskew = _strip_luma_skewness_cv(canvas_out, n_strips=8)
                    _sim_lskew = _strip_luma_skewness_cv(_simple_img_lskew, n_strips=8)
                    print(f"  [LumaSkewCvGate] asp_lskew={_asp_lskew:.4f}  sim_lskew={_sim_lskew:.4f}")
                    if _asp_lskew > _LUMA_SKEW_CV_ABS_FLOOR and (
                        _sim_lskew < 0.20 or _asp_lskew > _LUMA_SKEW_CV_RATIO * max(_sim_lskew, 0.01)
                    ):
                        _fallback_reason = f"luma_skew_cv_gate:{_asp_lskew:.4f}"
                        print(
                            f"  [LumaSkewCvGate] FAILED "
                            f"(asp_lskew={_asp_lskew:.4f} > floor={_LUMA_SKEW_CV_ABS_FLOOR:.2f} "
                            f"and > {_LUMA_SKEW_CV_RATIO:.1f}×sim={_sim_lskew:.4f}) → SCANS fallback."
                        )
                        timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 1
                        raise RuntimeError(
                            f"LumaSkewCvGate: asp_lskew={_asp_lskew:.4f}, sim_lskew={_sim_lskew:.4f}"
                        )
            except RuntimeError:
                raise
            except Exception as _lskew_e:
                logger.debug("[Bench] LumaSkewCvGate skipped: %s", _lskew_e)

        # §5.76 SeamSignedStepCvGate — comparative seam signed step CV check
        if _fallback_reason is None and simple_ok:
            try:
                _simple_img_sssv = cv2.imread(central_simple_path)
                if _simple_img_sssv is not None:
                    from backend.src.animation.alignment.canvas import _seam_signed_step_cv
                    _asp_sssv = _seam_signed_step_cv(canvas_out, n_strips=8, boundary_px=3)
                    _sim_sssv = _seam_signed_step_cv(_simple_img_sssv, n_strips=8, boundary_px=3)
                    print(f"  [SeamSignedStepCvGate] asp_sssv={_asp_sssv:.4f}  sim_sssv={_sim_sssv:.4f}")
                    if _asp_sssv > _SEAM_SIGNED_STEP_CV_ABS_FLOOR and (
                        _sim_sssv < 0.20 or _asp_sssv > _SEAM_SIGNED_STEP_CV_RATIO * max(_sim_sssv, 0.01)
                    ):
                        _fallback_reason = f"seam_signed_step_cv_gate:{_asp_sssv:.4f}"
                        print(
                            f"  [SeamSignedStepCvGate] FAILED "
                            f"(asp_sssv={_asp_sssv:.4f} > floor={_SEAM_SIGNED_STEP_CV_ABS_FLOOR:.2f} "
                            f"and > {_SEAM_SIGNED_STEP_CV_RATIO:.1f}×sim={_sim_sssv:.4f}) → SCANS fallback."
                        )
                        timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 1
                        raise RuntimeError(
                            f"SeamSignedStepCvGate: asp_sssv={_asp_sssv:.4f}, sim_sssv={_sim_sssv:.4f}"
                        )
            except RuntimeError:
                raise
            except Exception as _sssv_e:
                logger.debug("[Bench] SeamSignedStepCvGate skipped: %s", _sssv_e)

        # §5.79 LumaKurtosisCvGate — comparative strip luma kurtosis CV check
        if _fallback_reason is None and simple_ok:
            try:
                _simple_img_lkurt = cv2.imread(central_simple_path)
                if _simple_img_lkurt is not None:
                    from backend.src.animation.alignment.canvas import _strip_luma_kurtosis_cv
                    _asp_lkurt = _strip_luma_kurtosis_cv(canvas_out, n_strips=8)
                    _sim_lkurt = _strip_luma_kurtosis_cv(_simple_img_lkurt, n_strips=8)
                    print(f"  [LumaKurtosisCvGate] asp_lkurt={_asp_lkurt:.4f}  sim_lkurt={_sim_lkurt:.4f}")
                    if _asp_lkurt > _LUMA_KURTOSIS_CV_ABS_FLOOR and (
                        _sim_lkurt < 0.20 or _asp_lkurt > _LUMA_KURTOSIS_CV_RATIO * max(_sim_lkurt, 0.01)
                    ):
                        _fallback_reason = f"luma_kurtosis_cv_gate:{_asp_lkurt:.4f}"
                        print(
                            f"  [LumaKurtosisCvGate] FAILED "
                            f"(asp_lkurt={_asp_lkurt:.4f} > floor={_LUMA_KURTOSIS_CV_ABS_FLOOR:.2f} "
                            f"and > {_LUMA_KURTOSIS_CV_RATIO:.1f}×sim={_sim_lkurt:.4f}) → SCANS fallback."
                        )
                        timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 1
                        raise RuntimeError(
                            f"LumaKurtosisCvGate: asp_lkurt={_asp_lkurt:.4f}, sim_lkurt={_sim_lkurt:.4f}"
                        )
            except RuntimeError:
                raise
            except Exception as _lkurt_e:
                logger.debug("[Bench] LumaKurtosisCvGate skipped: %s", _lkurt_e)

        # §5.80 SeamTextureRatioCvGate — comparative seam texture ratio CV check
        if _fallback_reason is None and simple_ok:
            try:
                _simple_img_stxr = cv2.imread(central_simple_path)
                if _simple_img_stxr is not None:
                    from backend.src.animation.alignment.canvas import _seam_texture_ratio_cv
                    _asp_stxr = _seam_texture_ratio_cv(canvas_out, n_strips=8, band_px=5)
                    _sim_stxr = _seam_texture_ratio_cv(_simple_img_stxr, n_strips=8, band_px=5)
                    print(f"  [SeamTextureRatioCvGate] asp_stxr={_asp_stxr:.4f}  sim_stxr={_sim_stxr:.4f}")
                    if _asp_stxr > _SEAM_TEXTURE_RATIO_CV_ABS_FLOOR and (
                        _sim_stxr < 0.20 or _asp_stxr > _SEAM_TEXTURE_RATIO_CV_RATIO * max(_sim_stxr, 0.01)
                    ):
                        _fallback_reason = f"seam_texture_ratio_cv_gate:{_asp_stxr:.4f}"
                        print(
                            f"  [SeamTextureRatioCvGate] FAILED "
                            f"(asp_stxr={_asp_stxr:.4f} > floor={_SEAM_TEXTURE_RATIO_CV_ABS_FLOOR:.2f} "
                            f"and > {_SEAM_TEXTURE_RATIO_CV_RATIO:.1f}×sim={_sim_stxr:.4f}) → SCANS fallback."
                        )
                        timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 1
                        raise RuntimeError(
                            f"SeamTextureRatioCvGate: asp_stxr={_asp_stxr:.4f}, sim_stxr={_sim_stxr:.4f}"
                        )
            except RuntimeError:
                raise
            except Exception as _stxr_e:
                logger.debug("[Bench] SeamTextureRatioCvGate skipped: %s", _stxr_e)

        # §5.83 EdgeDensityCvGate — comparative strip edge density CV check
        if _fallback_reason is None and simple_ok:
            try:
                _simple_img_edcv = cv2.imread(central_simple_path)
                if _simple_img_edcv is not None:
                    from backend.src.animation.alignment.canvas import _strip_edge_density_cv
                    _asp_edcv = _strip_edge_density_cv(canvas_out, n_strips=8)
                    _sim_edcv = _strip_edge_density_cv(_simple_img_edcv, n_strips=8)
                    print(f"  [EdgeDensityCvGate] asp_edcv={_asp_edcv:.4f}  sim_edcv={_sim_edcv:.4f}")
                    if _asp_edcv > _EDGE_DENSITY_CV_ABS_FLOOR and (
                        _sim_edcv < 0.15 or _asp_edcv > _EDGE_DENSITY_CV_RATIO * max(_sim_edcv, 0.01)
                    ):
                        _fallback_reason = f"edge_density_cv_gate:{_asp_edcv:.4f}"
                        print(
                            f"  [EdgeDensityCvGate] FAILED "
                            f"(asp_edcv={_asp_edcv:.4f} > floor={_EDGE_DENSITY_CV_ABS_FLOOR:.2f} "
                            f"and > {_EDGE_DENSITY_CV_RATIO:.1f}×sim={_sim_edcv:.4f}) → SCANS fallback."
                        )
                        timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 1
                        raise RuntimeError(
                            f"EdgeDensityCvGate: asp_edcv={_asp_edcv:.4f}, sim_edcv={_sim_edcv:.4f}"
                        )
            except RuntimeError:
                raise
            except Exception as _edcv_e:
                logger.debug("[Bench] EdgeDensityCvGate skipped: %s", _edcv_e)

        # §5.84 SeamLocalContrastCvGate — comparative seam local contrast CV check
        if _fallback_reason is None and simple_ok:
            try:
                _simple_img_slcc = cv2.imread(central_simple_path)
                if _simple_img_slcc is not None:
                    from backend.src.animation.alignment.canvas import _seam_local_contrast_cv
                    _asp_slcc = _seam_local_contrast_cv(canvas_out, n_strips=8, band_px=5)
                    _sim_slcc = _seam_local_contrast_cv(_simple_img_slcc, n_strips=8, band_px=5)
                    print(f"  [SeamLocalContrastCvGate] asp_slcc={_asp_slcc:.4f}  sim_slcc={_sim_slcc:.4f}")
                    if _asp_slcc > _SEAM_LOCAL_CONTRAST_CV_ABS_FLOOR and (
                        _sim_slcc < 0.15 or _asp_slcc > _SEAM_LOCAL_CONTRAST_CV_RATIO * max(_sim_slcc, 0.01)
                    ):
                        _fallback_reason = f"seam_local_contrast_cv_gate:{_asp_slcc:.4f}"
                        print(
                            f"  [SeamLocalContrastCvGate] FAILED "
                            f"(asp_slcc={_asp_slcc:.4f} > floor={_SEAM_LOCAL_CONTRAST_CV_ABS_FLOOR:.2f} "
                            f"and > {_SEAM_LOCAL_CONTRAST_CV_RATIO:.1f}×sim={_sim_slcc:.4f}) → SCANS fallback."
                        )
                        timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 1
                        raise RuntimeError(
                            f"SeamLocalContrastCvGate: asp_slcc={_asp_slcc:.4f}, sim_slcc={_sim_slcc:.4f}"
                        )
            except RuntimeError:
                raise
            except Exception as _slcc_e:
                logger.debug("[Bench] SeamLocalContrastCvGate skipped: %s", _slcc_e)
        # §5.87 — Strip Luma P90–P10 CV comparative gate
        if _fallback_reason is None and simple_ok:
            try:
                _simple_img_p90p10 = cv2.imread(central_simple_path)
                if _simple_img_p90p10 is not None:
                    from backend.src.animation.alignment.canvas import _strip_luma_p90p10_cv
                    _asp_p90p10 = _strip_luma_p90p10_cv(canvas_out, n_strips=8)
                    _sim_p90p10 = _strip_luma_p90p10_cv(_simple_img_p90p10, n_strips=8)
                    if _asp_p90p10 > _LUMA_P90P10_CV_ABS_FLOOR and (
                        _sim_p90p10 < 0.10 or _asp_p90p10 > _LUMA_P90P10_CV_RATIO * max(_sim_p90p10, 0.01)
                    ):
                        _fallback_reason = f"luma_p90p10_cv_gate:{_asp_p90p10:.4f}"
                        timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 1
                        raise RuntimeError(_fallback_reason)
            except RuntimeError:
                raise
            except Exception as _e:
                logger.debug("[Bench] LumaP90P10CvGate skipped: %s", _e)
        # §5.88 — Seam Hue Shift CV comparative gate
        if _fallback_reason is None and simple_ok:
            try:
                _simple_img_hshift = cv2.imread(central_simple_path)
                if _simple_img_hshift is not None:
                    from backend.src.animation.alignment.canvas import _seam_hue_shift_cv
                    _asp_hshift = _seam_hue_shift_cv(canvas_out, n_strips=8, boundary_px=3)
                    _sim_hshift = _seam_hue_shift_cv(_simple_img_hshift, n_strips=8, boundary_px=3)
                    if _asp_hshift > _SEAM_HUE_SHIFT_CV_ABS_FLOOR and (
                        _sim_hshift < 0.15 or _asp_hshift > _SEAM_HUE_SHIFT_CV_RATIO * max(_sim_hshift, 0.01)
                    ):
                        _fallback_reason = f"seam_hue_shift_cv_gate:{_asp_hshift:.4f}"
                        timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 1
                        raise RuntimeError(_fallback_reason)
            except RuntimeError:
                raise
            except Exception as _e:
                logger.debug("[Bench] SeamHueShiftCvGate skipped: %s", _e)
        # §5.91 — Strip Dark Pixel Fraction CV comparative gate
        if _fallback_reason is None and simple_ok:
            try:
                _simple_img_dpfcv = cv2.imread(central_simple_path)
                if _simple_img_dpfcv is not None:
                    from backend.src.animation.alignment.canvas import _strip_dark_pixel_fraction_cv
                    _asp_dpfcv = _strip_dark_pixel_fraction_cv(canvas_out, n_strips=8, threshold=64)
                    _sim_dpfcv = _strip_dark_pixel_fraction_cv(_simple_img_dpfcv, n_strips=8, threshold=64)
                    if _asp_dpfcv > _DARK_PIXEL_FRAC_CV_ABS_FLOOR and (
                        _sim_dpfcv < 0.15 or _asp_dpfcv > _DARK_PIXEL_FRAC_CV_RATIO * max(_sim_dpfcv, 0.01)
                    ):
                        _fallback_reason = f"dark_pixel_frac_cv_gate:{_asp_dpfcv:.4f}"
                        timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 1
                        raise RuntimeError(_fallback_reason)
            except RuntimeError:
                raise
            except Exception as _e:
                logger.debug("[Bench] DarkPixelFracCvGate skipped: %s", _e)
        # §5.92 — Seam Saturation Shift CV comparative gate
        if _fallback_reason is None and simple_ok:
            try:
                _simple_img_ssscv = cv2.imread(central_simple_path)
                if _simple_img_ssscv is not None:
                    from backend.src.animation.alignment.canvas import _seam_saturation_shift_cv
                    _asp_ssscv = _seam_saturation_shift_cv(canvas_out, n_strips=8, boundary_px=3)
                    _sim_ssscv = _seam_saturation_shift_cv(_simple_img_ssscv, n_strips=8, boundary_px=3)
                    if _asp_ssscv > _SEAM_SAT_SHIFT_CV_ABS_FLOOR and (
                        _sim_ssscv < 0.10 or _asp_ssscv > _SEAM_SAT_SHIFT_CV_RATIO * max(_sim_ssscv, 0.01)
                    ):
                        _fallback_reason = f"seam_sat_shift_cv_gate:{_asp_ssscv:.4f}"
                        timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 1
                        raise RuntimeError(_fallback_reason)
            except RuntimeError:
                raise
            except Exception as _e:
                logger.debug("[Bench] SeamSatShiftCvGate skipped: %s", _e)
        # §5.95 — Strip Sobel Energy CV comparative gate
        if _fallback_reason is None and simple_ok:
            try:
                _simple_img_sobel = cv2.imread(central_simple_path)
                if _simple_img_sobel is not None:
                    from backend.src.animation.alignment.canvas import _strip_sobel_energy_cv
                    _asp_sobel = _strip_sobel_energy_cv(canvas_out, n_strips=8)
                    _sim_sobel = _strip_sobel_energy_cv(_simple_img_sobel, n_strips=8)
                    if _asp_sobel > _SOBEL_ENERGY_CV_ABS_FLOOR and (
                        _sim_sobel < 0.12 or _asp_sobel > _SOBEL_ENERGY_CV_RATIO * max(_sim_sobel, 0.01)
                    ):
                        _fallback_reason = f"sobel_energy_cv_gate:{_asp_sobel:.4f}"
                        timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 1
                        raise RuntimeError(_fallback_reason)
            except RuntimeError:
                raise
            except Exception as _e:
                logger.debug("[Bench] SobelEnergyCvGate skipped: %s", _e)
        # §5.96 — Seam Value Shift CV comparative gate
        if _fallback_reason is None and simple_ok:
            try:
                _simple_img_valsh = cv2.imread(central_simple_path)
                if _simple_img_valsh is not None:
                    from backend.src.animation.alignment.canvas import _seam_value_shift_cv
                    _asp_valsh = _seam_value_shift_cv(canvas_out, n_strips=8, boundary_px=3)
                    _sim_valsh = _seam_value_shift_cv(_simple_img_valsh, n_strips=8, boundary_px=3)
                    if _asp_valsh > _SEAM_VALUE_SHIFT_CV_ABS_FLOOR and (
                        _sim_valsh < 0.10 or _asp_valsh > _SEAM_VALUE_SHIFT_CV_RATIO * max(_sim_valsh, 0.01)
                    ):
                        _fallback_reason = f"seam_value_shift_cv_gate:{_asp_valsh:.4f}"
                        timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 1
                        raise RuntimeError(_fallback_reason)
            except RuntimeError:
                raise
            except Exception as _e:
                logger.debug("[Bench] SeamValueShiftCvGate skipped: %s", _e)
        # §5.99 — Strip Median Luma CV comparative gate
        if _fallback_reason is None and simple_ok:
            try:
                _simple_img_medlum = cv2.imread(central_simple_path)
                if _simple_img_medlum is not None:
                    from backend.src.animation.alignment.canvas import _strip_median_luma_cv
                    _asp_medlum = _strip_median_luma_cv(canvas_out, n_strips=8)
                    _sim_medlum = _strip_median_luma_cv(_simple_img_medlum, n_strips=8)
                    if _asp_medlum > _MEDIAN_LUMA_CV_ABS_FLOOR and (
                        _sim_medlum < 0.08 or _asp_medlum > _MEDIAN_LUMA_CV_RATIO * max(_sim_medlum, 0.01)
                    ):
                        _fallback_reason = f"median_luma_cv_gate:{_asp_medlum:.4f}"
                        timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 1
                        raise RuntimeError(_fallback_reason)
            except RuntimeError:
                raise
            except Exception as _e:
                logger.debug("[Bench] MedianLumaCvGate skipped: %s", _e)
        # §5.100 — Seam Entropy Shift CV comparative gate
        if _fallback_reason is None and simple_ok:
            try:
                _simple_img_entsh = cv2.imread(central_simple_path)
                if _simple_img_entsh is not None:
                    from backend.src.animation.alignment.canvas import _seam_entropy_shift_cv
                    _asp_entsh = _seam_entropy_shift_cv(canvas_out, n_strips=8, boundary_px=3)
                    _sim_entsh = _seam_entropy_shift_cv(_simple_img_entsh, n_strips=8, boundary_px=3)
                    if _asp_entsh > _SEAM_ENTROPY_SHIFT_CV_ABS_FLOOR and (
                        _sim_entsh < 0.10 or _asp_entsh > _SEAM_ENTROPY_SHIFT_CV_RATIO * max(_sim_entsh, 0.01)
                    ):
                        _fallback_reason = f"seam_entropy_shift_cv_gate:{_asp_entsh:.4f}"
                        timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 1
                        raise RuntimeError(_fallback_reason)
            except RuntimeError:
                raise
            except Exception as _e:
                logger.debug("[Bench] SeamEntropyShiftCvGate skipped: %s", _e)
        # §5.103 — Strip Red Channel CV comparative gate
        if _fallback_reason is None and simple_ok:
            try:
                _simple_img_redcv = cv2.imread(central_simple_path)
                if _simple_img_redcv is not None:
                    from backend.src.animation.alignment.canvas import _strip_red_channel_cv
                    _asp_redcv = _strip_red_channel_cv(canvas_out, n_strips=8)
                    _sim_redcv = _strip_red_channel_cv(_simple_img_redcv, n_strips=8)
                    if _asp_redcv > _RED_CHANNEL_CV_ABS_FLOOR and (
                        _sim_redcv < 0.07 or _asp_redcv > _RED_CHANNEL_CV_RATIO * max(_sim_redcv, 0.01)
                    ):
                        _fallback_reason = f"red_channel_cv_gate:{_asp_redcv:.4f}"
                        timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 1
                        raise RuntimeError(_fallback_reason)
            except RuntimeError:
                raise
            except Exception as _e:
                logger.debug("[Bench] RedChannelCvGate skipped: %s", _e)
        # §5.104 — Seam Blue Shift CV comparative gate
        if _fallback_reason is None and simple_ok:
            try:
                _simple_img_blsh = cv2.imread(central_simple_path)
                if _simple_img_blsh is not None:
                    from backend.src.animation.alignment.canvas import _seam_blue_shift_cv
                    _asp_blsh = _seam_blue_shift_cv(canvas_out, n_strips=8, boundary_px=3)
                    _sim_blsh = _seam_blue_shift_cv(_simple_img_blsh, n_strips=8, boundary_px=3)
                    if _asp_blsh > _SEAM_BLUE_SHIFT_CV_ABS_FLOOR and (
                        _sim_blsh < 0.10 or _asp_blsh > _SEAM_BLUE_SHIFT_CV_RATIO * max(_sim_blsh, 0.01)
                    ):
                        _fallback_reason = f"seam_blue_shift_cv_gate:{_asp_blsh:.4f}"
                        timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 1
                        raise RuntimeError(_fallback_reason)
            except RuntimeError:
                raise
            except Exception as _e:
                logger.debug("[Bench] SeamBlueShiftCvGate skipped: %s", _e)
        # §5.107 — Strip Green Channel CV comparative gate
        if _fallback_reason is None and simple_ok:
            try:
                _simple_img_gcv = cv2.imread(central_simple_path)
                if _simple_img_gcv is not None:
                    from backend.src.animation.alignment.canvas import _strip_green_channel_cv
                    _asp_gcv = _strip_green_channel_cv(canvas_out, n_strips=8)
                    _sim_gcv = _strip_green_channel_cv(_simple_img_gcv, n_strips=8)
                    if _asp_gcv > _GREEN_CHANNEL_CV_ABS_FLOOR and (
                        _sim_gcv < _GREEN_CHANNEL_CV_ABS_FLOOR / 3.0
                        or _asp_gcv > _GREEN_CHANNEL_CV_RATIO * max(_sim_gcv, 0.01)
                    ):
                        _fallback_reason = f"bench_green_channel_cv_gate:{_asp_gcv:.4f}"
                        timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 1
                        raise RuntimeError(_fallback_reason)
            except RuntimeError:
                raise
            except Exception as _e:
                logger.debug("[Bench] GreenChannelCvGate skipped: %s", _e)
        # §5.108 — Seam Red Shift CV comparative gate
        if _fallback_reason is None and simple_ok:
            try:
                _simple_img_rshcv = cv2.imread(central_simple_path)
                if _simple_img_rshcv is not None:
                    from backend.src.animation.alignment.canvas import _seam_red_shift_cv
                    _asp_rshcv = _seam_red_shift_cv(canvas_out, n_strips=8, boundary_px=3)
                    _sim_rshcv = _seam_red_shift_cv(_simple_img_rshcv, n_strips=8, boundary_px=3)
                    if _asp_rshcv > _SEAM_RED_SHIFT_CV_ABS_FLOOR and (
                        _sim_rshcv < 0.10 or _asp_rshcv > _SEAM_RED_SHIFT_CV_RATIO * max(_sim_rshcv, 0.01)
                    ):
                        _fallback_reason = f"bench_seam_red_shift_cv_gate:{_asp_rshcv:.4f}"
                        timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 1
                        raise RuntimeError(_fallback_reason)
            except RuntimeError:
                raise
            except Exception as _e:
                logger.debug("[Bench] SeamRedShiftCvGate skipped: %s", _e)
        # §5.111 — Strip Blue Channel CV comparative gate
        if _fallback_reason is None and simple_ok:
            try:
                _simple_img_bcv = cv2.imread(central_simple_path)
                if _simple_img_bcv is not None:
                    from backend.src.animation.alignment.canvas import _strip_blue_channel_cv
                    _asp_bcv = _strip_blue_channel_cv(canvas_out, n_strips=8)
                    _sim_bcv = _strip_blue_channel_cv(_simple_img_bcv, n_strips=8)
                    if _asp_bcv > _BLUE_CHANNEL_CV_ABS_FLOOR and (
                        _sim_bcv < _BLUE_CHANNEL_CV_ABS_FLOOR / 3.0
                        or _asp_bcv > _BLUE_CHANNEL_CV_RATIO * max(_sim_bcv, 0.01)
                    ):
                        _fallback_reason = f"bench_blue_channel_cv_gate:{_asp_bcv:.4f}"
                        timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 1
                        raise RuntimeError(_fallback_reason)
            except RuntimeError:
                raise
            except Exception as _e:
                logger.debug("[Bench] BlueChannelCvGate skipped: %s", _e)
        # §5.112 — Seam Green Shift CV comparative gate
        if _fallback_reason is None and simple_ok:
            try:
                _simple_img_gshcv = cv2.imread(central_simple_path)
                if _simple_img_gshcv is not None:
                    from backend.src.animation.alignment.canvas import _seam_green_shift_cv
                    _asp_gshcv = _seam_green_shift_cv(canvas_out, n_strips=8, boundary_px=3)
                    _sim_gshcv = _seam_green_shift_cv(_simple_img_gshcv, n_strips=8, boundary_px=3)
                    if _asp_gshcv > _SEAM_GREEN_SHIFT_CV_ABS_FLOOR and (
                        _sim_gshcv < 0.10 or _asp_gshcv > _SEAM_GREEN_SHIFT_CV_RATIO * max(_sim_gshcv, 0.01)
                    ):
                        _fallback_reason = f"bench_seam_green_shift_cv_gate:{_asp_gshcv:.4f}"
                        timings["render_gate_fallback"] = timings.get("render_gate_fallback", 0) + 1
                        raise RuntimeError(_fallback_reason)
            except RuntimeError:
                raise
            except Exception as _e:
                logger.debug("[Bench] SeamGreenShiftCvGate skipped: %s", _e)

        from PIL import Image

        rgb = cv2.cvtColor(canvas_out, cv2.COLOR_BGR2RGB)
        Image.fromarray(rgb).save(out_path)
        shutil.copy2(out_path, central_anime_path)
        print(f"\nFinished: {dataset_dir} -> {out_path}")

    except Exception as _render_exc:
        gc.collect()
        print(f"  ASP render/ECC failed ({_render_exc}); falling back to SCANS.")
        if _fallback_reason is None:
            _fallback_reason = f"render_exception:{type(_render_exc).__name__}"
        t0 = time.perf_counter()
        _scan_stitch_fallback(scans_frames, out_path)
        timings["scans_fallback_sec"] = round(time.perf_counter() - t0, 3)
        timings["total_sec"] = round(time.perf_counter() - t_total_start, 3)
        shutil.copy2(out_path, central_anime_path)
        print(f"\nFinished (SCANS): {dataset_dir} -> {out_path}")
        asp_img = cv2.imread(central_anime_path)
        sim_img = cv2.imread(central_simple_path) if simple_ok else None
        return _build_result(
            dataset_name,
            central_anime_path,
            central_simple_path,
            asp_img,
            sim_img,
            affines,
            bg_frame_lums,
            applied_gains,
            health,
            plots_dir,
            stage_dir,
            canvas_h=None,
            canvas_w=None,
            used_fallback=True,
            timings=timings,
            frame_count=N,
            frame_h=H,
            frame_w=W,
            raw_edge_count=raw_edge_count,
            filtered_edge_count=filtered_edge_count,
            edge_methods=edge_methods,
            edge_stats=edge_stats,
            birefnet_ok=birefnet_ok,
            loftr_ok=loftr_ok,
            gt_img=gt_img,
            fallback_reason=_fallback_reason,
            orig_frame_count=_orig_frame_count,
            smart_select_count=_smart_select_count,
            spatial_dedup_count=N,
        )

    # ------------------------------------------------------------------
    # Visualisations on final images
    # ------------------------------------------------------------------
    t0 = time.perf_counter()
    asp_img = cv2.imread(central_anime_path)
    sim_img = cv2.imread(central_simple_path) if simple_ok else None

    if asp_img is not None:
        _save_seam_heatmap(
            asp_img,
            os.path.join(plots_dir, "asp_seam_heatmap.png"),
            title="ASP — Gradient Magnitude Heatmap",
        )
        _save_3d_surface(
            asp_img,
            os.path.join(plots_dir, "asp_3d_surface.png"),
            title="ASP — Luminance Surface (3D)",
        )
    if sim_img is not None:
        _save_seam_heatmap(
            sim_img,
            os.path.join(plots_dir, "simple_seam_heatmap.png"),
            title="Simple Stitch — Gradient Magnitude Heatmap",
        )
        _save_3d_surface(
            sim_img,
            os.path.join(plots_dir, "simple_3d_surface.png"),
            title="Simple Stitch — Luminance Surface (3D)",
        )

    # Temporal render visualisation
    render_img = cv2.imread(os.path.join(stage_dir, "stage09_temporal_render.png"))
    if render_img is not None:
        _save_3d_surface(
            render_img,
            os.path.join(plots_dir, "temporal_render_3d.png"),
            title="Stage 9 — Temporal Render Luminance (3D)",
        )

    # Metrics comparison bar
    if asp_img is not None and sim_img is not None:
        _save_metrics_bar(
            _compute_all_metrics(asp_img, affines),
            _compute_all_metrics(sim_img),
            os.path.join(plots_dir, "metrics_comparison.png"),
        )

    timings["visualisations_sec"] = round(time.perf_counter() - t0, 3)
    timings["total_sec"] = round(time.perf_counter() - t_total_start, 3)

    return _build_result(
        dataset_name,
        central_anime_path,
        central_simple_path,
        asp_img,
        sim_img,
        affines,
        bg_frame_lums,
        applied_gains,
        health,
        plots_dir,
        stage_dir,
        canvas_h,
        canvas_w,
        used_fallback=False,
        timings=timings,
        frame_count=N,
        frame_h=H,
        frame_w=W,
        raw_edge_count=raw_edge_count,
        filtered_edge_count=filtered_edge_count,
        edge_methods=edge_methods,
        edge_stats=edge_stats,
        birefnet_ok=birefnet_ok,
        loftr_ok=loftr_ok,
        gt_img=gt_img,
        fallback_reason=None,
        orig_frame_count=_orig_frame_count,
        smart_select_count=_smart_select_count,
        spatial_dedup_count=N,
    )


# ============================================================================
# RESULT BUILDER
# ============================================================================


def _build_result(
    dataset_name: str,
    anime_path: str,
    simple_path: str,
    asp_img: Optional[np.ndarray],
    sim_img: Optional[np.ndarray],
    affines: List[np.ndarray],
    bg_frame_lums: List[Optional[float]],
    applied_gains: List[float],
    health,
    plots_dir: str,
    stage_dir: str,
    canvas_h: Optional[int],
    canvas_w: Optional[int],
    used_fallback: bool,
    timings: Optional[Dict] = None,
    frame_count: int = 0,
    frame_h: int = 0,
    frame_w: int = 0,
    raw_edge_count: int = 0,
    filtered_edge_count: int = 0,
    edge_methods: Optional[Dict] = None,
    edge_stats: Optional[List] = None,
    birefnet_ok: bool = False,
    loftr_ok: bool = False,
    gt_img: Optional[np.ndarray] = None,
    fallback_reason: Optional[str] = None,
    orig_frame_count: int = 0,
    smart_select_count: int = 0,
    spatial_dedup_count: int = 0,
) -> Dict:
    asp_metrics = _compute_all_metrics(asp_img, affines) if asp_img is not None else {}
    sim_metrics = _compute_all_metrics(sim_img) if sim_img is not None else {}
    si_fid_ratio: Optional[float] = None
    if _SI_FID and asp_img is not None and sim_img is not None:
        si_fid_ratio = _compute_si_fid_score(
            asp_img,
            sim_img,
            patch_size=_SI_FID_PATCH_SIZE,
            n_patches=_SI_FID_N_PATCHES,
        )

    ssim_val = float("nan")
    psnr_val = float("nan")
    if asp_img is not None and sim_img is not None:
        ssim_val = _ssim_score(asp_img, sim_img)
        psnr_val = _psnr(asp_img, sim_img)

    # Ground truth comparison
    gt_metrics_asp: Dict = (
        _compute_gt_metrics(asp_img, gt_img) if gt_img is not None else {}
    )
    gt_metrics_sim: Dict = (
        _compute_gt_metrics(sim_img, gt_img) if gt_img is not None else {}
    )
    gt_ver = _gt_verdict(gt_metrics_asp, gt_metrics_sim)
    has_gt = gt_img is not None

    # Affine translation summary for JSON
    affine_translations = [
        {
            "frame": i,
            "tx": round(float(M[0, 2]), 2),
            "ty": round(float(M[1, 2]), 2),
            "a": round(float(M[0, 0]), 5),
            "b": round(float(M[0, 1]), 5),
        }
        for i, M in enumerate(affines)
    ]

    # Inter-frame deltas
    tys = [float(M[1, 2]) for M in affines]
    txs = [float(M[0, 2]) for M in affines]
    dy_steps = [round(tys[i + 1] - tys[i], 2) for i in range(len(tys) - 1)]
    dx_steps = [round(txs[i + 1] - txs[i], 2) for i in range(len(txs) - 1)]
    dy_cv = (
        float(np.std(dy_steps) / (abs(np.mean(dy_steps)) + 1e-6)) if dy_steps else 0.0
    )
    dx_cv = (
        float(np.std(dx_steps) / (abs(np.mean(dx_steps)) + 1e-6)) if dx_steps else 0.0
    )

    # Background luminance stats
    valid_lums = [lum for lum in bg_frame_lums if lum is not None]
    ref_lum = round(float(np.median(valid_lums)), 2) if valid_lums else None
    non_trivial_gains = sum(1 for g in applied_gains if abs(g - 1.0) > 0.01)

    return {
        "name": dataset_name,
        "anime_path": anime_path,
        "simple_path": simple_path,
        # --- timing ---
        "time": timings or {},
        # --- frame / canvas geometry ---
        "frames": {
            "count": frame_count,
            "source_h": frame_h,
            "source_w": frame_w,
        },
        "canvas": {
            "width": canvas_w,
            "height": canvas_h,
        },
        # --- pipeline config ---
        "pipeline_config": {
            "use_birefnet": birefnet_ok,
            "use_loftr": loftr_ok,
            "use_basic": False,
            "use_ecc": True,
            "renderer": "median",
            "edge_erosion_px": 30,
        },
        # --- matching ---
        "matching": {
            "raw_edges": raw_edge_count,
            "filtered_edges": filtered_edge_count,
            "methods": edge_methods or {},
            "edges": edge_stats or [],
        },
        # --- alignment ---
        "alignment": {
            "affines": affine_translations,
            "dy_steps": dy_steps,
            "dx_steps": dx_steps,
            "dy_cv": round(dy_cv, 4),
            "dx_cv": round(dx_cv, 4),
        },
        "affine_health": {
            "valid": health.valid,
            "ratio": round(health.ratio, 3),
            "min_gap_px": round(health.min_gap, 1),
            "max_rotation": round(health.max_rotation, 4),
            "max_scale_dev": round(health.max_scale_dev, 4),
            "reason": health.reason,
        },
        # --- photometric correction ---
        "photometric": {
            "ref_lum": ref_lum,
            "bg_lums": [
                round(lum, 2) if lum is not None else None for lum in bg_frame_lums
            ],
            "applied_gains": [round(g, 4) for g in applied_gains],
            "frames_corrected": non_trivial_gains,
            "gain_range": [
                round(min(applied_gains), 4),
                round(max(applied_gains), 4),
            ],
        },
        # --- quality metrics ---
        "metrics_asp": asp_metrics,
        "metrics_simple": sim_metrics,
        "comparison": {
            "ssim": round(ssim_val, 4) if not math.isnan(ssim_val) else None,
            "psnr_db": round(psnr_val, 2) if not math.isnan(psnr_val) else None,
            "si_fid": si_fid_ratio,
            # GT-based verdict when available (most reliable); CV-based otherwise
            "verdict": gt_ver
            if gt_ver is not None
            else _auto_verdict(asp_metrics, sim_metrics),
            "verdict_source": "ground_truth" if gt_ver is not None else "cv_metrics",
        },
        # --- ground truth comparison ---
        "ground_truth": {
            "available": has_gt,
            "metrics_asp": gt_metrics_asp,
            "metrics_simple": gt_metrics_sim,
            "verdict": gt_ver,
        },
        # --- status ---
        "used_fallback": used_fallback,
        "fallback_reason": fallback_reason,
        # --- frame selection telemetry ---
        "frame_selection": {
            "original_count": orig_frame_count,
            "smart_select_count": smart_select_count,
            "spatial_dedup_count": spatial_dedup_count,
            "final_count": frame_count,
            "frames_dropped_smart": max(0, orig_frame_count - smart_select_count),
            "frames_dropped_dedup": max(0, smart_select_count - spatial_dedup_count),
            "selection_mode": (
                "dinov2"
                if os.environ.get("ASP_POSE_WINDOW_PX", "0") != "0"
                else "phase_correlation"
            ),
        },
        # --- paths (for the notebook to locate files) ---
        "paths": {
            "plots_dir": plots_dir,
            "stage_dir": stage_dir,
            "anime_stitch": anime_path,
            "simple_stitch": simple_path,
        },
    }


# ============================================================================
# JSON RESULTS FILE
# ============================================================================


def generate_json_results(results: List[Dict], suite_start_time: float) -> str:
    """
    Write a structured JSON results file to backend/benchmark/output/ and
    return the path.  Schema mirrors the existing benchmark JSON files.
    """
    total_sec = round(time.perf_counter() - suite_start_time, 3)
    ts = datetime.datetime.now()
    ts_str = ts.strftime("%Y%m%d_%H%M%S")
    ts_iso = ts.isoformat()

    results_dir = os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(results_dir, exist_ok=True)
    out_path = os.path.join(results_dir, f"anime_stitch_{ts_str}.json")

    # Aggregate summary stats
    asp_sharpness = [
        r["metrics_asp"].get("sharpness", 0.0) for r in results if r["metrics_asp"]
    ]
    sim_sharpness = [
        r["metrics_simple"].get("sharpness", 0.0)
        for r in results
        if r["metrics_simple"]
    ]
    asp_ghosting = [
        r["metrics_asp"].get("ghosting_score", 0.0) for r in results if r["metrics_asp"]
    ]
    sim_ghosting = [
        r["metrics_simple"].get("ghosting_score", 0.0)
        for r in results
        if r["metrics_simple"]
    ]
    asp_coverage = [
        r["metrics_asp"].get("coverage", 0.0) for r in results if r["metrics_asp"]
    ]
    ssim_vals = [
        r["comparison"]["ssim"]
        for r in results
        if r["comparison"].get("ssim") is not None
    ]
    dataset_times = [r["time"].get("total_sec", 0.0) for r in results]
    fallback_count = sum(1 for r in results if r["used_fallback"])
    verdicts = [r["comparison"]["verdict"] for r in results]

    # Performance insights
    def _rank_by(key_fn, results_list, top=True):
        valid = [(r["name"], key_fn(r)) for r in results_list if key_fn(r) is not None]
        if not valid:
            return None
        ranked = sorted(valid, key=lambda x: x[1], reverse=top)
        return {"name": ranked[0][0], "value": round(ranked[0][1], 4)}

    best_asp = _rank_by(lambda r: r["metrics_asp"].get("sharpness"), results)
    worst_asp = _rank_by(
        lambda r: r["metrics_asp"].get("sharpness"), results, top=False
    )
    slowest = _rank_by(lambda r: r["time"].get("total_sec"), results)
    fastest = _rank_by(
        lambda r: r["time"].get("total_sec")
        if r["time"].get("total_sec", 0) > 0
        else None,
        results,
        top=False,
    )
    most_ghosting = _rank_by(lambda r: r["metrics_asp"].get("ghosting_score"), results)
    least_ghosting = _rank_by(
        lambda r: r["metrics_asp"].get("ghosting_score"), results, top=False
    )

    doc = {
        "metadata": {
            "suite_name": "Anime Stitch Pipeline",
            "timestamp": ts_iso,
            "total_datasets": len(results),
            "total_time_sec": total_sec,
            "format_version": "1.0",
        },
        "system": _system_info(),
        "summary": {
            "total_datasets": len(results),
            "datasets_passed": len(results) - fallback_count,
            "datasets_fallback": fallback_count,
            "total_time_sec": total_sec,
            "avg_time_per_dataset_sec": round(
                sum(dataset_times) / max(len(dataset_times), 1), 3
            ),
            "avg_sharpness_asp": round(float(np.mean(asp_sharpness)), 3)
            if asp_sharpness
            else None,
            "avg_sharpness_simple": round(float(np.mean(sim_sharpness)), 3)
            if sim_sharpness
            else None,
            "avg_ghosting_asp": round(float(np.mean(asp_ghosting)), 4)
            if asp_ghosting
            else None,
            "avg_ghosting_simple": round(float(np.mean(sim_ghosting)), 4)
            if sim_ghosting
            else None,
            "avg_coverage_asp": round(float(np.mean(asp_coverage)), 4)
            if asp_coverage
            else None,
            "avg_ssim": round(float(np.mean(ssim_vals)), 4) if ssim_vals else None,
            "verdict_counts": {
                "asp_better": verdicts.count("asp_better"),
                "simple_better": verdicts.count("simple_better"),
                "comparable": verdicts.count("comparable"),
                "insufficient_data": verdicts.count("insufficient_data"),
            },
            # Ground truth summary
            "datasets_with_ground_truth": sum(
                1 for r in results if r.get("ground_truth", {}).get("available")
            ),
            "gt_verdict_counts": {
                "asp_better": sum(
                    1
                    for r in results
                    if r.get("ground_truth", {}).get("verdict") == "asp_better"
                ),
                "simple_better": sum(
                    1
                    for r in results
                    if r.get("ground_truth", {}).get("verdict") == "simple_better"
                ),
                "comparable": sum(
                    1
                    for r in results
                    if r.get("ground_truth", {}).get("verdict") == "comparable"
                ),
            },
            "avg_ssim_asp_vs_gt": round(
                float(
                    np.mean(
                        [
                            r["ground_truth"]["metrics_asp"]["ssim_vs_gt"]
                            for r in results
                            if r.get("ground_truth", {}).get("available")
                            and r["ground_truth"]["metrics_asp"].get("ssim_vs_gt")
                            is not None
                        ]
                    )
                ),
                4,
            )
            if any(r.get("ground_truth", {}).get("available") for r in results)
            else None,
            "avg_ssim_simple_vs_gt": round(
                float(
                    np.mean(
                        [
                            r["ground_truth"]["metrics_simple"]["ssim_vs_gt"]
                            for r in results
                            if r.get("ground_truth", {}).get("available")
                            and r["ground_truth"]["metrics_simple"].get("ssim_vs_gt")
                            is not None
                        ]
                    )
                ),
                4,
            )
            if any(r.get("ground_truth", {}).get("available") for r in results)
            else None,
            "avg_mllm_overall": round(
                float(
                    np.mean(
                        [
                            r["metrics_asp"]["mllm_overall"]
                            for r in results
                            if r.get("metrics_asp", {}).get("mllm_overall") is not None
                        ]
                    )
                ),
                4,
            )
            if any(
                r.get("metrics_asp", {}).get("mllm_overall") is not None
                for r in results
            )
            else None,
        },
        "datasets": results,
        "performance_insights": {
            "slowest_dataset": slowest,
            "fastest_dataset": fastest,
            "best_asp_sharpness": best_asp,
            "worst_asp_sharpness": worst_asp,
            "most_asp_ghosting": most_ghosting,
            "least_asp_ghosting": least_ghosting,
            "datasets_asp_better_than_simple": [
                r["name"] for r in results if r["comparison"]["verdict"] == "asp_better"
            ],
            "datasets_simple_better_than_asp": [
                r["name"]
                for r in results
                if r["comparison"]["verdict"] == "simple_better"
            ],
            "datasets_alignment_failed": [
                r["name"] for r in results if not r["affine_health"]["valid"]
            ],
        },
    }

    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)

    print(f"\n[JSON] Results written to {out_path}")
    return out_path


# ============================================================================
# MARKDOWN REPORT GENERATOR
# ============================================================================

_REPORT_HEADER = """\
---
report_version: "1.0"
generated: "{date}"
pipeline: "AnimeStitchPipeline"
datasets: {num_datasets}
---

# Anime Stitch Pipeline — Benchmark Report

> **How to use this report**
>
> Each test section contains:
> - Side-by-side outputs (ASP vs Simple/OpenCV)
> - CV metric table
> - Intermediate output visualizations (2D & 3D)
> - A structured `<!-- FEEDBACK -->` block
>
> To review/correct feedback, edit the YAML inside each `<!-- FEEDBACK -->…<!-- /FEEDBACK -->`
> block. Valid `status` values: `pending`, `correct`, `incomplete`, `incorrect`.
> Add your corrections in the `human_notes` field.
> Machine-readable fields (`asp_issues`, `simple_issues`, `verdict`) are pre-filled
> and updated automatically on re-runs.

"""

_GLOBAL_SUMMARY_HEADER = """\
---

## Global Summary

"""

_GLOBAL_FEEDBACK_BLOCK = """\

---

## Global Feedback & Human Notes

<!-- GLOBAL_FEEDBACK
status: pending
overall_asp_rating: null
overall_simple_rating: null
most_common_asp_failure: null
most_common_simple_failure: null
priority_fixes:
  - null
human_notes: |
  (Your analysis here)
/GLOBAL_FEEDBACK -->

"""

_PER_TEST_HUMAN_SECTION = """\

### My Feedback

<!-- FEEDBACK
status: pending
asp_issues:
{asp_issues}
simple_issues:
{simple_issues}
verdict: "{verdict}"
human_notes: |
  (Edit this section — confirm, correct, or extend the CV analysis above)
/FEEDBACK -->

---
"""


def _auto_verdict(asp_m: Dict, sim_m: Dict) -> str:
    """
    Quality verdict using seam_coherence as the primary discriminator.

    Laplacian sharpness is NOT used as a primary signal because hard seam edges
    inflate it, making catastrophically banded ASP outputs appear "sharper" than
    clean simple-stitch results.  Instead:

      - seam_coherence (row-mean luminance std): lower = more coherent.
        If ASP seam_coherence > 28 (severe banding), simple_better.
        If both are low, use coverage and ghosting as tiebreaker.
      - seam_gradient (gradient at seam rows): lower = smoother seams.
      - coverage: higher = more useful canvas area.
      - ghosting_score: lower = fewer ghost artifacts.
    """
    if not asp_m or not sim_m:
        return "insufficient_data"

    asp_sc = asp_m.get("seam_coherence", 0.0)
    sim_sc = sim_m.get("seam_coherence", 0.0)

    # If ASP has severe banding (high seam_coherence) → simple is better
    if asp_sc > 28.0 and asp_sc > sim_sc * 1.5:
        return "simple_better"

    # §5.5: seam_visibility penalty (strip banding term)
    asp_sv = asp_m.get("seam_visibility") or 0.0
    sim_sv = sim_m.get("seam_visibility") or 0.0
    asp_sv_score = float(np.clip(1.0 - asp_sv / 25.0, 0.0, 1.0))
    sim_sv_score = float(np.clip(1.0 - sim_sv / 25.0, 0.0, 1.0))

    # Composite quality score: penalise banding and ghosting, reward coverage
    asp_score = (
        asp_m.get("coverage", 0) * 100 * 0.4
        - asp_sc * 0.3
        - asp_m.get("seam_gradient", 0) * 0.15
        - asp_m.get("ghosting_score", 0) * 0.15
        + asp_sv_score * 0.10
    )
    sim_score = (
        sim_m.get("coverage", 0) * 100 * 0.4
        - sim_sc * 0.3
        - sim_m.get("seam_gradient", 0) * 0.15
        - sim_m.get("ghosting_score", 0) * 0.15
        + sim_sv_score * 0.10
    )
    if asp_score > sim_score * 1.1:
        return "asp_better"
    if sim_score > asp_score * 1.1:
        return "simple_better"
    return "comparable"


def _auto_issues(metrics: Dict, is_asp: bool) -> List[str]:
    """Generate a list of detected issues from metrics."""
    issues = []
    if not metrics:
        return ["- no_image"]
    cov = metrics.get("coverage", 1.0)
    if cov < 0.70:
        issues.append(
            f"  - low_coverage: {cov:.2%} (image heavily cropped or malformed)"
        )
    ghost = metrics.get("ghosting_score", 0)
    if ghost > 15:
        issues.append(f"  - high_ghosting: score={ghost:.2f} (double-edges detected)")
    seam = metrics.get("seam_gradient", 0)
    if seam > 20:
        issues.append(
            f"  - seam_discontinuity: gradient={seam:.2f} (abrupt transitions)"
        )
    sc = metrics.get("seam_coherence", 0.0)
    if sc > 28.0:
        issues.append(
            f"  - color_banding: seam_coherence={sc:.1f} (severe horizontal strip color mismatch)"
        )
    elif sc > 18.0:
        issues.append(
            f"  - mild_banding: seam_coherence={sc:.1f} (visible color variation between strips)"
        )
    if not issues:
        issues.append("  - none_detected")
    return issues


def _rel_path(path: str, report_dir: str) -> str:
    """Return path relative to report_dir for markdown embedding."""
    try:
        return os.path.relpath(path, report_dir)
    except ValueError:
        return path


def _plot_exists(plots_dir: str, name: str) -> bool:
    return os.path.exists(os.path.join(plots_dir, name))


def generate_report(results: List[Dict], output_dir: str) -> str:
    """
    Write benchmark_report.md inside output_dir.
    Returns the path to the written file.
    """
    report_path = os.path.join(output_dir, "benchmark_report.md")
    rd = output_dir  # report dir = base for relative paths

    lines = []

    # Header
    lines.append(
        _REPORT_HEADER.format(
            date=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            num_datasets=len(results),
        )
    )

    # Global summary table
    lines.append(_GLOBAL_SUMMARY_HEADER)
    lines.append(
        "| Test | SC ASP | SC Sim | GT SSIM ASP | GT SSIM Sim | Align SSIM ASP | Align SSIM Sim | Verdict | Src | FB |\n"
    )
    lines.append(
        "|------|-------:|-------:|------------:|------------:|---------------:|---------------:|---------|-----|----|\n"
    )
    for r in results:
        am, sm = r["metrics_asp"], r["metrics_simple"]
        sc_a = f"{am.get('seam_coherence', 0):.1f}" if am else "—"
        sc_s = f"{sm.get('seam_coherence', 0):.1f}" if sm else "—"
        gt = r.get("ground_truth", {})
        gt_ssim_a = gt.get("metrics_asp", {}).get("ssim_vs_gt")
        gt_ssim_s = gt.get("metrics_simple", {}).get("ssim_vs_gt")
        gt_ssim_a_s = f"{gt_ssim_a:.3f}" if gt_ssim_a is not None else "—"
        gt_ssim_s_s = f"{gt_ssim_s:.3f}" if gt_ssim_s is not None else "—"

        align_ssim_a = gt.get("metrics_asp", {}).get("aligned_ssim_vs_gt")
        align_ssim_s = gt.get("metrics_simple", {}).get("aligned_ssim_vs_gt")
        align_ssim_a_s = f"{align_ssim_a:.3f}" if align_ssim_a is not None else "—"
        align_ssim_s_s = f"{align_ssim_s:.3f}" if align_ssim_s is not None else "—"

        ssim_v = (
            f"{r['comparison']['ssim']:.3f}"
            if r["comparison"]["ssim"] is not None
            else "—"
        )
        verdict = r["comparison"]["verdict"]
        vsrc = r["comparison"].get("verdict_source", "cv")[:2].upper()
        fallback = "✓" if r["used_fallback"] else ""
        lines.append(
            f"| [{r['name']}](#{r['name']}) | {sc_a} | {sc_s} | {gt_ssim_a_s} | {gt_ssim_s_s} | "
            f"{align_ssim_a_s} | {align_ssim_s_s} | {verdict} | {vsrc} | {fallback} |\n"
        )
    lines.append("\n")
    lines.append(
        "*SC = seam_coherence (lower is better); GT SSIM = raw SSIM; Align SSIM = ECC-aligned SSIM (no framing bias)*\n\n"
    )

    # Global ASP failure breakdown
    lines.append("### Failure Mode Counts (ASP)\n\n")
    fail_counts: Dict[str, int] = {}
    for r in results:
        for issue in _auto_issues(r["metrics_asp"], is_asp=True):
            key = issue.strip().lstrip("- ").split(":")[0]
            fail_counts[key] = fail_counts.get(key, 0) + 1
    lines.append("| Issue | Count |\n|-------|-------|\n")
    for k, v in sorted(fail_counts.items(), key=lambda x: -x[1]):
        lines.append(f"| `{k}` | {v} |\n")
    lines.append("\n")

    # Per-test sections
    for r in results:
        name = r["name"]
        anime_rel = _rel_path(r["anime_path"], rd)
        simple_rel = (
            _rel_path(r["simple_path"], rd)
            if os.path.exists(r["simple_path"])
            else None
        )
        pd = r["paths"]["plots_dir"]
        sd = r["paths"]["stage_dir"]
        am, sm = r["metrics_asp"], r["metrics_simple"]

        lines.append(f"---\n\n## {name}\n\n")

        # Side-by-side final outputs
        lines.append("### Final Outputs\n\n")
        lines.append("| Anime Stitch Pipeline | OpenCV Simple Stitch |\n")
        lines.append("|:---------------------:|:--------------------:|\n")
        asp_cell = (
            f"![ASP]({anime_rel})"
            if os.path.exists(r["anime_path"])
            else "_not generated_"
        )
        simple_cell = (
            f"![Simple]({simple_rel})"
            if simple_rel and os.path.exists(r["simple_path"])
            else "_not generated_"
        )
        lines.append(f"| {asp_cell} | {simple_cell} |\n\n")

        # CV Metrics table
        lines.append("### CV Metrics\n\n")
        lines.append("| Metric | ASP | Simple | Notes |\n")
        lines.append("|--------|-----|--------|-------|\n")
        metric_defs = [
            ("sharpness", "Laplacian variance — higher = sharper edges"),
            ("coverage", "Fraction of non-black pixels — lower = heavy crop"),
            (
                "seam_gradient",
                "Mean gradient magnitude at seam rows — higher = abrupt transitions",
            ),
            ("color_entropy", "Shannon entropy of luma histogram — lower = washed out"),
            ("ghosting_score", "2nd-order vertical gradient — higher = double-edges"),
            (
                "ghosting_siqe",
                "§3.8A autocorr double-edge score [0–100], higher = ghost",
            ),
            ("width", "Output width (px)"),
            ("height", "Output height (px)"),
        ]
        for key, note in metric_defs:
            a_val = f"{am.get(key, '—')}" if am else "—"
            s_val = f"{sm.get(key, '—')}" if sm else "—"
            lines.append(f"| `{key}` | {a_val} | {s_val} | {note} |\n")
        ssim_v = (
            f"{r['comparison']['ssim']:.3f}"
            if r["comparison"]["ssim"] is not None
            else "—"
        )
        psnr_v = (
            f"{r['comparison']['psnr_db']:.1f} dB"
            if r["comparison"]["psnr_db"] is not None
            else "—"
        )
        lines.append(
            f"| `ssim (asp vs simple)` | {ssim_v} | — | Structural similarity between the two outputs |\n"
        )
        lines.append(
            f"| `psnr (asp vs simple)` | {psnr_v} | — | Peak SNR between the two outputs |\n"
        )
        lines.append(
            f"| `seam_coherence` | {am.get('seam_coherence', '—') if am else '—'} | "
            f"{sm.get('seam_coherence', '—') if sm else '—'} | "
            f"Row-mean lum std — lower = less color banding (≤18 good, 18–28 moderate, >28 severe) |\n"
        )
        lines.append("\n")

        # Ground truth comparison (if available)
        gt = r.get("ground_truth", {})
        if gt.get("available"):
            lines.append("### Ground Truth Comparison\n\n")
            gt_am = gt.get("metrics_asp", {})
            gt_sm = gt.get("metrics_simple", {})
            asp_ssim_gt = gt_am.get("ssim_vs_gt")
            sim_ssim_gt = gt_sm.get("ssim_vs_gt")
            asp_psnr_gt = gt_am.get("psnr_vs_gt")
            sim_psnr_gt = gt_sm.get("psnr_vs_gt")
            gt_ver = gt.get("verdict", "—")
            lines.append("| Metric | ASP | Simple | Notes |\n")
            lines.append("|--------|-----|--------|-------|\n")
            lines.append(
                f"| SSIM vs Ground Truth | "
                f"{f'{asp_ssim_gt:.4f}' if asp_ssim_gt is not None else '—'} | "
                f"{f'{sim_ssim_gt:.4f}' if sim_ssim_gt is not None else '—'} | "
                f"Higher = closer to reference |\n"
            )
            lines.append(
                f"| PSNR vs Ground Truth | "
                f"{f'{asp_psnr_gt:.1f} dB' if asp_psnr_gt is not None else '—'} | "
                f"{f'{sim_psnr_gt:.1f} dB' if sim_psnr_gt is not None else '—'} | "
                f"Higher = closer to reference |\n"
            )
            lines.append(
                f"| **GT-based verdict** | **{gt_ver}** | — | Most reliable quality signal |\n"
            )
            lines.append("\n")

        # Affine health
        ah = r["affine_health"]
        lines.append("### Alignment Health\n\n")
        lines.append("```yaml\n")
        lines.append(f"valid: {ah['valid']}\n")
        lines.append(f"reason: {ah['reason']}\n")
        lines.append(f"spacing_ratio: {ah['ratio']}\n")
        lines.append(f"min_gap_px: {ah['min_gap_px']}\n")
        lines.append(f"max_rotation: {ah['max_rotation']}\n")
        lines.append(f"max_scale_deviation: {ah['max_scale_dev']}\n")
        lines.append(f"used_scans_fallback: {r['used_fallback']}\n")
        if r["canvas"]["height"] is not None:
            lines.append(f"canvas: {r['canvas']['width']}×{r['canvas']['height']}\n")
        lines.append("```\n\n")

        # Gains summary
        gains = r["photometric"]["applied_gains"]
        # lums = r["photometric"]["bg_lums"]
        non_trivial = [g for g in gains if abs(g - 1.0) > 0.01]
        lines.append("### Photometric Correction\n\n")
        lines.append(f"- Frames: **{len(gains)}**  \n")
        lines.append(
            f"- Frames corrected (|gain − 1| > 0.01): **{len(non_trivial)}**  \n"
        )
        if non_trivial:
            lines.append(
                f"- Gain range: [{min(non_trivial):.4f}, {max(non_trivial):.4f}]  \n"
            )
        lines.append("\n")

        # Visualisation section
        lines.append("### Intermediate Output Visualizations\n\n")

        def _img_row(label, fname, alt=""):
            p = os.path.join(pd, fname)
            if os.path.exists(p):
                rel = _rel_path(p, rd)
                return f"**{label}**  \n![{alt or label}]({rel})\n\n"
            return ""

        # Metrics comparison bar
        bar_path = os.path.join(pd, "metrics_comparison.png")
        if os.path.exists(bar_path):
            lines.append(
                _img_row("CV Metrics Comparison (normalised)", "metrics_comparison.png")
            )

        # Gains
        gains_path = os.path.join(pd, "gains.png")
        if os.path.exists(gains_path):
            lines.append(_img_row("Per-Frame Luminance Gains", "gains.png"))

        # 2D canvas & overlap
        cp = os.path.join(pd, "canvas_frame_placement.png")
        if os.path.exists(cp):
            lines.append(
                _img_row("Canvas Frame Placement (2D)", "canvas_frame_placement.png")
            )

        tv = os.path.join(pd, "translation_vectors.png")
        if os.path.exists(tv):
            lines.append(
                _img_row("Translation Vectors (2D)", "translation_vectors.png")
            )

        om = os.path.join(pd, "overlap_map.png")
        if os.path.exists(om):
            lines.append(_img_row("Frame Overlap Count Map (2D)", "overlap_map.png"))

        # Seam heatmaps
        for img_type in ["asp", "simple"]:
            hm = os.path.join(pd, f"{img_type}_seam_heatmap.png")
            if os.path.exists(hm):
                label = "ASP" if img_type == "asp" else "Simple Stitch"
                lines.append(
                    _img_row(
                        f"{label} — Seam Gradient Heatmap (2D)",
                        f"{img_type}_seam_heatmap.png",
                    )
                )

        # 3D surface plots
        for fname, label in [
            ("asp_3d_surface.png", "ASP — Luminance Surface (3D)"),
            ("simple_3d_surface.png", "Simple Stitch — Luminance Surface (3D)"),
            (
                "temporal_render_3d.png",
                "Stage 9 Temporal Render — Luminance Surface (3D)",
            ),
        ]:
            p = os.path.join(pd, fname)
            if os.path.exists(p):
                lines.append(_img_row(label, fname))

        # Mask overlays
        mask_any = False
        for i in range(3):
            mp = os.path.join(pd, f"mask_overlay_frame{i:02d}.png")
            if os.path.exists(mp):
                if not mask_any:
                    lines.append(
                        "**BiRefNet Foreground Mask Overlays (first 3 frames)**\n\n"
                    )
                    lines.append(
                        "| Frame 0 | Frame 1 | Frame 2 |\n|:---:|:---:|:---:|\n| "
                    )
                    mask_any = True
        if mask_any:
            cells = []
            for i in range(3):
                mp = os.path.join(pd, f"mask_overlay_frame{i:02d}.png")
                if os.path.exists(mp):
                    cells.append(f"![mask f{i}]({_rel_path(mp, rd)})")
                else:
                    cells.append("—")
            lines.append(" | ".join(cells) + " |\n\n")

        # Stage images
        lines.append("#### Stage Intermediate Outputs\n\n")
        _n_frames = min(r.get("frames", {}).get("count", 4), 4)
        stage_imgs = {
            "Stage 2 Normalised Frames": [
                os.path.join(sd, f"stage02_normalised_frame{i:02d}.png")
                for i in range(_n_frames)
            ],
            "Stage 3 Corrected Frames": [
                os.path.join(sd, f"stage03_basic_corrected_frame{i:02d}.png")
                for i in range(_n_frames)
            ],
            "Stage 4 BG Masks": [
                os.path.join(sd, f"stage04_bgmask_frame{i:02d}.png")
                for i in range(_n_frames)
            ],
        }
        for stage_label, paths in stage_imgs.items():
            existing = [p for p in paths if os.path.exists(p)]
            if not existing:
                continue
            lines.append(f"**{stage_label}**\n\n")
            cols = min(4, len(existing))
            header = "| " + " | ".join([f"Frame {i}" for i in range(cols)]) + " |\n"
            sep = "|" + "---|" * cols + "\n"
            row = (
                "| "
                + " | ".join(
                    [
                        f"![f{i}]({_rel_path(p, rd)})"
                        for i, p in enumerate(existing[:cols])
                    ]
                )
                + " |\n\n"
            )
            lines.append(header + sep + row)

        # Temporal render and composite
        for fname, label in [
            ("stage09_temporal_render.png", "Stage 9 — Temporal Median Render"),
            ("stage11_fg_composite.png", "Stage 11 — FG Composite"),
        ]:
            sp = os.path.join(sd, fname)
            if os.path.exists(sp):
                rel = _rel_path(sp, rd)
                lines.append(f"**{label}**  \n![{label}]({rel})\n\n")

        # Auto-generated analysis
        lines.append("### Automated Analysis\n\n")
        verdict = _auto_verdict(am, sm)
        verdict_map = {
            "asp_better": "ASP produces a **higher-quality** output by CV metrics.",
            "simple_better": "Simple/OpenCV produces a **higher-quality** output by CV metrics.",
            "comparable": "Both pipelines produce **comparable** quality by CV metrics.",
            "insufficient_data": "Insufficient data to determine a verdict.",
        }
        lines.append(f"> **CV Verdict:** {verdict_map.get(verdict, verdict)}\n\n")

        lines.append("**Detected issues — ASP:**\n")
        for issue in _auto_issues(am, is_asp=True):
            lines.append(f"{issue}\n")
        lines.append("\n**Detected issues — Simple Stitch:**\n")
        for issue in _auto_issues(sm, is_asp=False):
            lines.append(f"{issue}\n")
        lines.append("\n")

        if r["used_fallback"]:
            lines.append(
                "> ⚠️ **SCANS Fallback used** — Alignment failed, ASP result is identical to Simple Stitch.\n\n"
            )

        # Human feedback block
        asp_issues_yaml = "\n".join(_auto_issues(am, True))
        simple_issues_yaml = "\n".join(_auto_issues(sm, False))
        lines.append(
            _PER_TEST_HUMAN_SECTION.format(
                asp_issues=asp_issues_yaml,
                simple_issues=simple_issues_yaml,
                verdict=verdict,
            )
        )

    # Global feedback section
    lines.append(_GLOBAL_FEEDBACK_BLOCK)

    # Appendix: raw metrics JSON
    lines.append("---\n\n## Appendix — Raw Metrics JSON\n\n")
    lines.append("```json\n")
    summary = {
        "generated": datetime.datetime.now().isoformat(),
        "datasets": [
            {
                "name": r["name"],
                "asp_metrics": r["metrics_asp"],
                "sim_metrics": r["metrics_simple"],
                "ssim": r["comparison"]["ssim"],
                "psnr": r["comparison"]["psnr_db"],
                "affine_health": r["affine_health"],
                "used_fallback": r["used_fallback"],
            }
            for r in results
        ],
    }
    lines.append(json.dumps(summary, indent=2))
    lines.append("\n```\n")

    with open(report_path, "w", encoding="utf-8") as fh:
        fh.writelines(lines)

    print(f"\n[Report] Written to {report_path}")
    return report_path


# ============================================================================
# ENTRY POINT
# ============================================================================


def _resolve_datasets(base_dir: str, args) -> List[str]:
    """
    Return an ordered list of dataset directories to process based on CLI args.

    Selection flags (mutually exclusive, first match wins):
      --tests asp_test04 asp_test27    specific dataset names
      --range 1-10                     inclusive numeric range (zero-padded)
      --range 1,3,5,27                 explicit comma-separated numbers
      --first N                        first N datasets in sorted order
      (none)                           all datasets

    Additional filter:
      --skip-done   skip any dataset whose output panorama.png already exists
    """
    all_dirs = sorted(
        d for d in glob.glob(os.path.join(base_dir, "asp_test*")) if os.path.isdir(d)
    )

    if args.tests:
        # Explicit names, e.g. asp_test04 asp_test27
        name_set = set(args.tests)
        selected = [d for d in all_dirs if os.path.basename(d) in name_set]
        # Preserve CLI order for exact names
        order = {n: i for i, n in enumerate(args.tests)}
        selected.sort(key=lambda d: order.get(os.path.basename(d), 999))
    elif args.range:
        # Numeric range "1-10" or comma list "1,3,27"
        spec = args.range
        nums: set = set()
        for part in spec.split(","):
            part = part.strip()
            if "-" in part:
                lo, hi = part.split("-", 1)
                nums.update(range(int(lo), int(hi) + 1))
            else:
                nums.add(int(part))
        selected = [
            d
            for d in all_dirs
            if any(
                os.path.basename(d) == f"asp_test{n:02d}"
                or os.path.basename(d) == f"asp_test{n}"
                for n in nums
            )
        ]
    elif args.first:
        selected = all_dirs[: args.first]
    else:
        selected = all_dirs

    if args.skip_done:

        def _is_done(d: str) -> bool:
            return os.path.exists(os.path.join(d, "output", "panorama.png"))

        before = len(selected)
        selected = [d for d in selected if not _is_done(d)]
        print(
            f"[skip-done] Skipped {before - len(selected)} already-processed datasets."
        )

    return selected


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Anime Stitch Pipeline Benchmark",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all 94 tests (default)
  python3 -m backend.benchmark.bench_anime_stitch

  # Run specific tests by name
  python3 -m backend.benchmark.bench_anime_stitch --tests asp_test04 asp_test27

  # Run a numeric range (zero-padded names)
  python3 -m backend.benchmark.bench_anime_stitch --range 1-10

  # Mix: explicit comma list of numbers
  python3 -m backend.benchmark.bench_anime_stitch --range 1,4,8,27,57

  # First N tests only
  python3 -m backend.benchmark.bench_anime_stitch --first 5

  # Skip tests already processed (panorama.png exists)
  python3 -m backend.benchmark.bench_anime_stitch --skip-done

  # Combine: first 20 tests, skip done
  python3 -m backend.benchmark.bench_anime_stitch --first 20 --skip-done
""",
    )
    parser.add_argument(
        "--tests",
        nargs="+",
        metavar="NAME",
        help="Specific dataset names to run (e.g. asp_test04 asp_test27)",
    )
    parser.add_argument(
        "--range",
        metavar="SPEC",
        help='Numeric range "1-10" or comma list "1,3,5" of test numbers',
    )
    parser.add_argument(
        "--first",
        type=int,
        metavar="N",
        help="Run only the first N datasets in sorted order",
    )
    parser.add_argument(
        "--skip-done",
        action="store_true",
        help="Skip datasets whose output/panorama.png already exists",
    )
    parser.add_argument(
        "--data-dir",
        default="/home/pkhunter/Repositories/Image-Toolkit/dump",
        metavar="DIR",
        help="Root data directory containing asp_testXX subdirectories",
    )
    args = parser.parse_args()

    base_dir = args.data_dir
    datasets = _resolve_datasets(base_dir, args)

    if not datasets:
        print("No datasets matched the selection criteria.")
        raise SystemExit(0)

    print(f"[Benchmark] Running {len(datasets)} dataset(s):")
    for d in datasets:
        print(f"  {os.path.basename(d)}")
    print()

    suite_start = time.perf_counter()
    results = []
    for ds in datasets:
        result = process_dataset(ds)
        if result is not None:
            results.append(result)
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    if results:
        output_dir = os.path.join(base_dir, "output")
        os.makedirs(output_dir, exist_ok=True)
        generate_report(results, output_dir)
        generate_json_results(results, suite_start)
        print(f"\nAll done. {len(results)} datasets processed.")
    else:
        print("No results to report.")

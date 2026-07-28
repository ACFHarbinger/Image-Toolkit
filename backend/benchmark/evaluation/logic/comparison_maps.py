"""Pixel-level comparison tools between two stitch outputs — the ImageJ/
DiffImg/ImageMagick-inspired half of the dashboard's spec. Every function is
a pure ``np.ndarray -> np.ndarray`` (or tuple) transform with no Qt
dependency, so each is independently unit-testable and reusable from either
the GUI or a future headless script.
"""

from __future__ import annotations

from typing import List, Tuple

import cv2
import numpy as np

try:
    from skimage.metrics import structural_similarity as _ssim

    _SSIM_OK = True
except ImportError:
    _SSIM_OK = False


def _match_shape(a: np.ndarray, b: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Resize b onto a's canvas — same "smaller-of-the-two-dims" convention
    bench_anime_stitch.py's own GT comparison metrics use."""
    h, w = a.shape[:2]
    if b.shape[:2] != (h, w):
        b = cv2.resize(b, (w, h), interpolation=cv2.INTER_AREA)
    return a, b


def abs_diff_inverted(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Absolute-difference map inverted so unchanged background reads white
    and any real difference pops as a dark/colored region."""
    a, b = _match_shape(a, b)
    diff = cv2.absdiff(a, b)
    return 255 - diff


def ssim_heatmap(a: np.ndarray, b: np.ndarray) -> Tuple[float, np.ndarray]:
    a, b = _match_shape(a, b)
    gray_a = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
    gray_b = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)
    if not _SSIM_OK:
        diff = cv2.absdiff(gray_a, gray_b).astype(np.float32) / 255.0
        score = float(1.0 - diff.mean())
        heat = cv2.applyColorMap((diff * 255).astype(np.uint8), cv2.COLORMAP_INFERNO)
        return score, heat
    score, ssim_map = _ssim(gray_a, gray_b, full=True, data_range=255)
    normalized = np.clip((1.0 - ssim_map) * 255.0, 0, 255).astype(np.uint8)
    heat = cv2.applyColorMap(normalized, cv2.COLORMAP_INFERNO)
    return float(score), heat


def false_color_overlay(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Red = a, cyan = b, so any translation/rotation misalignment shows as
    red/cyan ghosting fringes rather than a flat blend."""
    a, b = _match_shape(a, b)
    gray_a = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
    gray_b = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)
    out = np.zeros((*gray_a.shape, 3), dtype=np.uint8)
    out[..., 2] = gray_a  # R channel (BGR order)
    out[..., 1] = gray_b  # G
    out[..., 0] = gray_b  # B — G+B together = cyan
    return out


def alpha_blend(a: np.ndarray, b: np.ndarray, alpha: float = 0.5) -> np.ndarray:
    a, b = _match_shape(a, b)
    return cv2.addWeighted(a, alpha, b, 1.0 - alpha, 0.0)


def checkerboard_mosaic(a: np.ndarray, b: np.ndarray, tile: int = 64) -> np.ndarray:
    a, b = _match_shape(a, b)
    h, w = a.shape[:2]
    out = a.copy()
    for ty in range(0, h, tile):
        for tx in range(0, w, tile):
            if ((ty // tile) + (tx // tile)) % 2 == 1:
                out[ty:ty + tile, tx:tx + tile] = b[ty:ty + tile, tx:tx + tile]
    return out


def contour_bounding(
    a: np.ndarray, b: np.ndarray, blur_ksize: int = 15, thresh: int = 25
) -> Tuple[np.ndarray, List[Tuple[int, int, int, int]]]:
    """Gaussian-blur the diff map to suppress single-pixel noise, threshold
    it, then draw high-contrast boxes around the surviving changed regions
    on an alpha-blend base image — the "what actually moved" view."""
    a, b = _match_shape(a, b)
    diff = cv2.absdiff(a, b)
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    k = blur_ksize | 1  # GaussianBlur requires an odd kernel size
    blurred = cv2.GaussianBlur(gray, (k, k), 0)
    _, mask = cv2.threshold(blurred, thresh, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    base = alpha_blend(a, b, 0.5)
    boxes = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if w * h < 64:  # drop noise specks too small to be a real defect
            continue
        boxes.append((x, y, w, h))
        cv2.rectangle(base, (x, y), (x + w, y + h), (0, 255, 255), 2)
    return base, boxes


def pixel_value_grid(region_bgr: np.ndarray, max_cells: int = 24) -> str:
    """Text dump of raw BGR pixel values for a small selected region —
    Pixel Value Mode's numeric readout for a bbox-selected crop."""
    h, w = region_bgr.shape[:2]
    step_y = max(1, h // max_cells)
    step_x = max(1, w // max_cells)
    lines = []
    for y in range(0, h, step_y):
        row = " ".join(
            f"({region_bgr[y, x, 2]:3d},{region_bgr[y, x, 1]:3d},{region_bgr[y, x, 0]:3d})"
            for x in range(0, w, step_x)
        )
        lines.append(row)
    return "\n".join(lines)

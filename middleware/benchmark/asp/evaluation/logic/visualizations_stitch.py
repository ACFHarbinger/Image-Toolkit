"""Stitch-seam pixel views. Classic signals only — no learned model.

Local SSIM (box-filter map), OpenCV Lab Euclidean delta-E, Canny-XOR
distance, phase-correlation ghost residual, coverage gaps, Sobel-Y seam
energy, adjacent-band luma agreement, and Laplacian residual. Every raster
is area-downsampled so the long edge is at most 480 before the heavy work.
Pair views resample the second image onto the first after that. Heatmaps
are ``cv2.applyColorMap`` of a uint8 magnitude: bright means disagreement.
"""

from __future__ import annotations

import cv2
import numpy as np
from matplotlib.figure import Figure

from .figure_theme import themed_figure

_MAX_EDGE = 480
_SSIM_C1 = (0.01 * 255.0) ** 2
_SSIM_C2 = (0.03 * 255.0) ** 2


def _downsample(img: np.ndarray, max_edge: int = _MAX_EDGE) -> np.ndarray:
    """Area-downsample so the long edge is at most ``max_edge``."""
    height, width = img.shape[:2]
    long_edge = max(height, width)
    if long_edge <= max_edge:
        return img
    scale = long_edge / float(max_edge)
    return cv2.resize(
        img,
        (max(1, int(width / scale)), max(1, int(height / scale))),
        interpolation=cv2.INTER_AREA,
    )


def _pair(a_bgr: np.ndarray, b_bgr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Downsample both, then resample ``b`` onto ``a``'s canvas."""
    a = _downsample(a_bgr)
    b = _downsample(b_bgr)
    height, width = a.shape[:2]
    if b.shape[:2] != (height, width):
        b = cv2.resize(b, (width, height), interpolation=cv2.INTER_AREA)
    return a, b


def _gray(img_bgr: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)


def _heatmap(magnitude: np.ndarray) -> np.ndarray:
    mag = np.clip(magnitude, 0, 255).astype(np.uint8)
    return cv2.applyColorMap(mag, cv2.COLORMAP_INFERNO)


def local_ssim_map(a_bgr: np.ndarray, b_bgr: np.ndarray, win: int = 11) -> np.ndarray:
    """uint8 BGR heatmap. Bright = low structural agreement.

    Box-filter SSIM (``cv2.blur``), not skimage. ``C1=(0.01*255)**2``,
    ``C2=(0.03*255)**2``. ``win`` must be odd and >= 3.
    """
    if win < 3 or win % 2 == 0:
        raise ValueError("win must be odd and >= 3")
    a, b = _pair(a_bgr, b_bgr)
    ga = _gray(a).astype(np.float32)
    gb = _gray(b).astype(np.float32)
    kernel = (win, win)
    mu_a = cv2.blur(ga, kernel)
    mu_b = cv2.blur(gb, kernel)
    mu_a_sq = mu_a * mu_a
    mu_b_sq = mu_b * mu_b
    mu_ab = mu_a * mu_b
    sigma_a_sq = cv2.blur(ga * ga, kernel) - mu_a_sq
    sigma_b_sq = cv2.blur(gb * gb, kernel) - mu_b_sq
    sigma_ab = cv2.blur(ga * gb, kernel) - mu_ab
    numerator = (2.0 * mu_ab + _SSIM_C1) * (2.0 * sigma_ab + _SSIM_C2)
    denominator = (mu_a_sq + mu_b_sq + _SSIM_C1) * (sigma_a_sq + sigma_b_sq + _SSIM_C2)
    ssim = numerator / denominator
    return _heatmap((1.0 - ssim) * 255.0)


def delta_e_map(a_bgr: np.ndarray, b_bgr: np.ndarray) -> np.ndarray:
    """uint8 BGR heatmap of Euclidean distance in OpenCV Lab (0-255 Lab, not D65 CIEDE2000)."""
    a, b = _pair(a_bgr, b_bgr)
    lab_a = cv2.cvtColor(a, cv2.COLOR_BGR2Lab).astype(np.float32)
    lab_b = cv2.cvtColor(b, cv2.COLOR_BGR2Lab).astype(np.float32)
    distance = np.sqrt(np.sum((lab_a - lab_b) ** 2, axis=2))
    return _heatmap(distance)


def edge_disagreement(a_bgr: np.ndarray, b_bgr: np.ndarray) -> np.ndarray:
    """uint8 BGR heatmap of the distance transform of the Canny-XOR mask."""
    a, b = _pair(a_bgr, b_bgr)
    edges_a = cv2.Canny(_gray(a), 80, 160)
    edges_b = cv2.Canny(_gray(b), 80, 160)
    xor = cv2.bitwise_xor(edges_a, edges_b)
    # A one-pixel XOR sits under a unit of L2 distance, which uint8 would
    # quantize away. Scale so that disagreement stays visible and zeros stay 0.
    distance = cv2.distanceTransform(xor, cv2.DIST_L2, 3)
    return _heatmap(distance * 255.0)


def _phase_aligned_diff(ga: np.ndarray, gb: np.ndarray) -> np.ndarray:
    """Absolute gray difference after undoing ``phaseCorrelate``'s shift of ``b``.

    ``phaseCorrelate(a, b)`` is how far ``b`` sits from ``a``. The warp that
    brings ``b`` back is the negation. A raised correlate (or a non-finite
    peak) keeps the unshifted difference.
    """
    try:
        (shift_x, shift_y), _response = cv2.phaseCorrelate(ga, gb)
    except Exception:
        return cv2.absdiff(ga, gb)
    if not np.isfinite(shift_x) or not np.isfinite(shift_y):
        return cv2.absdiff(ga, gb)
    matrix = np.float32([[1.0, 0.0, -float(shift_x)], [0.0, 1.0, -float(shift_y)]])
    height, width = gb.shape[:2]
    shifted = cv2.warpAffine(
        gb,
        matrix,
        (width, height),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_WRAP,
    )
    return cv2.absdiff(ga, shifted)


def ghost_residual(a_bgr: np.ndarray, b_bgr: np.ndarray) -> np.ndarray:
    """uint8 BGR heatmap of abs gray difference after shifting b by cv2.phaseCorrelate.

    If phaseCorrelate raises, use the unshifted difference.
    """
    a, b = _pair(a_bgr, b_bgr)
    ga = _gray(a).astype(np.float32)
    gb = _gray(b).astype(np.float32)
    return _heatmap(_phase_aligned_diff(ga, gb))


def coverage_gap(a_bgr: np.ndarray, b_bgr: np.ndarray, dark: int = 8) -> np.ndarray:
    """uint8 BGR. Pixels where one image is darker than ``dark`` on all channels and the
    other is not are marked. Same content on both stays black.
    """
    a, b = _pair(a_bgr, b_bgr)
    a_dark = np.all(a < dark, axis=2)
    b_dark = np.all(b < dark, axis=2)
    gap = np.logical_xor(a_dark, b_dark)
    magnitude = np.zeros(gap.shape, dtype=np.uint8)
    magnitude[gap] = 255
    heat = cv2.applyColorMap(magnitude, cv2.COLORMAP_INFERNO)
    # Inferno's first stop is (4, 0, 0), not black. A non-gap must stay (0, 0, 0).
    heat[~gap] = 0
    return heat


def laplacian_residual(a_bgr: np.ndarray, b_bgr: np.ndarray) -> np.ndarray:
    """uint8 BGR heatmap of abs(Laplacian(a) - Laplacian(b)) on gray."""
    a, b = _pair(a_bgr, b_bgr)
    lap_a = cv2.Laplacian(_gray(a), cv2.CV_32F)
    lap_b = cv2.Laplacian(_gray(b), cv2.CV_32F)
    return _heatmap(np.abs(lap_a - lap_b))


def seam_energy_figure(img_bgr: np.ndarray) -> Figure:
    """matplotlib Figure. Row profile of Sobel-Y magnitude (horizontal edges).

    Title contains ``Seam energy``.
    """
    gray = _gray(_downsample(img_bgr)).astype(np.float32)
    sobel_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    profile = np.abs(sobel_y).mean(axis=1)
    fig, ax = themed_figure()
    ax.plot(np.arange(profile.shape[0]), profile, color="#ff6b6b", linewidth=1.2)
    ax.set_title("Seam energy")
    ax.set_xlabel("Row")
    ax.set_ylabel("Mean |Sobel-Y|")
    return fig


def _luma_hist(strip: np.ndarray) -> np.ndarray:
    hist = cv2.calcHist([strip], [0], None, [256], [0, 256])
    total = float(hist.sum())
    if total > 0.0:
        hist /= total
    return hist


def band_intersection_figure(img_bgr: np.ndarray, bands: int = 16) -> Figure:
    """matplotlib Figure. One bar per adjacent band pair.

    ``cv2.compareHist`` ``HISTCMP_BHATTACHARYYA`` on the luma histogram,
    plotted as ``1 - distance`` so 1 is a perfect match. Title contains
    ``Band intersection``. ``bands < 2`` raises ``ValueError``.
    """
    if bands < 2:
        raise ValueError("bands must be >= 2")
    gray = _gray(_downsample(img_bgr))
    strips = np.array_split(gray, bands, axis=0)
    hists = [_luma_hist(strip) for strip in strips]
    scores = [
        1.0 - cv2.compareHist(hists[i], hists[i + 1], cv2.HISTCMP_BHATTACHARYYA) for i in range(bands - 1)
    ]
    fig, ax = themed_figure()
    ax.bar(np.arange(bands - 1), scores, color="#00e5ff", width=0.8)
    ax.set_ylim(0.0, 1.0)
    ax.set_title("Band intersection")
    ax.set_xlabel("Adjacent band pair")
    ax.set_ylabel("1 - Bhattacharyya")
    return fig

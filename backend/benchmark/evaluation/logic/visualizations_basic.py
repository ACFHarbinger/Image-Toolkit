"""Per-image pixel-data visualizations: histograms, scatter plots, heatmaps,
gradient maps, and FFT analysis. Each function takes one BGR image (or a
selected region crop) and returns a matplotlib ``Figure`` ready for
``PlotCanvas``. Gradient heatmap conventions (Sobel magnitude, ``inferno``
colormap) match ``bench_anime_stitch.py``'s ``_save_seam_heatmap`` so a
dashboard user sees the same visual language as the static report.
"""

from __future__ import annotations

import cv2
import numpy as np
from matplotlib.figure import Figure

from ..constants.logic import _SCATTER_SAMPLE
from ..ui.mpl_canvas import themed_figure


def _subsample_pixels(img: np.ndarray, n: int = _SCATTER_SAMPLE) -> np.ndarray:
    h, w = img.shape[:2]
    total = h * w
    idx = np.random.default_rng(0).choice(total, size=min(n, total), replace=False)
    flat = img.reshape(-1, img.shape[2]) if img.ndim == 3 else img.reshape(-1, 1)
    return flat[idx]


def color_histogram_figure(img_bgr: np.ndarray) -> Figure:
    fig, ax = themed_figure()
    colors = (("b", "#4ecdc4"), ("g", "#6bff6b"), ("r", "#ff6b6b"))
    for i, (_, hexcolor) in enumerate(colors):
        hist = cv2.calcHist([img_bgr], [i], None, [256], [0, 256]).flatten()
        ax.plot(hist, color=hexcolor, alpha=0.85, linewidth=1.2)
    ax.set_title("Color Histogram (BGR channels)")
    ax.set_xlabel("Pixel value")
    ax.set_ylabel("Count")
    return fig


def cumulative_histogram_figure(img_bgr: np.ndarray) -> Figure:
    fig, ax = themed_figure()
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).flatten()
    cdf = np.cumsum(hist)
    cdf = cdf / cdf[-1] * 100.0
    ax.plot(cdf, color="#ffd93d", linewidth=1.6)
    ax.set_title("Cumulative Luminance Histogram")
    ax.set_xlabel("Pixel value")
    ax.set_ylabel("Cumulative %")
    return fig


def scatter_2d_figure(img_bgr: np.ndarray) -> Figure:
    fig, ax = themed_figure()
    px = _subsample_pixels(img_bgr)
    ax.scatter(px[:, 2], px[:, 1], s=2, c=px[:, ::-1] / 255.0, alpha=0.5)
    ax.set_title("2D Scatter — Red vs Green channel")
    ax.set_xlabel("Red")
    ax.set_ylabel("Green")
    return fig


def scatter_3d_figure(img_bgr: np.ndarray) -> Figure:
    fig, ax = themed_figure(projection="3d")
    px = _subsample_pixels(img_bgr, 1500)
    ax.scatter(px[:, 2], px[:, 1], px[:, 0], s=2, c=px[:, ::-1] / 255.0, alpha=0.6)
    ax.set_title("3D Scatter — RGB Color Space", color="white")
    ax.set_xlabel("R")
    ax.set_ylabel("G")
    ax.set_zlabel("B")
    return fig


def spatial_scatter_figure(img_bgr: np.ndarray) -> Figure:
    """Scatter of edge-pixel (x, y) locations — reveals where structural
    detail concentrates, distinct from the color-space scatter above."""
    fig, ax = themed_figure()
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 80, 160)
    ys, xs = np.nonzero(edges)
    if len(xs) > _SCATTER_SAMPLE:
        idx = np.random.default_rng(0).choice(len(xs), _SCATTER_SAMPLE, replace=False)
        xs, ys = xs[idx], ys[idx]
    ax.scatter(xs, ys, s=1, c="#00e5ff", alpha=0.4)
    ax.invert_yaxis()
    ax.set_aspect("equal")
    ax.set_title("Spatial Scatter — Edge Pixel Locations")
    return fig


def intensity_heatmap_figure(img_bgr: np.ndarray) -> Figure:
    fig, ax = themed_figure()
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    scale = max(1, max(gray.shape) // 512)
    if scale > 1:
        gray = cv2.resize(gray, (gray.shape[1] // scale, gray.shape[0] // scale))
    im = ax.imshow(gray, cmap="viridis", aspect="auto")
    ax.set_title("Intensity Heatmap")
    ax.axis("off")
    fig.colorbar(im, ax=ax, fraction=0.03)
    return fig


def gradient_heatmap_figure(img_bgr: np.ndarray) -> Figure:
    fig, ax = themed_figure()
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.sqrt(gx**2 + gy**2)
    scale = max(1, max(mag.shape) // 512)
    if scale > 1:
        mag = cv2.resize(mag, (mag.shape[1] // scale, mag.shape[0] // scale))
    im = ax.imshow(mag, cmap="inferno", aspect="auto")
    ax.set_title("Gradient Magnitude Heatmap")
    ax.axis("off")
    fig.colorbar(im, ax=ax, fraction=0.03)
    return fig


def fft_magnitude_figure(img_bgr: np.ndarray) -> Figure:
    fig, ax = themed_figure()
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    f = np.fft.fftshift(np.fft.fft2(gray))
    magnitude = np.log1p(np.abs(f))
    im = ax.imshow(magnitude, cmap="magma", aspect="auto")
    ax.set_title("FFT Magnitude Spectrum")
    ax.axis("off")
    fig.colorbar(im, ax=ax, fraction=0.03)
    return fig

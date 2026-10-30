"""2x new edge-directed interpolation from the local luminance covariance.

A structure tensor over a small window is the covariance of the luminance
gradient. Its dominant eigenvector is the edge normal. The 4-tap kernel
stays wide along the edge and tightens across it, so a horizontal edge is
not filled from a diagonal pair.
"""

from __future__ import annotations

import numpy as np

from middleware.src.services.media.gif_upscale.base import AlgorithmSpec
from middleware.src.services.media.gif_upscale.classical._support import (
    blend,
    box_mean,
    luma,
    output_size,
    prepare_frames,
    source_grid,
)
from middleware.src.services.media.gif_upscale.registry import register_algorithm

_ALLOWED = frozenset({2.0})
_WINDOW = 1


def _covariance_snap(level: np.ndarray, y0: np.ndarray, x0: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    gradient_y, gradient_x = np.gradient(level.astype(np.float64))
    jxx = box_mean(gradient_x * gradient_x, _WINDOW)
    jyy = box_mean(gradient_y * gradient_y, _WINDOW)
    jxy = box_mean(gradient_x * gradient_y, _WINDOW)
    height, width = level.shape
    y = np.clip(y0, 0, height - 1)
    x = np.clip(x0, 0, width - 1)
    cxx = jxx[y, x]
    cyy = jyy[y, x]
    cxy = jxy[y, x]
    # Normal of the dominant gradient. A horizontal edge has normal (0, 1).
    theta = 0.5 * np.arctan2(2.0 * cxy, cxx - cyy)
    normal_x = np.cos(theta)
    normal_y = np.sin(theta)
    delta = np.sqrt((cxx - cyy) ** 2 + 4.0 * cxy * cxy)
    lam1 = 0.5 * (cxx + cyy + delta)
    lam2 = 0.5 * (cxx + cyy - delta)
    strength = (lam1 - lam2) / (lam1 + lam2 + 1e-8)
    strength = np.where(lam1 + lam2 < 1e-8, 0.0, np.clip(strength, 0.0, 1.0))
    snap_x = (strength * normal_x * normal_x).astype(np.float32)
    snap_y = (strength * normal_y * normal_y).astype(np.float32)
    return snap_x, snap_y


def _upscale_frame(frame: np.ndarray, target_w: int, target_h: int) -> np.ndarray:
    y0, x0, fy, fx = source_grid(frame.shape[0], frame.shape[1], target_h, target_w)
    snap_x, snap_y = _covariance_snap(luma(frame), y0, x0)
    return np.clip(blend(frame, y0, x0, fy, fx, snap_x, snap_y), 0.0, 1.0).astype(np.float32)


def upscale(frames: list[np.ndarray], scale: float, opts: dict) -> list[np.ndarray]:
    prepared = prepare_frames(frames)
    if not prepared:
        return []
    scaled: list[np.ndarray] = []
    for frame in prepared:
        target_w, target_h = output_size(
            frame.shape[0],
            frame.shape[1],
            scale,
            opts,
            algorithm_id="nedi",
            allowed=_ALLOWED,
            downscale=False,
        )
        scaled.append(_upscale_frame(frame, target_w, target_h))
    return scaled


register_algorithm(
    AlgorithmSpec(
        id="nedi",
        family="classical",
        content="any",
        kind="classical",
        supports_scale=_ALLOWED,
        supports_downscale=False,
        needs_gpu=False,
        vram_mb_estimate=0,
        license="MIT",
        weights_sha256=None,
        available=lambda: (True, ""),
    ),
    upscale,
)

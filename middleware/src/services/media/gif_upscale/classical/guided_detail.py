"""Bilinear resize plus a clamped guided-filter detail residual.

Any positive scale, including downscale. The resize is float bilinear
(pixel centers), so a constant field is unchanged. The residual is the
resized frame minus a self-guided base layer. It is zero on flat windows
and applied only at a strict local extremum, which keeps a flat field —
including pixels that merely touch an edge — from ringing.
"""

from __future__ import annotations

import numpy as np

from middleware.src.services.media.gif_upscale.base import AlgorithmSpec
from middleware.src.services.media.gif_upscale.classical._support import (
    blend,
    box_mean,
    output_size,
    prepare_frames,
    source_grid,
)
from middleware.src.services.media.gif_upscale.registry import register_algorithm

_RADIUS = 1
_EPS = 0.05
_DETAIL_CAP = 0.25
_FLAT_VARIANCE = 1e-6
_EXTREMA_TOL = 1e-4


def _guided(image: np.ndarray) -> np.ndarray:
    mean = box_mean(image, _RADIUS)
    mean_sq = box_mean(image * image, _RADIUS)
    variance = np.maximum(mean_sq - mean * mean, 0.0)
    a = variance / (variance + _EPS)
    b = mean - a * mean
    return box_mean(a, _RADIUS) * image + box_mean(b, _RADIUS)


def _cross(channel: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    padded = np.pad(channel, 1, mode="edge")
    return padded[:-2, 1:-1], padded[2:, 1:-1], padded[1:-1, :-2], padded[1:-1, 2:]


def _with_detail(channel: np.ndarray) -> np.ndarray:
    detail = np.clip(channel - _guided(channel), -_DETAIL_CAP, _DETAIL_CAP)
    variance = box_mean(channel * channel, _RADIUS) - np.square(box_mean(channel, _RADIUS))
    detail = np.where(variance < _FLAT_VARIANCE, 0.0, detail)
    north, south, west, east = _cross(channel)
    tol = _EXTREMA_TOL
    peak = (channel >= north - tol) & (channel >= south - tol) & (channel >= west - tol) & (channel >= east - tol)
    peak &= (channel > north + tol) | (channel > south + tol) | (channel > west + tol) | (channel > east + tol)
    valley = (channel <= north + tol) & (channel <= south + tol) & (channel <= west + tol) & (channel <= east + tol)
    valley &= (channel < north - tol) | (channel < south - tol) | (channel < west - tol) | (channel < east - tol)
    boost = np.where(peak, np.maximum(detail, 0.0), 0.0)
    boost = np.where(valley, np.minimum(detail, 0.0), boost)
    return np.clip(channel + boost, 0.0, 1.0)


def _resize(frame: np.ndarray, target_w: int, target_h: int) -> np.ndarray:
    y0, x0, fy, fx = source_grid(frame.shape[0], frame.shape[1], target_h, target_w)
    snap = np.zeros((target_h, target_w), dtype=np.float32)
    resized = blend(frame, y0, x0, fy, fx, snap, snap)
    enhanced = np.empty_like(resized)
    for channel in range(4):
        enhanced[..., channel] = _with_detail(resized[..., channel])
    return enhanced.astype(np.float32)


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
            algorithm_id="guided-detail",
            allowed=frozenset(),
            downscale=True,
        )
        scaled.append(_resize(frame, target_w, target_h))
    return scaled


register_algorithm(
    AlgorithmSpec(
        id="guided-detail",
        family="classical",
        content="any",
        kind="classical",
        supports_scale=frozenset(),
        supports_downscale=True,
        needs_gpu=False,
        vram_mb_estimate=0,
        license="MIT",
        weights_sha256=None,
        available=lambda: (True, ""),
    ),
    upscale,
)

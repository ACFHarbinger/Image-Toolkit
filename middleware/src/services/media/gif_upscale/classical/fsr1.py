"""AMD FSR 1.0 style upscaler: reduced 4-tap directional EASU plus RCAS.

This is not the full 12-tap EASU. The 2x2 luminance gradient sets an
anisotropic 4-tap kernel: bilinear weight is left wide along the edge and
pulled toward the nearer sample across it. RCAS then adds a clamped
fraction of the local cross-neighborhood contrast.
"""

from __future__ import annotations

import numpy as np

from middleware.src.services.media.gif_upscale.base import AlgorithmSpec
from middleware.src.services.media.gif_upscale.classical._support import (
    blend,
    luma,
    output_size,
    prepare_frames,
    source_grid,
)
from middleware.src.services.media.gif_upscale.registry import register_algorithm

_ALLOWED = frozenset({2.0})
_RCAS_LIMIT = 0.2


def _gradient_snap(frame: np.ndarray, y0: np.ndarray, x0: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    level = luma(frame)
    height, width = level.shape
    y0c = np.clip(y0, 0, height - 1)
    x0c = np.clip(x0, 0, width - 1)
    y1c = np.clip(y0 + 1, 0, height - 1)
    x1c = np.clip(x0 + 1, 0, width - 1)
    l00 = level[y0c, x0c]
    l10 = level[y0c, x1c]
    l01 = level[y1c, x0c]
    l11 = level[y1c, x1c]
    across_x = np.abs((l10 + l11) - (l00 + l01))
    across_y = np.abs((l01 + l11) - (l00 + l10))
    total = across_x + across_y
    snap_x = np.divide(across_x, total, out=np.zeros_like(total), where=total > 1e-8)
    snap_y = np.divide(across_y, total, out=np.zeros_like(total), where=total > 1e-8)
    return snap_x, snap_y


def _rcas(image: np.ndarray) -> np.ndarray:
    """Sharpen by a contrast-limited negative lobe on the 5-tap cross.

    ``lobe`` is the largest weight that stays inside 0..1 given the local
    min and max, then capped. Flat neighborhoods have equal taps, so the
    fraction of contrast is zero and the pixel is unchanged.
    """
    padded = np.pad(image, ((1, 1), (1, 1), (0, 0)), mode="edge")
    north = padded[:-2, 1:-1]
    south = padded[2:, 1:-1]
    west = padded[1:-1, :-2]
    east = padded[1:-1, 2:]
    neighbor_sum = north + east + south + west
    minimum = np.minimum(np.minimum(north, south), np.minimum(west, east))
    maximum = np.maximum(np.maximum(north, south), np.maximum(west, east))
    hit_min = minimum / np.maximum(4.0 * maximum, 1e-6)
    high_den = 4.0 * minimum - 4.0
    hit_max = np.zeros_like(maximum)
    np.divide(1.0 - maximum, high_den, out=hit_max, where=np.abs(high_den) > 1e-6)
    lobe = np.clip(np.maximum(-hit_min, hit_max), -_RCAS_LIMIT, 0.0)
    sharpened = (image + lobe * neighbor_sum) / (1.0 + 4.0 * lobe)
    lo = np.minimum(minimum, image)
    hi = np.maximum(maximum, image)
    return np.clip(sharpened, lo, hi)


def _upscale_frame(frame: np.ndarray, target_w: int, target_h: int) -> np.ndarray:
    y0, x0, fy, fx = source_grid(frame.shape[0], frame.shape[1], target_h, target_w)
    snap_x, snap_y = _gradient_snap(frame, y0, x0)
    upscaled = blend(frame, y0, x0, fy, fx, snap_x, snap_y)
    return np.clip(_rcas(upscaled), 0.0, 1.0).astype(np.float32)


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
            algorithm_id="fsr1-easu",
            allowed=_ALLOWED,
            downscale=False,
        )
        scaled.append(_upscale_frame(frame, target_w, target_h))
    return scaled


register_algorithm(
    AlgorithmSpec(
        id="fsr1-easu",
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

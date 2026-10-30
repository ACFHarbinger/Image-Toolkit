"""Shared sampling helpers for the classical GIF scalers.

``_support`` is not a backend. ``load_backends`` skips modules whose names
start with an underscore.
"""

from __future__ import annotations

import numpy as np

from middleware.src.services.media.gif_upscale.base import AlgorithmError


def prepare_frames(frames: list[np.ndarray] | None) -> list[np.ndarray]:
    if frames is None:
        raise AlgorithmError("frames are required")
    prepared: list[np.ndarray] = []
    for frame in frames:
        array = np.array(frame, dtype=np.float32, copy=True)
        if array.ndim != 3 or array.shape[2] != 4:
            raise AlgorithmError(f"expected HxWx4 frames, got {array.shape}")
        if array.shape[0] < 1 or array.shape[1] < 1:
            raise AlgorithmError("source size must be positive")
        prepared.append(array)
    return prepared


def output_size(
    height: int,
    width: int,
    scale: float,
    opts: dict,
    *,
    algorithm_id: str,
    allowed: frozenset[float],
    downscale: bool,
) -> tuple[int, int]:
    """Return ``(width, height)``. Refuse scales the algorithm did not register."""
    size = opts.get("size") if opts else None
    if size:
        target_w, target_h = int(size[0]), int(size[1])
    else:
        factor = float(scale)
        if not np.isfinite(factor) or factor <= 0:
            raise AlgorithmError(f"{algorithm_id} scale must be positive")
        target_w = max(1, int(round(width * factor)))
        target_h = max(1, int(round(height * factor)))
    if target_w < 1 or target_h < 1:
        raise AlgorithmError(f"{algorithm_id} target size must be positive")
    if (target_w < width or target_h < height) and not downscale:
        raise AlgorithmError(f"{algorithm_id} does not downscale.")
    if allowed:
        scale_x = target_w / width
        scale_y = target_h / height
        matched = any(abs(scale_x - item) < 1e-3 and abs(scale_y - item) < 1e-3 for item in allowed)
        if not matched:
            supported = ", ".join(str(item) for item in sorted(allowed))
            raise AlgorithmError(
                f"{algorithm_id} supports scales {supported}, not {target_w}x{target_h} from {width}x{height}."
            )
    return target_w, target_h


def luma(frame: np.ndarray) -> np.ndarray:
    return 0.2126 * frame[..., 0] + 0.7152 * frame[..., 1] + 0.0722 * frame[..., 2]


def source_grid(src_h: int, src_w: int, target_h: int, target_w: int):
    """Pixel-center source coordinates for every output pixel."""
    oy = np.arange(target_h, dtype=np.float32)
    ox = np.arange(target_w, dtype=np.float32)
    sy = (oy + 0.5) * (src_h / float(target_h)) - 0.5
    sx = (ox + 0.5) * (src_w / float(target_w)) - 0.5
    y_floor = np.floor(sy)
    x_floor = np.floor(sx)
    y0 = y_floor.astype(np.int32)[:, None]
    x0 = x_floor.astype(np.int32)[None, :]
    fy = (sy - y_floor).astype(np.float32)[:, None]
    fx = (sx - x_floor).astype(np.float32)[None, :]
    return y0, x0, fy, fx


def steepen(fraction: np.ndarray, snap: np.ndarray, power: float = 4.0) -> np.ndarray:
    """Pull a bilinear fraction toward 0 or 1. ``snap`` 0 leaves it unchanged."""
    frac = np.clip(fraction.astype(np.float32), 0.0, 1.0)
    gain = 1.0 + np.clip(snap, 0.0, 1.0).astype(np.float32) * np.float32(power)
    near = np.power(frac, gain)
    far = np.power(1.0 - frac, gain)
    return near / (near + far + np.float32(1e-12))


def blend(frame: np.ndarray, y0, x0, fy, fx, snap_x, snap_y) -> np.ndarray:
    """4-tap blend. High snap on an axis samples less across that axis."""
    height, width = frame.shape[:2]
    y0c = np.clip(y0, 0, height - 1)
    x0c = np.clip(x0, 0, width - 1)
    y1c = np.clip(y0 + 1, 0, height - 1)
    x1c = np.clip(x0 + 1, 0, width - 1)
    c00 = frame[y0c, x0c]
    c10 = frame[y0c, x1c]
    c01 = frame[y1c, x0c]
    c11 = frame[y1c, x1c]
    wx = steepen(fx, snap_x)[..., None]
    wy = steepen(fy, snap_y)[..., None]
    top = c00 * (1.0 - wx) + c10 * wx
    bottom = c01 * (1.0 - wx) + c11 * wx
    return top * (1.0 - wy) + bottom * wy


def box_mean(src: np.ndarray, radius: int) -> np.ndarray:
    k = 2 * radius + 1
    padded = np.pad(np.asarray(src, dtype=np.float64), radius, mode="edge")
    integral = np.pad(np.cumsum(np.cumsum(padded, axis=0), axis=1), ((1, 0), (1, 0)))
    total = integral[k:, k:] - integral[:-k, k:] - integral[k:, :-k] + integral[:-k, :-k]
    return total / float(k * k)

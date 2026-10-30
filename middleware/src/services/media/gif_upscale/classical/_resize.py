"""Shared resize math for the classical GIF scalers.

Filters run on premultiplied alpha so a transparent edge does not bleed color,
then straight alpha is restored. A vanished weight sum is an error: callers
must not be handed a silent nearest or Lanczos image.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from middleware.src.services.media.gif_upscale.base import AlgorithmError, AlgorithmSpec, Frames
from middleware.src.services.media.gif_upscale.registry import register_algorithm

Kernel = Callable[[np.ndarray], np.ndarray]
_SUPPORT_EPS = 1e-8
_WEIGHT_EPS = 1e-12


def register_classical(algorithm_id: str, upscale: Callable[[Frames, float, dict], Frames]) -> None:
    register_algorithm(
        AlgorithmSpec(
            id=algorithm_id,
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


def mitchell_kernel(b: float, c: float) -> Kernel:
    """Mitchell–Netravali cubic. Catmull-Rom is B=0, C=0.5."""

    def kernel(x: np.ndarray) -> np.ndarray:
        ax = np.abs(x)
        result = np.zeros(ax.shape, dtype=np.float64)
        first = ax < 1.0
        second = (ax >= 1.0) & (ax < 2.0)
        x1 = ax[first]
        result[first] = (
            (12.0 - 9.0 * b - 6.0 * c) * x1**3 + (-18.0 + 12.0 * b + 6.0 * c) * x1**2 + (6.0 - 2.0 * b)
        ) / 6.0
        x2 = ax[second]
        result[second] = (
            (-b - 6.0 * c) * x2**3 + (6.0 * b + 30.0 * c) * x2**2 + (-12.0 * b - 48.0 * c) * x2 + (8.0 * b + 24.0 * c)
        ) / 6.0
        return result

    return kernel


def lanczos_kernel(a: float = 3.0) -> Kernel:
    def kernel(x: np.ndarray) -> np.ndarray:
        ax = np.abs(x)
        result = np.zeros(ax.shape, dtype=np.float64)
        small = ax < 1e-12
        mid = (~small) & (ax < a)
        result[small] = 1.0
        pix = np.pi * ax[mid]
        result[mid] = (np.sin(pix) / pix) * (np.sin(pix / a) / (pix / a))
        return result

    return kernel


def jinc(x: np.ndarray) -> np.ndarray:
    """Normalized sinc the lane calls jinc: sin(pi x) / (pi x), and 1 at 0."""
    ax = np.abs(np.asarray(x, dtype=np.float64))
    result = np.ones(ax.shape, dtype=np.float64)
    mask = ax > 1e-12
    pix = np.pi * ax[mask]
    result[mask] = np.sin(pix) / pix
    return result


def resize_separable(
    frames: Frames,
    scale: float,
    opts: dict,
    algorithm_id: str,
    kernel: Kernel,
    support: float,
    *,
    dering: bool = False,
    clip_unit: bool = False,
) -> Frames:
    width, height = _target_size(scale, opts, algorithm_id)
    resized: Frames = []
    for frame in frames:
        premul = _premultiply(_require_rgba(frame, algorithm_id))
        filtered = _separable(premul, width, height, kernel, support, algorithm_id)
        if dering:
            filtered = _clamp_rgb_to_neighborhood(filtered, premul, support, algorithm_id)
        resized.append(_finish(filtered, algorithm_id, clip_unit=clip_unit))
    return resized


def resize_ewa(frames: Frames, scale: float, opts: dict, algorithm_id: str) -> Frames:
    width, height = _target_size(scale, opts, algorithm_id)
    resized: Frames = []
    for frame in frames:
        premul = _premultiply(_require_rgba(frame, algorithm_id))
        resized.append(_finish(_ewa(premul, width, height, algorithm_id), algorithm_id, clip_unit=True))
    return resized


def _target_size(scale: float, opts: dict, algorithm_id: str) -> tuple[int, int]:
    try:
        scale_value = float(scale)
    except (TypeError, ValueError) as exc:
        raise AlgorithmError(f"{algorithm_id} needs a positive scale, got {scale!r}.") from exc
    if not np.isfinite(scale_value) or scale_value <= 0.0:
        raise AlgorithmError(f"{algorithm_id} needs a positive scale, got {scale!r}.")
    if not isinstance(opts, dict) or "size" not in opts:
        raise AlgorithmError(f"{algorithm_id} needs opts['size'] as (width, height), not a fallback resize.")
    size = opts["size"]
    try:
        width = int(size[0])
        height = int(size[1])
    except (TypeError, ValueError, IndexError) as exc:
        raise AlgorithmError(f"{algorithm_id} needs opts['size'] as (width, height), got {size!r}.") from exc
    if width < 1 or height < 1:
        raise AlgorithmError(f"{algorithm_id} needs a positive target size, got {width}x{height}.")
    return width, height


def _require_rgba(frame: np.ndarray, algorithm_id: str) -> np.ndarray:
    try:
        array = np.asarray(frame, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise AlgorithmError(f"{algorithm_id} expected numeric HxWx4 frames.") from exc
    if array.ndim != 3 or array.shape[2] != 4 or array.shape[0] < 1 or array.shape[1] < 1:
        raise AlgorithmError(f"{algorithm_id} expected HxWx4 frames, got shape {getattr(frame, 'shape', None)}.")
    if not np.isfinite(array).all():
        raise AlgorithmError(f"{algorithm_id} refused a frame with non-finite values.")
    return array


def _premultiply(frame: np.ndarray) -> np.ndarray:
    premul = np.array(frame, dtype=np.float64, copy=True)
    premul[..., :3] *= premul[..., 3:4]
    return premul


def _unpremultiply(frame: np.ndarray) -> np.ndarray:
    alpha = frame[..., 3:4]
    rgb = np.zeros_like(frame[..., :3])
    np.divide(frame[..., :3], alpha, out=rgb, where=alpha > 1e-6)
    return np.concatenate([rgb, alpha], axis=-1)


def _finish(premul: np.ndarray, algorithm_id: str, *, clip_unit: bool) -> np.ndarray:
    straight = _unpremultiply(premul)
    if clip_unit:
        straight = np.clip(straight, 0.0, 1.0)
    if not np.isfinite(straight).all():
        raise AlgorithmError(f"{algorithm_id} produced non-finite pixels.")
    return straight.astype(np.float32, copy=False)


def _tap_table(src_len: int, dst_len: int, support: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    src_pos = (np.arange(dst_len, dtype=np.float64) + 0.5) * (src_len / dst_len) - 0.5
    radius = int(np.ceil(support - _SUPPORT_EPS))
    offsets = np.arange(1 - radius, radius + 1, dtype=np.int32)
    indices = np.floor(src_pos).astype(np.int32)[:, None] + offsets[None, :]
    delta = src_pos[:, None] - indices.astype(np.float64)
    valid = (indices >= 0) & (indices < src_len) & (np.abs(delta) < support)
    return indices, delta, valid


def _normalized_weights(delta: np.ndarray, valid: np.ndarray, kernel: Kernel, algorithm_id: str) -> np.ndarray:
    weights = np.where(valid, kernel(delta), 0.0)
    total = weights.sum(axis=1)
    if np.any(~np.isfinite(total) | (np.abs(total) < _WEIGHT_EPS)):
        raise AlgorithmError(f"{algorithm_id} filter weight sum vanished; refusing to fall back.")
    return weights / total[:, None]


def _resample_width(image: np.ndarray, dst_w: int, kernel: Kernel, support: float, algorithm_id: str) -> np.ndarray:
    src_h, src_w, channels = image.shape
    indices, delta, valid = _tap_table(src_w, dst_w, support)
    weights = _normalized_weights(delta, valid, kernel, algorithm_id)
    out = np.zeros((src_h, dst_w, channels), dtype=np.float64)
    for tap in range(indices.shape[1]):
        idx = np.clip(indices[:, tap], 0, src_w - 1)
        out += image[:, idx, :] * weights[None, :, tap, None]
    return out


def _separable(
    image: np.ndarray,
    dst_w: int,
    dst_h: int,
    kernel: Kernel,
    support: float,
    algorithm_id: str,
) -> np.ndarray:
    wide = _resample_width(image, dst_w, kernel, support, algorithm_id)
    tall = np.swapaxes(wide, 0, 1)
    resized = _resample_width(tall, dst_h, kernel, support, algorithm_id)
    return np.swapaxes(resized, 0, 1)


def _clamp_rgb_to_neighborhood(filtered: np.ndarray, source: np.ndarray, support: float, algorithm_id: str) -> np.ndarray:
    """Keep each RGB sample inside the source window that built it.

    Lanczos's negative lobe rings past a step. Clamping to that window's min
    and max removes the halo without pulling in a different kernel.
    """
    dst_h, dst_w = filtered.shape[:2]
    lo, hi = _neighborhood_range(source[..., :3], dst_h, dst_w, support, algorithm_id)
    clamped = np.array(filtered, copy=True)
    clamped[..., :3] = np.clip(filtered[..., :3], lo, hi)
    return clamped


def _neighborhood_range(
    rgb: np.ndarray,
    dst_h: int,
    dst_w: int,
    support: float,
    algorithm_id: str,
) -> tuple[np.ndarray, np.ndarray]:
    src_h, src_w, _channels = rgb.shape
    y_idx, _y_delta, y_ok = _tap_table(src_h, dst_h, support)
    x_idx, _x_delta, x_ok = _tap_table(src_w, dst_w, support)
    vertical_lo = np.full((dst_h, src_w, 3), np.inf, dtype=np.float64)
    vertical_hi = np.full((dst_h, src_w, 3), -np.inf, dtype=np.float64)
    for tap in range(y_idx.shape[1]):
        ok = y_ok[:, tap]
        if not np.any(ok):
            continue
        gathered = rgb[np.clip(y_idx[:, tap], 0, src_h - 1)]
        mask = ok[:, None, None]
        vertical_lo = np.where(mask, np.minimum(vertical_lo, gathered), vertical_lo)
        vertical_hi = np.where(mask, np.maximum(vertical_hi, gathered), vertical_hi)
    lo = np.full((dst_h, dst_w, 3), np.inf, dtype=np.float64)
    hi = np.full((dst_h, dst_w, 3), -np.inf, dtype=np.float64)
    for tap in range(x_idx.shape[1]):
        ok = x_ok[:, tap]
        if not np.any(ok):
            continue
        cols = np.clip(x_idx[:, tap], 0, src_w - 1)
        mask = ok[None, :, None]
        lo = np.where(mask, np.minimum(lo, vertical_lo[:, cols, :]), lo)
        hi = np.where(mask, np.maximum(hi, vertical_hi[:, cols, :]), hi)
    if not np.isfinite(lo).all() or not np.isfinite(hi).all():
        raise AlgorithmError(f"{algorithm_id} found an empty source neighborhood; refusing to fall back.")
    return lo, hi


def _ewa(image: np.ndarray, dst_w: int, dst_h: int, algorithm_id: str) -> np.ndarray:
    src_h, src_w, _channels = image.shape
    # Downscales widen the 3-lobe window so one output pixel covers the texels
    # that map onto it. Upscales keep the reconstruction radius (blur >= 1).
    blur_x = max(src_w / dst_w, 1.0)
    blur_y = max(src_h / dst_h, 1.0)
    support = 3.0
    src_x = (np.arange(dst_w, dtype=np.float64) + 0.5) * (src_w / dst_w) - 0.5
    src_y = (np.arange(dst_h, dtype=np.float64) + 0.5) * (src_h / dst_h) - 0.5
    x_off = _ewa_offsets(support * blur_x)
    y_off = _ewa_offsets(support * blur_y)
    out = np.empty((dst_h, dst_w, image.shape[2]), dtype=np.float64)
    chunk = _ewa_chunk(dst_w, y_off.size, x_off.size)
    for start in range(0, dst_h, chunk):
        stop = min(dst_h, start + chunk)
        out[start:stop] = _ewa_rows(image, src_x, src_y[start:stop], x_off, y_off, blur_x, blur_y, support, algorithm_id)
    return out


def _ewa_offsets(radius: float) -> np.ndarray:
    limit = int(np.ceil(radius)) + 1
    return np.arange(-limit, limit + 1, dtype=np.int32)


def _ewa_chunk(dst_w: int, y_taps: int, x_taps: int) -> int:
    bytes_per_row = max(1, y_taps * x_taps * max(dst_w, 1) * 8)
    return max(1, min(64, int(32 * 1024 * 1024 / bytes_per_row)))


def _ewa_rows(
    image: np.ndarray,
    src_x: np.ndarray,
    src_y: np.ndarray,
    x_off: np.ndarray,
    y_off: np.ndarray,
    blur_x: float,
    blur_y: float,
    support: float,
    algorithm_id: str,
) -> np.ndarray:
    src_h, src_w, channels = image.shape
    base_y = np.floor(src_y).astype(np.int32)
    base_x = np.floor(src_x).astype(np.int32)
    acc = np.zeros((src_y.shape[0], src_x.shape[0], channels), dtype=np.float64)
    weight_sum = np.zeros((src_y.shape[0], src_x.shape[0]), dtype=np.float64)
    for y_tap in y_off:
        row_index = base_y + int(y_tap)
        y_valid = (row_index >= 0) & (row_index < src_h)
        dy = (row_index - src_y) / blur_y
        rows = image[np.clip(row_index, 0, src_h - 1)]
        _ewa_accumulate_x(acc, weight_sum, rows, base_x, x_off, src_x, dy, y_valid, src_w, blur_x, support)
    if np.any(~np.isfinite(weight_sum) | (np.abs(weight_sum) < _WEIGHT_EPS)):
        raise AlgorithmError(f"{algorithm_id} filter weight sum vanished; refusing to fall back.")
    return acc / weight_sum[..., None]


def _ewa_accumulate_x(
    acc: np.ndarray,
    weight_sum: np.ndarray,
    rows: np.ndarray,
    base_x: np.ndarray,
    x_off: np.ndarray,
    src_x: np.ndarray,
    dy: np.ndarray,
    y_valid: np.ndarray,
    src_w: int,
    blur_x: float,
    support: float,
) -> None:
    for x_tap in x_off:
        col_index = base_x + int(x_tap)
        x_valid = (col_index >= 0) & (col_index < src_w)
        dx = (col_index - src_x) / blur_x
        radius = np.hypot(dy[:, None], dx[None, :])
        inside = radius < support
        weight = np.zeros(radius.shape, dtype=np.float64)
        if np.any(inside):
            sample = radius[inside]
            weight[inside] = jinc(sample) * jinc(sample / support)
        weight = np.where(y_valid[:, None] & x_valid[None, :], weight, 0.0)
        gathered = rows[:, np.clip(col_index, 0, src_w - 1), :]
        acc += gathered * weight[..., None]
        weight_sum += weight

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
        premul = _premultiply(_require_rgba(frame, algorithm_id, dtype=np.float32))
        filtered = _separable(premul, width, height, kernel, support, algorithm_id, dering=dering)
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


def _require_rgba(frame: np.ndarray, algorithm_id: str, dtype: np.dtype = np.float64) -> np.ndarray:
    try:
        array = np.asarray(frame, dtype=dtype)
    except (TypeError, ValueError) as exc:
        raise AlgorithmError(f"{algorithm_id} expected numeric HxWx4 frames.") from exc
    if array.ndim != 3 or array.shape[2] != 4 or array.shape[0] < 1 or array.shape[1] < 1:
        raise AlgorithmError(f"{algorithm_id} expected HxWx4 frames, got shape {getattr(frame, 'shape', None)}.")
    if not np.isfinite(array).all():
        raise AlgorithmError(f"{algorithm_id} refused a frame with non-finite values.")
    return array


def _premultiply(frame: np.ndarray) -> np.ndarray:
    premul = np.array(frame, copy=True)
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


# One gathered tap at a time. A full-frame copy per Lanczos tap is what spilled dering into swap.
_GATHER_BYTES = 4 * 1024 * 1024


def _scan_chunk(row_count: int, width: int, channels: int) -> int:
    row_bytes = max(width, 1) * channels * np.dtype(np.float32).itemsize
    return max(1, min(row_count, _GATHER_BYTES // max(row_bytes, 1)))


def _axis_plan(
    src_len: int,
    dst_len: int,
    support: float,
    kernel: Kernel,
    algorithm_id: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    indices, delta, valid = _tap_table(src_len, dst_len, support)
    weights = _normalized_weights(delta, valid, kernel, algorithm_id)
    clipped = np.clip(indices, 0, src_len - 1)
    return (
        np.ascontiguousarray(clipped.T, dtype=np.intp),
        np.ascontiguousarray(weights.T, dtype=np.float32),
        np.ascontiguousarray(valid.T),
    )


def _apply_taps(image: np.ndarray, indices: np.ndarray, weights: np.ndarray) -> np.ndarray:
    if image.dtype != np.float32 or not image.flags.c_contiguous:
        image = np.ascontiguousarray(image, dtype=np.float32)
    row_count, _src, channels = image.shape
    n_taps, dst = indices.shape
    out = np.zeros((row_count, dst, channels), dtype=np.float32)
    active = [tap for tap in range(n_taps) if np.any(weights[tap])]
    if not active:
        return out
    chunk = _scan_chunk(row_count, dst, channels)
    gathered = np.empty((chunk, dst, channels), dtype=np.float32)
    for start in range(0, row_count, chunk):
        stop = min(row_count, start + chunk)
        block = image[start:stop]
        buf = gathered[: stop - start]
        acc = out[start:stop]
        for tap in active:
            np.take(block, indices[tap], axis=1, out=buf)
            np.multiply(buf, weights[tap][None, :, None], out=buf)
            np.add(acc, buf, out=acc)
    return out


def _separable(
    image: np.ndarray,
    dst_w: int,
    dst_h: int,
    kernel: Kernel,
    support: float,
    algorithm_id: str,
    *,
    dering: bool,
) -> np.ndarray:
    src_h, src_w, _channels = image.shape
    x_index, x_weight, x_valid = _axis_plan(src_w, dst_w, support, kernel, algorithm_id)
    y_index, y_weight, y_valid = _axis_plan(src_h, dst_h, support, kernel, algorithm_id)
    wide = _apply_taps(image, x_index, x_weight)
    tall = np.ascontiguousarray(np.swapaxes(wide, 0, 1))
    high = _apply_taps(tall, y_index, y_weight)
    filtered = np.ascontiguousarray(np.swapaxes(high, 0, 1))
    if dering:
        _clamp_rgb_to_neighborhood(filtered, image[..., :3], y_index, y_valid, x_index, x_valid, algorithm_id)
    return filtered


def _clamp_rgb_to_neighborhood(
    filtered: np.ndarray,
    source_rgb: np.ndarray,
    y_index: np.ndarray,
    y_valid: np.ndarray,
    x_index: np.ndarray,
    x_valid: np.ndarray,
    algorithm_id: str,
) -> None:
    """Keep each RGB sample inside the source window that built it.

    Lanczos's negative lobe rings past a step. Clamping to that window's min
    and max removes the halo without pulling in a different kernel.
    """
    lo, hi = _neighborhood_range(source_rgb, y_index, y_valid, x_index, x_valid, algorithm_id)
    rgb = filtered[..., :3]
    np.clip(rgb, lo, hi, out=rgb)


def _neighborhood_range(
    rgb: np.ndarray,
    y_index: np.ndarray,
    y_valid: np.ndarray,
    x_index: np.ndarray,
    x_valid: np.ndarray,
    algorithm_id: str,
) -> tuple[np.ndarray, np.ndarray]:
    rgb = np.ascontiguousarray(rgb, dtype=np.float32)
    src_w = int(rgb.shape[1])
    channels = int(rgb.shape[2])
    dst_h = int(y_index.shape[1])
    dst_w = int(x_index.shape[1])
    lo = np.full((dst_h, dst_w, channels), np.inf, dtype=np.float32)
    hi = np.full((dst_h, dst_w, channels), -np.inf, dtype=np.float32)
    chunk = _scan_chunk(dst_h, max(src_w, dst_w), channels)
    vertical_lo = np.empty((chunk, src_w, channels), dtype=np.float32)
    vertical_hi = np.empty((chunk, src_w, channels), dtype=np.float32)
    row_buf = np.empty((chunk, src_w, channels), dtype=np.float32)
    col_buf = np.empty((chunk, dst_w, channels), dtype=np.float32)
    for start in range(0, dst_h, chunk):
        stop = min(dst_h, start + chunk)
        _reduce_vertical(rgb, y_index, y_valid, start, stop, vertical_lo, vertical_hi, row_buf)
        _reduce_horizontal(
            vertical_lo[: stop - start],
            vertical_hi[: stop - start],
            x_index,
            x_valid,
            lo[start:stop],
            hi[start:stop],
            col_buf[: stop - start],
        )
    if not np.isfinite(lo).all() or not np.isfinite(hi).all():
        raise AlgorithmError(f"{algorithm_id} found an empty source neighborhood; refusing to fall back.")
    return lo, hi


def _reduce_vertical(
    rgb: np.ndarray,
    y_index: np.ndarray,
    y_valid: np.ndarray,
    start: int,
    stop: int,
    vertical_lo: np.ndarray,
    vertical_hi: np.ndarray,
    row_buf: np.ndarray,
) -> None:
    span = stop - start
    vlo = vertical_lo[:span]
    vhi = vertical_hi[:span]
    rows = row_buf[:span]
    vlo.fill(np.inf)
    vhi.fill(-np.inf)
    for tap in range(y_index.shape[0]):
        valid = y_valid[tap, start:stop]
        if not np.any(valid):
            continue
        np.take(rgb, y_index[tap, start:stop], axis=0, out=rows)
        # where= leaves pixels outside this tap's window untouched, without copying lo/hi.
        mask = valid[:, None, None]
        np.minimum(vlo, rows, out=vlo, where=mask)
        np.maximum(vhi, rows, out=vhi, where=mask)


def _reduce_horizontal(
    vertical_lo: np.ndarray,
    vertical_hi: np.ndarray,
    x_index: np.ndarray,
    x_valid: np.ndarray,
    lo: np.ndarray,
    hi: np.ndarray,
    col_buf: np.ndarray,
) -> None:
    for tap in range(x_index.shape[0]):
        valid = x_valid[tap]
        if not np.any(valid):
            continue
        cols = x_index[tap]
        mask = valid[None, :, None]
        np.take(vertical_lo, cols, axis=1, out=col_buf)
        np.minimum(lo, col_buf, out=lo, where=mask)
        np.take(vertical_hi, cols, axis=1, out=col_buf)
        np.maximum(hi, col_buf, out=hi, where=mask)


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

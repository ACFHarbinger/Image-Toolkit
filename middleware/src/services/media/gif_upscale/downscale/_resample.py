"""Box filter shared by the GIF downscalers. Not a backend; the registry skips ``_`` modules."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from middleware.src.services.media.gif_upscale.base import AlgorithmError, AlgorithmSpec
from middleware.src.services.media.gif_upscale.registry import register_algorithm

# Inverse of the sRGB knot 0.04045. The rounded constant 0.0031308 does not round-trip.
_LINEAR_KNOT = 0.04045 / 12.92
_PATCH = 2
FrameFn = Callable[[np.ndarray, int, int], np.ndarray]


def _available() -> tuple[bool, str]:
    return (True, "")


def register_downscaler(algorithm_id: str, upscale: Callable) -> None:
    register_algorithm(
        AlgorithmSpec(
            id=algorithm_id,
            family="downscale",
            content="any",
            kind="classical",
            supports_scale=frozenset(),
            supports_downscale=True,
            needs_gpu=False,
            vram_mb_estimate=0,
            license="MIT",
            weights_sha256=None,
            available=_available,
        ),
        upscale,
    )


def output_size(opts: dict) -> tuple[int, int]:
    size = opts["size"]
    width, height = int(size[0]), int(size[1])
    if width < 1 or height < 1:
        raise ValueError("target size must be positive")
    return width, height


def reject_upscale(algorithm_id: str, frame: np.ndarray, width: int, height: int) -> None:
    source_height, source_width = frame.shape[:2]
    if width > source_width or height > source_height:
        raise AlgorithmError(f"{algorithm_id} does not upscale.")


def to_float32(image: np.ndarray) -> np.ndarray:
    return np.clip(np.asarray(image, dtype=np.float64), 0.0, 1.0).astype(np.float32)


def resize_frames(algorithm_id: str, frames: list[np.ndarray], opts: dict, resample: FrameFn) -> list[np.ndarray]:
    width, height = output_size(opts)
    resized: list[np.ndarray] = []
    for frame in frames:
        reject_upscale(algorithm_id, frame, width, height)
        if frame.shape[0] == height and frame.shape[1] == width:
            resized.append(to_float32(frame))
        else:
            resized.append(to_float32(resample(frame, height, width)))
    return resized


def srgb_to_linear(encoded: np.ndarray) -> np.ndarray:
    encoded = np.asarray(encoded, dtype=np.float64)
    return np.where(encoded <= 0.04045, encoded / 12.92, ((encoded + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(linear: np.ndarray) -> np.ndarray:
    linear = np.asarray(linear, dtype=np.float64)
    return np.where(linear <= _LINEAR_KNOT, linear * 12.92, 1.055 * np.power(np.maximum(linear, 0.0), 1.0 / 2.4) - 0.055)


def encoded_area(frame: np.ndarray, out_h: int, out_w: int) -> np.ndarray:
    return _premul_area(_prepare(frame, linear=False), out_h, out_w)


def linear_area(frame: np.ndarray, out_h: int, out_w: int) -> np.ndarray:
    return _encode_linear(_premul_area(_prepare(frame, linear=True), out_h, out_w))


def ssim_area(frame: np.ndarray, out_h: int, out_w: int) -> np.ndarray:
    """Linear-light area, plus the Öztireli contrast ratio. Flat patches have no residual to scale."""
    prepared = _prepare(frame, linear=True)
    base = _premul_area(prepared, out_h, out_w)
    low = area_downsample(prepared, out_h, out_w)
    second = area_downsample(prepared * prepared, out_h, out_w)
    mean, ratio = _contrast_stats(low, second)
    sharpened = _amplify(low, mean, ratio)
    # The ratio is unbounded; clamp so a channel cannot leave [0, 1].
    boosted = np.clip(base + (sharpened - low), 0.0, 1.0)
    return _encode_linear(boosted)


def area_downsample(image: np.ndarray, out_h: int, out_w: int) -> np.ndarray:
    working = _resize_axis(np.asarray(image, dtype=np.float64), out_w, 1)
    return _resize_axis(working, out_h, 0)


def _prepare(frame: np.ndarray, *, linear: bool) -> np.ndarray:
    straight = np.asarray(frame, dtype=np.float64)
    rgb = np.clip(straight[..., :3], 0.0, 1.0)
    alpha = np.clip(straight[..., 3:4], 0.0, 1.0)
    if linear:
        rgb = srgb_to_linear(rgb)
    # Alpha 0 has no color. Leaving the stored RGB in would tint the composite.
    rgb = np.where(alpha > 0.0, rgb, 0.0)
    return np.concatenate([rgb, alpha], axis=-1)


def _premul_area(straight: np.ndarray, out_h: int, out_w: int) -> np.ndarray:
    alpha = straight[..., 3:4]
    premul = np.concatenate([straight[..., :3] * alpha, alpha], axis=-1)
    return _unpremultiply(area_downsample(premul, out_h, out_w))


def _unpremultiply(premul: np.ndarray) -> np.ndarray:
    alpha = premul[..., 3:4]
    rgb = np.zeros(premul.shape[:2] + (3,), dtype=np.float64)
    np.divide(premul[..., :3], alpha, out=rgb, where=alpha > 0.0)
    return np.concatenate([rgb, alpha], axis=-1)


def _encode_linear(straight: np.ndarray) -> np.ndarray:
    rgb = linear_to_srgb(np.clip(straight[..., :3], 0.0, 1.0))
    return np.concatenate([rgb, straight[..., 3:4]], axis=-1)


def _resize_axis(image: np.ndarray, dst: int, axis: int) -> np.ndarray:
    if image.shape[axis] == dst:
        return image
    moved = np.moveaxis(image, axis, 0)
    reduced = _box_reduce(moved.reshape(moved.shape[0], -1), dst)
    return np.moveaxis(reduced.reshape((dst, *moved.shape[1:])), 0, axis)


def _box_reduce(samples: np.ndarray, dst: int) -> np.ndarray:
    """Coverage-weighted mean. Prefix integrals sample the piecewise-constant pixels."""
    src, count = samples.shape
    cumulative = np.empty((src + 1, count), dtype=np.float64)
    cumulative[0] = 0.0
    np.cumsum(samples, axis=0, out=cumulative[1:])
    edges = np.arange(dst + 1, dtype=np.float64) * src / dst
    edges[-1] = src
    prefix = _integral(cumulative, samples, edges)
    spans = np.diff(edges)
    return (prefix[1:] - prefix[:-1]) / spans[:, None]


def _integral(cumulative: np.ndarray, samples: np.ndarray, positions: np.ndarray) -> np.ndarray:
    src = samples.shape[0]
    floor = np.floor(positions)
    frac = positions - floor
    index = np.clip(floor.astype(np.int64), 0, src)
    covered = cumulative[index]
    partial = np.zeros_like(covered)
    inside = index < src
    if np.any(inside):
        partial[inside] = samples[index[inside]] * frac[inside, None]
    return covered + partial


def _patch_mean(image: np.ndarray) -> np.ndarray:
    height, width = image.shape[:2]
    total = np.zeros_like(image)
    for dy in range(_PATCH):
        rows = np.clip(np.arange(height) + dy, 0, height - 1)
        for dx in range(_PATCH):
            cols = np.clip(np.arange(width) + dx, 0, width - 1)
            total += image[np.ix_(rows, cols)]
    return total / float(_PATCH * _PATCH)


def _contrast_stats(low: np.ndarray, second: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mean = _patch_mean(low)
    low_var = np.maximum(_patch_mean(low * low) - mean * mean, 0.0)
    high_var = np.maximum(_patch_mean(second) - mean * mean, 0.0)
    # σ_low == 0 makes σ_high/σ_low undefined. Those patches stay on the area value.
    ratio = np.full(low.shape, 2.0, dtype=np.float64)
    stable = low_var >= 1e-6
    np.divide(high_var, low_var, out=ratio, where=stable)
    np.sqrt(ratio, out=ratio, where=stable)
    return mean, ratio


def _amplify(low: np.ndarray, mean: np.ndarray, ratio: np.ndarray) -> np.ndarray:
    height, width = low.shape[:2]
    total = np.zeros_like(low)
    for oy in range(_PATCH):
        rows = np.clip(np.arange(height) - oy, 0, height - 1)
        for ox in range(_PATCH):
            cols = np.clip(np.arange(width) - ox, 0, width - 1)
            local_mean = mean[np.ix_(rows, cols)]
            local_ratio = ratio[np.ix_(rows, cols)]
            total += local_mean + local_ratio * (low - local_mean)
    return total / float(_PATCH * _PATCH)

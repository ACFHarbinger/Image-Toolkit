"""Anime4K v1 push (bloc97, MIT). No CNN and no weights.

Luminance is a heightmap. Where one side of a pixel is consistently lighter, the
pixel takes on that side's color so a dark line loses its blurred edge. The
resize then samples along the edge and falls back to bilinear where the
gradient is weak.
"""

from __future__ import annotations

import numpy as np

from middleware.src.services.media.gif_upscale.base import AlgorithmError, AlgorithmSpec
from middleware.src.services.media.gif_upscale.registry import register_algorithm

# A hard step has central-difference magnitude 0.5. At or above half of that
# the resize follows the edge; below it the blend is mostly bilinear.
_EDGE_REFERENCE = np.float32(0.25)
_PUSH_STRENGTH = np.float32(0.6)
_ALPHA_EPS = np.float32(1e-8)

# Eight v1 push kernels. A side wins only when every sample on it is lighter
# than the center and the opposite side: one strong edge, not texture noise.
_PUSH_KERNELS = (
    (("tl", "tc", "tr"), ("br", "bc", "bl")),
    (("br", "bc", "bl"), ("tl", "tc", "tr")),
    (("mr", "tc", "tr"), ("ml", "bc")),
    (("bl", "ml", "bc"), ("mr", "tc")),
    (("mr", "br", "tr"), ("ml", "tl", "bl")),
    (("ml", "tl", "bl"), ("mr", "br", "tr")),
    (("mr", "br", "bc"), ("ml", "tc")),
    (("tc", "ml", "tl"), ("mr", "bc")),
)
_OFFSETS = {
    "tl": (-1, -1),
    "tc": (-1, 0),
    "tr": (-1, 1),
    "ml": (0, -1),
    "mr": (0, 1),
    "bl": (1, -1),
    "bc": (1, 0),
    "br": (1, 1),
}


def upscale(frames: list[np.ndarray], scale: float, opts: dict) -> list[np.ndarray]:
    options = opts or {}
    return [_upscale_frame(np.asarray(frame, dtype=np.float32), float(scale), options) for frame in frames]


def _upscale_frame(frame: np.ndarray, scale: float, opts: dict) -> np.ndarray:
    height, width = frame.shape[:2]
    target_w, target_h = _target_size(width, height, scale, opts)
    straight = frame[..., :3]
    alpha = frame[..., 3:4]
    premul = np.empty((height, width, 4), dtype=np.float32)
    premul[..., :3] = straight * alpha
    premul[..., 3] = alpha[..., 0]
    pushed = _push_lines(premul, _luminance(straight))
    if target_w == width and target_h == height:
        scaled = pushed
    else:
        gradients = _central_gradients(_luminance(_straight_rgb(pushed)))
        scaled = _resize_along_edges(pushed, gradients, target_w, target_h)
    return _unpremultiply(scaled)


def _target_size(width: int, height: int, scale: float, opts: dict) -> tuple[int, int]:
    size = opts.get("size")
    if size:
        target_w = int(size[0])
        target_h = int(size[1])
    else:
        target_w = int(round(width * scale))
        target_h = int(round(height * scale))
    if target_w < 1 or target_h < 1:
        raise AlgorithmError("target size must be positive")
    return target_w, target_h


def _luminance(rgb: np.ndarray) -> np.ndarray:
    return rgb[..., 0] * np.float32(0.299) + rgb[..., 1] * np.float32(0.587) + rgb[..., 2] * np.float32(0.114)


def _straight_rgb(premul: np.ndarray) -> np.ndarray:
    alpha = premul[..., 3:4]
    straight = np.empty(premul.shape[:-1] + (3,), dtype=np.float32)
    np.divide(premul[..., :3], alpha, out=straight, where=alpha > _ALPHA_EPS)
    np.copyto(straight, 0, where=np.broadcast_to(alpha <= _ALPHA_EPS, straight.shape))
    return straight


def _central_gradients(luma: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    padded = np.pad(luma, 1, mode="edge")
    grad_x = (padded[1:-1, 2:] - padded[1:-1, :-2]) * np.float32(0.5)
    grad_y = (padded[2:, 1:-1] - padded[:-2, 1:-1]) * np.float32(0.5)
    return grad_x, grad_y


def _neighbors(image: np.ndarray) -> dict[str, np.ndarray]:
    extra = tuple((0, 0) for _ in range(image.ndim - 2))
    padded = np.pad(image, ((1, 1), (1, 1)) + extra, mode="edge")
    height, width = image.shape[:2]
    return {name: padded[1 + dy : 1 + dy + height, 1 + dx : 1 + dx + width] for name, (dy, dx) in _OFFSETS.items()}


def _push_lines(premul: np.ndarray, luma: np.ndarray) -> np.ndarray:
    colors = _neighbors(premul)
    lumas = _neighbors(luma)
    lightest_color = premul.copy()
    lightest_luma = luma.copy()
    for toward, opposite in _PUSH_KERNELS:
        side_luma = [lumas[name] for name in toward]
        side_min = np.minimum.reduce(side_luma)
        side_max = np.maximum.reduce([luma, *[lumas[name] for name in opposite]])
        average_luma = np.add.reduce(side_luma) / np.float32(3)
        average_color = np.add.reduce([colors[name] for name in toward]) / np.float32(3)
        blended_luma = luma * (np.float32(1) - _PUSH_STRENGTH) + average_luma * _PUSH_STRENGTH
        blended_color = premul * (np.float32(1) - _PUSH_STRENGTH) + average_color * _PUSH_STRENGTH
        take = (side_min > side_max) & (blended_luma > lightest_luma)
        lightest_luma = np.where(take, blended_luma, lightest_luma)
        lightest_color = np.where(take[..., None], blended_color, lightest_color)
    return lightest_color


def _resize_along_edges(
    premul: np.ndarray,
    gradients: tuple[np.ndarray, np.ndarray],
    target_w: int,
    target_h: int,
) -> np.ndarray:
    src_h, src_w = premul.shape[:2]
    ys = _dst_to_src(src_h, target_h)
    xs = _dst_to_src(src_w, target_w)
    grid_y = np.broadcast_to(ys[:, None], (target_h, target_w))
    grid_x = np.broadcast_to(xs[None, :], (target_h, target_w))
    sample_x, sample_y = _steer_along_edges(grid_x, grid_y, gradients)
    return _bilinear(premul, sample_x, sample_y)


def _dst_to_src(src_size: int, dst_size: int) -> np.ndarray:
    # Pixel-center map, same convention as Pillow's bilinear. Keeps a constant
    # image constant and puts a 2x line on the two rows the regression compares.
    dst = np.arange(dst_size, dtype=np.float32)
    return (dst + np.float32(0.5)) * (np.float32(src_size) / np.float32(dst_size)) - np.float32(0.5)


def _steer_along_edges(
    grid_x: np.ndarray,
    grid_y: np.ndarray,
    gradients: tuple[np.ndarray, np.ndarray],
) -> tuple[np.ndarray, np.ndarray]:
    grad_x, grad_y = gradients
    src_h, src_w = grad_x.shape
    nearest_x = np.clip(np.rint(grid_x).astype(np.int32), 0, src_w - 1)
    nearest_y = np.clip(np.rint(grid_y).astype(np.int32), 0, src_h - 1)
    local_x = grad_x[nearest_y, nearest_x]
    local_y = grad_y[nearest_y, nearest_x]
    magnitude = np.hypot(local_x, local_y)
    gate = np.clip(magnitude / _EDGE_REFERENCE, 0.0, 1.0).astype(np.float32)
    scale = np.maximum(magnitude, np.float32(1e-8))
    normal_x = (local_x / scale).astype(np.float32)
    normal_y = (local_y / scale).astype(np.float32)
    offset_x = grid_x - nearest_x.astype(np.float32)
    offset_y = grid_y - nearest_y.astype(np.float32)
    across = offset_x * normal_x + offset_y * normal_y
    # Drop the part of the sample offset that crosses the edge. What remains
    # moves along the line. ``gate`` is 0 on a flat region, so this is bilinear.
    return grid_x - across * normal_x * gate, grid_y - across * normal_y * gate


def _bilinear(image: np.ndarray, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    height, width = image.shape[:2]
    x0 = np.floor(xs).astype(np.int32)
    y0 = np.floor(ys).astype(np.int32)
    fx = (xs - x0.astype(np.float32)).astype(np.float32)[..., None]
    fy = (ys - y0.astype(np.float32)).astype(np.float32)[..., None]
    x0c = np.clip(x0, 0, width - 1)
    x1c = np.clip(x0 + 1, 0, width - 1)
    y0c = np.clip(y0, 0, height - 1)
    y1c = np.clip(y0 + 1, 0, height - 1)
    one = np.float32(1)
    top = image[y0c, x0c] * (one - fx) + image[y0c, x1c] * fx
    bottom = image[y1c, x0c] * (one - fx) + image[y1c, x1c] * fx
    return (top * (one - fy) + bottom * fy).astype(np.float32, copy=False)


def _unpremultiply(premul: np.ndarray) -> np.ndarray:
    alpha = premul[..., 3:4]
    rgb = np.empty(premul.shape[:-1] + (3,), dtype=np.float32)
    np.divide(premul[..., :3], alpha, out=rgb, where=alpha > _ALPHA_EPS)
    np.copyto(rgb, 0, where=np.broadcast_to(alpha <= _ALPHA_EPS, rgb.shape))
    out = np.empty_like(premul)
    out[..., :3] = rgb
    out[..., 3] = premul[..., 3]
    return out


register_algorithm(
    AlgorithmSpec(
        id="anime4k",
        family="anime4k",
        content="anime",
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

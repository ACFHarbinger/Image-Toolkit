"""Deterministic circular-brush stamping onto a layer's pixel buffer or
mask (standalone-editor paint-tools slice; see
``docs/moon/roadmaps/engine_architecture.md``'s gate-5 exception).

Pure numpy, no Qt -- mirrors ``layer_stack.py``'s split between "what the
data is / how it changes" (here) and "how it gets on screen" (the
``LayerCanvas`` widget in ``cel_shaded_generator_gui``, which maps mouse
events to pixel coordinates and calls into this module).

``stamp_dot``/``stamp_line`` paint HxWx4 RGBA layer pixels with a
hard-edged circular brush, deliberately not anti-aliased -- the simplest
deterministic stamp that is still testable pixel-for-pixel.
``stamp_dot_soft``/``stamp_line_soft`` add a ``hardness`` falloff on the
same straight-alpha "over" compositing: fully opaque within
``hardness * radius`` of the center, then linearly fading to fully
transparent at the edge (``hardness=1.0`` degenerates to the exact same
coverage as the hard brush). ``erase_dot``/``erase_line`` share the same
circular/falloff coverage but reduce ``pixels``' existing alpha instead of
blending a new color over it -- the standard raster-editor eraser
semantic, and the reason it needs its own compositing rather than reusing
``stamp_*`` with a transparent color (an "over" blend with a fully
transparent top color is a no-op, not an erase). ``stamp_mask_dot``/
``stamp_mask_line`` paint an HxW uint8 mask by direct overwrite instead --
alpha-blending a mask against itself has no useful meaning, so painting a
mask always just sets the covered pixels to the given intensity (255
reveals, 0 hides); masks have no soft variant or eraser for the same
reason -- painting a mask to 0 already *is* erasing it.
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "erase_dot",
    "erase_line",
    "stamp_dot",
    "stamp_dot_soft",
    "stamp_line",
    "stamp_line_soft",
    "stamp_mask_dot",
    "stamp_mask_line",
]


def _circular_mask(radius: int) -> np.ndarray:
    offsets = np.arange(-radius, radius + 1)
    yy, xx = np.meshgrid(offsets, offsets, indexing="ij")
    return (xx**2 + yy**2) <= radius**2


def _circular_falloff(radius: int, hardness: float) -> np.ndarray:
    """Per-pixel coverage in ``[0, 1]`` for a soft circular brush: fully
    opaque (``1.0``) within ``hardness * radius`` of the center, then
    linearly fading to ``0.0`` at ``radius``. ``hardness=1.0`` produces the
    exact same coverage as :func:`_circular_mask` (no soft edge at all);
    ``hardness=0.0`` fades from the very center."""
    offsets = np.arange(-radius, radius + 1)
    yy, xx = np.meshgrid(offsets, offsets, indexing="ij")
    distance = np.sqrt((xx**2 + yy**2).astype(np.float64))
    if radius == 0:
        return (distance <= 0).astype(np.float64)
    hard_radius = hardness * radius
    span = radius - hard_radius
    if span <= 0:
        return (distance <= radius).astype(np.float64)
    coverage = np.clip(1.0 - (distance - hard_radius) / span, 0.0, 1.0)
    coverage[distance <= hard_radius] = 1.0
    return coverage


def _clip_region(
    shape2d: tuple[int, int], cx: int, cy: int, radius: int, brush: np.ndarray
) -> tuple[np.ndarray, int, int, int, int] | None:
    """``brush`` (a ``(2*radius+1)``-square coverage array, boolean or
    float) clipped to ``shape2d``'s bounds, plus the matching pixel-array
    slice bounds ``(y0, y1, x0, x1)``. ``None`` if the brush falls
    entirely off-canvas."""
    height, width = shape2d
    diameter = brush.shape[0]
    x0, y0 = cx - radius, cy - radius
    img_x0, img_x1 = max(0, x0), min(width, x0 + diameter)
    img_y0, img_y1 = max(0, y0), min(height, y0 + diameter)
    if img_x0 >= img_x1 or img_y0 >= img_y1:
        return None
    brush_slice = brush[img_y0 - y0 : img_y1 - y0, img_x0 - x0 : img_x1 - x0]
    return brush_slice, img_y0, img_y1, img_x0, img_x1


def _blend_color_over(
    region: np.ndarray, mask: np.ndarray, color: tuple[int, int, int, int]
) -> None:
    """Straight-alpha "over" ``color`` onto ``region`` in place, wherever
    ``mask`` is true."""
    top_alpha = color[3] / 255.0
    if top_alpha <= 0 or not mask.any():
        return
    base_alpha = region[:, :, 3:4].astype(np.float64) / 255.0
    out_alpha = top_alpha + base_alpha * (1.0 - top_alpha)
    base_rgb = region[:, :, :3].astype(np.float64)
    top_rgb = np.array(color[:3], dtype=np.float64)
    blended = top_rgb * top_alpha + base_rgb * base_alpha * (1.0 - top_alpha)
    out_rgb = np.zeros_like(base_rgb)
    safe = out_alpha[:, :, 0] > 0
    out_rgb[safe] = blended[safe] / out_alpha[safe]
    new_rgb = np.clip(out_rgb, 0, 255).astype(np.uint8)
    new_alpha = np.clip(out_alpha[:, :, 0] * 255.0, 0, 255).astype(np.uint8)
    region[:, :, :3][mask] = new_rgb[mask]
    region[:, :, 3][mask] = new_alpha[mask]


def _blend_color_over_weighted(
    region: np.ndarray, weight: np.ndarray, color: tuple[int, int, int, int]
) -> None:
    """Straight-alpha "over" ``color`` onto ``region`` in place, scaling
    ``color``'s alpha per-pixel by ``weight`` (a ``[0, 1]`` coverage
    array) before blending -- the soft-brush counterpart of
    :func:`_blend_color_over`'s uniform boolean mask."""
    painted = weight > 0
    if color[3] <= 0 or not painted.any():
        return
    base_alpha = region[:, :, 3:4].astype(np.float64) / 255.0
    top_alpha = (weight * (color[3] / 255.0))[:, :, None]
    out_alpha = top_alpha + base_alpha * (1.0 - top_alpha)
    base_rgb = region[:, :, :3].astype(np.float64)
    top_rgb = np.array(color[:3], dtype=np.float64)
    blended = top_rgb * top_alpha + base_rgb * base_alpha * (1.0 - top_alpha)
    out_rgb = np.zeros_like(base_rgb)
    safe = out_alpha[:, :, 0] > 0
    out_rgb[safe] = blended[safe] / out_alpha[safe]
    new_rgb = np.clip(out_rgb, 0, 255).astype(np.uint8)
    new_alpha = np.clip(out_alpha[:, :, 0] * 255.0, 0, 255).astype(np.uint8)
    region[:, :, :3][painted] = new_rgb[painted]
    region[:, :, 3][painted] = new_alpha[painted]


def _erase_alpha(region: np.ndarray, weight: np.ndarray) -> None:
    """Reduce ``region``'s alpha channel in place by ``weight`` (a
    ``[0, 1]`` coverage array, bool or float): ``new_alpha = alpha * (1 -
    weight)``. RGB is left untouched -- irrelevant once alpha reaches
    zero, and a partially erased soft edge should keep revealing the same
    color underneath, not a different one."""
    coverage = weight.astype(np.float64)
    erased = coverage > 0
    if not erased.any():
        return
    alpha = region[:, :, 3].astype(np.float64)
    new_alpha = np.clip(alpha * (1.0 - coverage), 0, 255).astype(np.uint8)
    region[:, :, 3][erased] = new_alpha[erased]


def _validate_pixels(pixels: np.ndarray) -> None:
    if (
        not isinstance(pixels, np.ndarray)
        or pixels.ndim != 3
        or pixels.shape[2] != 4
        or pixels.dtype != np.uint8
    ):
        raise ValueError("pixels must be an HxWx4 uint8 RGBA array")


def _validate_mask_buffer(mask_buffer: np.ndarray) -> None:
    if (
        not isinstance(mask_buffer, np.ndarray)
        or mask_buffer.ndim != 2
        or mask_buffer.dtype != np.uint8
    ):
        raise ValueError("mask buffer must be an HxW uint8 array")


def _validate_color(color: tuple[int, int, int, int]) -> None:
    if len(color) != 4 or not all(isinstance(c, int) and 0 <= c <= 255 for c in color):
        raise ValueError("color must be an (r, g, b, a) tuple of ints in [0, 255]")


def _validate_radius(radius: int) -> None:
    if not isinstance(radius, int) or radius < 0:
        raise ValueError("radius must be a non-negative integer")


def _validate_intensity(intensity: int) -> None:
    if not isinstance(intensity, int) or not 0 <= intensity <= 255:
        raise ValueError("intensity must be an int in [0, 255]")


def _validate_hardness(hardness: float) -> None:
    if not isinstance(hardness, (int, float)) or not 0.0 <= hardness <= 1.0:
        raise ValueError("hardness must be a float in [0.0, 1.0]")


def stamp_dot(
    pixels: np.ndarray, cx: int, cy: int, radius: int, color: tuple[int, int, int, int]
) -> None:
    """Stamp one hard-edged filled circle of ``color`` centered at pixel
    ``(cx, cy)`` onto ``pixels`` in place. Silently clips to the canvas
    bounds; a circle entirely off-canvas is a no-op."""
    _validate_pixels(pixels)
    _validate_color(color)
    _validate_radius(radius)
    clip = _clip_region(pixels.shape[:2], cx, cy, radius, _circular_mask(radius))
    if clip is None:
        return
    mask_slice, y0, y1, x0, x1 = clip
    _blend_color_over(pixels[y0:y1, x0:x1], mask_slice, color)


def stamp_line(
    pixels: np.ndarray,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    radius: int,
    color: tuple[int, int, int, int],
) -> None:
    """Stamp overlapping dots along the segment from ``(x0, y0)`` to
    ``(x1, y1)`` so a fast mouse drag still paints a continuous stroke
    rather than isolated dots."""
    if x0 == x1 and y0 == y1:
        stamp_dot(pixels, x0, y0, radius, color)
        return
    distance = float(np.hypot(x1 - x0, y1 - y0))
    spacing = max(1, radius // 2 or 1)
    count = max(1, int(distance / spacing) + 1)
    for x, y in zip(np.linspace(x0, x1, count), np.linspace(y0, y1, count), strict=True):
        stamp_dot(pixels, int(round(x)), int(round(y)), radius, color)


def stamp_dot_soft(
    pixels: np.ndarray,
    cx: int,
    cy: int,
    radius: int,
    color: tuple[int, int, int, int],
    hardness: float,
) -> None:
    """Stamp one soft-edged filled circle of ``color`` centered at pixel
    ``(cx, cy)`` onto ``pixels`` in place, fully opaque within
    ``hardness * radius`` and linearly fading to transparent at ``radius``
    (``hardness=1.0`` is pixel-identical to :func:`stamp_dot`). Silently
    clips to the canvas bounds; a circle entirely off-canvas is a no-op."""
    _validate_pixels(pixels)
    _validate_color(color)
    _validate_radius(radius)
    _validate_hardness(hardness)
    clip = _clip_region(pixels.shape[:2], cx, cy, radius, _circular_falloff(radius, hardness))
    if clip is None:
        return
    coverage_slice, y0, y1, x0, x1 = clip
    _blend_color_over_weighted(pixels[y0:y1, x0:x1], coverage_slice, color)


def stamp_line_soft(
    pixels: np.ndarray,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    radius: int,
    color: tuple[int, int, int, int],
    hardness: float,
) -> None:
    """Stamp overlapping soft dots along the segment from ``(x0, y0)`` to
    ``(x1, y1)``, mirroring :func:`stamp_line` for :func:`stamp_dot_soft`."""
    if x0 == x1 and y0 == y1:
        stamp_dot_soft(pixels, x0, y0, radius, color, hardness)
        return
    distance = float(np.hypot(x1 - x0, y1 - y0))
    spacing = max(1, radius // 2 or 1)
    count = max(1, int(distance / spacing) + 1)
    for x, y in zip(np.linspace(x0, x1, count), np.linspace(y0, y1, count), strict=True):
        stamp_dot_soft(pixels, int(round(x)), int(round(y)), radius, color, hardness)


def erase_dot(pixels: np.ndarray, cx: int, cy: int, radius: int, hardness: float) -> None:
    """Reduce the alpha of ``pixels`` within a circular brush of ``radius``
    centered at ``(cx, cy)``, in place -- the eraser counterpart of
    :func:`stamp_dot`/:func:`stamp_dot_soft`. ``hardness=1.0`` erases
    fully and uniformly within the radius (matching :func:`stamp_dot`'s
    hard edge); lower values fade the erase toward the edge, same as
    :func:`stamp_dot_soft`. Silently clips to the canvas bounds; a circle
    entirely off-canvas is a no-op."""
    _validate_pixels(pixels)
    _validate_radius(radius)
    _validate_hardness(hardness)
    brush = _circular_mask(radius) if hardness >= 1.0 else _circular_falloff(radius, hardness)
    clip = _clip_region(pixels.shape[:2], cx, cy, radius, brush)
    if clip is None:
        return
    coverage_slice, y0, y1, x0, x1 = clip
    _erase_alpha(pixels[y0:y1, x0:x1], coverage_slice)


def erase_line(
    pixels: np.ndarray, x0: int, y0: int, x1: int, y1: int, radius: int, hardness: float
) -> None:
    """Stamp overlapping erase dots along the segment from ``(x0, y0)`` to
    ``(x1, y1)``, mirroring :func:`stamp_line` for :func:`erase_dot`."""
    if x0 == x1 and y0 == y1:
        erase_dot(pixels, x0, y0, radius, hardness)
        return
    distance = float(np.hypot(x1 - x0, y1 - y0))
    spacing = max(1, radius // 2 or 1)
    count = max(1, int(distance / spacing) + 1)
    for x, y in zip(np.linspace(x0, x1, count), np.linspace(y0, y1, count), strict=True):
        erase_dot(pixels, int(round(x)), int(round(y)), radius, hardness)


def stamp_mask_dot(mask_buffer: np.ndarray, cx: int, cy: int, radius: int, intensity: int) -> None:
    """Set every pixel of ``mask_buffer`` within ``radius`` of ``(cx, cy)``
    to ``intensity`` in place (255 fully reveals the layer, 0 fully hides
    it). Direct overwrite, not alpha-blended -- blending a mask against
    itself has no useful meaning."""
    _validate_mask_buffer(mask_buffer)
    _validate_intensity(intensity)
    _validate_radius(radius)
    clip = _clip_region(mask_buffer.shape, cx, cy, radius, _circular_mask(radius))
    if clip is None:
        return
    mask_slice, y0, y1, x0, x1 = clip
    region = mask_buffer[y0:y1, x0:x1]
    region[mask_slice] = intensity


def stamp_mask_line(
    mask_buffer: np.ndarray, x0: int, y0: int, x1: int, y1: int, radius: int, intensity: int
) -> None:
    """Stamp overlapping mask dots along the segment from ``(x0, y0)`` to
    ``(x1, y1)``, mirroring :func:`stamp_line`."""
    if x0 == x1 and y0 == y1:
        stamp_mask_dot(mask_buffer, x0, y0, radius, intensity)
        return
    distance = float(np.hypot(x1 - x0, y1 - y0))
    spacing = max(1, radius // 2 or 1)
    count = max(1, int(distance / spacing) + 1)
    for x, y in zip(np.linspace(x0, x1, count), np.linspace(y0, y1, count), strict=True):
        stamp_mask_dot(mask_buffer, int(round(x)), int(round(y)), radius, intensity)

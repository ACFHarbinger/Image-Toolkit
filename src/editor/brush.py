"""Deterministic circular-brush stamping onto a layer's pixel buffer
(standalone-editor paint-tools slice; see
``docs/moon/roadmaps/engine_architecture.md``'s gate-5 exception).

Pure numpy, no Qt -- mirrors ``layer_stack.py``'s split between "what the
data is / how it changes" (here) and "how it gets on screen" (the
``LayerCanvas`` widget in ``cel_shaded_generator_gui``, which maps mouse
events to pixel coordinates and calls into this module). A hard-edged
circular brush with straight-alpha "over" compositing, deliberately not
anti-aliased -- the simplest deterministic stamp that is still testable
pixel-for-pixel; a softer/anti-aliased brush is a later slice on the same
``stamp_dot``/``stamp_line`` contract.
"""

from __future__ import annotations

import numpy as np

__all__ = ["stamp_dot", "stamp_line"]


def _circular_mask(radius: int) -> np.ndarray:
    offsets = np.arange(-radius, radius + 1)
    yy, xx = np.meshgrid(offsets, offsets, indexing="ij")
    return (xx**2 + yy**2) <= radius**2


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


def _validate_pixels(pixels: np.ndarray) -> None:
    if (
        not isinstance(pixels, np.ndarray)
        or pixels.ndim != 3
        or pixels.shape[2] != 4
        or pixels.dtype != np.uint8
    ):
        raise ValueError("pixels must be an HxWx4 uint8 RGBA array")


def _validate_color(color: tuple[int, int, int, int]) -> None:
    if len(color) != 4 or not all(isinstance(c, int) and 0 <= c <= 255 for c in color):
        raise ValueError("color must be an (r, g, b, a) tuple of ints in [0, 255]")


def stamp_dot(
    pixels: np.ndarray, cx: int, cy: int, radius: int, color: tuple[int, int, int, int]
) -> None:
    """Stamp one hard-edged filled circle of ``color`` centered at pixel
    ``(cx, cy)`` onto ``pixels`` in place. Silently clips to the canvas
    bounds; a circle entirely off-canvas is a no-op."""
    _validate_pixels(pixels)
    _validate_color(color)
    if not isinstance(radius, int) or radius < 0:
        raise ValueError("radius must be a non-negative integer")
    height, width = pixels.shape[:2]
    mask = _circular_mask(radius)
    diameter = mask.shape[0]
    x0, y0 = cx - radius, cy - radius
    img_x0, img_x1 = max(0, x0), min(width, x0 + diameter)
    img_y0, img_y1 = max(0, y0), min(height, y0 + diameter)
    if img_x0 >= img_x1 or img_y0 >= img_y1:
        return
    mask_slice = mask[img_y0 - y0 : img_y1 - y0, img_x0 - x0 : img_x1 - x0]
    region = pixels[img_y0:img_y1, img_x0:img_x1]
    _blend_color_over(region, mask_slice, color)


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

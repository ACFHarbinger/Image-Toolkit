"""Separable Keys cubic with B=0, C=0.5 (Catmull-Rom) on premultiplied alpha."""

from __future__ import annotations

from middleware.src.services.media.gif_upscale.base import Frames
from middleware.src.services.media.gif_upscale.classical._resize import (
    mitchell_kernel,
    register_classical,
    resize_separable,
)

_KERNEL = mitchell_kernel(0.0, 0.5)


def upscale(frames: Frames, scale: float, opts: dict) -> Frames:
    # Negative lobes stay. Clamping them would hide the edge comparison with bicubic-sharper.
    return resize_separable(frames, scale, opts, "catmull-rom", _KERNEL, support=2.0)


register_classical("catmull-rom", upscale)

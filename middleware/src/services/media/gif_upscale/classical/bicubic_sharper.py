"""Separable Mitchell–Netravali cubic with B=0, C=0.75."""

from __future__ import annotations

from middleware.src.services.media.gif_upscale.base import Frames
from middleware.src.services.media.gif_upscale.classical._resize import (
    mitchell_kernel,
    register_classical,
    resize_separable,
)

_KERNEL = mitchell_kernel(0.0, 0.75)


def upscale(frames: Frames, scale: float, opts: dict) -> Frames:
    # C=0.75 rings harder than Catmull-Rom. Leave that overshoot so the step stays steeper.
    return resize_separable(frames, scale, opts, "bicubic-sharper", _KERNEL, support=2.0)


register_classical("bicubic-sharper", upscale)

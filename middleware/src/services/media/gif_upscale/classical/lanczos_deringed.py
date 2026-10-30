"""Separable Lanczos3 with a local clamp so step edges do not ring."""

from __future__ import annotations

from middleware.src.services.media.gif_upscale.base import Frames
from middleware.src.services.media.gif_upscale.classical._resize import (
    lanczos_kernel,
    register_classical,
    resize_separable,
)

_KERNEL = lanczos_kernel(3.0)


def upscale(frames: Frames, scale: float, opts: dict) -> Frames:
    # Omitted params["quality"] on an upscale is balanced, decided in resize_separable.
    return resize_separable(
        frames,
        scale,
        opts,
        "lanczos3-dering",
        _KERNEL,
        support=3.0,
        dering=True,
        clip_unit=True,
    )


register_classical("lanczos3-dering", upscale)

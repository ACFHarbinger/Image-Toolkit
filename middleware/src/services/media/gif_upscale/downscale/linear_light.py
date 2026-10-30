"""Area downscale in linear light, then encoded back to sRGB. Alpha is premultiplied in linear light."""

from __future__ import annotations

from middleware.src.services.media.gif_upscale.downscale._resample import (
    linear_area,
    register_downscaler,
    resize_frames,
)


def upscale(frames, scale, opts):
    del scale
    return resize_frames("linear-light", frames, opts, linear_area)


register_downscaler("linear-light", upscale)

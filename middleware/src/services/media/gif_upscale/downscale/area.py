"""Area (box) downscale in encoded sRGB. Alpha is premultiplied before the average."""

from __future__ import annotations

from middleware.src.services.media.gif_upscale.downscale._resample import (
    encoded_area,
    register_downscaler,
    resize_frames,
)


def upscale(frames, scale, opts):
    del scale
    return resize_frames("area", frames, opts, encoded_area)


register_downscaler("area", upscale)

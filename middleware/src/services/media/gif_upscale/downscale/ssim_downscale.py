"""SSIM downscale: linear-light area, then a clamped local-contrast residual."""

from __future__ import annotations

from middleware.src.services.media.gif_upscale.downscale._resample import (
    register_downscaler,
    resize_frames,
    ssim_area,
)


def upscale(frames, scale, opts):
    del scale
    return resize_frames("ssim-downscale", frames, opts, ssim_area)


register_downscaler("ssim-downscale", upscale)

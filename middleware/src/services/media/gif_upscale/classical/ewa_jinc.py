"""Elliptical weighted average with a 3-lobe jinc window on premultiplied alpha."""

from __future__ import annotations

from middleware.src.services.media.gif_upscale.base import Frames
from middleware.src.services.media.gif_upscale.classical._resize import register_classical, resize_ewa


def upscale(frames: Frames, scale: float, opts: dict) -> Frames:
    return resize_ewa(frames, scale, opts, "ewa-jinc")


register_classical("ewa-jinc", upscale)

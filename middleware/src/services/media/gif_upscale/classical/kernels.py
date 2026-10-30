"""Pillow kernels already exposed by the Sampler subtab. Any scale, including downscale."""

from __future__ import annotations

import numpy as np
from PIL import Image

from middleware.src.services.media.gif_upscale.base import AlgorithmSpec
from middleware.src.services.media.gif_upscale.registry import register_algorithm

_FILTERS = {
    "nearest": Image.Resampling.NEAREST,
    "bilinear": Image.Resampling.BILINEAR,
    "bicubic": Image.Resampling.BICUBIC,
    "lanczos": Image.Resampling.LANCZOS,
}


def resize_rgba(frames: list[np.ndarray], scale: float, opts: dict, resample: Image.Resampling) -> list[np.ndarray]:
    del scale
    resized: list[np.ndarray] = []
    for frame in frames:
        height, width = frame.shape[:2]
        size = opts.get("size")
        if size:
            target = (int(size[0]), int(size[1]))
        else:
            factor = float(opts.get("scale", 1))
            target = (max(1, round(width * factor)), max(1, round(height * factor)))
        if target[0] < 1 or target[1] < 1:
            raise ValueError("target size must be positive")
        image = Image.fromarray(_uint8(frame), "RGBA")
        try:
            output = image.resize(target, resample)
            try:
                resized.append(np.asarray(output).astype(np.float32) / 255.0)
            finally:
                output.close()
        finally:
            image.close()
    return resized


def _uint8(frame: np.ndarray) -> np.ndarray:
    array = np.asarray(frame)
    if array.dtype == np.uint8:
        return array
    return np.clip(np.rint(array.astype(np.float32) * 255.0), 0, 255).astype(np.uint8)


def _register(algorithm_id: str, resample: Image.Resampling) -> None:
    def upscale(frames: list[np.ndarray], scale: float, opts: dict) -> list[np.ndarray]:
        merged = dict(opts)
        merged.setdefault("scale", scale)
        return resize_rgba(frames, scale, merged, resample)

    register_algorithm(
        AlgorithmSpec(
            id=algorithm_id,
            family="pillow",
            content="any",
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


for _name, _filter in _FILTERS.items():
    _register(_name, _filter)

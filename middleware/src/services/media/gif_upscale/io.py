"""GIF decode. Pillow's seek yields the composited canvas; disposal math is tested beside it."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class GifClip:
    frames: list[np.ndarray]
    durations: list[int]
    loop: int


def iter_gif_frames(path: str) -> Iterator[tuple[np.ndarray, int, int]]:
    """Yield ``(rgba_uint8, duration_ms, loop)`` one frame at a time."""
    from PIL import Image

    with Image.open(path) as image:
        loop = int(image.info.get("loop", 0) or 0)
        count = int(getattr(image, "n_frames", 1) or 1)
        for index in range(count):
            image.seek(index)
            raw_duration = image.info.get("duration", 100)
            duration = 100 if raw_duration is None else int(raw_duration)
            yield np.asarray(image.convert("RGBA")).copy(), duration, loop


def decode_gif(path: str) -> GifClip:
    frames: list[np.ndarray] = []
    durations: list[int] = []
    loop = 0
    for frame, duration, frame_loop in iter_gif_frames(path):
        frames.append(frame)
        durations.append(duration)
        loop = frame_loop
    if not frames:
        raise ValueError("GIF has no frames.")
    return GifClip(frames, durations, loop)


def composite_disposal(
    canvas: np.ndarray,
    frame: np.ndarray,
    xy: tuple[int, int],
    disposal: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Draw one partial frame. Returns the displayed canvas and the canvas for the next frame.

    Disposal 2 clears the frame rectangle after it has been shown. Disposal 3 restores
    the canvas from before this frame. Other values leave the drawn canvas in place.
    """
    displayed = canvas.copy()
    x, y = xy
    height, width = frame.shape[:2]
    region = displayed[y : y + height, x : x + width]
    if region.shape[:2] != frame.shape[:2]:
        raise ValueError("frame extends outside the canvas")
    region[:] = _over(region, frame)
    if disposal == 2:
        nxt = displayed.copy()
        nxt[y : y + height, x : x + width] = 0
        return displayed, nxt
    if disposal == 3:
        return displayed, canvas.copy()
    return displayed, displayed.copy()


def _over(dst: np.ndarray, src: np.ndarray) -> np.ndarray:
    src_alpha = src[:, :, 3:4].astype(np.float32) / 255.0
    dst_alpha = dst[:, :, 3:4].astype(np.float32) / 255.0
    out_alpha = src_alpha + dst_alpha * (1.0 - src_alpha)
    out_rgb = src[:, :, :3].astype(np.float32) * src_alpha + dst[:, :, :3].astype(np.float32) * dst_alpha * (
        1.0 - src_alpha
    )
    safe = np.where(out_alpha > 0, out_rgb / np.maximum(out_alpha, 1e-6), 0.0)
    merged = np.concatenate([safe, out_alpha * 255.0], axis=2)
    return np.clip(np.rint(merged), 0, 255).astype(np.uint8)

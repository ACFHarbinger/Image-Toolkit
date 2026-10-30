"""GIF writer with one palette for the whole clip and position-stable dithering.

Pillow's default save quantizes every frame on its own, so gradients band and
the palette shifts between frames. This writer builds one palette, dithers with
a fixed Bayer mask (the threshold depends on the pixel coordinate, not on the
previous frame), and keeps a transparent index when any frame needs it.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

import numpy as np

from middleware.src.services.media.gif_upscale.base import AlgorithmError

_BAYER_8 = np.array(
    [
        [0, 32, 8, 40, 2, 34, 10, 42],
        [48, 16, 56, 24, 50, 18, 58, 26],
        [12, 44, 4, 36, 14, 46, 6, 38],
        [60, 28, 52, 20, 62, 30, 54, 22],
        [3, 35, 11, 43, 1, 33, 9, 41],
        [51, 19, 59, 27, 49, 17, 57, 25],
        [15, 47, 7, 39, 13, 45, 5, 37],
        [63, 31, 55, 23, 61, 29, 53, 21],
    ],
    dtype=np.float32,
)


def encode_gif(
    path: str,
    frames: list[np.ndarray],
    durations: list[int],
    loop: int,
    *,
    encoder: str = "temporal",
    dither: str = "ordered",
    progress: Callable[[str, int, int], None] | None = None,
) -> str:
    """Write an animated GIF. Returns the encoder that actually ran."""
    if not frames:
        raise ValueError("GIF has no frames.")
    if len(durations) != len(frames):
        raise ValueError("each frame needs a duration")
    chosen = encoder.strip().lower()
    if chosen == "gifski":
        if _encode_gifski(path, frames, durations, loop):
            return "gifski"
        _write_palette_gif(path, frames, durations, loop, dither=dither, method="mediancut", progress=progress)
        return "temporal"
    if chosen == "libimagequant":
        _write_palette_gif(path, frames, durations, loop, dither=dither, method="libimagequant", progress=progress)
        return "libimagequant"
    if chosen not in {"temporal", "auto"}:
        raise AlgorithmError(f"Unknown GIF encoder {encoder!r}.")
    if chosen == "auto" and shutil.which("gifski"):
        try:
            if _encode_gifski(path, frames, durations, loop):
                return "gifski"
        except (OSError, subprocess.CalledProcessError):
            pass
        try:
            _write_palette_gif(path, frames, durations, loop, dither=dither, method="libimagequant", progress=progress)
            return "libimagequant"
        except AlgorithmError:
            pass
    _write_palette_gif(path, frames, durations, loop, dither=dither, method="mediancut", progress=progress)
    return "temporal"


def _as_uint8(frame: np.ndarray) -> np.ndarray:
    array = np.asarray(frame)
    if array.dtype == np.uint8:
        return array
    return np.clip(np.rint(array.astype(np.float32) * 255.0), 0, 255).astype(np.uint8)


def _write_palette_gif(
    path: str,
    frames: list[np.ndarray],
    durations: list[int],
    loop: int,
    *,
    dither: str,
    method: str,
    progress: Callable[[str, int, int], None] | None = None,
) -> None:
    uint8 = [_as_uint8(frame) for frame in frames]
    transparent = any(int(frame[:, :, 3].min()) < 128 for frame in uint8)
    colors = 255 if transparent else 256
    palette = _shared_palette(uint8, colors, method)
    if transparent:
        palette = np.vstack([np.zeros((1, 3), dtype=np.float32), palette])
    images = []
    frame_count = len(uint8)
    for frame_index, frame in enumerate(uint8):
        if progress is not None:
            progress("encode", frame_index, frame_count)
        index = _indexes(frame[:, :, :3], palette[1:] if transparent else palette, dither)
        if transparent:
            index = index + 1
            index[frame[:, :, 3] < 128] = 0
        images.append(_paletted(index, palette))
    extra: dict = {"disposal": 2, "optimize": False}
    if transparent:
        extra["transparency"] = 0
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    images[0].save(
        path,
        format="GIF",
        save_all=True,
        append_images=images[1:],
        duration=list(durations),
        loop=int(loop),
        **extra,
    )
    for image in images:
        image.close()


def _shared_palette(frames: list[np.ndarray], colors: int, method: str) -> np.ndarray:
    from PIL import Image

    quantizer = Image.Quantize.MEDIANCUT
    if method == "libimagequant":
        quantizer = getattr(Image.Quantize, "LIBIMAGEQUANT", None)
        if quantizer is None:
            raise AlgorithmError("libimagequant is not available in this Pillow build.")
    height, width = frames[0].shape[:2]
    strip = Image.new("RGB", (width, height * len(frames)))
    for index, frame in enumerate(frames):
        strip.paste(Image.fromarray(frame[:, :, :3], "RGB"), (0, index * height))
    try:
        quantized = strip.quantize(colors=colors, method=quantizer, dither=Image.Dither.NONE)
    except (ValueError, OSError) as exc:
        if method != "libimagequant":
            raise
        raise AlgorithmError(f"libimagequant is not available in this Pillow build: {exc}") from exc
    finally:
        strip.close()
    raw = quantized.getpalette() or []
    quantized.close()
    usable = colors * 3
    if len(raw) < usable:
        raw = raw + [0] * (usable - len(raw))
    return np.array(raw[:usable], dtype=np.float32).reshape(colors, 3)


def _indexes(rgb: np.ndarray, palette: np.ndarray, dither: str) -> np.ndarray:
    adjusted = rgb.astype(np.float32)
    if dither == "ordered":
        height, width = rgb.shape[:2]
        yy, xx = np.mgrid[0:height, 0:width]
        threshold = (_BAYER_8[yy % 8, xx % 8] + 0.5) / 64.0 - 0.5
        adjusted = adjusted + threshold[:, :, None] * 24.0
    flat = adjusted.reshape(-1, 3)
    chosen = np.empty(flat.shape[0], dtype=np.uint8)
    step = 8192
    for start in range(0, flat.shape[0], step):
        chunk = flat[start : start + step]
        distance = ((chunk[:, None, :] - palette[None, :, :]) ** 2).sum(axis=2)
        chosen[start : start + step] = distance.argmin(axis=1).astype(np.uint8)
    return chosen.reshape(rgb.shape[:2])


def _paletted(index: np.ndarray, palette: np.ndarray):
    from PIL import Image

    image = Image.fromarray(index.astype(np.uint8), mode="P")
    flat = np.zeros(768, dtype=np.uint8)
    count = min(256, palette.shape[0])
    flat[: count * 3] = np.clip(np.rint(palette[:count]), 0, 255).astype(np.uint8).reshape(-1)
    image.putpalette(flat.tobytes())
    return image


def _gifski_fps(durations: list[int]) -> float | None:
    """One fps when every frame shares a delay gifski can represent. Otherwise None."""
    if not durations or any(delay != durations[0] for delay in durations):
        return None
    delay = durations[0]
    if delay <= 0:
        return None
    fps = round(1000.0 / delay, 3)
    if fps <= 0 or abs(1000.0 / fps - delay) > 1.0:
        return None
    return fps


def _encode_gifski(path: str, frames: list[np.ndarray], durations: list[int], loop: int) -> bool:
    """Write with gifski when one frame rate matches the source delays.

    Returns False when the delays differ or cannot be expressed as one fps, so the
    caller can keep those delays with the temporal writer. A missing binary is an error.
    """
    binary = shutil.which("gifski")
    if not binary:
        raise AlgorithmError("gifski is not installed.")
    fps = _gifski_fps(durations)
    if fps is None:
        return False
    from PIL import Image

    with tempfile.TemporaryDirectory(prefix="gifski-") as directory:
        root = Path(directory)
        names: list[str] = []
        for index, frame in enumerate(frames):
            png = root / f"frame-{index:04d}.png"
            Image.fromarray(_as_uint8(frame), "RGBA").save(png)
            names.append(str(png))
        subprocess.run(
            [binary, "-o", path, "--fps", str(fps), "--repeat", str(int(loop)), *names],
            check=True,
            capture_output=True,
        )
    return True

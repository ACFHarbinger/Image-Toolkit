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


# Above this size of scaled RGBA floats, a clip is written one frame at a time.
STREAM_RGBA_BYTES = 256 * 1024 * 1024


class IndexedGifWriter:
    """Append indexed frames to one GIF without keeping the clip in memory."""

    def __init__(self, path: str, width: int, height: int, palette: np.ndarray, loop: int, *, transparent: bool) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._file = Path(path).open("wb")  # noqa: SIM115 — closed in close(), after every frame is written
        self._width = width
        self._height = height
        self._transparent = transparent
        table = np.zeros(768, dtype=np.uint8)
        count = min(256, int(palette.shape[0]))
        flat = np.clip(np.rint(palette[:count]), 0, 255).astype(np.uint8).reshape(-1)
        table[: flat.size] = flat
        self._file.write(b"GIF89a")
        self._file.write(_u16(width) + _u16(height) + bytes((0xF7, 0, 0)))
        self._file.write(table.tobytes())
        self._file.write(b"\x21\xff\x0bNETSCAPE2.0\x03\x01" + _u16(int(loop)) + b"\x00")

    def add_frame(self, index: np.ndarray, duration_ms: int) -> None:
        delay = max(1, int(round(int(duration_ms) / 10))) if duration_ms else 1
        packed = 0x08 | (0x01 if self._transparent else 0)
        trans = 0 if self._transparent else 0
        self._file.write(b"\x21\xf9\x04" + bytes((packed,)) + _u16(delay) + bytes((trans, 0)))
        self._file.write(b"\x2c" + _u16(0) + _u16(0) + _u16(self._width) + _u16(self._height) + b"\x00")
        payload = _lzw(np.ascontiguousarray(index, dtype=np.uint8).reshape(-1).tobytes(), 8)
        self._file.write(b"\x08")
        for start in range(0, len(payload), 255):
            block = payload[start : start + 255]
            self._file.write(bytes((len(block),)) + block)
        self._file.write(b"\x00")

    def close(self) -> None:
        self._file.write(b"\x3b")
        self._file.close()


def index_frame(
    frame: np.ndarray,
    palette: np.ndarray,
    *,
    transparent: bool,
    dither: str = "ordered",
    quality: str = "balanced",
    lut: np.ndarray | None = None,
) -> np.ndarray:
    """Map one RGBA uint8 frame onto the shared palette."""
    colors = palette[1:] if transparent else palette
    index = _indexes(frame[:, :, :3], colors, dither, quality=quality, lut=lut)
    if transparent:
        index = index + 1
        index[frame[:, :, 3] < 128] = 0
    return index


def _u16(value: int) -> bytes:
    return int(value).to_bytes(2, "little", signed=False)


def _lzw(data: bytes, min_code_size: int) -> bytes:
    """GIF LZW, least-significant bit first, clear code included."""
    clear = 1 << min_code_size
    end = clear + 1
    code_size = min_code_size + 1
    next_code = end + 1
    table = {bytes([i]): i for i in range(clear)}
    bits = 0
    nbits = 0
    out = bytearray()

    def emit(code: int, size: int) -> None:
        nonlocal bits, nbits
        bits |= code << nbits
        nbits += size
        while nbits >= 8:
            out.append(bits & 0xFF)
            bits >>= 8
            nbits -= 8

    emit(clear, code_size)
    prefix = b""
    for value in data:
        suffix = bytes((value,))
        joined = prefix + suffix
        if joined in table:
            prefix = joined
            continue
        emit(table[prefix], code_size)
        if next_code < 4096:
            table[joined] = next_code
            next_code += 1
            if code_size < 12 and next_code > (1 << code_size):
                code_size += 1
        else:
            emit(clear, code_size)
            table = {bytes([i]): i for i in range(clear)}
            next_code = end + 1
            code_size = min_code_size + 1
        prefix = suffix
    if prefix:
        emit(table[prefix], code_size)
    if next_code == (1 << code_size) and code_size < 12:
        code_size += 1
    emit(end, code_size)
    if nbits:
        out.append(bits & 0xFF)
    return bytes(out)


def encode_gif(
    path: str,
    frames: list[np.ndarray],
    durations: list[int],
    loop: int,
    *,
    encoder: str = "temporal",
    dither: str = "ordered",
    quality: str = "balanced",
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
        _write_palette_gif(
            path, frames, durations, loop, dither=dither, method="mediancut", quality=quality, progress=progress
        )
        return "temporal"
    if chosen == "libimagequant":
        _write_palette_gif(
            path, frames, durations, loop, dither=dither, method="libimagequant", quality=quality, progress=progress
        )
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
            _write_palette_gif(
                path, frames, durations, loop, dither=dither, method="libimagequant", quality=quality, progress=progress
            )
            return "libimagequant"
        except AlgorithmError:
            pass
    _write_palette_gif(
        path, frames, durations, loop, dither=dither, method="mediancut", quality=quality, progress=progress
    )
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
    quality: str = "balanced",
    progress: Callable[[str, int, int], None] | None = None,
) -> None:
    uint8 = [_as_uint8(frame) for frame in frames]
    transparent = any(int(frame[:, :, 3].min()) < 128 for frame in uint8)
    colors = 255 if transparent else 256
    palette = _shared_palette(uint8, colors, method)
    if transparent:
        palette = np.vstack([np.zeros((1, 3), dtype=np.float32), palette])
    active_colors = palette[1:] if transparent else palette
    lut = build_palette_lut(active_colors) if _normalize_quality(quality) != "exact" else None
    images = []
    frame_count = len(uint8)
    for frame_index, frame in enumerate(uint8):
        if progress is not None:
            progress("encode", frame_index, frame_count)
        index = _indexes(frame[:, :, :3], active_colors, dither, quality=quality, lut=lut)
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


_BAYER_OFFSET_TILE = (((_BAYER_8 + 0.5) / 64.0 - 0.5) * 24.0).astype(np.float32)
_LUT_GRID_128 = np.arange(128, dtype=np.float32) * np.float32(255.0 / 127.0)
_BAYER_CACHE: dict[tuple[int, int], np.ndarray] = {}
_LUT_CACHE: dict[tuple[tuple[int, ...], bytes], np.ndarray] = {}
_CACHE_LIMIT = 4


def _normalize_quality(quality: str | None) -> str:
    mode = "balanced" if quality is None else str(quality).strip().lower()
    if mode not in {"exact", "balanced", "fast"}:
        raise AlgorithmError(f"Unknown palette indexing quality {quality!r}.")
    return mode


def _bayer_grid(height: int, width: int) -> np.ndarray:
    """Return the cached ``(height, width)`` float32 Bayer offset grid."""
    key = (int(height), int(width))
    cached = _BAYER_CACHE.get(key)
    if cached is not None:
        return cached
    tiles_y = (height + 7) // 8
    tiles_x = (width + 7) // 8
    grid = np.ascontiguousarray(np.tile(_BAYER_OFFSET_TILE, (tiles_y, tiles_x))[:height, :width], dtype=np.float32)
    if len(_BAYER_CACHE) >= _CACHE_LIMIT:
        _BAYER_CACHE.pop(next(iter(_BAYER_CACHE)))
    _BAYER_CACHE[key] = grid
    return grid


def build_palette_lut(palette: np.ndarray) -> np.ndarray:
    """Build (or fetch from cache) the flat ``128^3`` uint8 7-bit RGB -> palette index LUT."""
    pal = np.ascontiguousarray(palette, dtype=np.float32)
    if pal.ndim != 2 or pal.shape[1] != 3 or pal.shape[0] < 1:
        raise AlgorithmError(f"Palette must have shape (K, 3), got {pal.shape}.")
    key = (pal.shape, pal.tobytes())
    cached = _LUT_CACHE.get(key)
    if cached is not None:
        return cached
    dr = (_LUT_GRID_128[:, None] - pal[None, :, 0]) ** 2
    dg = (_LUT_GRID_128[:, None] - pal[None, :, 1]) ** 2
    db = (_LUT_GRID_128[:, None] - pal[None, :, 2]) ** 2
    dgb = np.ascontiguousarray((dg[:, None, :] + db[None, :, :]).reshape(16384, pal.shape[0]), dtype=np.float32)
    lut = np.empty((128, 16384), dtype=np.uint8)
    buf = np.empty_like(dgb)
    for r_index in range(128):
        np.add(dgb, dr[r_index], out=buf)
        # argmin breaks ties deterministically by picking the lowest palette index.
        lut[r_index] = buf.argmin(axis=1)
    flat_lut = lut.reshape(-1)
    if len(_LUT_CACHE) >= _CACHE_LIMIT:
        _LUT_CACHE.pop(next(iter(_LUT_CACHE)))
    _LUT_CACHE[key] = flat_lut
    return flat_lut


def _indexes(
    rgb: np.ndarray,
    palette: np.ndarray,
    dither: str,
    *,
    quality: str = "balanced",
    lut: np.ndarray | None = None,
) -> np.ndarray:
    mode = _normalize_quality(quality)
    if mode == "exact":
        return _indexes_exact(rgb, palette, dither)
    active_lut = build_palette_lut(palette) if lut is None else lut
    return _indexes_lut(rgb, active_lut, dither)


def _indexes_exact(rgb: np.ndarray, palette: np.ndarray, dither: str) -> np.ndarray:
    """Exact nearest-color lookup via BLAS identity ``0.5*||p||^2 - x @ p.T``."""
    pal = np.ascontiguousarray(palette, dtype=np.float32)
    adjusted = rgb.astype(np.float32)
    if dither == "ordered":
        height, width = rgb.shape[:2]
        adjusted = adjusted + _bayer_grid(height, width)[:, :, None]
    flat = np.ascontiguousarray(adjusted.reshape(-1, 3), dtype=np.float32)
    half = np.float32(0.5) * (pal**2).sum(axis=1)
    chosen = np.empty(flat.shape[0], dtype=np.uint8)
    step = 65536
    for start in range(0, flat.shape[0], step):
        chunk = flat[start : start + step]
        scores = half[None, :] - chunk @ pal.T
        # argmin breaks ties deterministically by picking the lowest palette index.
        chosen[start : start + step] = scores.argmin(axis=1).astype(np.uint8)
    return chosen.reshape(rgb.shape[:2])


def _indexes_lut(rgb: np.ndarray, lut: np.ndarray, dither: str) -> np.ndarray:
    """7-bit (128^3) lookup table with L3-resident per-channel shift accumulation."""
    height, width = rgb.shape[:2]
    scale = np.float32(127.0 / 255.0)
    if dither != "ordered":
        q_table = np.rint(np.arange(256, dtype=np.float32) * scale).astype(np.int32)
        key = (q_table[rgb[:, :, 0]] << 14) | (q_table[rgb[:, :, 1]] << 7) | q_table[rgb[:, :, 2]]
        return lut[key]
    bayer = _bayer_grid(height, width)
    buf = np.empty((height, width), dtype=np.float32)
    q = np.empty((height, width), dtype=np.int32)
    key = np.zeros((height, width), dtype=np.int32)
    for channel, shift in ((0, 14), (1, 7), (2, 0)):
        np.add(rgb[:, :, channel], bayer, out=buf, casting="unsafe")
        np.clip(buf, 0.0, 255.0, out=buf)
        np.multiply(buf, scale, out=buf)
        np.rint(buf, out=buf)
        np.copyto(q, buf, casting="unsafe")
        if shift:
            q <<= shift
        key |= q
    return lut[key]


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

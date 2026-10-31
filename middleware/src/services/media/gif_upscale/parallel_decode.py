"""Parallel GIF decode. Each frame's LZW data is independent, only compositing is ordered.

``iter_gif_frames_parallel`` yields the same ``(rgba_uint8, duration_ms, loop)`` tuples as
``io.iter_gif_frames``. The block structure is scanned once without any LZW work, the frames are
decoded by Pillow's C decoder in worker processes (one mini GIF per frame), and the main process
composites them in order. In-flight work is bounded so memory stays flat for any clip length.

Compositing follows Pillow's rules. A clip whose disposal or background handling is not proven
identical to Pillow's is decoded sequentially instead, so the output never differs from the
sequential decoder.
"""

from __future__ import annotations

import io
import mmap
import os
import struct
from collections import deque
from collections.abc import Iterator
from concurrent.futures import Future, ProcessPoolExecutor
from dataclasses import dataclass
from multiprocessing import get_context

import numpy as np

from middleware.src.services.media.gif_upscale.io import iter_gif_frames

DEFAULT_DURATION_MS = 100


@dataclass(frozen=True)
class GifInfo:
    width: int
    height: int
    gct: bytes
    gct_bits: int
    background: int
    loop: int


@dataclass(frozen=True)
class FrameRecord:
    left: int
    top: int
    width: int
    height: int
    flags: int
    lct: bytes
    start: int  # LZW minimum code size byte
    end: int  # one past the block terminator
    disposal: int
    transparent: int | None
    delay_cs: int | None
    gce: bytes


def _u16(data, pos: int) -> int:
    return data[pos] | (data[pos + 1] << 8)


def _skip_sub_blocks(data, pos: int) -> int:
    while True:
        size = data[pos]
        pos += 1 + size
        if size == 0:
            return pos


def scan_gif(path: str) -> tuple[GifInfo, list[FrameRecord]]:
    """Walk the block structure. No LZW data is decoded."""
    with open(path, "rb") as handle, mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as data:
        if bytes(data[0:3]) != b"GIF":
            raise ValueError("not a GIF file")
        width, height = _u16(data, 6), _u16(data, 8)
        packed, background = data[10], data[11]
        pos = 13
        gct = b""
        gct_bits = packed & 7
        if packed & 0x80:
            size = 3 * (2 ** (gct_bits + 1))
            gct = bytes(data[pos : pos + size])
            pos += size
        loop = 0
        frames: list[FrameRecord] = []
        gce: tuple[int, int, int, bytes] | None = None
        while pos < len(data):
            block = data[pos]
            if block == 0x3B:
                break
            if block == 0x21:
                label = data[pos + 1]
                if label == 0xF9 and data[pos + 2] == 4:
                    gce = (data[pos + 3], _u16(data, pos + 4), data[pos + 6], bytes(data[pos : pos + 8]))
                    pos += 8
                    continue
                if label == 0xFF and bytes(data[pos + 3 : pos + 14]) == b"NETSCAPE2.0" and data[pos + 14] == 3:
                    loop = _u16(data, pos + 16)
                pos = _skip_sub_blocks(data, pos + 2)
                continue
            if block != 0x2C:
                raise ValueError(f"unexpected GIF block {block:#x} at {pos}")
            left, top = _u16(data, pos + 1), _u16(data, pos + 3)
            w, h = _u16(data, pos + 5), _u16(data, pos + 7)
            flags = data[pos + 9]
            pos += 10
            lct = b""
            if flags & 0x80:
                size = 3 * (2 ** ((flags & 7) + 1))
                lct = bytes(data[pos : pos + size])
                pos += size
            start = pos
            pos = _skip_sub_blocks(data, pos + 1)
            graphic = gce[0] if gce else 0
            frames.append(
                FrameRecord(
                    left=left,
                    top=top,
                    width=w,
                    height=h,
                    flags=flags,
                    lct=lct,
                    start=start,
                    end=pos,
                    disposal=(graphic >> 2) & 7,
                    transparent=(gce[2] if gce and graphic & 1 else None),
                    delay_cs=(gce[1] if gce else None),
                    gce=(gce[3] if gce else b""),
                )
            )
            gce = None
    return GifInfo(width, height, gct, gct_bits, background, loop), frames


def _decode_job(job: tuple) -> np.ndarray:
    """Worker: decode one frame's rectangle to RGBA with Pillow's C decoder."""
    from PIL import Image

    path, gct, gct_bits, rec = job
    with open(path, "rb") as handle:
        handle.seek(rec.start)
        payload = handle.read(rec.end - rec.start)
    screen = struct.pack("<HH", rec.width, rec.height) + bytes([(0x80 | gct_bits) if gct else 0, 0, 0])
    descriptor = b"\x2c" + struct.pack("<HHHH", 0, 0, rec.width, rec.height) + bytes([rec.flags])
    mini = b"GIF89a" + screen + gct + rec.gce + descriptor + rec.lct + payload + b"\x3b"
    with Image.open(io.BytesIO(mini)) as image:
        return np.asarray(image.convert("RGBA")).copy()


def _proven_equivalent(info: GifInfo, frames: list[FrameRecord]) -> bool:
    """Compositing rules this module matches exactly. Anything else uses the sequential decoder."""
    if not frames or info.width < 1 or info.height < 1:
        return False
    first = frames[0]
    if (first.left, first.top, first.width, first.height) != (0, 0, info.width, info.height):
        return False  # a partial first frame leaves canvas pixels Pillow fills in its own way
    previous_disposal = 0
    for rec in frames:
        # Pillow retains the previous nonzero disposal for unspecified frames.
        if rec.disposal == 0 and previous_disposal in (2, 3):
            return False
        if rec.disposal:
            previous_disposal = rec.disposal
        if rec.left + rec.width > info.width or rec.top + rec.height > info.height:
            return False
        if rec.disposal == 2 and rec.transparent is None:
            return False  # background-colour disposal: Pillow-specific, not matched here
    return True


class _Compositor:
    def __init__(self, info: GifInfo) -> None:
        self.canvas = np.zeros((info.height, info.width, 4), np.uint8)
        self.info = info

    def draw(self, rec: FrameRecord, rgba: np.ndarray, *, first: bool) -> tuple[np.ndarray, np.ndarray | None]:
        """Draw one frame. Returns the displayed canvas and the canvas to restore for disposal 3.

        Pillow treats "restore previous" on the first frame as "leave in place", so it saves nothing there.
        """
        saved = self.canvas.copy() if rec.disposal == 3 and not first else None
        region = self.canvas[rec.top : rec.top + rec.height, rec.left : rec.left + rec.width]
        if first:
            region[:] = rgba  # keeps the palette colour under alpha 0, as Pillow does
        elif rec.transparent is not None:
            # One uint32 per pixel: a masked word copy is about 7x faster than a boolean-mask copy.
            dst = region.view(np.uint32)[..., 0]
            src = np.ascontiguousarray(rgba).view(np.uint32)[..., 0]
            np.copyto(dst, src, where=(src >> 24) > 0)
        else:
            region[:] = rgba
        return self.canvas.copy(), saved

    def dispose(self, rec: FrameRecord, saved: np.ndarray | None) -> None:
        if rec.disposal == 2:  # only reached with a transparent index (see _proven_equivalent)
            # Pillow fills with the transparent index's palette colour at alpha 0, not with black.
            table = rec.lct or self.info.gct
            at = 3 * int(rec.transparent or 0)
            rgb = table[at : at + 3] if len(table) >= at + 3 else b"\x00\x00\x00"
            self.canvas[rec.top : rec.top + rec.height, rec.left : rec.left + rec.width] = (*rgb, 0)
        elif rec.disposal == 3 and saved is not None:
            self.canvas = saved


def _duration_ms(rec: FrameRecord) -> int:
    if rec.delay_cs is None:
        return DEFAULT_DURATION_MS
    return int(rec.delay_cs) * 10


def iter_gif_frames_parallel(
    path: str, workers: int = 4, *, window: int | None = None
) -> Iterator[tuple[np.ndarray, int, int]]:
    """Yield ``(rgba_uint8, duration_ms, loop)`` per frame, decoded by ``workers`` processes.

    ``workers <= 1`` and clips this module cannot match exactly use the sequential decoder. The
    pool uses the ``spawn`` start method so it is safe after CUDA or Qt are initialised. Closing
    the generator (or breaking out of the loop) stops the pool and cancels queued frames.
    """
    workers = max(1, int(workers))
    info, frames = scan_gif(path)
    if workers == 1 or len(frames) < 2 or not _proven_equivalent(info, frames):
        yield from iter_gif_frames(path)
        return
    in_flight = max(workers * 2, int(window or workers * 4))
    compositor = _Compositor(info)
    pool = ProcessPoolExecutor(max_workers=min(workers, len(frames)), mp_context=get_context("spawn"))
    pending: deque[Future] = deque()
    next_job = 0
    try:
        for index, rec in enumerate(frames):
            while next_job < len(frames) and len(pending) < in_flight:
                pending.append(pool.submit(_decode_job, (path, info.gct, info.gct_bits, frames[next_job])))
                next_job += 1
            rgba = pending.popleft().result()
            shown, saved = compositor.draw(rec, rgba, first=index == 0)
            yield shown, _duration_ms(rec), info.loop
            compositor.dispose(rec, saved)
    finally:
        for future in pending:
            future.cancel()
        pool.shutdown(wait=True, cancel_futures=True)


def default_workers() -> int:
    """Leave a few cores for the rest of the pipeline."""
    return max(1, (os.cpu_count() or 2) - 4)


__all__ = ["FrameRecord", "GifInfo", "default_workers", "iter_gif_frames_parallel", "scan_gif"]

"""GIF and scrolling-video export for ``ImageMerger``."""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
from typing import Iterator, List, Optional, Tuple

import numpy as np
from loguru import logger
from PIL import Image


class _GifVideoMixin:
    """GIF creation and scrolling-video export methods for ``ImageMerger``."""

    def _create_gif(
        image_paths: List[str], output_path: str, duration: int = 500
    ) -> Image.Image:
        """
        Creates an animated GIF from the provided images.
        Resizes all images to match the size of the first image to ensure consistency.
        """
        if not image_paths:
            raise ValueError("No images provided for GIF creation.")

        if output_path.lower().endswith(".png"):
            output_path = output_path[:-4] + ".gif"

        # Stream frames: open/process one source at a time instead of holding
        # every frame decoded in memory simultaneously. Pillow's GIF writer
        # iterates ``append_images`` lazily (each element through
        # ``ImageSequence.Iterator``) and copies each frame as it goes, so a
        # generator that yields then closes its source keeps peak allocation to
        # ~one frame (plus Pillow's in-flight copy) regardless of frame count.
        first = Image.open(image_paths[0])
        base_size = first.size
        first_frame = (
            first
            if first.size == base_size
            else first.resize(base_size, Image.Resampling.LANCZOS)
        )
        if first_frame is not first:
            first.close()

        def _frames() -> Iterator[Image.Image]:
            for path in image_paths[1:]:
                img = Image.open(path)
                frame = (
                    img.resize(base_size, Image.Resampling.LANCZOS)
                    if img.size != base_size
                    else img
                )
                try:
                    yield frame
                finally:
                    # Pillow copies each frame before advancing to the next one,
                    # so closing the source here never invalidates a frame the
                    # writer is still using.
                    img.close()

        first_frame.save(
            output_path,
            format="GIF",
            append_images=_frames(),
            save_all=True,
            duration=duration,
            loop=0,
            optimize=True,
        )

        return first_frame

    @staticmethod
    def export_scrolling_video(  # noqa: C901
        image_path: str,
        output_path: str,
        scroll_speed_px_per_frame: int = 10,
        fps: int = 30,
        resolution: Optional[Tuple[int, int]] = None,
        scroll_axis: Optional[str] = None,
        codec: str = "libx264",
    ) -> str:
        """
        Exports a stitched panorama as a scrolling video (roadmap §4.2 Option
        B — FFmpeg pipe, full-resolution/quality path): a sliding "viewport"
        window is cropped across the panorama and each position's raw RGB
        bytes are piped to an `ffmpeg` subprocess via stdin, which encodes
        them straight to the target codec/container. No intermediate frame
        files are written and no Python video library is required — the
        same convention `video_converter.py` uses elsewhere in this codebase
        (bare "ffmpeg" on PATH via subprocess).

        Parameters
        ----------
        image_path    : source panorama (any PIL-readable format).
        output_path   : destination video file (extension picks the
                        container, e.g. .mp4/.webm — ffmpeg infers it).
        scroll_speed_px_per_frame : viewport translation per output frame.
        fps           : output frame rate.
        resolution    : (W, H) of the output video/viewport. If None, it is
                        derived from the panorama: the full extent along the
                        non-scrolling axis, and a 16:9-ish extent (clamped to
                        the image size) along the scrolling axis.
        scroll_axis   : 'vertical' | 'horizontal' | None (auto-detect from
                        aspect ratio — taller-than-wide scrolls vertically,
                        wider-than-tall scrolls horizontally).
        codec         : ffmpeg video encoder name (libx264, libx265,
                        libvpx-vp9, ...). Output pixel format is always
                        yuv420p for broad player compatibility, per the
                        roadmap's own example command.

        Returns
        -------
        The output_path (str) — unlike the other merge helpers this isn't a
        loaded Image.Image, since the product is a video file.

        Nothing-to-scroll behaviour: if the panorama is smaller than one
        viewport's worth of scroll along the scroll axis, this does NOT
        raise — it exports a short static clip (`fps` frames, i.e. ~1 second)
        of the single frame instead, so the export action always produces a
        usable file. Documented choice per roadmap §4.2 task notes.
        """
        if shutil.which("ffmpeg") is None:
            raise RuntimeError(
                "ffmpeg not found on PATH; required for scrolling video export "
                "(see backend/src/core/video_converter.py for this project's "
                "other ffmpeg usage)"
            )
        if scroll_speed_px_per_frame < 1:
            raise ValueError("scroll_speed_px_per_frame must be >= 1")
        if fps < 1:
            raise ValueError("fps must be >= 1")

        with Image.open(image_path) as im:
            source = im.convert("RGB")
        img_w, img_h = source.size

        if scroll_axis is None:
            scroll_axis = "vertical" if img_h >= img_w else "horizontal"
        if scroll_axis not in ("vertical", "horizontal"):
            raise ValueError("scroll_axis must be 'vertical', 'horizontal', or None")

        if resolution is not None:
            out_w, out_h = resolution
        elif scroll_axis == "vertical":
            out_w = img_w
            out_h = max(1, round(out_w * 9 / 16))
        else:
            out_h = img_h
            out_w = max(1, round(out_h * 16 / 9))

        # Never crop a viewport bigger than the source itself.
        out_w = min(out_w, img_w)
        out_h = min(out_h, img_h)
        # yuv420p requires even dimensions.
        out_w = max(2, out_w - (out_w % 2))
        out_h = max(2, out_h - (out_h % 2))

        scroll_range = (img_h - out_h) if scroll_axis == "vertical" else (img_w - out_w)

        frame_source = np.asarray(source)  # HxWx3 RGB, contiguous

        def crop_at(offset: int) -> np.ndarray:
            if scroll_axis == "vertical":
                return frame_source[offset : offset + out_h, 0:out_w]
            return frame_source[0:out_h, offset : offset + out_w]

        if scroll_range <= 0:
            # Nothing to scroll (see docstring) — static 1-second clip.
            offsets = [0] * fps
        else:
            offsets = list(range(0, scroll_range, scroll_speed_px_per_frame))
            if offsets[-1] != scroll_range:
                offsets.append(scroll_range)  # always reach the far edge

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        cmd = [
            "ffmpeg",
            "-y",
            "-f", "rawvideo",
            "-pix_fmt", "rgb24",
            "-s", f"{out_w}x{out_h}",
            "-r", str(fps),
            "-i", "pipe:0",
            "-an",
            "-c:v", codec,
            "-pix_fmt", "yuv420p",
            output_path,
        ]

        logger.info(
            f"Exporting scrolling video ({scroll_axis}, {len(offsets)} frames "
            f"@ {fps}fps, viewport {out_w}x{out_h}) -> '{output_path}'"
        )

        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        try:
            assert proc.stdin is not None
            for offset in offsets:
                frame = np.ascontiguousarray(crop_at(offset))
                proc.stdin.write(frame.tobytes())
            proc.stdin.close()
            proc.wait(timeout=600)
        except BrokenPipeError:
            proc.wait(timeout=600)
        finally:
            if proc.stdin is not None and not proc.stdin.closed:
                with contextlib.suppress(Exception):
                    proc.stdin.close()

        if proc.returncode != 0 or not os.path.exists(output_path):
            stderr = proc.stderr.read().decode("utf-8", "ignore") if proc.stderr else ""
            raise RuntimeError(
                f"ffmpeg scrolling video export failed (code {proc.returncode}): "
                f"{stderr[-800:]}"
            )

        return output_path


__all__ = ["_GifVideoMixin"]

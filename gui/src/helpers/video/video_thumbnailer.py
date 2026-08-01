import hashlib
import os
import shutil
import subprocess
import threading

from backend.src.constants import (
    IS_LINUX,
    THUMBNAIL_CACHE_DIR,
)
from backend.src.core import telemetry
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage


def _decode_span(tool: str, video_path: str):
    """telemetry.span() around a QImage decode -- this is the suspected
    native-crash boundary from Addendum 11 in
    .agent/cache/gallery_crash_deleteorphaned_2026-07-27.md: the FIRST
    QImage().loadFromData() call in the process's lifetime lazily loads
    Qt's JPEG plugin off whichever thread calls it (here, one of
    VideoScannerWorker's ThreadPoolExecutor threads, not the main thread),
    with the JPype JVM already loaded in-process. If a crash happens inside
    this span, the telemetry file's last line being a `.start` with no
    matching `.end` is itself the finding -- see debug/telemetry_analyzer.py."""
    return telemetry.span(
        "native", "qimage_decode",
        tool=tool, video_path=video_path, tid=threading.get_ident(),
    )


def get_video_thumbnail_cache_path(video_path: str) -> str:
    """Computes the deterministic path for a video thumbnail on disk."""
    THUMBNAIL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path_hash = hashlib.md5(video_path.encode("utf-8")).hexdigest()
    return str(THUMBNAIL_CACHE_DIR / f"{path_hash}.jpg")


class VideoThumbnailer:
    """
    A standalone utility to generate video thumbnails with speed comparable to
    system file explorers (Dolphin/Explorer).
    """

    def __init__(self):
        # Detect available tools once
        self.has_ffmpegthumbnailer = shutil.which("ffmpegthumbnailer") is not None
        self.has_ffmpeg = shutil.which("ffmpeg") is not None
        self.is_linux = IS_LINUX

    def _get_nice_prefix(self) -> list[str]:
        """Returns ['nice', '-n', '19'] on Linux to lower subprocess priority."""
        if self.is_linux:
            return ["nice", "-n", "19"]
        return []

    def _crop_to_square(self, img: QImage, size: int) -> QImage:
        """Center-crops the image to a square of the given size."""
        # 1. Scale to cover the square
        scaled = img.scaled(
            size,
            size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )

        # 2. Crop center
        diff_x = (scaled.width() - size) // 2
        diff_y = (scaled.height() - size) // 2
        return scaled.copy(diff_x, diff_y, size, size)

    def generate(
        self, video_path: str, size: int, crop_square: bool = False
    ) -> QImage | None:
        if not os.path.exists(video_path):
            return None

        if size is None or size <= 0:
            size = 180  # Default fallback

        # Strategy 1: ffmpegthumbnailer (Fastest, specialized C++ tool)
        # Used by Kubuntu Dolphin and many Linux FMs.
        if self.has_ffmpegthumbnailer:
            try:
                cmd = self._get_nice_prefix() + [
                    "ffmpegthumbnailer",
                    "-i",
                    video_path,
                    "-o",
                    "-",  # Write to stdout
                    "-s",
                    str(size),  # Size (max dimension)
                    "-t",
                    "15",  # Seek to 15% to avoid black intro frames
                    "-c",
                    "jpeg",  # JPEG is fast to encode/decode
                    "-q",
                    "5",  # Quality (low is fine for thumbs)
                ]
                # Timeout prevents hanging on corrupt files
                result = subprocess.run(
                    cmd, capture_output=True, check=True, timeout=15.0
                )

                img = QImage()
                # Load directly from memory buffer
                with _decode_span("ffmpegthumbnailer", video_path):
                    decode_ok = img.loadFromData(result.stdout)
                if decode_ok:
                    if crop_square:
                        return self._crop_to_square(img, size)
                    return img
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                pass  # Fallback

        # Strategy 2: FFmpeg (Optimized input seeking)
        if self.has_ffmpeg:

            def run_ffmpeg(seek_time):
                # -ss BEFORE -i is critical: it triggers "input seeking" (jumping to keyframes)
                # rather than decoding up to the timestamp.
                cmd = self._get_nice_prefix() + [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-ss",
                    seek_time,
                    "-i",
                    video_path,
                    "-vf",
                    f"scale={size}:-1",  # Downscale inside pipeline (saves RAM)
                    "-vframes",
                    "1",
                    "-f",
                    "image2",
                    "-c:v",
                    "mjpeg",
                    "pipe:1",
                ]
                return subprocess.run(
                    cmd, capture_output=True, check=True, timeout=15.0
                )

            try:
                # Try seeking to 5 seconds first (avoids black intros)
                result = run_ffmpeg("00:00:05")
                img = QImage()
                with _decode_span("ffmpeg@5s", video_path):
                    decode_ok = img.loadFromData(result.stdout)
                if decode_ok:
                    if crop_square:
                        return self._crop_to_square(img, size)
                    return img
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                # Fallback: Try seeking to start (0s) for short videos
                try:
                    result = run_ffmpeg("00:00:00")
                    img = QImage()
                    with _decode_span("ffmpeg@0s", video_path):
                        decode_ok = img.loadFromData(result.stdout)
                    if decode_ok:
                        if crop_square:
                            return self._crop_to_square(img, size)
                        return img
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                    pass

        return None

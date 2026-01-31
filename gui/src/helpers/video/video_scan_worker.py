import os
import shutil
import subprocess
import concurrent.futures
from pathlib import Path

from PySide6.QtGui import QImage
from PySide6.QtCore import Signal, QRunnable, QObject
from backend.src.utils.definitions import SUPPORTED_VIDEO_FORMATS

try:
    import platform
    IS_LINUX = platform.system() == "Linux"
except ImportError:
    IS_LINUX = False

try:
    import base
    HAS_NATIVE_IMAGING = True
except ImportError:
    HAS_NATIVE_IMAGING = False


class VideoScanSignals(QObject):
    thumbnail_ready = Signal(str, QImage)  # path, QImage
    finished = Signal()


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
        from PySide6.QtCore import Qt

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

    def generate(self, video_path: str, size: int, crop_square: bool = False) -> QImage | None:
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
                if img.loadFromData(result.stdout):
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
                if img.loadFromData(result.stdout):
                    if crop_square:
                        return self._crop_to_square(img, size)
                    return img
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                # Fallback: Try seeking to start (0s) for short videos
                try:
                    result = run_ffmpeg("00:00:00")
                    img = QImage()
                    if img.loadFromData(result.stdout):
                        if crop_square:
                            return self._crop_to_square(img, size)
                        return img
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                    pass

        return None


def process_video_task(args):
    """
    Helper function to run in a thread.
    """
    path, target_height, thumbnailer, crop_square = args
    try:
        image = thumbnailer.generate(path, target_height, crop_square=crop_square)
        return path, image
    except Exception:
        return path, None


class VideoScannerWorker(QRunnable):
    """
    Scans a directory for videos and generates thumbnails.
    Replaces heavy OpenCV decoding with lightweight subprocess calls.
    """

    def __init__(self, directory, target_height=180, crop_square=False):
        super().__init__()
        self.directory = directory
        self.target_height = target_height
        self.crop_square = crop_square
        self.signals = VideoScanSignals()
        self.is_cancelled = False
        self.executor = None
        self.thumbnailer = VideoThumbnailer()

    def stop(self):
        """Signals the worker to stop scanning."""
        self.is_cancelled = True
        if self.executor:
            self.executor.shutdown(wait=False, cancel_futures=True)

    def run(self):
        if self.is_cancelled:
            return

        if not os.path.isdir(self.directory):
            self.signals.finished.emit()
            return

        try:
            # 1. Gather all video paths
            video_paths = []

            # Use Rust backend for fast scanning if available, else standard os.scandir
            if HAS_NATIVE_IMAGING:
                video_paths = base.scan_files(
                    [self.directory], list(SUPPORTED_VIDEO_FORMATS), False
                )
            else:
                try:
                    entries = sorted(
                        os.scandir(self.directory), key=lambda e: e.name.lower()
                    )
                    video_paths = [
                        e.path
                        for e in entries
                        if e.is_file()
                        and Path(e.path).suffix.lower() in SUPPORTED_VIDEO_FORMATS
                    ]
                except OSError:
                    pass

            if not video_paths:
                self.signals.finished.emit()
                return

            if self.is_cancelled:
                return

            # 2. Process in Parallel
            # We use ThreadPoolExecutor. Since the actual work happens in external
            # subprocesses (ffmpeg), Python threads are just waiting for IO.
            # We limit max_workers to avoid disk thrashing (too many simultaneous seeks).
            max_workers = min(os.cpu_count(), 8)
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=max_workers
            ) as executor:
                self.executor = executor

                # Submit all tasks
                futures = {
                    executor.submit(
                        process_video_task,
                        (path, self.target_height, self.thumbnailer, self.crop_square),
                    ): path
                    for path in video_paths
                }

                for future in concurrent.futures.as_completed(futures):
                    if self.is_cancelled:
                        break

                    try:
                        path, image = future.result()
                        # Emit result regardless of success/failure
                        # Receiver must handle null/invalid images
                        safe_image = image if image else QImage()
                        self.signals.thumbnail_ready.emit(path, safe_image)
                    except Exception:
                        pass

        except Exception:
            pass
        finally:
            self.signals.finished.emit()

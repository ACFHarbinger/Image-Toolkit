import concurrent.futures
import os
from pathlib import Path

from backend.src.constants import (
    HAS_NATIVE_IMAGING,
    SUPPORTED_VIDEO_FORMATS,
)
from PySide6.QtCore import QObject, QRunnable, Signal
from PySide6.QtGui import QImage

if HAS_NATIVE_IMAGING:
    import base


from .video_thumbnailer import VideoThumbnailer, get_video_thumbnail_cache_path


class _VideoScanSignals(QObject):
    thumbnail_ready = Signal(str, QImage)  # path, QImage
    finished = Signal()



def process_video_task(args):
    """
    Helper function to run in a thread.
    Checks for a cached thumbnail on disk before generating a new one.
    """
    path, target_height, thumbnailer, crop_square = args
    try:
        # 1. Check Disk Cache
        cache_path = get_video_thumbnail_cache_path(path)
        if os.path.exists(cache_path):
            img = QImage(cache_path)
            if not img.isNull():
                return path, img

        # 2. Generate New Thumbnail
        image = thumbnailer.generate(path, target_height, crop_square=crop_square)

        # 3. Save to Disk Cache if successful
        if image and not image.isNull():
            image.save(cache_path, "JPG")

        return path, image
    except Exception:
        return path, None


class VideoScannerWorker(QRunnable):
    """
    Scans a directory for videos and generates thumbnails.
    Replaces heavy OpenCV decoding with lightweight subprocess calls.
    """

    def __init__(self, directory, target_height=180, crop_square=False, recursive=None):
        super().__init__()
        self.directory = directory
        self.target_height = target_height
        self.crop_square = crop_square
        self.signals = _VideoScanSignals()
        self.is_cancelled = False
        self.executor = None
        self.thumbnailer = VideoThumbnailer()
        if recursive is None:
            from gui.src.windows.settings.app_settings import AppSettings
            self.recursive = AppSettings.recursive_scan()
        else:
            self.recursive = recursive

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

            # Use C++ backend for fast scanning if available, else standard os.scandir / os.walk
            if HAS_NATIVE_IMAGING:
                video_paths = base.scan_files_multi( # pyrefly: ignore [missing-attribute]
                    [self.directory], list(SUPPORTED_VIDEO_FORMATS), self.recursive
                )
            else:
                try:
                    if self.recursive:
                        video_paths = []
                        for root, dirs, files in os.walk(self.directory):
                            if self.is_cancelled:
                                break
                            # Skip hidden directories in-place (starts with dot)
                            dirs[:] = [d for d in dirs if not d.startswith(".")]
                            for file in files:
                                if file.startswith("."):
                                    continue
                                path_obj = Path(root) / file
                                if path_obj.suffix.lower() in SUPPORTED_VIDEO_FORMATS:
                                    video_paths.append(str(path_obj))
                        video_paths.sort(key=lambda p: os.path.basename(p).lower())
                    else:
                        entries = sorted(
                            os.scandir(self.directory), key=lambda e: e.name.lower()
                        )
                        video_paths = [
                            e.path
                            for e in entries
                            if e.is_file()
                            and not e.name.startswith(".")
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
            max_workers = min(os.cpu_count(), 8) # pyrefly: ignore [bad-specialization]
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

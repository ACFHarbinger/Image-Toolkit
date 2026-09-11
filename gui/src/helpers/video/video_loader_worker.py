import contextlib
import os

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QImage
from shiboken6 import Shiboken

from gui.src.helpers.base import BaseQRunnableWorker

from .video_thumbnailer import VideoThumbnailer, get_video_thumbnail_cache_path


class _VideoLoaderSignalsStream(QObject):
    """
    Defines the signals for the VideoLoaderWorker.
    Must be a separate QObject because QRunnable does not inherit QObject.
    """

    # Emits (file_path, loaded_QImage)
    result = Signal(str, QImage)
    # Emits list of (file_path, loaded_QImage), and list of requested_paths
    batch_result = Signal(list, list)


class VideoLoaderWorker(BaseQRunnableWorker):
    """
    Worker task to load and scale a SINGLE video thumbnail.
    Designed to be run in a QThreadPool -- same architecture as
    ImageLoaderWorker, never implicated in the deleteOrphaned crash class
    (see .agent/cache/gallery_crash_deleteorphaned_2026-07-27.md,
    Addendum 24). The actual decode work (subprocess + QImage) happens on
    a Qt-managed QThreadPool worker thread, one decode per runnable --
    unlike the old VideoScannerWorker's bespoke internal
    ThreadPoolExecutor, which fanned out concurrent decodes across
    non-Qt-managed threads.
    """

    # Set externally by callers that track cancellation generations (e.g.
    # AbstractClassSingleGallery._trigger_video_load) -- not assigned in
    # __init__ since not every caller needs it.
    load_generation: int

    def __init__(self, path: str, target_size: int, crop_square: bool = False):
        super().__init__()
        self.path = path
        self.target_size = target_size
        self.crop_square = crop_square
        self.stream = _VideoLoaderSignalsStream()
        self.thumbnailer = VideoThumbnailer()

        # Auto-delete ensures the runnable is cleaned up after 'run' finishes

    def stop(self):
        """Signals the worker to stop."""
        self.cancel()

    def _execute(self) -> object:
        if self._cancelled:
            return
        try:
            # 1. Check Disk Cache
            cache_path = get_video_thumbnail_cache_path(self.path)
            if os.path.exists(cache_path):
                img = QImage(cache_path)
                if not img.isNull():
                    self._safe_emit(self.path, img)
                    return

            # 2. Generate New Thumbnail
            image = self.thumbnailer.generate(self.path, self.target_size, crop_square=self.crop_square)
            if image and not image.isNull():
                # 3. Save to Disk Cache
                image.save(cache_path, "JPG")  # pyrefly: ignore [no-matching-overload]
                self._safe_emit(self.path, image)
            else:
                self._safe_emit(self.path, QImage())
        except Exception:
            self._safe_emit(self.path, QImage())
        finally:
            if Shiboken.isValid(self.stream):
                self.stream.deleteLater()

    def _safe_emit(self, path, image):
        with contextlib.suppress(RuntimeError):
            self.stream.result.emit(path, image)

import contextlib
import os

from PySide6.QtCore import QObject, QRunnable, Signal, Slot
from PySide6.QtGui import QImage
from shiboken6 import Shiboken

from gui.src.helpers.gc_safe import gc_disabled_run

from .video_thumbnailer import VideoThumbnailer, get_video_thumbnail_cache_path


class _BatchVideoLoaderSignals(QObject):
    # Emits (file_path, loaded_QImage)
    result = Signal(str, QImage)
    # Emits list of (file_path, loaded_QImage), and list of requested_paths
    batch_result = Signal(list, list)


class BatchVideoLoaderWorker(QRunnable):
    """
    Worker task to load and scale a BATCH of video thumbnails, one at a
    time, sequentially, on a single QThreadPool worker thread -- same
    chunked-dispatch model as BatchImageLoaderWorker.
    """

    def __init__(self, paths: list[str], target_size: int, crop_square: bool = False):
        super().__init__()
        self.paths = paths
        self.target_size = target_size
        self.crop_square = crop_square
        self.signals = _BatchVideoLoaderSignals()
        self.thumbnailer = VideoThumbnailer()
        self._is_cancelled = False
        self.setAutoDelete(True)

    def stop(self):
        """Signals the worker to stop."""
        self._is_cancelled = True

    @gc_disabled_run
    @Slot()
    def run(self):
        if self._is_cancelled:
            return
        results = []
        try:
            for path in self.paths:
                if self._is_cancelled:
                    break
                try:
                    # 1. Check Disk Cache
                    cache_path = get_video_thumbnail_cache_path(path)
                    if os.path.exists(cache_path):
                        img = QImage(cache_path)
                        if not img.isNull():
                            self._safe_emit(path, img)
                            results.append((path, img))
                            continue

                    # 2. Generate New Thumbnail
                    image = self.thumbnailer.generate(path, self.target_size, crop_square=self.crop_square)
                    if image and not image.isNull():
                        # 3. Save to Disk Cache
                        image.save(cache_path, "JPG")  # pyrefly: ignore [no-matching-overload]
                        self._safe_emit(path, image)
                        results.append((path, image))
                    else:
                        self._safe_emit(path, QImage())
                        results.append((path, QImage()))
                except Exception:
                    self._safe_emit(path, QImage())
                    results.append((path, QImage()))

            with contextlib.suppress(RuntimeError):
                self.signals.batch_result.emit(results, self.paths)
        finally:
            if Shiboken.isValid(self.signals):
                self.signals.deleteLater()

    def _safe_emit(self, path, image):
        with contextlib.suppress(RuntimeError):
            self.signals.result.emit(path, image)

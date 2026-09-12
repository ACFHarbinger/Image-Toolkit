import contextlib
import os

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QImage
from shiboken6 import Shiboken

from gui.src.helpers.base import BaseQRunnableWorker

from .video_thumbnailer import VideoThumbnailer, get_video_thumbnail_cache_path


class _BatchVideoLoaderSignalsStream(QObject):
    # Emits (file_path, loaded_QImage)
    result = Signal(str, QImage)
    # Emits list of (file_path, loaded_QImage), and list of requested_paths
    batch_result = Signal(list, list)


class BatchVideoLoaderWorker(BaseQRunnableWorker):
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
        self.stream = _BatchVideoLoaderSignalsStream()
        self.thumbnailer = VideoThumbnailer()

    def stop(self):
        """Signals the worker to stop."""
        self.cancel()

    def _execute(self) -> object:
        if self._cancelled:
            return
        results = []
        try:
            for path in self.paths:
                if self._cancelled:
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
                self.stream.batch_result.emit(results, self.paths)
        finally:
            if Shiboken.isValid(self.stream):
                self.stream.deleteLater()

    def _safe_emit(self, path, image):
        with contextlib.suppress(RuntimeError):
            self.stream.result.emit(path, image)

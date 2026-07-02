from PySide6.QtGui import QImage
from PySide6.QtCore import QRunnable, QObject, Signal, Slot
from shiboken6 import Shiboken

import os
from .video_scan_worker import VideoThumbnailer, get_video_thumbnail_cache_path


class _VideoLoaderSignals(QObject):
    """
    Defines the signals for the VideoLoaderWorker.
    Must be a separate QObject because QRunnable does not inherit QObject.
    """

    # Emits (file_path, loaded_QImage)
    result = Signal(str, QImage)
    # Emits list of (file_path, loaded_QImage), and list of requested_paths
    batch_result = Signal(list, list)


class VideoLoaderWorker(QRunnable):
    """
    Worker task to load and scale a SINGLE video thumbnail.
    Designed to be run in a QThreadPool.
    """

    def __init__(self, path: str, target_size: int):
        super().__init__()
        self.path = path
        self.target_size = target_size
        self.signals = _VideoLoaderSignals()
        self.thumbnailer = VideoThumbnailer()
        self._is_cancelled = False

        # Auto-delete ensures the runnable is cleaned up after 'run' finishes
        self.setAutoDelete(True)

    def stop(self):
        """Signals the worker to stop."""
        self._is_cancelled = True

    @Slot()
    def run(self):
        if self._is_cancelled:
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
            image = self.thumbnailer.generate(self.path, self.target_size)
            if image and not image.isNull():
                # 3. Save to Disk Cache
                image.save(cache_path, "JPG") # pyrefly: ignore [no-matching-overload]
                self._safe_emit(self.path, image)
            else:
                self._safe_emit(self.path, QImage())
        except Exception:
            self._safe_emit(self.path, QImage())
        finally:
            if Shiboken.isValid(self.signals):
                self.signals.deleteLater()

    def _safe_emit(self, path, image):
        try:
            self.signals.result.emit(path, image)
        except RuntimeError:
            pass


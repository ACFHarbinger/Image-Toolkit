from PySide6.QtGui import QImage
from PySide6.QtCore import QRunnable, QObject, Signal, Slot

from .video_scan_worker import VideoThumbnailer


class VideoLoaderSignals(QObject):
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
        self.signals = VideoLoaderSignals()
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
            image = self.thumbnailer.generate(self.path, self.target_size)
            if image and not image.isNull():
                self._safe_emit(self.path, image)
            else:
                self._safe_emit(self.path, QImage())
        except Exception:
            self._safe_emit(self.path, QImage())

    def _safe_emit(self, path, image):
        try:
            self.signals.result.emit(path, image)
        except RuntimeError:
            pass


class BatchVideoLoaderWorker(QRunnable):
    """
    Worker task to load and scale a BATCH of video thumbnails.
    """

    def __init__(self, paths: list[str], target_size: int):
        super().__init__()
        self.paths = paths
        self.target_size = target_size
        self.signals = VideoLoaderSignals()
        self.thumbnailer = VideoThumbnailer()
        self._is_cancelled = False
        self.setAutoDelete(True)

    def stop(self):
        """Signals the worker to stop."""
        self._is_cancelled = True

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
                    image = self.thumbnailer.generate(path, self.target_size)
                    if image and not image.isNull():
                        self._safe_emit(path, image)
                        results.append((path, image))
                    else:
                        self._safe_emit(path, QImage())
                        results.append((path, QImage()))
                except Exception:
                    self._safe_emit(path, QImage())
                    results.append((path, QImage()))

            try:
                self.signals.batch_result.emit(results, self.paths)
            except RuntimeError:
                pass

        except Exception as e:
            print(f"BatchVideoLoaderWorker error: {e}")
            try:
                self.signals.batch_result.emit([], self.paths)
            except RuntimeError:
                pass

    def _safe_emit(self, path, image):
        try:
            self.signals.result.emit(path, image)
        except RuntimeError:
            pass

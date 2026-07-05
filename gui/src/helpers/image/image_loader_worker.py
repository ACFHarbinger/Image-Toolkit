import contextlib

from backend.src.constants import HAS_NATIVE_IMAGING
from PySide6.QtCore import QObject, QRunnable, Qt, Signal, Slot
from PySide6.QtGui import QImage
from shiboken6 import Shiboken

from .batch_image_loader_worker import native_load_batch


class _LoaderSignals(QObject):
    """
    Defines the signals for the ImageLoaderWorker.
    Must be a separate QObject because QRunnable does not inherit QObject.
    """

    # Emits (file_path, loaded_QImage)
    result = Signal(str, QImage)
    # Emits list of (file_path, loaded_QImage), and list of requested_paths
    batch_result = Signal(list, list)


class ImageLoaderWorker(QRunnable):
    """
    Worker task to load and scale a SINGLE image.
    Designed to be run in a QThreadPool.
    """

    def __init__(self, path: str, target_size: int):
        super().__init__()
        self.path = path
        self.target_size = target_size
        self.signals = _LoaderSignals()
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
            if HAS_NATIVE_IMAGING:
                # Returns list[(path, QImage | None, error: str)]
                results = native_load_batch([self.path], self.target_size)
                if self._is_cancelled:
                    return
                if results:
                    _path, q_img, err = results[0]
                    if q_img is not None and not err:
                        self._safe_emit(self.path, q_img)
                        return

            # Fallback using QImage instead of QPixmap
            q_img = QImage(self.path)
            if not q_img.isNull():
                scaled = q_img.scaled(
                    self.target_size,
                    self.target_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._safe_emit(self.path, scaled)
            else:
                self._safe_emit(self.path, QImage())
        except Exception:
            self._safe_emit(self.path, QImage())
        finally:
            if Shiboken.isValid(self.signals):
                self.signals.deleteLater()

    def _safe_emit(self, path, image):
        with contextlib.suppress(RuntimeError):
            self.signals.result.emit(path, image)


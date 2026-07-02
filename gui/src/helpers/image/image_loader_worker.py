from PySide6.QtGui import QImage
from PySide6.QtCore import QRunnable, QObject, Signal, Slot, Qt
from shiboken6 import Shiboken
from backend.src.constants import HAS_NATIVE_IMAGING

if HAS_NATIVE_IMAGING:
    import base


def process_image_batch(paths: list[str], target_size: int):
    """
    Process a batch of images using the C++ backend in a separate process.
    Returns a list of (path, buffer, width, height) tuples.
    """
    try:
        import base

        # Returns List[(path, buffer, width, height)]
        results = base.load_image_batch(paths, target_size)
        return results
    except Exception:
        return []


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
                results = base.load_image_batch([self.path], self.target_size)
                if self._is_cancelled:
                    return
                if results:
                    path, buffer, w, h = results[0]
                    q_img = QImage(buffer, w, h, QImage.Format_RGBA8888)
                    self._safe_emit(self.path, q_img.copy())
                    return

            # Fallback using QImage instead of QPixmap
            q_img = QImage(self.path)
            if not q_img.isNull():
                scaled = q_img.scaled(
                    self.target_size,
                    self.target_size,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
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
        try:
            self.signals.result.emit(path, image)
        except RuntimeError:
            pass


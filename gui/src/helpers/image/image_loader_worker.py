import contextlib

from backend.src.constants import HAS_NATIVE_IMAGING
from PySide6.QtCore import QObject, QRunnable, Signal, Slot
from PySide6.QtGui import QImage
from shiboken6 import Shiboken

from gui.src.helpers.gc_safe import gc_disabled_run

from ._qimagereader_disk_cache import load_qir_thumbnail
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

    # Set externally by callers that track cancellation generations (e.g.
    # AbstractClassSingleGallery._trigger_image_load) -- not assigned in
    # __init__ since not every caller needs it.
    load_generation: int

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

    @gc_disabled_run
    @Slot()
    def run(self):
        if self._is_cancelled:
            return
        try:
            # GIFs never go through the native decoder: it decodes via
            # OpenCV's cv::imread/imdecode, whose GIF support is absent or
            # unreliable depending on the build. Rather than a clean
            # failure (which the per-file None-check below could catch), a
            # misdecoded GIF can come back as a *valid but garbage* image
            # (e.g. a tiny/degenerate buffer upscaled to the thumbnail
            # size, rendering as a uniform solid-color block) -- so
            # `q_img is not None and not err` below isn't enough to trust
            # the result for this format. Qt's QImageReader supports GIF
            # (as its first frame) reliably through Qt's built-in plugins.
            if HAS_NATIVE_IMAGING and not self.path.lower().endswith(".gif"):
                # Returns list[(path, QImage | None, error: str)]
                results = native_load_batch([self.path], self.target_size)
                if self._is_cancelled:
                    return
                if results:
                    _path, q_img, err = results[0]
                    if q_img is not None and not err:
                        self._safe_emit(self.path, q_img)
                        return

            scaled = self._load_via_qimagereader(self.path, self.target_size)
            if self._is_cancelled:
                return
            self._safe_emit(self.path, scaled)
        except Exception:
            if not self._is_cancelled:
                self._safe_emit(self.path, QImage())
        finally:
            if Shiboken.isValid(self.signals):
                self.signals.deleteLater()

    @staticmethod
    def _load_via_qimagereader(path: str, target_size: int) -> QImage:
        """Shared QIR/GIF-poster thumbnail path (see load_qir_thumbnail)."""
        return load_qir_thumbnail(path, target_size)

    def _safe_emit(self, path, image):
        with contextlib.suppress(RuntimeError):
            self.signals.result.emit(path, image)


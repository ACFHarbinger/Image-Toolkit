from PySide6.QtGui import QImage
from PySide6.QtCore import QRunnable, QObject, Signal, Slot, Qt
from shiboken6 import Shiboken
from backend.src.constants import HAS_NATIVE_IMAGING

if HAS_NATIVE_IMAGING:
    import base


class _BatchLoaderSignals(QObject):
    # Emits (file_path, loaded_QImage)
    result = Signal(str, QImage)
    # Emits list of (file_path, loaded_QImage), and list of requested_paths
    batch_result = Signal(list, list)


class BatchImageLoaderWorker(QRunnable):
    """
    Worker task to load and scale a BATCH of images using Rust.
    Supports running in a separate process/executor if provided.
    """

    def __init__(self, paths: list[str], target_size: int):
        super().__init__()
        self.paths = paths
        self.target_size = target_size
        self.signals = _BatchLoaderSignals()
        self._is_cancelled = False
        self.setAutoDelete(True)

    def stop(self):
        """Signals the worker to stop."""
        self._is_cancelled = True

    @Slot()
    def run(self):
        if self._is_cancelled:
            return
        try:
            # 1. Fallback if no native imaging
            if not HAS_NATIVE_IMAGING:
                self._run_fallback()
                return

            # 2. Native Rust Parallel Path
            raw_results = base.load_image_batch(self.paths, self.target_size)

            if self._is_cancelled:
                return

            # Process raw results into QImages and EMIT IMMEDIATELY
            processed_results = []
            if raw_results:
                for path, buffer, w, h in raw_results:
                    # QImage.Format_RGBA8888 is 4 bytes per pixel
                    q_img = QImage(buffer, w, h, QImage.Format_RGBA8888)
                    res = (path, q_img.copy())
                    processed_results.append(res)
                    # Emit individual result for progressive UI updates
                    self._safe_emit_result(path, res[1])

            try:
                self.signals.batch_result.emit(processed_results, self.paths)
            except RuntimeError:
                pass
        finally:
            # Crucial: Ensure the QObject signals stay alive until the event loop
            # can deliver any pending signals. deleteLater() schedules this safely.
            if Shiboken.isValid(self.signals):
                self.signals.deleteLater()

    def _run_fallback(self):
        """Fallback: load one by one using QImage (slow but safe)"""
        results = []
        for path in self.paths:
            try:
                if self._is_cancelled:
                    break
                q_img = QImage(path)
                if not q_img.isNull():
                    scaled = q_img.scaled(
                        self.target_size,
                        self.target_size,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                    results.append((path, scaled))
                    self._safe_emit_result(path, scaled)
                else:
                    results.append((path, QImage()))
                    self._safe_emit_result(path, QImage())
            except Exception:
                results.append((path, QImage()))
                self._safe_emit_result(path, QImage())

        try:
            self.signals.batch_result.emit(results, self.paths)
        except RuntimeError:
            pass

    def _safe_emit_result(self, path, image):
        try:
            self.signals.result.emit(path, image)
        except RuntimeError:
            pass

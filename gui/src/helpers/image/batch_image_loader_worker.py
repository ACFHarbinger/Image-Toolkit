import numpy as np
from PySide6.QtGui import QImage
from PySide6.QtCore import QRunnable, QObject, Signal, Slot, Qt
from shiboken6 import Shiboken
from backend.src.constants import HAS_NATIVE_IMAGING

if HAS_NATIVE_IMAGING:
    import base


def _bgr_array_to_qimage(arr: np.ndarray) -> QImage:
    """base.load_image_batch returns HxWx3 BGR uint8 arrays (cv::imread order).
    Convert to a tightly-packed RGB buffer and copy it into a QImage."""
    rgb = np.ascontiguousarray(arr[:, :, ::-1])
    h, w = rgb.shape[0], rgb.shape[1]
    q_img = QImage(rgb.data, w, h, rgb.strides[0], QImage.Format.Format_RGB888)
    return q_img.copy()


class _BatchLoaderSignals(QObject):
    # Emits (file_path, loaded_QImage)
    result = Signal(str, QImage)
    # Emits list of (file_path, loaded_QImage), and list of requested_paths
    batch_result = Signal(list, list)


class BatchImageLoaderWorker(QRunnable):
    """
    Worker task to load and scale a BATCH of images using C++.
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

            # 2. Native C++ Parallel Path
            # Returns list[(path, HxWx3 BGR uint8 ndarray | None, error: str)]
            raw_results = base.load_image_batch( # pyrefly: ignore [missing-attribute]
                self.paths, self.target_size, self.target_size, True
            )

            if self._is_cancelled:
                return

            # Process raw results into QImages and EMIT IMMEDIATELY
            processed_results = []
            if raw_results:
                for path, arr, err in raw_results:
                    if arr is None or err:
                        q_img = QImage()
                    else:
                        q_img = _bgr_array_to_qimage(arr)
                    res = (path, q_img)
                    processed_results.append(res)
                    # Emit individual result for progressive UI updates
                    self._safe_emit_result(path, res[1])

            try:
                self.signals.batch_result.emit(processed_results, self.paths)
            except RuntimeError:
                pass
        except Exception:
            # A failure anywhere in the native path (unexpected return shape,
            # decode error, etc.) must not leave the gallery's placeholders
            # stuck in "Loading..." forever -- fall back to the safe
            # one-by-one QImage path instead.
            if not self._is_cancelled:
                self._run_fallback()
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
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
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

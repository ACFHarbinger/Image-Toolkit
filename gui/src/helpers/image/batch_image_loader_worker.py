import numpy as np
from PySide6.QtGui import QImage
from PySide6.QtCore import QRunnable, QObject, Signal, Slot, Qt
from shiboken6 import Shiboken
from backend.src.constants import HAS_NATIVE_IMAGING, THUMBNAIL_CACHE_DIR

if HAS_NATIVE_IMAGING:
    import base

# Set to False if the loaded native module predates the (rgb, cache_dir) params
_NATIVE_SUPPORTS_RGB_CACHE = True


def _bgr_array_to_qimage(arr: np.ndarray) -> QImage:
    """base.load_image_batch returns HxWx3 BGR uint8 arrays (cv::imread order).
    Convert to a tightly-packed RGB buffer and copy it into a QImage."""
    rgb = np.ascontiguousarray(arr[:, :, ::-1])
    h, w = rgb.shape[0], rgb.shape[1]
    q_img = QImage(rgb.data, w, h, rgb.strides[0], QImage.Format.Format_RGB888)
    return q_img.copy()


def _rgb_array_to_qimage(arr: np.ndarray) -> QImage:
    """Wrap an already-RGB HxWx3 uint8 array in a QImage (single copy)."""
    h, w = arr.shape[0], arr.shape[1]
    q_img = QImage(arr.data, w, h, arr.strides[0], QImage.Format.Format_RGB888)
    return q_img.copy()


def native_load_batch(paths: list[str], target_size: int) -> list[tuple[str, QImage | None, str]]:
    """Call base.load_image_batch with the RGB + disk-cache fast path,
    falling back to the legacy BGR signature for older native builds.
    Returns list of (path, QImage|None, error)."""
    global _NATIVE_SUPPORTS_RGB_CACHE
    if _NATIVE_SUPPORTS_RGB_CACHE:
        try:
            raw = base.load_image_batch(  # pyrefly: ignore [missing-attribute]
                paths, target_size, target_size, True,
                True, str(THUMBNAIL_CACHE_DIR),
            )
            return [
                (p, _rgb_array_to_qimage(a) if a is not None and not e else None, e)
                for p, a, e in raw
            ]
        except TypeError:
            _NATIVE_SUPPORTS_RGB_CACHE = False

    raw = base.load_image_batch(  # pyrefly: ignore [missing-attribute]
        paths, target_size, target_size, True
    )
    return [
        (p, _bgr_array_to_qimage(a) if a is not None and not e else None, e)
        for p, a, e in raw
    ]


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

            # 2. Native C++ Parallel Path (reduced decode + disk cache + RGB out)
            raw_results = native_load_batch(self.paths, self.target_size)

            if self._is_cancelled:
                return

            # Process results and EMIT IMMEDIATELY
            processed_results = []
            for path, q_img, _err in raw_results:
                if q_img is None:
                    q_img = QImage()
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

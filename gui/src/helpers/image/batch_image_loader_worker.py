import contextlib

import numpy as np
from backend.src.constants import HAS_NATIVE_IMAGING, THUMBNAIL_CACHE_DIR
from backend.src.core import telemetry
from PySide6.QtCore import QObject, QRunnable, Qt, Signal, Slot
from PySide6.QtGui import QImage
from shiboken6 import Shiboken

from gui.src.constants.helpers import _NATIVE_SUPPORTS_RGB_CACHE
from gui.src.helpers.gc_safe import gc_disabled_run

if HAS_NATIVE_IMAGING:
    import base

# Set to False if the loaded native module predates the (rgb, cache_dir) params


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
    Returns list of (path, QImage|None, error).

    Serialized via ``telemetry.NATIVE_IMAGE_BATCH_LOCK`` -- see that lock's
    docstring in ``backend/src/core/telemetry.py`` for why concurrent Python-
    level entries into this native boundary (not just concurrent OpenMP
    work within a single call) are unsafe and were the actual root cause of
    this project's long-running QSocketNotifier/SIGSEGV crash class.
    """
    global _NATIVE_SUPPORTS_RGB_CACHE
    if _NATIVE_SUPPORTS_RGB_CACHE:
        try:
            with telemetry.NATIVE_IMAGE_BATCH_LOCK:
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

    with telemetry.NATIVE_IMAGE_BATCH_LOCK:
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

    @gc_disabled_run
    @Slot()
    def run(self):
        if self._is_cancelled:
            return
        try:
            # GIFs never go through the native decoder: it decodes via
            # OpenCV's cv::imread/imdecode, whose GIF support is absent or
            # unreliable depending on the build -- rather than a clean
            # failure (which the per-file None-check below could catch),
            # a misdecoded GIF can come back as a *valid but garbage*
            # image (e.g. a tiny/degenerate buffer upscaled to the
            # thumbnail size, rendering as a uniform solid-color block).
            # Qt's own QImage(path) loader supports GIF (as its first
            # frame) reliably through Qt's built-in image plugins.
            gif_paths = [p for p in self.paths if p.lower().endswith(".gif")]
            native_paths = [p for p in self.paths if not p.lower().endswith(".gif")]

            processed_results: list[tuple[str, QImage]] = []

            for path in gif_paths:
                if self._is_cancelled:
                    return
                q_img = self._load_one_via_qimage(path)
                processed_results.append((path, q_img))
                self._safe_emit_result(path, q_img)

            if native_paths:
                if not HAS_NATIVE_IMAGING:
                    for path in native_paths:
                        if self._is_cancelled:
                            return
                        q_img = self._load_one_via_qimage(path)
                        processed_results.append((path, q_img))
                        self._safe_emit_result(path, q_img)
                else:
                    # Native C++ Parallel Path (reduced decode + disk cache + RGB out)
                    raw_results = native_load_batch(native_paths, self.target_size)

                    if self._is_cancelled:
                        return

                    for path, q_img, _err in raw_results:
                        if q_img is None:
                            # The native decoder failed for just this one
                            # file -- fall back to Qt's own QImage(path)
                            # loader for this file specifically instead of
                            # leaving its thumbnail permanently blank; the
                            # batch-level `except Exception` below never
                            # fires for a per-file failure like this.
                            q_img = self._load_one_via_qimage(path)
                        processed_results.append((path, q_img))
                        self._safe_emit_result(path, q_img)

            with contextlib.suppress(RuntimeError):
                self.signals.batch_result.emit(processed_results, self.paths)
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

    def _load_one_via_qimage(self, path: str) -> QImage:
        """Load and scale a single file via Qt's own QImage plugins (slower
        than the native path, but supports formats it can't decode)."""
        try:
            q_img = QImage(path)
            if q_img.isNull():
                return QImage()
            return q_img.scaled(
                self.target_size,
                self.target_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        except Exception:
            return QImage()

    def _run_fallback(self):
        """Fallback: load one by one using QImage (slow but safe)"""
        results = []
        for path in self.paths:
            if self._is_cancelled:
                break
            scaled = self._load_one_via_qimage(path)
            results.append((path, scaled))
            self._safe_emit_result(path, scaled)

        with contextlib.suppress(RuntimeError):
            self.signals.batch_result.emit(results, self.paths)

    def _safe_emit_result(self, path, image):
        with contextlib.suppress(RuntimeError):
            self.signals.result.emit(path, image)

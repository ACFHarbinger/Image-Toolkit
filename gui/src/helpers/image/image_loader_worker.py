from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import QRunnable, QObject, Signal, Slot, Qt

from concurrent.futures import Executor

try:
    import base

    HAS_NATIVE_IMAGING = True
except ImportError:
    HAS_NATIVE_IMAGING = False


def process_image_batch(paths: list[str], target_size: int):
    """
    Process a batch of images using the Rust backend in a separate process.
    Returns a list of (path, buffer, width, height) tuples.
    """
    try:
        import base

        # Returns List[(path, buffer, width, height)]
        results = base.load_image_batch(paths, target_size)
        return results
    except Exception:
        return []


class LoaderSignals(QObject):
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
        self.signals = LoaderSignals()

        # Auto-delete ensures the runnable is cleaned up after 'run' finishes
        self.setAutoDelete(True)

    @Slot()
    def run(self):
        try:
            if HAS_NATIVE_IMAGING:
                results = base.load_image_batch([self.path], self.target_size)
                if results:
                    path, buffer, w, h = results[0]
                    q_img = QImage(buffer, w, h, QImage.Format_RGBA8888)
                    self.signals.result.emit(self.path, q_img.copy())
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
                self.signals.result.emit(self.path, scaled)
            else:
                self.signals.result.emit(self.path, QImage())
        except Exception:
            self.signals.result.emit(self.path, QPixmap())


class BatchImageLoaderWorker(QRunnable):
    """
    Worker task to load and scale a BATCH of images using Rust.
    Supports running in a separate process/executor if provided.
    """

    def __init__(self, paths: list[str], target_size: int):
        super().__init__()
        self.paths = paths
        self.target_size = target_size
        self.signals = LoaderSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self):
        try:
            # 1. Fallback if no native imaging
            if not HAS_NATIVE_IMAGING:
                self._run_fallback()
                return

            # 2. Native Rust Parallel Path
            raw_results = base.load_image_batch(self.paths, self.target_size)

            # Process raw results into QImages and EMIT IMMEDIATELY
            processed_results = []
            if raw_results:
                for path, buffer, w, h in raw_results:
                    # QImage.Format_RGBA8888 is 4 bytes per pixel
                    q_img = QImage(buffer, w, h, QImage.Format_RGBA8888)
                    res = (path, q_img.copy())
                    processed_results.append(res)
                    # Emit individual result for progressive UI updates
                    self.signals.result.emit(path, res[1])

            self.signals.batch_result.emit(processed_results, self.paths)

        except Exception as e:
            self.signals.batch_result.emit([], self.paths)

    def _run_fallback(self):
        """Fallback: load one by one using QImage (slow but safe)"""
        results = []
        for path in self.paths:
            try:
                q_img = QImage(path)
                if not q_img.isNull():
                    scaled = q_img.scaled(
                        self.target_size,
                        self.target_size,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                    results.append((path, scaled))
                    self.signals.result.emit(path, scaled)
                else:
                    results.append((path, QImage()))
                    self.signals.result.emit(path, QImage())
            except Exception as e:
                results.append((path, QImage()))
                self.signals.result.emit(path, QImage())
        self.signals.batch_result.emit(results, self.paths)

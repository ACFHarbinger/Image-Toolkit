from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import QRunnable, QObject, Signal, Slot, Qt

import multiprocessing
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

    # Emits (file_path, loaded_pixmap)
    result = Signal(str, QPixmap)
    # Emits list of (file_path, loaded_pixmap), and list of requested_paths
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
                    pix = QPixmap.fromImage(q_img.copy())
                    self.signals.result.emit(self.path, pix)
                    return

            pixmap = QPixmap(self.path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    self.target_size,
                    self.target_size,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
                scaled_copy = scaled.copy()
                self.signals.result.emit(self.path, scaled_copy)
            else:
                self.signals.result.emit(self.path, QPixmap())
        except Exception:
            self.signals.result.emit(self.path, QPixmap())


class BatchImageLoaderWorker(QRunnable):
    """
    Worker task to load and scale a BATCH of images using Rust.
    Supports running in a separate process/executor if provided.
    """

    def __init__(self, paths: list[str], target_size: int, executor: Executor = None):
        super().__init__()
        self.paths = paths
        self.target_size = target_size
        self.executor = executor
        self.signals = LoaderSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self):
        try:
            # 1. Fallback if no native imaging
            if not HAS_NATIVE_IMAGING:
                self._run_fallback()
                return

            # 2. Multiprocessing Path (Preferred)
            if self.executor:
                future = self.executor.submit(process_image_batch, self.paths, self.target_size)
                # This blocks the QThreadPool thread, which is intentional/acceptable
                # because we are offloading CPU work to the ProcessPool.
                raw_results = future.result()
            else:
                # 3. In-Thread Path (if no executor provided)
                raw_results = base.load_image_batch(self.paths, self.target_size)
            
            # Process raw results into QPixmaps (Must be done in this thread/process, not the child)
            processed_results = []
            if raw_results:
                for path, buffer, w, h in raw_results:
                    # QImage.Format_RGBA8888 is 4 bytes per pixel
                    q_img = QImage(buffer, w, h, QImage.Format_RGBA8888)
                    # Need to copy because buffer might be GC'd or modified?
                    # Actually, PyBytes is immutable, allowing QImage to reference it. 
                    # But QPixmap.fromImage makes a deep copy anyway.
                    pix = QPixmap.fromImage(q_img.copy())
                    processed_results.append((path, pix))
            
            self.signals.batch_result.emit(processed_results, self.paths)

        except Exception as e:
            print(f"BatchImageLoaderWorker error: {e}")
            self.signals.batch_result.emit([], self.paths)

    def _run_fallback(self):
        """Fallback: load one by one using QPixmap (slow but safe)"""
        results = []
        for path in self.paths:
            try:
                pix = QPixmap(path)
                if not pix.isNull():
                    scaled = pix.scaled(
                        self.target_size, self.target_size,
                        Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )
                    results.append((path, scaled))
                else:
                    results.append((path, QPixmap()))
            except Exception:
                results.append((path, QPixmap()))
        self.signals.batch_result.emit(results, self.paths)

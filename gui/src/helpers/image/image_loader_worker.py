from PySide6.QtGui import QPixmap
from PySide6.QtCore import QRunnable, QObject, Signal, Slot, Qt


class LoaderSignals(QObject):
    """
    Defines the signals for the ImageLoaderWorker.
    Must be a separate QObject because QRunnable does not inherit QObject.
    """

    # Emits (file_path, loaded_pixmap)
    result = Signal(str, QPixmap)


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
            pixmap = QPixmap(self.path)
            if not pixmap.isNull():
                # Scale the image for the thumbnail view
                # Using FastTransformation for speed, or SmoothTransformation for quality
                # Given we are threading, SmoothTransformation is affordable and looks better.
                scaled = pixmap.scaled(
                    self.target_size,
                    self.target_size,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
                self.signals.result.emit(self.path, scaled)
            else:
                # Emit null pixmap to indicate failure/corruption
                self.signals.result.emit(self.path, QPixmap())
        except Exception:
            self.signals.result.emit(self.path, QPixmap())

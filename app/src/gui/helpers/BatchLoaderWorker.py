# BatchLoaderWorker.py

from PySide6.QtGui import QPixmap
from PySide6.QtCore import QObject, Signal, Slot, Qt


class BatchThumbnailLoaderWorker(QObject):
    """
    Worker to load and scale a batch of images sequentially on a single separate thread.
    Emits a signal for each completed thumbnail for progressive display.
    """

    # Signal to create the placeholder on the main thread: (index, path)
    # --- ADDED SIGNAL ---
    create_placeholder = Signal(int, str)
    
    # Signal to send the result: (index, QPixmap, path)
    thumbnail_loaded = Signal(int, QPixmap, str)
    
    # Signal emitted when all images are processed
    loading_finished = Signal()

    def __init__(self, paths: list[str], size: int):
        super().__init__()
        self.paths = paths
        self.size = size

    @Slot()
    def run_load_batch(self):
        """Loads, scales, and emits the QPixmap for each image sequentially."""
        
        for i, path in enumerate(self.paths):
            try:
                # 1. Notify main thread to create placeholder before blocking load
                # --- ADDED SIGNAL EMIT ---
                self.create_placeholder.emit(i, path)
                
                # 2. Load the image using QPixmap (Blocking call on this worker thread)
                pixmap = QPixmap(path)
                
                if not pixmap.isNull():
                    # 3. Scale the QPixmap
                    scaled = pixmap.scaled(
                        self.size, self.size, 
                        Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )
                    # 4. Emit the result back to the main thread immediately
                    self.thumbnail_loaded.emit(i, scaled, path)
                else:
                    # Emit a null/empty pixmap for load errors
                    self.thumbnail_loaded.emit(i, QPixmap(), path)

            except Exception:
                # Emit an empty pixmap on unexpected error
                self.thumbnail_loaded.emit(i, QPixmap(), path)
        
        # 5. Signal that the entire batch is done
        self.loading_finished.emit()

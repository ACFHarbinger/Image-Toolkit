import os
from typing import List, Tuple
from PySide6.QtGui import QPixmap
from PySide6.QtCore import QObject, Signal, Slot, Qt

class BatchThumbnailLoaderWorker(QObject):
    """
    Worker to load and scale ALL images on a background thread,
    then return them all at once to prevent signal flooding (Seg Faults).
    """

    # Signal to send ALL results at once: List of (path, QPixmap)
    batch_finished = Signal(list)

    def __init__(self, paths: list[str], size: int):
        super().__init__()
        self.paths = paths
        self.size = size

    @Slot()
    def run_load_batch(self):
        """
        Loads and scales all images into a local list, then emits once.
        """
        loaded_results: List[Tuple[str, QPixmap]] = []
        
        for path in self.paths:
            try:
                # Load the image
                pixmap = QPixmap(path)
                
                if not pixmap.isNull():
                    # Scale the QPixmap
                    scaled = pixmap.scaled(
                        self.size, self.size, 
                        Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )
                    loaded_results.append((path, scaled))
                else:
                    # Handle corrupt images gracefully (optional: return empty pixmap)
                    loaded_results.append((path, QPixmap()))

            except Exception:
                # Skip or handle files that cause read errors
                loaded_results.append((path, QPixmap()))
        
        # Emit EVERYTHING in one go.
        # This prevents the Main Thread event loop from being flooded 
        # by thousands of individual signals.
        self.batch_finished.emit(loaded_results)

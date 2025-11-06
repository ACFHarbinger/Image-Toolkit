import os

from PySide6.QtCore import QObject, Signal, Slot
from ...utils.definitions import SUPPORTED_IMG_FORMATS


class ImageScannerWorker(QObject):
    """Worker to perform file system scanning on a separate thread."""
    
    scan_finished = Signal(list)
    scan_error = Signal(str)

    def __init__(self, directory: str):
        super().__init__()
        self.directory = directory

    @Slot()
    def run_scan(self):
        """The long-running task that runs in the separate thread, now using os.walk()."""
        image_paths = []
        try:
            for root, _, filenames in os.walk(self.directory):
                for entry in filenames:
                    # Check for supported image extensions
                    if entry.lower().endswith(tuple(SUPPORTED_IMG_FORMATS)):
                        # CORRECT: os.path.join joins two strings: root and entry
                        full_path = os.path.join(root, entry) 
                        image_paths.append(full_path)
            
            # Send the sorted results back to the main thread
            self.scan_finished.emit(sorted(image_paths))
        except Exception as e:
            # Handle potential errors like PermissionError
            self.scan_error.emit(f"Could not scan directory and subdirectories: {e}")

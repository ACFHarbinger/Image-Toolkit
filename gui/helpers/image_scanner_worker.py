import os
from typing import List, Union
from PySide6.QtCore import QObject, Signal, Slot
from backend.src.utils.definitions import SUPPORTED_IMG_FORMATS


class ImageScannerWorker(QObject):
    """
    Worker to perform file system scanning on a separate thread.
    Now supports initialization with a single directory path or a list of paths
    for unified processing (delegating list handling to internal logic).
    """
    
    scan_finished = Signal(list)
    scan_error = Signal(str)

    def __init__(self, directories: Union[str, List[str]]):
        super().__init__()
        
        # --- MODIFICATION: Handle single string or list input ---
        if isinstance(directories, (str, os.PathLike)):
            self.directories = [str(directories)]
        elif isinstance(directories, list):
            # Filter out empty or None entries
            self.directories = [d for d in directories if d and os.path.isdir(d)]
        else:
            self.directories = []
        # --- END MODIFICATION ---

    @Slot()
    def run_scan(self):
        """
        Iterates through all provided directories and aggregates image paths
        using os.walk() for recursive scanning.
        """
        image_paths = []
        supported_extensions = tuple(f'.{fmt}' for fmt in SUPPORTED_IMG_FORMATS)
        
        if not self.directories:
            self.scan_error.emit("No valid directories provided for scanning.")
            return

        try:
            for directory in self.directories:
                if not os.path.isdir(directory):
                    self.scan_error.emit(f"Path is not a valid directory: {directory}")
                    # Note: We emit an error and return immediately, preventing processing of subsequent paths.
                    # For continued processing, this error handling would need to be inside the loop.
                    return

                for root, _, filenames in os.walk(directory):
                    for entry in filenames:
                        # Check for supported image extensions
                        if entry.lower().endswith(supported_extensions):
                            full_path = os.path.join(root, entry) 
                            image_paths.append(full_path)
            
            # Send the sorted results back to the main thread
            self.scan_finished.emit(sorted(image_paths))
        except Exception as e:
            # Handle potential errors like PermissionError
            self.scan_error.emit(f"Could not scan directory and subdirectories: {e}")

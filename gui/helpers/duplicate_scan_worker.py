from PySide6.QtCore import Slot, Signal, QObject
from backend.src.core.file_system_entries import DuplicateFinder


class DuplicateScanWorker(QObject):
    """Worker thread for scanning duplicates to avoid freezing UI."""
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, directory, extensions):
        super().__init__()
        self.directory = directory
        self.extensions = extensions

    @Slot()
    def run(self):
        try:
            results = DuplicateFinder.find_duplicate_images(
                self.directory, 
                self.extensions, 
                recursive=True
            )
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))

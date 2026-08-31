import imagehash
from PIL import Image
from PySide6.QtCore import QRunnable, Slot

from gui.src.helpers.gc_safe import gc_disabled_run

from .scan_signals import ScanSignals


class PhashTask(QRunnable):
    """
    Task to compute perceptual hash for a single image.
    """

    def __init__(self, path: str):
        super().__init__()
        self.path = path
        self.signals = ScanSignals()
        self.setAutoDelete(True)

    @gc_disabled_run
    @Slot()
    def run(self):
        try:
            with Image.open(self.path) as img:
                # Compute hash
                img_hash = imagehash.average_hash(img)
                self.signals.result.emit((self.path, img_hash))
        except Exception:
            # On failure, emit None so the main counter still increments
            self.signals.result.emit((self.path, None))

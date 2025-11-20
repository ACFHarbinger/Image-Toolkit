from PySide6.QtCore import QRunnable, Slot
from .scan_signals import ScanSignals
from models.siamese_network import SiameseModelLoader


class SiameseTask(QRunnable):
    """
    Task to compute Deep Learning Embeddings (Siamese/One-Shot).
    """
    def __init__(self, path: str):
        super().__init__()
        self.path = path
        self.signals = ScanSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self):
        try:
            # Get the singleton instance
            loader = SiameseModelLoader()
            
            # Compute embedding
            # This returns a 512-float vector representing the image content
            embedding = loader.get_embedding(self.path)
            
            if embedding is not None:
                self.signals.result.emit((self.path, embedding))
            else:
                self.signals.result.emit((self.path, None))
                
        except Exception as e:
            # In case torch is not installed or other critical error
            self.signals.result.emit((self.path, None))

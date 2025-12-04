import cv2
import numpy as np

from PIL import Image
from PySide6.QtCore import QRunnable, Slot
from .scan_signals import ScanSignals


class SiftTask(QRunnable):
    """
    Task to compute SIFT descriptors for a single image.
    Uses Euclidean Distance (L2) norms, unlike ORB's Hamming distance.
    """

    def __init__(self, path: str):
        super().__init__()
        self.path = path
        self.signals = ScanSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self):
        try:
            # Initialize SIFT (Local instance is thread-safer)
            # limiting nfeatures helps performance while maintaining accuracy
            sift = cv2.SIFT_create(nfeatures=1000)

            # --- ROBUST LOAD (Standardized pipeline) ---
            pil_img_rgba = Image.open(self.path).convert("RGBA")
            pil_img = pil_img_rgba.convert("L")
            img_np = np.array(pil_img)
            # -----------------------------------------

            # Compute descriptors
            kp, des = sift.detectAndCompute(img_np, None)

            # SIFT returns float descriptors.
            # We check if we have enough features to make a valid comparison.
            if des is not None and len(des) > 10:
                self.signals.result.emit((self.path, des))
            else:
                self.signals.result.emit((self.path, None))

        except Exception:
            self.signals.result.emit((self.path, None))

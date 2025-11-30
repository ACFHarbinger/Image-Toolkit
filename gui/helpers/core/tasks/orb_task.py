import cv2
import numpy as np

from PIL import Image
from PySide6.QtCore import QRunnable, Slot
from .scan_signals import ScanSignals


class OrbTask(QRunnable):
    """
    Task to compute ORB descriptors for a single image.
    """
    def __init__(self, path: str):
        super().__init__()
        self.path = path
        self.signals = ScanSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self):
        try:
            # Initialize ORB (local instance per thread is safer)
            orb = cv2.ORB_create(nfeatures=500)
            
            # --- ROBUST LOAD (From previous logic) ---
            # 1. Load: Open and convert to RGBA first to handle palette transparency
            pil_img_rgba = Image.open(self.path).convert('RGBA')
            
            # 2. Grayscale: Convert the RGBA image to Luminance ('L')
            pil_img = pil_img_rgba.convert('L')
            
            # 3. Numpy: Convert the PIL image to a NumPy array for OpenCV
            img_np = np.array(pil_img)
            # -----------------------------------------

            # Compute descriptors
            kp, des = orb.detectAndCompute(img_np, None)
            
            if des is not None and len(des) > 10:
                self.signals.result.emit((self.path, des))
            else:
                self.signals.result.emit((self.path, None))
                
        except Exception:
            self.signals.result.emit((self.path, None))

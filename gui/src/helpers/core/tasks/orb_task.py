from gui.src.helpers.base import BaseQRunnableWorker


class OrbTask(BaseQRunnableWorker):
    """
    Task to compute ORB descriptors for a single image.
    """

    def __init__(self, path: str):
        super().__init__()
        self.path = path

    def _execute(self) -> object:
        try:
            import cv2
            import numpy as np
            from PIL import Image

            # Initialize ORB (local instance per thread is safer)
            orb = cv2.ORB_create(nfeatures=500)  # pyrefly: ignore [missing-attribute]

            # --- ROBUST LOAD (From previous logic) ---
            # 1. Load: Open and convert to RGBA first to handle palette transparency
            pil_img_rgba = Image.open(self.path).convert("RGBA")

            # 2. Grayscale: Convert the RGBA image to Luminance ('L')
            pil_img = pil_img_rgba.convert("L")

            # 3. Numpy: Convert the PIL image to a NumPy array for OpenCV
            img_np = np.array(pil_img)
            # -----------------------------------------

            # Compute descriptors
            kp, des = orb.detectAndCompute(img_np, None)

            if des is not None and len(des) > 10:
                return (self.path, des)
            return (self.path, None)
        except Exception:
            # On failure, return None so the main counter still increments
            return (self.path, None)

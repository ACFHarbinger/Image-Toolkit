import numpy as np
from PIL import Image

from gui.src.helpers.base import BaseQRunnableWorker


class SsimTask(BaseQRunnableWorker):
    """
    Task to prepare an image for SSIM comparison.

    SSIM requires images to be of identical dimensions. This task
    loads the image, converts it to grayscale, and resizes it to a
    fixed standard (256x256) to optimize the O(N^2) comparison phase.
    """

    def __init__(self, path: str):
        super().__init__()
        self.path = path
        self.process_size = (256, 256)  # Fixed size for SSIM comparison

    def _execute(self) -> object:
        try:
            # --- ROBUST LOAD ---
            # Use PIL for initial load to handle edge-case formats/palettes better than cv2
            pil_img_rgba = Image.open(self.path).convert("RGBA")
            pil_img = pil_img_rgba.convert("L")  # Convert to Grayscale

            # Resize using PIL High Quality downsampling
            # This is crucial: SSIM fails if dimensions don't match perfectly.
            pil_img = pil_img.resize(self.process_size, Image.Resampling.LANCZOS)

            # Convert to Numpy float32 for OpenCV processing
            img_np = np.array(pil_img).astype(np.float32)

            return (self.path, img_np)
        except Exception:
            return (self.path, None)

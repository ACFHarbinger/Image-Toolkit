import imagehash
from PIL import Image

from gui.src.helpers.base import BaseQRunnableWorker


class PhashTask(BaseQRunnableWorker):
    """
    Task to compute perceptual hash for a single image.
    """

    def __init__(self, path: str):
        super().__init__()
        self.path = path

    def _execute(self) -> object:
        try:
            with Image.open(self.path) as img:
                # Compute hash
                img_hash = imagehash.average_hash(img)
                return (self.path, img_hash)
        except Exception:
            # On failure, return None so the main counter still increments
            return (self.path, None)

from gui.src.helpers.base import BaseQRunnableWorker


class SiameseTask(BaseQRunnableWorker):
    """
    Task to compute Deep Learning Embeddings (Siamese/One-Shot).
    """

    def __init__(self, path: str):
        super().__init__()
        self.path = path

    def _execute(self) -> object:
        try:
            from backend.src.models.core.siamese_network import SiameseModelLoader

            # Get the singleton instance
            loader = SiameseModelLoader()

            # Compute embedding
            # This returns a 512-float vector representing the image content
            embedding = loader.get_embedding(self.path)

            if embedding is not None:
                return (self.path, embedding)
            return (self.path, None)
        except Exception:
            # In case torch is not installed or other critical error
            return (self.path, None)

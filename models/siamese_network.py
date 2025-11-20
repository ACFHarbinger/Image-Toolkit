import torch
import torchvision.models as models

from PIL import Image


class SiameseModelLoader:
    """
    Singleton class to load the ResNet model once and share it 
    across worker threads.
    """
    _instance = None
    _model = None
    _device = None
    _transform = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SiameseModelLoader, cls).__new__(cls)
        return cls._instance

    def load_model(self):
        if self._model is None:
            # 1. Detect Device (GPU is faster, but CPU is safer for general compatibility)
            self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            
            # 2. Load Pre-trained ResNet18 (Lightweight and effective)
            # We use the "default" weights which are trained on ImageNet
            weights = models.ResNet18_Weights.DEFAULT
            self._model = models.resnet18(weights=weights)
            
            # 3. Convert to Feature Extractor
            # Remove the final classification layer (fc) to get the embedding vector (512-dim)
            self._model.fc = torch.nn.Identity()
            
            self._model.to(self._device)
            self._model.eval() # Set to inference mode

            # 4. Define Standard Transforms
            self._transform = weights.transforms()

    def get_embedding(self, img_path: str):
        """
        Generates a 512-dimensional vector for the image.
        """
        if self._model is None:
            self.load_model()

        try:
            # Load and convert to RGB (ResNet expects 3 channels)
            img = Image.open(img_path).convert('RGB')
            
            # Apply transforms (Resize, CenterCrop, Normalize)
            img_t = self._transform(img)
            
            # Add batch dimension (3, H, W) -> (1, 3, H, W)
            batch_t = torch.unsqueeze(img_t, 0).to(self._device)

            # Inference
            with torch.no_grad():
                output = self._model(batch_t)
            
            # Return as 1D numpy array
            return output.cpu().numpy().flatten()
        except Exception:
            return None

import torch
import numpy as np
import cv2
from PIL import Image
from torchvision import transforms

# BiRefNet depends on transformers, and sometimes needs patches for remote code execution
try:
    import transformers.configuration_utils
    original_getattribute = transformers.configuration_utils.PretrainedConfig.__getattribute__

    def patched_getattribute(self, key):
        if key == 'is_encoder_decoder':
            return False
        return original_getattribute(self, key)

    transformers.configuration_utils.PretrainedConfig.__getattribute__ = patched_getattribute
    from transformers import AutoModelForImageSegmentation
except ImportError:
    print("[BiRefNet] Transformers not installed. Background removal will be unavailable.")

class BiRefNetWrapper:
    _instance = None
    _model = None
    
    def __init__(self, model_name="ZhengPeng7/BiRefNet", device=None):
        self.device = device if device else ("cuda" if torch.cuda.is_available() else "cpu")
        self.model_name = model_name
        self.transform = transforms.Compose([
            transforms.Resize((1024, 1024)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])

    def load_model(self):
        if BiRefNetWrapper._model is None:
            print(f"[BiRefNet] Loading model {self.model_name} on {self.device}...")
            BiRefNetWrapper._model = AutoModelForImageSegmentation.from_pretrained(
                self.model_name, 
                trust_remote_code=True
            ).to(self.device)
            BiRefNetWrapper._model.eval()
        return BiRefNetWrapper._model

    def get_mask(self, img_np: np.ndarray) -> np.ndarray:
        """
        Generates a binary mask where 1 = foreground (character).
        Input: BGR numpy array (OpenCV format)
        Output: Binary numpy array (0 or 255)
        """
        model = self.load_model()
        
        # Convert BGR to RGB and PIL
        img_rgb = cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(img_rgb)
        
        input_tensor = self.transform(image).unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            preds = model(input_tensor)[-1].sigmoid().cpu().numpy()
        
        # Post-process mask
        mask = preds[0].squeeze()
        mask = cv2.resize(mask, (img_np.shape[1], img_np.shape[0]))
        
        # Threshold to create binary mask
        binary_mask = (mask > 0.5).astype(np.uint8) * 255
        return binary_mask

    def apply_segmentation(self, img_np: np.ndarray) -> np.ndarray:
        """Returns the image with background removed (black background)."""
        mask = self.get_mask(img_np)
        mask_3ch = cv2.merge([mask, mask, mask])
        result = cv2.bitwise_and(img_np, mask_3ch)
        return result

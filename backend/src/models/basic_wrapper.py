import torch
import torch.nn.functional as F
import numpy as np
import cv2
from typing import List, Tuple

class BaSiCWrapper:
    """
    Retrospective Background and Shading Correction (BaSiC).
    Estimates flat-field and dark-field profiles from a sequence of images.
    Utilizes PyTorch for accelerated sparse and low-rank decomposition.
    """

    def __init__(self, device: str = None):
        self.device = device if device else ("cuda" if torch.cuda.is_available() else "cpu")
        self.flat_field = None
        self.dark_field = None

    def estimate_profiles(self, images: List[np.ndarray], iterations: int = 20) -> Tuple[np.ndarray, np.ndarray]:
        """
        Estimates the flat-field (shading) and dark-field (offset) from a stack of images.
        Based on the BaSiC algorithm principles.
        """
        if len(images) < 5:
            # Not enough images for a good estimate, return defaults
            h, w = images[0].shape[:2]
            return np.ones((h, w, 3), dtype=np.float32), np.zeros((h, w, 3), dtype=np.float32)

        # 1. Convert to float32 tensors and stack
        # Shape: (N, C, H, W)
        stack = []
        for img in images:
            stack.append(torch.from_numpy(img).permute(2, 0, 1).float().to(self.device))
        
        X = torch.stack(stack) / 255.0  # Normalize to [0, 1]
        N, C, H, W = X.shape

        # 2. Sparse and Low-Rank Decomposition (Simplified)
        # We want to find B (flat-field) such that X_i ≈ S_i * B + D
        # In a simpler form, B is the common shading pattern.
        
        # Initial estimate: median along the stack is robust to moving objects
        # We compute median per channel
        B, _ = torch.median(X, dim=0)
        
        # Normalize B so its mean is 1.0 (it's a gain map)
        mean_b = B.mean(dim=(1, 2), keepdim=True)
        B = B / (mean_b + 1e-6)
        
        # 3. Iterative refinement (optional, simplified)
        # For a truly perfect stitch, we could refine B by ignoring sparse outliers (foreground)
        for _ in range(3):
            # Compute residuals
            # X_i / B should be roughly constant
            normalized_stack = X / (B.unsqueeze(0) + 1e-6)
            # Re-estimate B by weighting pixels that are closer to the median.
            weights = torch.exp(-torch.abs(X - B.unsqueeze(0)) * 10.0)
            B = torch.sum(X * weights, dim=0) / (torch.sum(weights, dim=0) + 1e-6)
            mean_b = B.mean(dim=(1, 2), keepdim=True)
            B = B / (mean_b + 1e-6)

        # 4. Final smoothing and clamping to prevent extreme artifacts
        # Shading is usually low-frequency
        self.flat_field = B.permute(1, 2, 0).cpu().numpy()
        
        # Smooth the flat-field to remove noise from moving objects
        self.flat_field = cv2.GaussianBlur(self.flat_field, (31, 31), 0)
        
        # Clamp the flat-field to [0.5, 2.0] to prevent extreme gain
        self.flat_field = np.clip(self.flat_field, 0.5, 2.0)
        
        self.dark_field = np.zeros_like(self.flat_field) # Simplified dark-field for now

        return self.flat_field, self.dark_field

    def apply_correction(self, img: np.ndarray) -> np.ndarray:
        """
        Applies the estimated shading correction to a single image.
        C = (R - D) / B
        """
        if self.flat_field is None:
            return img

        img_f = img.astype(np.float32) / 255.0
        corrected = (img_f - self.dark_field) / (self.flat_field + 1e-6)
        
        # Re-scale back to [0, 255] and clip
        return np.clip(corrected * 255.0, 0, 255).astype(np.uint8)

    def process_batch(self, images: List[np.ndarray]) -> List[np.ndarray]:
        """Corrects a batch of images after estimating profiles from them."""
        self.estimate_profiles(images)
        return [self.apply_correction(img) for img in images]

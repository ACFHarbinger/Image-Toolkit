import torch
import numpy as np
import cv2
import kornia.feature as KF
from typing import Tuple, Optional

class LoFTRWrapper:
    """
    LoFTR (Local Feature Transformer) for robust feature matching.
    Excellent for repetitive or texture-less regions where SIFT fails.
    """

    def __init__(self, device: str = None):
        self.device = device if device else ("cuda" if torch.cuda.is_available() else "cpu")
        self.matcher = None

    def load_model(self):
        if self.matcher is None:
            # Load pre-trained LoFTR on Outdoor or Indoor weights
            # For general anime/scans, "outdoor" often generalizes well due to larger context
            self.matcher = KF.LoFTR(pretrained="outdoor").to(self.device)
            self.matcher.eval()

    def match(self, img1: np.ndarray, img2: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Matches features between two images.
        Returns: (pts1, pts2, confidence)
        """
        self.load_model()

        # 1. Convert to grayscale tensors
        g1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
        g2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)

        # LoFTR expects images to be divisible by 8 (or 16 depending on version)
        # We'll resize to a multiple of 16 for safety
        h1, w1 = g1.shape
        h2, w2 = g2.shape
        
        # Target size (max 800 for speed/memory)
        max_dim = 800
        scale1 = min(max_dim / h1, max_dim / w1, 1.0)
        scale2 = min(max_dim / h2, max_dim / w2, 1.0)
        
        nh1, nw1 = int(round(h1 * scale1 / 16) * 16), int(round(w1 * scale1 / 16) * 16)
        nh2, nw2 = int(round(h2 * scale2 / 16) * 16), int(round(w2 * scale2 / 16) * 16)

        t1 = torch.from_numpy(cv2.resize(g1, (nw1, nh1))).float()[None, None].to(self.device) / 255.0
        t2 = torch.from_numpy(cv2.resize(g2, (nw2, nh2))).float()[None, None].to(self.device) / 255.0

        # 2. Inference
        with torch.no_grad():
            input_dict = {"image0": t1, "image1": t2}
            correspondences = self.matcher(input_dict)

        # 3. Extract points and scale back
        mkpts0 = correspondences["keypoints0"].cpu().numpy()
        mkpts1 = correspondences["keypoints1"].cpu().numpy()
        mconf = correspondences["confidence"].cpu().numpy()

        # Rescale points to original resolution
        mkpts0[:, 0] = mkpts0[:, 0] * (w1 / nw1)
        mkpts0[:, 1] = mkpts0[:, 1] * (h1 / nh1)
        mkpts1[:, 0] = mkpts1[:, 0] * (w2 / nw2)
        mkpts1[:, 1] = mkpts1[:, 1] * (h2 / nh2)

        return mkpts0, mkpts1, mconf

    def get_transform(self, img1: np.ndarray, img2: np.ndarray) -> Optional[np.ndarray]:
        """
        Estimates the Homography (3x3) between two images.
        """
        pts1, pts2, conf = self.match(img1, img2)
        
        if len(pts1) < 4:
            return None

        # Filter by confidence
        mask = conf > 0.5
        if np.sum(mask) < 4:
            return None
            
        pts1, pts2 = pts1[mask], pts2[mask]

        H, status = cv2.findHomography(pts1, pts2, cv2.RANSAC, 5.0)
        return H if status.sum() > 4 else None

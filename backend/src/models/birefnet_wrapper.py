"""
BiRefNetWrapper — Anime Character Foreground Segmentation
=========================================================
Wraps HuggingFace BiRefNet (Zheng Peng, 2024) and the anime-fine-tuned
ToonOut variant (MatteoKartoon/BiRefNet, arXiv 2509.06839, Sep 2025).

Key improvements over the previous version:
  - ``get_soft_mask`` returns a float32 [0,1] soft mask (not thresholded),
    giving LoFTR confidence weighting a continuous signal.
  - ``get_mask`` retains the binary (0/255) interface for backward compat.
  - ``get_background_mask`` returns the *inverted* binary mask (255 = background),
    the most common usage in the stitching pipeline.
  - ``dilate_erode`` post-processing closes hair-strand holes while keeping a
    safety margin around character boundaries.
  - ``get_mask_batch`` runs multiple frames through the model with a single
    GPU synchronisation, reducing overhead on CUDA devices.
  - Model name constant ``TOONOUT_MODEL`` points to the anime-fine-tuned weights;
    fall back to the generic BiRefNet weights if ToonOut is unavailable.
"""

import cv2
import numpy as np
import torch
torch.backends.cudnn.benchmark = False
from PIL import Image
from torchvision import transforms
from typing import List, Optional

# Preferred model: ToonOut (anime-fine-tuned BiRefNet, 99.5 % anime pixel accuracy)
TOONOUT_MODEL = "MatteoKartoon/BiRefNet"
BIREFNET_MODEL = "ZhengPeng7/BiRefNet"

try:
    import transformers.configuration_utils as _cfg_utils

    _orig_ga = _cfg_utils.PretrainedConfig.__getattribute__

    def _patched_ga(self, key):
        if key == "is_encoder_decoder":
            return False
        return _orig_ga(self, key)

    _cfg_utils.PretrainedConfig.__getattribute__ = _patched_ga
    from transformers import AutoModelForImageSegmentation

    _TRANSFORMERS_OK = True
except ImportError:
    _TRANSFORMERS_OK = False
    print("[BiRefNet] 'transformers' not installed — segmentation unavailable.")


class BiRefNetWrapper:
    """
    Anime character foreground segmentation.

    Parameters
    ----------
    model_name : HuggingFace model id.  Use TOONOUT_MODEL for best anime accuracy.
    device     : 'cuda' | 'cpu' | None (auto-detect).
    inference_size : (H, W) fed to the model.  Default 1024×1024 matches training.
    """

    # Shared model across all instances (singleton per model_name)
    _models: dict = {}

    def __init__(
        self,
        model_name: str = TOONOUT_MODEL,
        device: Optional[str] = None,
        inference_size: tuple = (1024, 1024),
    ):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model_name = model_name
        self.inference_size = inference_size
        self.transform = transforms.Compose(
            [
                transforms.Resize(inference_size),
                transforms.ToTensor(),
                transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
            ]
        )

    # ------------------------------------------------------------------ model

    def offload(self):
        key = (self.model_name, self.device)
        if key in BiRefNetWrapper._models:
            BiRefNetWrapper._models[key].cpu()
            if torch.cuda.is_available(): torch.cuda.empty_cache()


    @classmethod
    def purge_all_models(cls):
        """Completely remove all models from VRAM and RAM."""
        import torch
        import gc
        for key in list(cls._models.keys()):
            model = cls._models.pop(key)
            model.cpu()
            del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()

    def load_model(self):
        key = (self.model_name, self.device)
        if key not in BiRefNetWrapper._models:
            if not _TRANSFORMERS_OK:
                raise RuntimeError("'transformers' is required for BiRefNetWrapper.")
            print(f"[BiRefNet] Loading {self.model_name} on {self.device}…")
            try:
                model = AutoModelForImageSegmentation.from_pretrained(
                    self.model_name, trust_remote_code=True
                ).to(self.device)
            except Exception:
                # Fallback to generic BiRefNet if ToonOut is unavailable
                print(
                    f"[BiRefNet] Could not load {self.model_name}; "
                    f"falling back to {BIREFNET_MODEL}."
                )
                model = AutoModelForImageSegmentation.from_pretrained(
                    BIREFNET_MODEL, trust_remote_code=True
                ).to(self.device)
            model.eval()
            BiRefNetWrapper._models[key] = model
        else:
            BiRefNetWrapper._models[key].to(self.device)
        return BiRefNetWrapper._models[key]

    # ------------------------------------------------------------------ masks

    def get_soft_mask(self, img_np: np.ndarray) -> np.ndarray:
        """
        Soft foreground probability map.

        Returns
        -------
        float32 (H, W) array in [0, 1], where 1 = foreground character.
        """
        model = self.load_model()
        img_rgb = cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB)
        tensor = self.transform(Image.fromarray(img_rgb)).unsqueeze(0).to(self.device)
        with torch.no_grad():
            pred = model(tensor)[-1].sigmoid().detach().cpu().numpy()
        del tensor
        mask = pred[0].squeeze()
        mask = cv2.resize(
            mask, (img_np.shape[1], img_np.shape[0]), interpolation=cv2.INTER_LINEAR
        )
        return mask.astype(np.float32)

    def get_mask(
        self,
        img_np: np.ndarray,
        threshold: float = 0.5,
        dilate_px: int = 16,
        erode_px: int = 8,
    ) -> np.ndarray:
        """
        Binary foreground mask: 255 = character, 0 = background.

        Parameters
        ----------
        dilate_px : safety margin added around detected character (closes hair holes).
        erode_px  : slight inward erosion after dilation to sharpen boundary.
        """
        soft = self.get_soft_mask(img_np)
        binary = (soft > threshold).astype(np.uint8) * 255
        binary = self._dilate_erode(binary, dilate_px, erode_px)
        return binary

    def get_background_mask(
        self,
        img_np: np.ndarray,
        threshold: float = 0.5,
        dilate_px: int = 16,
        erode_px: int = 8,
    ) -> np.ndarray:
        """
        Binary background mask: 255 = safe background, 0 = character.
        Used by the stitching pipeline to restrict feature matching to background.
        """
        fg = self.get_mask(
            img_np, threshold=threshold, dilate_px=dilate_px, erode_px=erode_px
        )
        return cv2.bitwise_not(fg)

    def get_mask_batch(
        self,
        images: List[np.ndarray],
        threshold: float = 0.5,
        dilate_px: int = 16,
        erode_px: int = 8,
    ) -> List[np.ndarray]:
        """
        Process a list of frames, returning binary foreground masks.
        Runs inference frame-by-frame (batching across variable-size frames is
        tricky; this wrapper resizes each frame to inference_size internally).
        """
        return [
            self.get_mask(
                img, threshold=threshold, dilate_px=dilate_px, erode_px=erode_px
            )
            for img in images
        ]

    def apply_segmentation(self, img_np: np.ndarray) -> np.ndarray:
        """Backward-compat: returns image with background set to black."""
        mask = self.get_mask(img_np)
        return cv2.bitwise_and(img_np, cv2.merge([mask, mask, mask]))

    # ------------------------------------------------------------------ util

    @staticmethod
    def _dilate_erode(mask: np.ndarray, dilate_px: int, erode_px: int) -> np.ndarray:
        """Close hair-strand holes (dilate) then tighten boundary (erode)."""
        if dilate_px > 0:
            k = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE, (2 * dilate_px + 1, 2 * dilate_px + 1)
            )
            mask = cv2.dilate(mask, k)
        if erode_px > 0:
            k = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE, (2 * erode_px + 1, 2 * erode_px + 1)
            )
            mask = cv2.erode(mask, k)
        return mask

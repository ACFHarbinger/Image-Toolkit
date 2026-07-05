"""
BiRefNetWrapper — Anime Character Foreground Segmentation
=========================================================
Wraps local vendor/BiRefNet (Zheng Peng, 2024) and the anime-fine-tuned
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

import gc
import logging
import os
import sys
from typing import List, Optional

import cv2
import numpy as np
import torch
from PIL import Image

from backend.src.errors import ModelLoadError
from backend.src.models.core.base import ModelWrapper, lazy_load

logger = logging.getLogger(__name__)

torch.backends.cudnn.benchmark = False

# Preferred model: ToonOut (anime-fine-tuned BiRefNet, 99.5 % anime pixel accuracy)
TOONOUT_MODEL = "ZhengPeng7/BiRefNet"
BIREFNET_MODEL = "MatteoKartoon/BiRefNet"

_BIREFNET_OK = False
_BIREFNET_ERR = ""

_VENDOR_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..", "vendor", "BiRefNet"
)

try:
    if os.path.isdir(_VENDOR_PATH) and _VENDOR_PATH not in sys.path:
        sys.path.insert(0, _VENDOR_PATH)
    from birefnet.models.birefnet import BiRefNet
    from huggingface_hub import hf_hub_download
    _BIREFNET_OK = True
except Exception as _e:
    _BIREFNET_ERR = str(_e)
    logger.info(f"[BiRefNet] Failed to import local BiRefNet: {_e}")


class BiRefNetWrapper(ModelWrapper):
    """
    Anime character foreground segmentation using local vendor/BiRefNet.

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
        self.model_name = model_name
        self.inference_size = inference_size
        super().__init__(device)
        # SimpleImagePreprocessor: resize + normalize per BiRefNet training
        self._h, self._w = inference_size

    @classmethod
    def is_available(cls) -> bool:
        return _BIREFNET_OK

    @property
    def loaded(self) -> bool:
        return (self.model_name, self.device) in BiRefNetWrapper._models

    # ------------------------------------------------------------------ model

    def unload(self) -> None:
        """Remove this instance's model from VRAM/RAM, then flush CUDA cache."""
        key = (self.model_name, self.device)
        if key in BiRefNetWrapper._models:
            model = BiRefNetWrapper._models.pop(key)
            model.cpu()
            del model
        super().unload()

    def offload(self):
        key = (self.model_name, self.device)
        if key in BiRefNetWrapper._models:
            BiRefNetWrapper._models[key].cpu()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    @classmethod
    def purge_all_models(cls):
        """Completely remove all models from VRAM and RAM."""

        for key in list(cls._models.keys()):
            model = cls._models.pop(key)
            model.cpu()
            del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()

    def load(self) -> None:
        """Load the BiRefNet segmentation model onto self.device."""
        self._ensure_loaded()

    def _ensure_loaded(self):
        """Load if needed and return the active model instance."""
        key = (self.model_name, self.device)
        if key not in BiRefNetWrapper._models:
            if not _BIREFNET_OK:
                raise ModelLoadError(
                    f"Failed to load local BiRefNet module. Error: {_BIREFNET_ERR}"
                )
            logger.info(f"[BiRefNet] Loading {self.model_name} on {self.device}…")
            try:
                # Create local BiRefNet model instance
                model = BiRefNet(bb_pretrained=False)  # Don't load backbone pretrained
                model.eval()

                # Download weights from HuggingFace Hub
                try:
                    ckpt_path = hf_hub_download(
                        repo_id=self.model_name,
                        filename="pytorch_model.bin",
                        cache_dir=os.path.expanduser("~/.cache/huggingface/hub"),
                    )
                    logger.info(f"[BiRefNet] Loading weights from {ckpt_path}…")
                    state_dict = torch.load(ckpt_path, map_location="cpu")
                    model.load_state_dict(state_dict, strict=True)
                except Exception as hf_err:
                    # Fallback to generic BiRefNet if ToonOut is unavailable
                    logger.debug(
                        f"[BiRefNet] Could not load {self.model_name} weights: {hf_err}; "
                        f"falling back to {BIREFNET_MODEL}."
                    )
                    try:
                        ckpt_path = hf_hub_download(
                            repo_id=BIREFNET_MODEL,
                            filename="pytorch_model.bin",
                            cache_dir=os.path.expanduser("~/.cache/huggingface/hub"),
                        )
                        state_dict = torch.load(ckpt_path, map_location="cpu")
                        model.load_state_dict(state_dict, strict=True)
                    except Exception as fallback_err:
                        raise ModelLoadError(
                            f"Could not load BiRefNet weights from HF Hub: {fallback_err}"
                        ) from fallback_err

                model = model.to(self.device)
                BiRefNetWrapper._models[key] = model
            except Exception as e:
                raise ModelLoadError(f"Failed to load BiRefNet: {e}") from e
        else:
            BiRefNetWrapper._models[key].to(self.device)
        return BiRefNetWrapper._models[key]

    # backward-compat alias used by external callers
    load_model = _ensure_loaded

    # ------------------------------------------------------------------ masks

    def _preprocess_image(self, img_np: np.ndarray) -> torch.Tensor:
        """Preprocess image: RGB convert, resize, normalize to [0,1] tensor."""
        img_rgb = cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB)
        img_pil = Image.fromarray(img_rgb)
        img_resized = img_pil.resize((self._w, self._h), Image.BILINEAR)
        img_tensor = torch.from_numpy(np.array(img_resized)).float() / 255.0
        # Normalize: BiRefNet uses ImageNet stats
        img_tensor = img_tensor.permute(2, 0, 1)  # HWC -> CHW
        mean = torch.tensor([0.485, 0.456, 0.406], device=self.device).view(3, 1, 1)
        std = torch.tensor([0.229, 0.224, 0.225], device=self.device).view(3, 1, 1)
        img_tensor = img_tensor.to(self.device)
        img_tensor = (img_tensor - mean) / std
        return img_tensor.unsqueeze(0)

    @lazy_load
    def get_soft_mask(self, img_np: np.ndarray) -> np.ndarray:
        """
        Soft foreground probability map.

        Returns
        -------
        float32 (H, W) array in [0, 1], where 1 = foreground character.
        """
        model = self._ensure_loaded()
        tensor = self._preprocess_image(img_np)
        with torch.no_grad():
            # BiRefNet returns list of predictions; last is final output
            preds = model(tensor)
            if isinstance(preds, list):
                pred = preds[-1]  # final prediction
            else:
                pred = preds
            pred = pred.sigmoid().detach().cpu().numpy()
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

        Frames are pre-transformed to ``inference_size`` tensors and grouped into
        VRAM-sized chunks determined by ``_compute_batch_size()``.  On CPU or when
        VRAM estimation fails the method falls back to batch_size=1 (original
        behaviour).
        """
        if not images:
            return []

        model = self._ensure_loaded()

        # Pre-transform all images and record original sizes for resize-back.
        tensors: List[torch.Tensor] = []
        orig_sizes: List[tuple] = []
        mean = torch.tensor([0.485, 0.456, 0.406], device=self.device).view(3, 1, 1)
        std = torch.tensor([0.229, 0.224, 0.225], device=self.device).view(3, 1, 1)
        for img_np in images:
            img_rgb = cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB)
            img_pil = Image.fromarray(img_rgb)
            img_resized = img_pil.resize((self._w, self._h), Image.BILINEAR)
            img_tensor = torch.from_numpy(np.array(img_resized)).float() / 255.0
            img_tensor = img_tensor.permute(2, 0, 1)  # HWC -> CHW
            img_tensor = img_tensor.to(self.device)
            img_tensor = (img_tensor - mean) / std
            tensors.append(img_tensor)
            orig_sizes.append((img_np.shape[0], img_np.shape[1]))

        batch_size = self._compute_batch_size()
        soft_masks: List[np.ndarray] = []

        for start in range(0, len(tensors), batch_size):
            chunk = tensors[start : start + batch_size]
            batch = torch.stack(chunk).to(self.device)
            with torch.no_grad():
                preds = model(batch)
                if isinstance(preds, list):
                    preds = preds[-1]  # final prediction
                preds = preds.sigmoid().detach().cpu().numpy()
            del batch
            for i, pred in enumerate(preds):
                raw = pred.squeeze()  # (H_inf, W_inf)
                h, w = orig_sizes[start + i]
                raw = cv2.resize(raw, (w, h), interpolation=cv2.INTER_LINEAR)
                soft_masks.append(raw.astype(np.float32))

        results: List[np.ndarray] = []
        for soft in soft_masks:
            binary = (soft > threshold).astype(np.uint8) * 255
            binary = self._dilate_erode(binary, dilate_px, erode_px)
            results.append(binary)
        return results

    def _compute_batch_size(self) -> int:
        """Return how many frames can safely be batched given current free VRAM.

        Uses 32× the raw tensor size as a per-frame VRAM estimate (input +
        BiRefNet Swin activations + decoder + output).  Caps at 4 regardless of
        VRAM to avoid OOM from activation spikes.  Returns 1 on CPU or failure.
        """
        if self.device == "cpu" or not torch.cuda.is_available():
            return 1
        try:
            free_bytes, _ = torch.cuda.mem_get_info()
            reserve = 1 * 1024 ** 3  # 1 GB safety margin
            usable = max(0, free_bytes - reserve)
            h, w = self.inference_size
            per_frame_bytes = h * w * 3 * 4 * 32  # 32× raw tensor size
            batch_size = max(1, int(usable / per_frame_bytes))
            return min(batch_size, 4)
        except Exception:
            return 1

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

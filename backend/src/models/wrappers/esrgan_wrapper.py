"""
ESRGANWrapper — Shared Anime-Aware Tiled Super-Resolution
==========================================================
Content Gen §1.6 [Quick Win]: a shared `Real-ESRGAN anime_6B` upscaler
module, meant to be reused by both the generation tabs and the ASP
super-resolution stage. The roadmap's own text claimed
``animation/super_res.py`` already existed and just needed "unifying" —
that file does not exist anywhere in this codebase (confirmed via
repo-wide search before writing anything here); no super-resolution
module existed at all. This wrapper is the actual shared primitive the
roadmap wants; wiring it into the generation tabs' GUI and into an ASP
super-resolution pipeline stage are separate, larger follow-on integration
tasks not attempted here (this Quick Win is the reusable module itself).

Architecture: RRDBNet (Residual-in-Residual Dense Block Network), the
generator Real-ESRGAN uses. The full `basicsr`/`realesrgan` PyPI packages
are not installed in this project's `.venv` and were deliberately not
added — they carry a large, fragile dependency tree (basicsr has known
compatibility breaks against newer torchvision). Instead this module
defines a minimal, self-contained RRDBNet in plain `torch`, matching the
pattern already established for BiRefNet/ToonOut in `birefnet_wrapper.py`
(load raw weights into a hand-written architecture rather than depend on
the upstream training framework).

Verified against the real checkpoint before writing the architecture:
downloaded `RealESRGAN_x4plus_anime_6B.pth` and inspected its state dict
directly — confirms 6 RRDB blocks (hence "6B"), `num_feat=64`, weights
wrapped under a top-level `params_ema` key (Real-ESRGAN's own convention,
falls back to `params` for non-EMA checkpoints), and exact key names
matching this file's `RRDBNet`/`ResidualDenseBlock` — not guessed from
memory.
"""

import logging
import os
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from backend.src.errors import ModelLoadError
from backend.src.models.core.base import ModelWrapper, lazy_load
from backend.src.constants.models import ANIME_6B_FILENAME

logger = logging.getLogger(__name__)

# Real-ESRGAN's official anime_6B release, re-hosted verbatim (same filename,
# same checkpoint bytes) on these HF Hub mirrors -- verified reachable via the
# HF Hub API and containing the exact expected `RRDBNet` key structure before
# being hardcoded here. Two independent mirrors, same convention as
# birefnet_wrapper.py's primary/fallback pattern in case one goes stale.
ANIME_6B_MODEL = "ximso/RealESRGAN_x4plus_anime_6B"
ANIME_6B_MODEL_FALLBACK = "gemasai/RealESRGAN_x4plus_anime_6B"


class ResidualDenseBlock(nn.Module):
    """5-conv densely-connected block with a residual scale of 0.2 (RRDBNet)."""

    def __init__(self, num_feat: int = 64, num_grow_ch: int = 32):
        super().__init__()
        self.conv1 = nn.Conv2d(num_feat, num_grow_ch, 3, 1, 1)
        self.conv2 = nn.Conv2d(num_feat + num_grow_ch, num_grow_ch, 3, 1, 1)
        self.conv3 = nn.Conv2d(num_feat + 2 * num_grow_ch, num_grow_ch, 3, 1, 1)
        self.conv4 = nn.Conv2d(num_feat + 3 * num_grow_ch, num_grow_ch, 3, 1, 1)
        self.conv5 = nn.Conv2d(num_feat + 4 * num_grow_ch, num_feat, 3, 1, 1)
        self.lrelu = nn.LeakyReLU(negative_slope=0.2, inplace=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x1 = self.lrelu(self.conv1(x))
        x2 = self.lrelu(self.conv2(torch.cat((x, x1), 1)))
        x3 = self.lrelu(self.conv3(torch.cat((x, x1, x2), 1)))
        x4 = self.lrelu(self.conv4(torch.cat((x, x1, x2, x3), 1)))
        x5 = self.conv5(torch.cat((x, x1, x2, x3, x4), 1))
        return x5 * 0.2 + x


class RRDB(nn.Module):
    """Residual in Residual Dense Block: 3 `ResidualDenseBlock`s, scale 0.2."""

    def __init__(self, num_feat: int, num_grow_ch: int = 32):
        super().__init__()
        self.rdb1 = ResidualDenseBlock(num_feat, num_grow_ch)
        self.rdb2 = ResidualDenseBlock(num_feat, num_grow_ch)
        self.rdb3 = ResidualDenseBlock(num_feat, num_grow_ch)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.rdb1(x)
        out = self.rdb2(out)
        out = self.rdb3(out)
        return out * 0.2 + x


class RRDBNet(nn.Module):
    """
    Real-ESRGAN's generator network. Default `num_block=6` matches the
    anime_6B checkpoint (the standard photoreal model uses 23 blocks; this
    class works for either, given the matching weights).
    """

    def __init__(
        self,
        num_in_ch: int = 3,
        num_out_ch: int = 3,
        num_feat: int = 64,
        num_block: int = 6,
        num_grow_ch: int = 32,
    ):
        super().__init__()
        self.conv_first = nn.Conv2d(num_in_ch, num_feat, 3, 1, 1)
        self.body = nn.Sequential(
            *[RRDB(num_feat, num_grow_ch) for _ in range(num_block)]
        )
        self.conv_body = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        # Two 2x pixel-shuffle-free (nearest-upsample + conv) stages = 4x total.
        self.conv_up1 = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_up2 = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_hr = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_last = nn.Conv2d(num_feat, num_out_ch, 3, 1, 1)
        self.lrelu = nn.LeakyReLU(negative_slope=0.2, inplace=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        feat = self.conv_first(x)
        body_feat = self.conv_body(self.body(feat))
        feat = feat + body_feat
        feat = self.lrelu(
            self.conv_up1(F.interpolate(feat, scale_factor=2, mode="nearest"))
        )
        feat = self.lrelu(
            self.conv_up2(F.interpolate(feat, scale_factor=2, mode="nearest"))
        )
        out = self.conv_last(self.lrelu(self.conv_hr(feat)))
        return out


class ESRGANWrapper(ModelWrapper):
    """
    Shared anime-aware tiled super-resolution wrapper (Content Gen §1.6).

    Parameters
    ----------
    model_name : HF Hub repo id. Default is the anime_6B mirror.
    scale : output scale factor. 4 for the anime_6B checkpoint.
    tile_size : max tile edge (px) fed to the network per pass. Large
        images are processed in overlapping tiles to bound VRAM/RAM use,
        the same approach the upstream Real-ESRGAN project uses (a plain
        whole-image forward pass on a multi-thousand-pixel panorama would
        need far more VRAM than most consumer GPUs have).
    tile_pad : overlap (px, in *input* resolution) added around each tile
        so seam artifacts at tile boundaries fall inside the discarded
        overlap region rather than the kept output.
    """

    _models: dict = {}

    def __init__(
        self,
        model_name: str = ANIME_6B_MODEL,
        device: Optional[str] = None,
        scale: int = 4,
        num_block: int = 6,
        tile_size: int = 400,
        tile_pad: int = 10,
    ):
        super().__init__(device=device)
        self.model_name = model_name
        self.scale = scale
        self.num_block = num_block
        self.tile_size = tile_size
        self.tile_pad = tile_pad
        self._model: Optional[RRDBNet] = None

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def unload(self) -> None:
        self._model = None
        super().unload()

    @staticmethod
    def _load_state_dict(repo_id: str) -> dict:
        from huggingface_hub import hf_hub_download

        cache = os.path.expanduser("~/.cache/huggingface/hub")
        ckpt = hf_hub_download(
            repo_id=repo_id, filename=ANIME_6B_FILENAME, cache_dir=cache
        )
        logger.info(f"[ESRGAN] Loading weights from {ckpt}…")
        sd = torch.load(ckpt, map_location="cpu")
        # Real-ESRGAN's own convention: EMA weights (best quality) under
        # "params_ema", raw weights under "params". Prefer EMA when present.
        if isinstance(sd, dict) and ("params_ema" in sd or "params" in sd):
            sd = sd.get("params_ema", sd.get("params"))
        return sd

    def load(self) -> None:
        """Load the RRDBNet anime_6B model onto self.device."""
        key = (self.model_name, self.num_block, self.device)
        if key in ESRGANWrapper._models:
            self._model = ESRGANWrapper._models[key]
            return

        model = RRDBNet(num_block=self.num_block)
        try:
            state_dict = self._load_state_dict(self.model_name)
            model.load_state_dict(state_dict, strict=True)
        except Exception as primary_err:
            logger.debug(
                f"[ESRGAN] Could not load {self.model_name}: {primary_err}; "
                f"falling back to {ANIME_6B_MODEL_FALLBACK}."
            )
            try:
                state_dict = self._load_state_dict(ANIME_6B_MODEL_FALLBACK)
                model.load_state_dict(state_dict, strict=True)
            except Exception as fallback_err:
                raise ModelLoadError(
                    f"Could not load Real-ESRGAN anime_6B weights from HF Hub: "
                    f"{fallback_err}"
                ) from fallback_err

        model.eval()
        model = model.to(self.device)
        ESRGANWrapper._models[key] = model
        self._model = model

    @lazy_load
    def upscale(self, image: np.ndarray) -> np.ndarray:
        """
        Upscale a BGR uint8 image by `self.scale`x, tiled for memory safety.

        Parameters
        ----------
        image : (H, W, 3) uint8, BGR (OpenCV convention, matching this
            project's other image-processing entry points).

        Returns
        -------
        (H*scale, W*scale, 3) uint8 BGR.
        """
        h, w = image.shape[:2]
        rgb = image[:, :, ::-1].astype(np.float32) / 255.0
        tensor = torch.from_numpy(rgb.transpose(2, 0, 1)).unsqueeze(0).to(self.device)

        if max(h, w) <= self.tile_size:
            with torch.no_grad():
                out = self._model(tensor)
            return self._tensor_to_bgr(out)

        return self._tile_process(tensor, h, w)

    def _tile_process(self, tensor: torch.Tensor, h: int, w: int) -> np.ndarray:
        scale = self.scale
        tile = self.tile_size
        pad = self.tile_pad
        out_h, out_w = h * scale, w * scale
        output = torch.zeros((1, 3, out_h, out_w), dtype=tensor.dtype)

        tiles_x = (w + tile - 1) // tile
        tiles_y = (h + tile - 1) // tile
        with torch.no_grad():
            for ty in range(tiles_y):
                for tx in range(tiles_x):
                    x0, y0 = tx * tile, ty * tile
                    x1, y1 = min(x0 + tile, w), min(y0 + tile, h)

                    px0, py0 = max(0, x0 - pad), max(0, y0 - pad)
                    px1, py1 = min(w, x1 + pad), min(h, y1 + pad)

                    tile_in = tensor[:, :, py0:py1, px0:px1]
                    tile_out = self._model(tile_in).cpu()

                    # Map the kept (non-overlap) region into output space.
                    keep_x0 = (x0 - px0) * scale
                    keep_y0 = (y0 - py0) * scale
                    keep_x1 = keep_x0 + (x1 - x0) * scale
                    keep_y1 = keep_y0 + (y1 - y0) * scale

                    output[:, :, y0 * scale : y1 * scale, x0 * scale : x1 * scale] = (
                        tile_out[:, :, keep_y0:keep_y1, keep_x0:keep_x1]
                    )

        return self._tensor_to_bgr(output)

    @staticmethod
    def _tensor_to_bgr(tensor: torch.Tensor) -> np.ndarray:
        arr = tensor.squeeze(0).clamp(0, 1).cpu().numpy().transpose(1, 2, 0)
        rgb = (arr * 255.0).round().astype(np.uint8)
        return rgb[:, :, ::-1].copy()

    def upscale_path(self, input_path: str, output_path: str) -> None:
        """Convenience file-in/file-out entry point."""
        import cv2

        img = cv2.imread(input_path)
        if img is None:
            raise FileNotFoundError(f"Could not read image: {input_path}")
        result = self.upscale(img)
        cv2.imwrite(output_path, result)

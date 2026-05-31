"""
backend/src/anim/super_res.py
==============================
Real-ESRGAN anime super-resolution post-processing (P2.2).

``RealESRGAN_x4plus_anime_6B`` is trained on anime-specific degradation:
JPEG compression artifacts at colour boundaries, cel-shade gradient loss,
and line-art thinning.  It preserves clean outlines and flat-shading
gradients where the photo SR model over-smooths.

Applied as an optional final stage after Stage 13 crop.  Tile-and-stitch
is used internally so large panoramas (5000×4000+) fit in VRAM.
"""

from __future__ import annotations

import sys
import types

import numpy as np

_UPSCALE_OK = False
_UPSCALE_ERR = ""


def _ensure_basicsr() -> bool:
    """
    Apply a one-time compatibility shim for basicsr on torchvision >= 0.16.

    torchvision removed ``torchvision.transforms.functional_tensor`` in v0.16;
    basicsr 1.4.2 still imports ``rgb_to_grayscale`` from there.  We inject a
    stub module before the first basicsr import so all subsequent imports work.
    """
    if "torchvision.transforms.functional_tensor" not in sys.modules:
        try:
            from torchvision.transforms import functional as _tvF

            _stub = types.ModuleType("torchvision.transforms.functional_tensor")
            _stub.rgb_to_grayscale = _tvF.rgb_to_grayscale  # type: ignore[attr-defined]
            sys.modules["torchvision.transforms.functional_tensor"] = _stub
        except Exception:
            pass
    return True


try:
    _ensure_basicsr()
    from basicsr.archs.rrdbnet_arch import RRDBNet  # type: ignore
    from realesrgan import RealESRGANer  # type: ignore

    _UPSCALE_OK = True
except Exception as _e:
    _UPSCALE_ERR = str(_e)


_MODEL_CACHE: dict = {}


def _get_upsampler(
    scale: int = 4, tile: int = 512, device: str = "cpu"
) -> "RealESRGANer":
    """Return a cached RealESRGANer for the anime_6B model."""
    key = (scale, tile, device)
    if key in _MODEL_CACHE:
        return _MODEL_CACHE[key]

    from huggingface_hub import hf_hub_download

    # anime_6B: 6 RRDB blocks — lighter and sharper on anime than the 23-block model
    model_arch = RRDBNet(
        num_in_ch=3,
        num_out_ch=3,
        num_feat=64,
        num_block=6,
        num_grow_ch=32,
        scale=4,
    )
    # Download weights from HuggingFace mirror
    ckpt_path = hf_hub_download(
        repo_id="ai-forever/Real-ESRGAN",
        filename="RealESRGAN_x4plus_anime_6B.pth",
    )
    upsampler = RealESRGANer(
        scale=scale,
        model_path=ckpt_path,
        model=model_arch,
        tile=tile,
        tile_pad=10,
        pre_pad=0,
        half=(device == "cuda"),
        device=device,
    )
    _MODEL_CACHE[key] = upsampler
    return upsampler


def upscale_anime(
    img: np.ndarray,
    scale: int = 2,
    tile: int = 512,
    device: str = "cpu",
) -> np.ndarray:
    """
    Upscale a BGR uint8 image using Real-ESRGAN anime_6B.

    Parameters
    ----------
    img   : (H, W, 3) BGR uint8 image.
    scale : 2 or 4 (4× is the native model scale; 2× downsamples after).
    tile  : tile size in pixels (512 is safe for 8 GB VRAM).
    device: 'cuda' or 'cpu'.

    Returns
    -------
    (H*scale, W*scale, 3) BGR uint8 upscaled image.
    """
    if not _UPSCALE_OK:
        raise ImportError(
            f"Real-ESRGAN not available: {_UPSCALE_ERR}\n"
            "Install with: pip install realesrgan basicsr"
        )
    upsampler = _get_upsampler(scale=4, tile=tile, device=device)
    # RealESRGANer.enhance expects BGR uint8; outscale controls final scale
    output, _ = upsampler.enhance(img, outscale=scale)
    return output


__all__ = ["upscale_anime", "_UPSCALE_OK"]

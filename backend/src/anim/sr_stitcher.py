"""
backend/src/anim/sr_stitcher.py
================================
SRStitcher — unified diffusion inpainting for seam fusion (P3.4).

SRStitcher (NeurIPS 2024, arXiv:2404.14951) collapses the traditional
registration → fusion → rectangling pipeline into a single diffusion
inpainting pass.  Weighted masks guide the reverse diffusion over seam and
border regions, producing seamless, style-consistent fills without any
stitching-specific training.

For anime content we use an anime-compatible inpainting model
(``Linaqruf/anything-v3-1`` or ``stablediffusionapi/anything-v5``) so the
generated content matches the cel-shaded style of the source frames.

Integration points
------------------
1. Seam smoothing — after Stage 11 (foreground composite), run inpainting
   over the seam band to eliminate hard Laplacian transitions.
2. Border fill — after Stage 13 (crop), run inpainting over black-corner
   regions for diagonal-pan panoramas (replaces P1.8 diffusion inpainting).

Both passes are optional and controlled by flags on AnimeStitchPipeline.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import cv2
import numpy as np
import torch

import importlib.util as _importlib_util

# Fast availability probe — no import, just checks for the package on sys.path.
# §3.14: actual `from diffusers import ...` is deferred to _ensure_diffusers().
_DIFFUSERS_OK: bool = _importlib_util.find_spec("diffusers") is not None
_DIFFUSERS_ERR = "" if _DIFFUSERS_OK else "diffusers not installed"
_DIFFUSERS_LOADED = False  # True once the lazy import has completed
# Populated lazily on first call to _ensure_diffusers()
StableDiffusionInpaintPipeline = None
AutoPipelineForInpainting = None
_PILImage = None

# Fallback model IDs to try in order (public, no auth required)
_ANIME_INPAINT_MODELS = [
    "Uminosachi/realisticVisionV51_v51VAE-inpainting",
    "runwayml/stable-diffusion-inpainting",
]

_PIPELINE_CACHE: dict = {}


def _ensure_diffusers() -> bool:
    """Lazy-load diffusers + PIL once; populate module-level sentinels.  §3.14.

    Returns True if diffusers is available and successfully imported.
    Calling this multiple times is safe (no-op after first successful load).
    """
    global _DIFFUSERS_OK, _DIFFUSERS_LOADED, _DIFFUSERS_ERR  # noqa: PLW0603
    global StableDiffusionInpaintPipeline, AutoPipelineForInpainting, _PILImage  # noqa: PLW0603
    if not _DIFFUSERS_OK:
        return False
    if _DIFFUSERS_LOADED:
        return True
    try:
        from diffusers import (  # type: ignore
            StableDiffusionInpaintPipeline as _SD,
            AutoPipelineForInpainting as _AP,
        )
        from PIL import Image as _PI
        StableDiffusionInpaintPipeline = _SD
        AutoPipelineForInpainting = _AP
        _PILImage = _PI
        _DIFFUSERS_LOADED = True
    except Exception as _e:
        _DIFFUSERS_OK = False
        _DIFFUSERS_ERR = str(_e)
    return _DIFFUSERS_LOADED


def _get_inpaint_pipeline(device: str = "cpu", model_id: Optional[str] = None):
    """Load and cache an inpainting pipeline."""
    if not _ensure_diffusers():
        raise ImportError(f"diffusers not available: {_DIFFUSERS_ERR}")

    key = (model_id, device)
    if key in _PIPELINE_CACHE:
        return _PIPELINE_CACHE[key]

    models_to_try = [model_id] + _ANIME_INPAINT_MODELS if model_id else _ANIME_INPAINT_MODELS
    for mid in models_to_try:
        try:
            print(f"[SRStitcher] Loading inpainting model: {mid} on {device}…")
            dtype = torch.float16 if device == "cuda" else torch.float32
            pipe = AutoPipelineForInpainting.from_pretrained(
                mid,
                torch_dtype=dtype,
                safety_checker=None,
            ).to(device)
            pipe.set_progress_bar_config(disable=True)
            _PIPELINE_CACHE[key] = pipe
            print(f"[SRStitcher] Model loaded: {mid}")
            return pipe
        except Exception as _e:
            print(f"[SRStitcher] Could not load {mid}: {_e}")

    raise RuntimeError("No inpainting model could be loaded.")


def _build_seam_mask(
    canvas: np.ndarray,
    seam_y_positions: List[int],
    seam_band_px: int = 80,
) -> np.ndarray:
    """
    Build a binary mask covering the horizontal seam bands.

    Parameters
    ----------
    canvas          : (H, W, 3) uint8.
    seam_y_positions: list of canvas y-coordinates of seam centres.
    seam_band_px    : total band width around each seam centre.

    Returns
    -------
    mask : (H, W) uint8 — 255 = inpaint this region.
    """
    H, W = canvas.shape[:2]
    mask = np.zeros((H, W), dtype=np.uint8)
    half = seam_band_px // 2
    for sy in seam_y_positions:
        y0 = max(0, sy - half)
        y1 = min(H, sy + half)
        mask[y0:y1, :] = 255
    return mask


def _build_border_mask(canvas: np.ndarray) -> np.ndarray:
    """
    Build a mask covering black-pixel regions (canvas coverage gaps).

    Returns (H, W) uint8 — 255 = inpaint.
    """
    black = canvas.max(axis=2) == 0
    mask = (black.astype(np.uint8)) * 255
    # Dilate slightly so inpainting has context beyond the hard edge
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    mask = cv2.dilate(mask, kernel)
    return mask


def _inpaint_region(
    canvas: np.ndarray,
    mask: np.ndarray,
    device: str = "cpu",
    prompt: str = "anime background, seamless, high quality, detailed",
    negative_prompt: str = "blurry, low quality, artifacts, seam, border",
    num_steps: int = 30,
    guidance: float = 7.5,
    strength: float = 0.85,
    tile_size: int = 512,
    tile_overlap: int = 64,
    model_id: Optional[str] = None,
) -> np.ndarray:
    """
    Inpaint masked regions of canvas using a diffusion model.

    Uses tile-and-stitch so large panoramas (5000 × 4000+) fit in VRAM.
    Only tiles that overlap the mask are processed; unmasked tiles are
    returned unchanged.
    """
    if not _ensure_diffusers():
        return canvas

    H, W = canvas.shape[:2]
    if mask.sum() == 0:
        return canvas

    try:
        pipe = _get_inpaint_pipeline(device=device, model_id=model_id)
    except Exception as _e:
        print(f"[SRStitcher] Pipeline unavailable ({_e}); skipping inpainting.")
        return canvas

    result = canvas.copy()
    step = tile_size - tile_overlap

    for y0 in range(0, H, step):
        y1 = min(y0 + tile_size, H)
        for x0 in range(0, W, step):
            x1 = min(x0 + tile_size, W)

            tile_mask = mask[y0:y1, x0:x1]
            if tile_mask.sum() < 100:
                continue  # nothing to inpaint in this tile

            tile_img = canvas[y0:y1, x0:x1]
            th, tw = tile_img.shape[:2]

            # Pad to tile_size × tile_size (SD requires fixed size)
            pad_h = tile_size - th
            pad_w = tile_size - tw
            tile_img_pad = cv2.copyMakeBorder(tile_img, 0, pad_h, 0, pad_w, cv2.BORDER_REFLECT)
            tile_mask_pad = cv2.copyMakeBorder(tile_mask, 0, pad_h, 0, pad_w, cv2.BORDER_CONSTANT, value=0)

            pil_img = _PILImage.fromarray(cv2.cvtColor(tile_img_pad, cv2.COLOR_BGR2RGB))
            pil_mask = _PILImage.fromarray(tile_mask_pad)

            try:
                with torch.no_grad():
                    out_pil = pipe(
                        prompt=prompt,
                        negative_prompt=negative_prompt,
                        image=pil_img,
                        mask_image=pil_mask,
                        num_inference_steps=num_steps,
                        guidance_scale=guidance,
                        strength=strength,
                        height=tile_size,
                        width=tile_size,
                    ).images[0]
                out_bgr = cv2.cvtColor(np.array(out_pil), cv2.COLOR_RGB2BGR)[:th, :tw]
                # Composite: only update inpainted pixels (mask > 0)
                m = tile_mask > 0
                result_tile = result[y0:y1, x0:x1]
                result_tile[m] = out_bgr[m]
                result[y0:y1, x0:x1] = result_tile
            except Exception as _e:
                print(f"[SRStitcher] Tile ({y0},{x0}) inpaint failed: {_e}")

    return result


def seam_diffusion_fusion(
    canvas: np.ndarray,
    seam_y_positions: List[int],
    device: str = "cpu",
    seam_band_px: int = 80,
    num_steps: int = 25,
    model_id: Optional[str] = None,
) -> np.ndarray:
    """
    Smooth seam bands using diffusion inpainting (P3.4 primary path).

    Parameters
    ----------
    canvas          : (H, W, 3) uint8 panorama.
    seam_y_positions: list of y-coordinates for seam centre lines.
    device          : 'cuda' or 'cpu'.
    seam_band_px    : inpaint band width (px).
    num_steps       : denoising steps.

    Returns
    -------
    Smoothed canvas with seam artefacts replaced by diffusion-generated content.
    """
    mask = _build_seam_mask(canvas, seam_y_positions, seam_band_px)
    print(
        f"[SRStitcher] Seam diffusion fusion: {len(seam_y_positions)} seams, "
        f"band={seam_band_px}px, mask coverage={mask.mean():.1%}."
    )
    return _inpaint_region(canvas, mask, device=device, num_steps=num_steps, model_id=model_id)


def border_diffusion_fill(
    canvas: np.ndarray,
    device: str = "cpu",
    num_steps: int = 25,
    model_id: Optional[str] = None,
) -> np.ndarray:
    """
    Fill black-corner border regions via diffusion inpainting (P3.4 border path).

    Used as an alternative to P1.8 (mfsr.inpaint_gaps) for diagonal-pan
    panoramas where the simple inpainting module produces visible texture
    discontinuities.  The diffusion model generates style-consistent content.
    """
    mask = _build_border_mask(canvas)
    coverage = float(mask.sum()) / (canvas.shape[0] * canvas.shape[1] * 255.0)
    if coverage < 0.005:
        return canvas  # negligible border — skip
    print(
        f"[SRStitcher] Border diffusion fill: coverage gap={coverage:.1%}."
    )
    return _inpaint_region(canvas, mask, device=device, num_steps=num_steps, model_id=model_id)


__all__ = [
    "seam_diffusion_fusion",
    "border_diffusion_fill",
    "_build_seam_mask",
    "_build_border_mask",
    "_DIFFUSERS_OK",
]

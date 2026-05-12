"""
Diffusion-based inpainting for canvas gap regions.

Priority chain:
  1. Stable Diffusion inpainting pipeline (HuggingFace, GPU)
  2. LaMa (Large Mask inpainting, HuggingFace)
  3. OpenCV Navier-Stokes (cv2.INPAINT_NS) — lightweight CPU fallback
  4. OpenCV Telea (cv2.INPAINT_TELEA) — last resort

Selects automatically based on available GPU memory and installed packages.
"""

from __future__ import annotations

import cv2
import numpy as np

try:
    import torch
    _TORCH_OK = True
except ImportError:
    _TORCH_OK = False


def _has_gpu_memory(min_gb: float = 4.0) -> bool:
    """True if a CUDA GPU with at least ``min_gb`` free memory is available."""
    if not _TORCH_OK or not torch.cuda.is_available():
        return False
    try:
        free, total = torch.cuda.mem_get_info()
        return free >= int(min_gb * (1024**3))
    except Exception:
        # mem_get_info missing on some torch builds
        return True


def _try_stable_diffusion(
    canvas: np.ndarray,
    mask: np.ndarray,
    prompt: str,
    seed: int,
) -> np.ndarray:
    """Run a HuggingFace Stable Diffusion inpaint pipeline."""
    if not _has_gpu_memory(min_gb=4.0):
        raise RuntimeError("Stable Diffusion inpaint requires >=4 GB free VRAM")
    try:
        from diffusers import StableDiffusionInpaintPipeline  # type: ignore
        from PIL import Image as _PIL
    except ImportError as e:
        raise RuntimeError(f"diffusers/PIL not installed: {e}")

    dtype = torch.float16 if _TORCH_OK and torch.cuda.is_available() else torch.float32
    pipe = StableDiffusionInpaintPipeline.from_pretrained(
        "runwayml/stable-diffusion-inpainting",
        torch_dtype=dtype,
    )
    pipe = pipe.to("cuda" if _TORCH_OK and torch.cuda.is_available() else "cpu")

    rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
    pil_img = _PIL.fromarray(rgb)
    pil_mask = _PIL.fromarray(mask)

    # SD inpaint expects 512x512 multiples; downscale + upscale around the call.
    H, W = canvas.shape[:2]
    target = 512
    pil_img_s = pil_img.resize((target, target), _PIL.LANCZOS)
    pil_mask_s = pil_mask.resize((target, target), _PIL.NEAREST)

    generator = None
    if _TORCH_OK:
        generator = torch.Generator(
            device="cuda" if torch.cuda.is_available() else "cpu"
        ).manual_seed(int(seed))

    result = pipe(
        prompt=prompt,
        image=pil_img_s,
        mask_image=pil_mask_s,
        generator=generator,
        num_inference_steps=30,
    ).images[0]
    result = result.resize((W, H), _PIL.LANCZOS)
    out_rgb = np.asarray(result)
    out_bgr = cv2.cvtColor(out_rgb, cv2.COLOR_RGB2BGR)
    # Only paste the inpainted region back; leave the rest of the canvas alone.
    m = (mask > 0)
    canvas_out = canvas.copy()
    canvas_out[m] = out_bgr[m]
    return canvas_out


def _try_lama(canvas: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Run the LaMa large-mask inpainter (HuggingFace simple-lama-inpainting)."""
    try:
        from simple_lama_inpainting import SimpleLama  # type: ignore
        from PIL import Image as _PIL
    except ImportError as e:
        raise RuntimeError(f"simple_lama_inpainting not installed: {e}")

    rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
    pil_img = _PIL.fromarray(rgb)
    pil_mask = _PIL.fromarray(mask).convert("L")

    lama = SimpleLama()
    out = lama(pil_img, pil_mask)
    out_rgb = np.asarray(out)
    out_bgr = cv2.cvtColor(out_rgb, cv2.COLOR_RGB2BGR)
    if out_bgr.shape[:2] != canvas.shape[:2]:
        out_bgr = cv2.resize(
            out_bgr,
            (canvas.shape[1], canvas.shape[0]),
            interpolation=cv2.INTER_LANCZOS4,
        )
    m = (mask > 0)
    canvas_out = canvas.copy()
    canvas_out[m] = out_bgr[m]
    return canvas_out


def _cv2_inpaint(canvas: np.ndarray, mask: np.ndarray, flag: int) -> np.ndarray:
    """OpenCV inpainting (Navier-Stokes or Telea)."""
    return cv2.inpaint(canvas, mask, inpaintRadius=8, flags=flag)


def inpaint_gaps(
    canvas: np.ndarray,
    mask: np.ndarray,  # 255 = gap to fill, 0 = valid content
    method: str = "auto",
    prompt: str = "anime background, detailed, high quality",
    seed: int = 42,
) -> np.ndarray:
    """Fill canvas gaps using the best available inpainting method."""
    if canvas is None or mask is None or mask.max() == 0:
        return canvas

    if mask.dtype != np.uint8:
        mask = mask.astype(np.uint8)
    if mask.ndim == 3:
        mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)

    chain = []
    if method == "auto":
        chain = ["stable_diffusion", "lama", "ns", "telea"]
    else:
        chain = [method]

    last_err = None
    for m in chain:
        try:
            if m in ("sd", "stable_diffusion", "diffusion"):
                return _try_stable_diffusion(canvas, mask, prompt, seed)
            if m == "lama":
                return _try_lama(canvas, mask)
            if m in ("ns", "navier_stokes"):
                return _cv2_inpaint(canvas, mask, cv2.INPAINT_NS)
            if m == "telea":
                return _cv2_inpaint(canvas, mask, cv2.INPAINT_TELEA)
        except Exception as e:
            last_err = e
            continue

    print(f"[MFSR] inpaint_gaps: all methods failed (last: {last_err}); returning input.")
    return canvas


__all__ = ["inpaint_gaps"]

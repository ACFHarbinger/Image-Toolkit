"""
Prior knowledge injection for MFSR using pre-trained anime upscaling models.

Supported backends (in priority order):
  1. Real-ESRGAN (HuggingFace model: 'ai-forever/Real-ESRGAN')
  2. waifu2x via subprocess (if installed)
  3. EDSR via torchvision (fallback)
  4. Bicubic upscale (last resort)

The prior is injected into the DCT restoration loop to prevent
convergence to noisy local minima.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile

import cv2
import numpy as np

try:
    import torch
    _TORCH_OK = True
except ImportError:
    _TORCH_OK = False


def _try_real_esrgan(img: np.ndarray, scale: int, noise_level: int) -> np.ndarray:
    """Run Real-ESRGAN (HuggingFace) if available."""
    if not _TORCH_OK:
        raise RuntimeError("torch unavailable")
    try:
        from huggingface_hub import hf_hub_download
        from RealESRGAN import RealESRGAN  # type: ignore
    except ImportError as e:
        raise RuntimeError(f"Real-ESRGAN not installed: {e}")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = RealESRGAN(device, scale=max(1, scale))
    # Try to load weights from HuggingFace
    repo = "ai-forever/Real-ESRGAN"
    weight_name = f"RealESRGAN_x{max(1, scale)}.pth"
    try:
        weight_path = hf_hub_download(repo, weight_name)
        model.load_weights(weight_path, download=False)
    except Exception:
        # Real-ESRGAN can download by itself.
        model.load_weights(weight_name, download=True)

    from PIL import Image as _PIL
    pil = _PIL.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    out = model.predict(pil)
    out_np = np.asarray(out)
    out_bgr = cv2.cvtColor(out_np, cv2.COLOR_RGB2BGR)
    if out_bgr.shape[:2] != img.shape[:2]:
        out_bgr = cv2.resize(
            out_bgr, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_AREA
        )
    return out_bgr


def _try_waifu2x(img: np.ndarray, scale: int, noise_level: int) -> np.ndarray:
    """Run waifu2x via the `waifu2x-ncnn-vulkan` CLI if installed."""
    exe = shutil.which("waifu2x-ncnn-vulkan")
    if exe is None:
        exe = shutil.which("waifu2x")
    if exe is None:
        raise RuntimeError("waifu2x CLI not found in PATH")

    with tempfile.TemporaryDirectory() as td:
        in_path = os.path.join(td, "in.png")
        out_path = os.path.join(td, "out.png")
        cv2.imwrite(in_path, img)
        cmd = [
            exe,
            "-i", in_path,
            "-o", out_path,
            "-n", str(int(noise_level)),
            "-s", str(max(1, int(scale))),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=120)
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
            raise RuntimeError(f"waifu2x failed: {e}")
        out = cv2.imread(out_path)
        if out is None:
            raise RuntimeError("waifu2x produced no output")
        if out.shape[:2] != img.shape[:2]:
            out = cv2.resize(
                out, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_AREA
            )
        return out


def _try_edsr(img: np.ndarray, scale: int, noise_level: int) -> np.ndarray:
    """Use OpenCV's DnnSuperResImpl_create with an EDSR model (if available)."""
    try:
        sr = cv2.dnn_superres.DnnSuperResImpl_create()
    except AttributeError as e:
        raise RuntimeError(f"OpenCV super-resolution not available: {e}")

    # Try a couple of common model filenames on disk
    candidates = [
        f"EDSR_x{max(1, scale)}.pb",
        f"models/EDSR_x{max(1, scale)}.pb",
        os.path.expanduser(f"~/.cache/opencv-models/EDSR_x{max(1, scale)}.pb"),
    ]
    model_path = next((p for p in candidates if os.path.exists(p)), None)
    if model_path is None:
        raise RuntimeError("No EDSR weights found on disk")

    sr.readModel(model_path)
    sr.setModel("edsr", max(1, scale))
    out = sr.upsample(img)
    if out.shape[:2] != img.shape[:2]:
        out = cv2.resize(
            out, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_AREA
        )
    return out


def _bicubic(img: np.ndarray, scale: int) -> np.ndarray:
    """Lanczos/Bicubic 'denoise' fallback: upscale->blur->downscale."""
    if scale <= 1:
        # Light bilateral smoothing as a denoise prior
        return cv2.bilateralFilter(img, d=5, sigmaColor=25, sigmaSpace=25)
    h, w = img.shape[:2]
    up = cv2.resize(img, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC)
    up = cv2.bilateralFilter(up, d=5, sigmaColor=25, sigmaSpace=25)
    return cv2.resize(up, (w, h), interpolation=cv2.INTER_AREA)


def apply_prior(
    img: np.ndarray,
    scale: int = 1,
    noise_level: int = 1,
    backend: str = "auto",
) -> np.ndarray:
    """
    Apply anime-specific denoising/SR prior to an image.
    Returns same-resolution refined image (noise removed, edges sharpened).
    """
    if img is None or img.size == 0:
        return img
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    chain = []
    if backend == "auto":
        chain = ["real_esrgan", "waifu2x", "edsr", "bicubic"]
    else:
        chain = [backend]
    last_err = None
    for b in chain:
        try:
            if b == "real_esrgan":
                return _try_real_esrgan(img, scale, noise_level)
            if b == "waifu2x":
                return _try_waifu2x(img, scale, noise_level)
            if b == "edsr":
                return _try_edsr(img, scale, noise_level)
            if b == "bicubic":
                return _bicubic(img, scale)
        except Exception as e:
            last_err = e
            continue

    print(f"[MFSR] apply_prior: all backends failed (last: {last_err}); returning input.")
    return img


__all__ = ["apply_prior"]

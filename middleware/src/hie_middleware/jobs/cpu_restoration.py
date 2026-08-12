"""Dependency-light Pillow restoration runners for owned local images.

These are conservative CPU baselines, not substitutes for trained neural
restoration models. They exist so the editor has a real executable path while
optional ONNX/PyTorch/OpenCV backends are being integrated.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import CancelToken, JobProgress, ReportFn


def cpu_deblur_runner(
    input_ref: str, options: dict[str, Any], token: CancelToken, report: ReportFn
) -> str:
    """Apply bounded Pillow UnsharpMask enhancement and save a new image."""
    from PIL import Image, ImageFilter

    source = _open_image(input_ref)
    token.raise_if_cancelled()
    strength = float(options.get("strength", 1.0))
    if not 0.0 <= strength <= 3.0:
        raise ValueError("deblur strength must be between 0 and 3")
    radius = float(options.get("radius", 1.2))
    if not 0.1 <= radius <= 5.0:
        raise ValueError("deblur radius must be between 0.1 and 5")
    percent = int(100 + strength * 150)
    report(JobProgress(0.35, "applying CPU deblur baseline"))
    restored = source.filter(ImageFilter.UnsharpMask(radius=radius, percent=percent, threshold=2))
    token.raise_if_cancelled()
    output = _output_path(input_ref, options, "deblur")
    restored.save(output)
    report(JobProgress(0.9, "saved deblur preview", {"output_ref": str(output), "backend": "pillow-cpu"}))
    return str(output)


def cpu_masked_inpainting_runner(
    input_ref: str, options: dict[str, Any], token: CancelToken, report: ReportFn
) -> str:
    """Fill a supplied logo mask with a conservative median-neighborhood baseline."""
    from PIL import Image, ImageFilter

    source = _open_image(input_ref)
    mask_ref = options.get("mask_ref")
    if not isinstance(mask_ref, str) or not mask_ref.strip():
        raise ValueError("masked_inpainting requires mask_ref")
    mask = _open_image(mask_ref).convert("L")
    if mask.size != source.size:
        raise ValueError("mask dimensions must match the input image")
    token.raise_if_cancelled()
    radius = int(options.get("radius", 5))
    if radius not in {3, 5, 7, 9}:
        raise ValueError("inpainting radius must be one of 3, 5, 7, or 9")
    report(JobProgress(0.35, "applying CPU masked-inpainting baseline"))
    neighborhood = source.filter(ImageFilter.MedianFilter(size=radius))
    restored = Image.composite(neighborhood, source, mask)
    token.raise_if_cancelled()
    output = _output_path(input_ref, options, "inpaint")
    restored.save(output)
    report(JobProgress(0.9, "saved inpainting preview", {"output_ref": str(output), "backend": "pillow-cpu"}))
    return str(output)


def opencv_masked_inpainting_runner(
    input_ref: str, options: dict[str, Any], token: CancelToken, report: ReportFn
) -> str:
    """Use OpenCV Telea/Navier-Stokes inpainting when the optional extra exists."""
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise RuntimeError(
            "OpenCV runner unavailable; install HIE with the restoration-opencv extra"
        ) from exc
    from PIL import Image

    source = _open_image(input_ref).convert("RGB")
    mask_ref = options.get("mask_ref")
    if not isinstance(mask_ref, str) or not mask_ref.strip():
        raise ValueError("masked_inpainting requires mask_ref")
    mask = _open_image(mask_ref).convert("L")
    if mask.size != source.size:
        raise ValueError("mask dimensions must match the input image")
    token.raise_if_cancelled()
    radius = float(options.get("radius", 3.0))
    if not 1.0 <= radius <= 20.0:
        raise ValueError("OpenCV inpainting radius must be between 1 and 20")
    method = options.get("method", "telea")
    flag = cv2.INPAINT_NS if method == "ns" else cv2.INPAINT_TELEA
    report(JobProgress(0.35, "applying OpenCV inpainting"))
    restored = cv2.inpaint(np.asarray(source), np.asarray(mask), radius, flag)
    token.raise_if_cancelled()
    output = _output_path(input_ref, options, "opencv-inpaint")
    Image.fromarray(cv2.cvtColor(restored, cv2.COLOR_BGR2RGB)).save(output)
    report(JobProgress(0.9, "saved OpenCV inpainting preview", {"output_ref": str(output), "backend": "opencv"}))
    return str(output)


def _open_image(path: str):
    from PIL import Image

    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"image does not exist: {path}")
    with Image.open(source) as image:
        return image.convert("RGBA").copy()


def _output_path(input_ref: str, options: dict[str, Any], suffix: str) -> Path:
    output = options.get("output_ref")
    if output:
        return Path(output)
    source = Path(input_ref)
    return source.with_name(f"{source.stem}.{suffix}{source.suffix}")

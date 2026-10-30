"""Run one GIF through the selected registry backend and the palette writer."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from middleware.src.services.media.gif_upscale.base import AlgorithmError
from middleware.src.services.media.gif_upscale.encode import encode_gif
from middleware.src.services.media.gif_upscale.io import decode_gif
from middleware.src.services.media.gif_upscale.registry import get_algorithm, list_algorithms

__all__ = ["list_algorithms", "resample_gif", "resample_still"]


def resample_gif(input_path: str, output_path: str, params: dict[str, Any]) -> dict[str, Any]:
    try:
        clip = decode_gif(input_path)
        frames = [frame.astype(np.float32) / 255.0 for frame in clip.frames]
        scaled, width, height, _algorithm_id = _scale_frames(frames, params, "gif")
        encoder = encode_gif(
            output_path,
            scaled,
            clip.durations,
            clip.loop,
            encoder=str(params.get("encoder") or "temporal"),
            dither=str(params.get("dither") or "ordered"),
        )
    except (AlgorithmError, OSError, ValueError) as exc:
        return {"success": False, "message": str(exc)}
    return {
        "success": True,
        "message": f"Wrote {width}x{height} {output_path}",
        "width": width,
        "height": height,
        "encoder": encoder,
    }


def resample_still(input_path: str, output_path: str, params: dict[str, Any]) -> dict[str, Any]:
    """Resize one still with the same registry entry a GIF would use, then save that format."""
    from PIL import Image

    try:
        with Image.open(input_path) as image:
            frame = np.asarray(image.convert("RGBA")).astype(np.float32) / 255.0
        scaled, width, height, _algorithm_id = _scale_frames([frame], params, "still")
        _save_still(scaled[0], output_path)
    except (AlgorithmError, OSError, ValueError) as exc:
        return {"success": False, "message": str(exc)}
    return {"success": True, "message": f"Wrote {width}x{height} {output_path}", "width": width, "height": height}


def _scale_frames(frames: list[np.ndarray], params: dict[str, Any], container: str) -> tuple[list[np.ndarray], int, int, str]:
    algorithm_id = str(params.get("algorithm") or "lanczos").strip().lower()
    registered = get_algorithm(algorithm_id)
    if container not in registered.spec.containers:
        raise AlgorithmError(f"{algorithm_id} does not resample {container} images.")
    available, reason = registered.spec.available()
    if not available:
        raise AlgorithmError(reason or f"{algorithm_id} is unavailable.")
    source_height, source_width = frames[0].shape[:2]
    width, height = _target_size((source_width, source_height), params)
    refusal = _scale_refusal(registered.spec, source_width, source_height, width, height)
    if refusal:
        raise AlgorithmError(refusal)
    scale = width / source_width
    scaled = registered.upscale(frames, float(scale), {"size": (width, height), "params": params})
    if len(scaled) != len(frames):
        raise AlgorithmError(f"{algorithm_id} returned {len(scaled)} frames for {len(frames)} inputs.")
    return scaled, width, height, algorithm_id


def _save_still(frame: np.ndarray, path: str) -> None:
    from PIL import Image

    pixels = np.clip(np.rint(np.asarray(frame) * 255.0), 0, 255).astype(np.uint8)
    image = Image.fromarray(pixels, "RGBA")
    converted = image
    try:
        if Path(path).suffix.lower() in {".jpg", ".jpeg", ".bmp"}:
            converted = image.convert("RGB")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        converted.save(path)
    finally:
        if converted is not image:
            converted.close()
        image.close()


def _target_size(size: tuple[int, int], params: dict[str, Any]) -> tuple[int, int]:
    width, height = size
    if str(params.get("mode") or "factor") == "dimensions":
        width = int(params.get("width") or 0)
        height = int(params.get("height") or 0)
    else:
        factor = float(params.get("factor") or 1)
        width = max(1, round(width * factor))
        height = max(1, round(height * factor))
    if width < 1 or height < 1:
        raise ValueError("target size must be positive")
    return width, height


def _scale_refusal(spec: Any, source_width: int, source_height: int, width: int, height: int) -> str:
    if (width < source_width or height < source_height) and not spec.supports_downscale:
        return f"{spec.id} does not downscale."
    if not spec.supports_scale:
        return ""
    scale_x = width / source_width
    scale_y = height / source_height
    if any(abs(scale_x - allowed) < 1e-3 and abs(scale_y - allowed) < 1e-3 for allowed in spec.supports_scale):
        return ""
    supported = ", ".join(str(value) for value in sorted(spec.supports_scale))
    return (
        f"{spec.id} supports scales {supported}, not {width}x{height} from {source_width}x{source_height}."
    )

"""Inspect caller-supplied image paths for the preview window (#895).

This module never opens library.db. A difference map is refused when the
two files differ in size or when either image is larger than four million
pixels, so a preview cannot pull an unbounded decode into the sidecar.
"""

from __future__ import annotations

import base64
import io
from contextlib import ExitStack
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, UnidentifiedImageError

_MAX_PIXELS = 4_000_000
_FRAME_EDGE = 512


def describe_paths(paths: list[str]) -> dict[str, Any]:
    # The runtime schema subset has no maxItems, so the cap lives here.
    if len(paths) > 32:
        raise ValueError("describe accepts at most 32 paths")
    return {"items": [_describe_one(path) for path in paths]}


def _describe_one(path: str) -> dict[str, Any]:
    file = Path(path)
    blank = {
        "path": path,
        "exists": False,
        "width": 0,
        "height": 0,
        "animated": False,
        "error": "not a file",
    }
    if not file.is_file():
        return blank
    try:
        with Image.open(file) as image:
            width, height = image.size
            frames = int(getattr(image, "n_frames", 1))
    except (UnidentifiedImageError, OSError) as exc:
        return {
            "path": path,
            "exists": True,
            "width": 0,
            "height": 0,
            "animated": False,
            "error": str(exc),
        }
    return {
        "path": path,
        "exists": True,
        "width": int(width),
        "height": int(height),
        "animated": frames > 1,
        "error": "",
    }


def frame_png(path: str) -> dict[str, Any]:
    """First frame only. Animated playback stays on the Qt viewer for now."""
    blank = {"path": path, "width": 0, "height": 0, "png_base64": "", "error": "not a file"}
    file = Path(path)
    if not file.is_file():
        return blank
    try:
        with _open_rgba(path) as frame, io.BytesIO() as buffer:
            frame.thumbnail((_FRAME_EDGE, _FRAME_EDGE))
            frame.save(buffer, format="PNG")
            width, height = frame.size
            encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        return {"path": path, "width": 0, "height": 0, "png_base64": "", "error": str(exc)}

    return {
        "path": path,
        "width": width,
        "height": height,
        "png_base64": encoded,
        "error": "",
    }


def _unavailable(reason: str) -> dict[str, Any]:
    return {
        "available": False,
        "width": 0,
        "height": 0,
        "mean_abs": 0.0,
        "reason": reason,
        "png_base64": "",
    }


def _check_dimensions(image: Image.Image) -> None:
    width, height = image.size
    if width < 1 or height < 1 or width * height > _MAX_PIXELS:
        raise ValueError("image is too large")


def _open_rgba(path: str) -> Image.Image:
    with Image.open(path) as image:
        _check_dimensions(image)
        return image.convert("RGBA")


def _premultiplied_rgb(image: Image.Image) -> Image.Image:
    with image.convert("RGB") as rgb, image.getchannel("A") as alpha, alpha.convert("RGB") as mask:
        return ImageChops.multiply(rgb, mask)


def difference_map(left: str, right: str, boost: int) -> dict[str, Any]:
    try:
        with ExitStack() as stack:
            inputs = [stack.enter_context(Image.open(path)) for path in (left, right)]
            # Inspect both headers before allocating either decoded frame.
            for image in inputs:
                _check_dimensions(image)
            if inputs[0].size != inputs[1].size:
                return _unavailable("size mismatch")
            frames = [stack.enter_context(image.convert("RGBA")) for image in inputs]
            colors = [stack.enter_context(_premultiplied_rgb(image)) for image in frames]
            color_diff = stack.enter_context(ImageChops.difference(*colors))
            alphas = [stack.enter_context(image.getchannel("A")) for image in frames]
            alpha_diff = stack.enter_context(ImageChops.difference(*alphas))
            alpha_rgb = stack.enter_context(alpha_diff.convert("RGB"))
            # Alpha-only changes must be visible; hidden RGB values must not be.
            diff = stack.enter_context(ImageChops.lighter(color_diff, alpha_rgb))
            raw = diff.tobytes()
            mean = sum(raw) / len(raw) if raw else 0.0
            if boost != 1:
                diff = stack.enter_context(diff.point(lambda channel: min(255, channel * boost)))
            with io.BytesIO() as buffer:
                diff.save(buffer, format="PNG")
                return {
                    "available": True,
                    "width": diff.width,
                    "height": diff.height,
                    "mean_abs": mean,
                    "reason": "",
                    "png_base64": base64.b64encode(buffer.getvalue()).decode("ascii"),
                }
    except FileNotFoundError as exc:
        return _unavailable(f"not a file: {exc}")
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        return _unavailable(str(exc))

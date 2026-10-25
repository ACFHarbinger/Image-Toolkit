"""Inspect caller-supplied image paths for the preview window (#895).

This module never opens library.db. A difference map is refused when the
two files differ in size or when either image is larger than four million
pixels, so a preview cannot pull an unbounded decode into the sidecar.
"""

from __future__ import annotations

import base64
import io
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
        with Image.open(file) as image:
            frame = image.convert("RGB")
            frame.thumbnail((_FRAME_EDGE, _FRAME_EDGE))
            buffer = io.BytesIO()
            frame.save(buffer, format="PNG")
            width, height = frame.size
            frame.close()
    except (UnidentifiedImageError, OSError) as exc:
        return {"path": path, "width": 0, "height": 0, "png_base64": "", "error": str(exc)}
    return {
        "path": path,
        "width": width,
        "height": height,
        "png_base64": base64.b64encode(buffer.getvalue()).decode("ascii"),
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


def _open_rgb(path: str) -> Image.Image:
    """Decode RGB only after the header dimensions are within the pixel cap.

    ``Image.open`` reads the header. ``convert`` allocates the buffer, so a
    file that is too large is closed before that conversion.
    """
    file = Path(path)
    if not file.is_file():
        raise FileNotFoundError(path)
    image = Image.open(file)
    try:
        width, height = image.size
        if width < 1 or height < 1 or width * height > _MAX_PIXELS:
            raise ValueError("image is too large")
        # convert() returns the same object when the mode is already RGB.
        rgb = image.convert("RGB")
        if rgb is image:
            rgb = image.copy()
        return rgb
    finally:
        image.close()


def difference_map(left: str, right: str, boost: int) -> dict[str, Any]:
    left_image = None
    right_image = None
    try:
        try:
            left_image = _open_rgb(left)
            right_image = _open_rgb(right)
        except FileNotFoundError as exc:
            return _unavailable(f"not a file: {exc}")
        except ValueError as exc:
            return _unavailable(str(exc))
        except (UnidentifiedImageError, OSError) as exc:
            return _unavailable(str(exc))
        if left_image.size != right_image.size:
            return _unavailable("size mismatch")
        width, height = left_image.size
        diff = ImageChops.difference(left_image, right_image)
    finally:
        if left_image is not None:
            left_image.close()
        if right_image is not None:
            right_image.close()
    raw = diff.tobytes()
    total = sum(raw)
    count = len(raw)
    mean = (total / count) if count else 0.0
    if boost != 1:
        diff = diff.point(lambda channel: min(255, channel * boost))
    buffer = io.BytesIO()
    diff.save(buffer, format="PNG")
    diff.close()
    return {
        "available": True,
        "width": width,
        "height": height,
        "mean_abs": mean,
        "reason": "",
        "png_base64": base64.b64encode(buffer.getvalue()).decode("ascii"),
    }

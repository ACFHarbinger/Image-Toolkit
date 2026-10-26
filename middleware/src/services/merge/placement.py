"""Paste caller images onto stored rectangles (#1107).

Pillow is imported inside the compose function. This module does not open
library.db and does not call the panorama engines.
"""

from __future__ import annotations

from typing import Any

from middleware.src.services.merge.concatenate import _preview_png, _reject_canvas, _save

_MAX_PLACEMENTS = 32


def place(placements: list[dict[str, Any]], output_path: str) -> dict[str, Any]:
    try:
        _validate(placements, output_path)
        width, height = _canvas_size(placements)
        preview = _compose(placements, output_path, width, height)
    except (OSError, ValueError) as exc:
        return _failed(output_path, str(exc))
    return {
        "written": True,
        "output_path": output_path,
        "width": width,
        "height": height,
        "preview_png_base64": preview,
        "error": "",
    }


def _failed(output_path: str, error: str) -> dict[str, Any]:
    return {
        "written": False,
        "output_path": output_path,
        "width": 0,
        "height": 0,
        "preview_png_base64": "",
        "error": error,
    }


def _validate(placements: list[dict[str, Any]], output_path: str) -> None:
    from pathlib import Path

    if len(placements) < 1 or len(placements) > _MAX_PLACEMENTS:
        raise ValueError("place accepts 1 to 32 images")
    destination = Path(output_path)
    if destination.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
        raise ValueError("unsupported output")
    if destination.is_dir() or not destination.parent.is_dir():
        raise ValueError("output directory is missing")
    resolved_out = destination.resolve()
    if resolved_out in {Path(str(item["path"])).resolve() for item in placements}:
        raise ValueError("output matches an input")
    for item in placements:
        _box(item)


def _box(item: dict[str, Any]) -> None:
    for name in ("x", "y", "width", "height"):
        value = item[name]
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{name} must be an integer")
    if item["x"] < 0 or item["y"] < 0 or item["width"] < 1 or item["height"] < 1:
        raise ValueError("placement is outside the canvas")
    if item["x"] + item["width"] > 8192 or item["y"] + item["height"] > 8192:
        raise ValueError("image is too large")


def _canvas_size(placements: list[dict[str, Any]]) -> tuple[int, int]:
    width = max(int(item["x"]) + int(item["width"]) for item in placements)
    height = max(int(item["y"]) + int(item["height"]) for item in placements)
    _reject_canvas(width, height)
    return width, height


def _compose(placements: list[dict[str, Any]], output_path: str, width: int, height: int) -> str:
    from PIL import Image

    canvas = Image.new("RGB", (width, height), (255, 255, 255))
    try:
        for item in placements:
            _paste(canvas, item)
        encoded = _preview_png(canvas)
        _save(canvas, output_path)
        return encoded
    finally:
        canvas.close()


def _paste(canvas: Any, item: dict[str, Any]) -> None:
    from pathlib import Path

    from PIL import Image, UnidentifiedImageError

    path = str(item["path"])
    if not Path(path).is_file():
        raise ValueError(f"not a file: {path}")
    try:
        with Image.open(path) as image:
            _reject_canvas(*image.size)
            rgb = image.convert("RGB")
            try:
                resized = rgb.resize((int(item["width"]), int(item["height"])), Image.Resampling.LANCZOS)
                try:
                    canvas.paste(resized, (int(item["x"]), int(item["y"])))
                finally:
                    resized.close()
            finally:
                if rgb is not image:
                    rgb.close()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError(str(exc)) from exc

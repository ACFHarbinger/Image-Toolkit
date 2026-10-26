"""Concatenate caller image paths (#903).

This module never opens library.db and never calls the panorama engines.
Header size is checked before a pixel decode. The output canvas is refused
when it would exceed four million pixels.
"""

from __future__ import annotations

import base64
import io
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from PIL import Image

_MAX_PIXELS = 4_000_000
_MAX_PATHS = 8
_MAX_EDGE = 8192
_FORMATS = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG"}


def concatenate(
    paths: list[str],
    output_path: str,
    direction: str,
    spacing: int,
    align: str,
) -> dict[str, Any]:
    try:
        _validate(paths, output_path, direction, spacing, align)
        sizes = [_header_size(path) for path in paths]
        width, height = _canvas_size(sizes, direction, spacing)
        _reject_canvas(width, height)
        preview = _compose(paths, sizes, output_path, direction, spacing, align, width, height)
    except (ValueError, OSError) as exc:
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


def _validate(paths: list[str], output_path: str, direction: str, spacing: int, align: str) -> None:
    # The runtime schema subset has no maxItems, so the cap lives here.
    if direction not in {"horizontal", "vertical"}:
        raise ValueError("direction must be horizontal or vertical")
    if align not in {"start", "center", "end"}:
        raise ValueError("align must be start, center, or end")
    if isinstance(spacing, bool) or not isinstance(spacing, int) or spacing < 0 or spacing > 64:
        raise ValueError("spacing must be from 0 to 64")
    if len(paths) < 2 or len(paths) > _MAX_PATHS:
        raise ValueError("concatenate accepts 2 to 8 paths")
    destination = Path(output_path)
    if destination.suffix.lower() not in _FORMATS:
        raise ValueError("unsupported output")
    if destination.is_dir() or not destination.parent.is_dir():
        raise ValueError("output directory is missing")
    resolved_out = destination.resolve()
    if resolved_out in {Path(path).resolve() for path in paths}:
        raise ValueError("output matches an input")


def _header_size(path: str) -> tuple[int, int]:
    from PIL import Image, UnidentifiedImageError

    file = Path(path)
    if not file.is_file():
        raise ValueError(f"not a file: {path}")
    try:
        with Image.open(file) as image:
            width, height = image.size
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError(str(exc)) from exc
    _reject_canvas(width, height)
    return int(width), int(height)


def _reject_canvas(width: int, height: int) -> None:
    if width < 1 or height < 1 or width > _MAX_EDGE or height > _MAX_EDGE or width * height > _MAX_PIXELS:
        raise ValueError("image is too large")


def _canvas_size(sizes: list[tuple[int, int]], direction: str, spacing: int) -> tuple[int, int]:
    gaps = spacing * (len(sizes) - 1)
    if direction == "horizontal":
        return sum(width for width, _height in sizes) + gaps, max(height for _width, height in sizes)
    return max(width for width, _height in sizes), sum(height for _width, height in sizes) + gaps


def _cross_offset(spare: int, align: str) -> int:
    if align == "center":
        return spare // 2
    if align == "end":
        return spare
    return 0


def _open_rgb(path: str) -> Image.Image:
    from PIL import Image

    image = Image.open(path)
    try:
        _reject_canvas(*image.size)
        rgb = image.convert("RGB")
        if rgb is image:
            rgb = image.copy()
        return rgb
    finally:
        image.close()


def _preview_png(canvas: Image.Image) -> str:
    preview = canvas.copy()
    try:
        preview.thumbnail((512, 512))
        with io.BytesIO() as buffer:
            preview.save(buffer, format="PNG")
            return base64.b64encode(buffer.getvalue()).decode("ascii")
    finally:
        preview.close()


def _save(canvas: Image.Image, output_path: str) -> None:
    destination = Path(output_path)
    partial: Path | None = None
    try:
        # Save through the exclusively created descriptor, never a predictable path.
        with tempfile.NamedTemporaryFile(
            mode="w+b",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".partial",
            delete=False,
        ) as stream:
            partial = Path(stream.name)
            canvas.save(stream, format=_FORMATS[destination.suffix.lower()])
        partial.replace(destination)
    finally:
        if partial is not None:
            partial.unlink(missing_ok=True)


def _compose(
    paths: list[str],
    sizes: list[tuple[int, int]],
    output_path: str,
    direction: str,
    spacing: int,
    align: str,
    width: int,
    height: int,
) -> str:
    from PIL import Image

    canvas = Image.new("RGB", (width, height), (255, 255, 255))
    try:
        cursor = 0
        for path, (item_width, item_height) in zip(paths, sizes, strict=True):
            rgb = _open_rgb(path)
            try:
                if direction == "horizontal":
                    box = (cursor, _cross_offset(height - item_height, align))
                    cursor += item_width + spacing
                else:
                    box = (_cross_offset(width - item_width, align), cursor)
                    cursor += item_height + spacing
                canvas.paste(rgb, box)
            finally:
                rgb.close()
        encoded = _preview_png(canvas)
        _save(canvas, output_path)
        return encoded
    finally:
        canvas.close()

"""Merge modes beyond the horizontal/vertical contract path.

Canvas placement stays in this module. Grid, panorama, sequential, gif, and
the resize alignments go through ImageMerger, the same dispatcher the Qt tab uses.
"""

from __future__ import annotations

import base64
import io
import tempfile
from pathlib import Path
from typing import Any

_BACKGROUNDS = {
    "transparent": (0, 0, 0, 0),
    "white": (255, 255, 255, 255),
    "black": (0, 0, 0, 255),
}


def run_merge(params: dict[str, Any]) -> dict[str, Any]:
    direction = str(params.get("direction") or "")
    paths = [str(path) for path in params.get("paths") or [] if str(path).strip()]
    output_path = str(params.get("output_path") or "")
    if len(paths) < 2:
        raise ValueError("Select at least 2 images.")
    if not output_path:
        raise ValueError("output path is required")
    if direction == "canvas":
        inputs = paths + [str(item.get("path") or "") for item in params.get("canvas_layout", []) if isinstance(item, dict)]
        destination = Path(output_path).resolve()
        if any(destination == Path(path).resolve() for path in inputs if path):
            raise ValueError("output matches an input")
        return _canvas(paths, output_path, params)
    try:
        return _engine_merge(paths, output_path, direction, params)
    except Exception as exc:
        return {
            "success": False,
            "written": False,
            "output_path": output_path,
            "width": 0,
            "height": 0,
            "preview_png_base64": "",
            "error": str(exc),
            "message": str(exc),
        }


def _engine_merge(paths: list[str], output_path: str, direction: str, params: dict[str, Any]) -> dict[str, Any]:
    from middleware.src.core.image.image_merger import ImageMerger

    grid = None
    if direction == "grid":
        grid = (int(params.get("rows") or 2), int(params.get("cols") or 2))
    image = ImageMerger.merge_images(
        paths,
        output_path,
        direction,
        grid_size=grid,
        spacing=int(params.get("spacing") or 0),
        align_mode=str(params.get("align") or "Default (Top/Center)"),
        duration=int(params.get("duration") or 500),
        engine=str(params.get("engine") or "opencv"),
        engine_kwargs=_engine_kwargs(params),
    )
    width, height = image.size
    preview = _preview_png(image)
    image.close()
    return {
        "success": True,
        "written": True,
        "output_path": output_path,
        "width": width,
        "height": height,
        "preview_png_base64": preview,
        "error": "",
        "message": f"Wrote {output_path}",
    }


def _engine_kwargs(params: dict[str, Any]) -> dict[str, Any]:
    engine = str(params.get("engine") or "opencv")
    if engine == "hugin":
        return {"projection": int(params.get("projection") or 0)}
    if engine == "overmix":
        return {
            "aligner": str(params.get("aligner") or "Recursive"),
            "render_stat": str(params.get("render_stat") or "average"),
        }
    if engine == "asp":
        return {}
    return {"stitcher_mode": int(params.get("stitcher_mode") or 0)}


def _canvas(paths: list[str], output_path: str, params: dict[str, Any]) -> dict[str, Any]:
    layout = params.get("canvas_layout")
    if isinstance(layout, list) and layout:
        return _canvas_from_layout(output_path, params, layout)
    from PIL import Image

    spacing = max(0, int(params.get("spacing") or 0))
    background = _BACKGROUNDS.get(str(params.get("background") or "transparent").lower(), _BACKGROUNDS["transparent"])
    opened = [Image.open(path).convert("RGBA") for path in paths]
    try:
        width = int(params.get("canvas_width") or 0)
        height = int(params.get("canvas_height") or 0)
        if width < 1 or height < 1:
            width = sum(image.width for image in opened) + spacing * (len(opened) - 1)
            height = max(image.height for image in opened)
        canvas = Image.new("RGBA", (width, height), background)
        x = 0
        y = 0
        row_height = 0
        for image in opened:
            if x > 0 and x + image.width > width:
                x = 0
                y += row_height + spacing
                row_height = 0
            canvas.alpha_composite(image, (x, y))
            x += image.width + spacing
            row_height = max(row_height, image.height)
        return _save_canvas(canvas, output_path, width, height)
    finally:
        for image in opened:
            image.close()


def _canvas_from_layout(output_path: str, params: dict[str, Any], layout: list[Any]) -> dict[str, Any]:
    """Paste each {path,x,y,w,h} where the editor placed it."""
    from PIL import Image

    width = int(params.get("canvas_width") or 0)
    height = int(params.get("canvas_height") or 0)
    if width < 1:
        width = 1920
    if height < 1:
        height = 1080
    background = _BACKGROUNDS.get(str(params.get("background") or "transparent").lower(), _BACKGROUNDS["transparent"])
    canvas = Image.new("RGBA", (width, height), background)
    opened: list[Any] = []
    try:
        for item in layout:
            if not isinstance(item, dict):
                continue
            path = str(item.get("path") or "")
            if not path:
                continue
            image = Image.open(path).convert("RGBA")
            opened.append(image)
            w = max(1, int(item.get("w") or image.width))
            h = max(1, int(item.get("h") or image.height))
            placed = image
            if image.size != (w, h):
                placed = image.resize((w, h), Image.Resampling.LANCZOS)
                opened.append(placed)
            canvas.alpha_composite(placed, (int(item.get("x") or 0), int(item.get("y") or 0)))
        return _save_canvas(canvas, output_path, width, height)
    finally:
        for image in opened:
            image.close()


def _save_canvas(canvas: Any, output_path: str, width: int, height: int) -> dict[str, Any]:
    from PIL import Image

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    preview = _preview_png(canvas)
    with tempfile.NamedTemporaryFile(dir=destination.parent, suffix=destination.suffix, delete=False) as handle:
        temporary = Path(handle.name)
    try:
        if destination.suffix.lower() in {".jpg", ".jpeg"}:
            with Image.new("RGB", canvas.size, (255, 255, 255)) as flat:
                flat.paste(canvas, mask=canvas.getchannel("A"))
                flat.save(temporary)
        else:
            canvas.save(temporary)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
        canvas.close()
    return {
        "success": True,
        "written": True,
        "output_path": output_path,
        "width": width,
        "height": height,
        "preview_png_base64": preview,
        "error": "",
        "message": f"Wrote {output_path}",
    }


def _preview_png(image: Any) -> str:
    from PIL import Image

    preview = image.copy() if isinstance(image, Image.Image) else image
    try:
        preview.thumbnail((512, 512))
        with io.BytesIO() as buffer:
            preview.save(buffer, format="PNG")
            return base64.b64encode(buffer.getvalue()).decode("ascii")
    finally:
        preview.close()

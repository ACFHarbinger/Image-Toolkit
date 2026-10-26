"""Video snapshot, range extract, and image-sheet cuts (#1107).

ffmpeg is resolved when a video action runs. A missing binary is an error.
This module does not invent frame bytes and does not open library.db.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

_MAX_PIXELS = 4_000_000
_MAX_EDGE = 8192


def snapshot_frame(path: str, time_seconds: float, output_path: str) -> dict[str, Any]:
    error = _media_ready(path, output_path, time_seconds, None)
    if error:
        return _file_result(output_path, error)
    command = [_ffmpeg_bin(), "-y", "-ss", str(time_seconds), "-i", path, "-frames:v", "1", output_path]
    if command[0] == "":
        return _file_result(output_path, "ffmpeg is not available")
    return _run_ffmpeg(command, output_path)


def extract_range(path: str, start_seconds: float, end_seconds: float, output_path: str) -> dict[str, Any]:
    error = _media_ready(path, output_path, start_seconds, end_seconds)
    if error:
        return _file_result(output_path, error)
    ffmpeg = _ffmpeg_bin()
    if not ffmpeg:
        return _file_result(output_path, "ffmpeg is not available")
    if Path(output_path).suffix.lower() == ".gif":
        command = [
            ffmpeg,
            "-y",
            "-ss",
            str(start_seconds),
            "-to",
            str(end_seconds),
            "-i",
            path,
            "-vf",
            "fps=10,scale=320:-1:flags=lanczos",
            output_path,
        ]
    else:
        command = [ffmpeg, "-y", "-ss", str(start_seconds), "-to", str(end_seconds), "-i", path, "-c", "copy", output_path]
    return _run_ffmpeg(command, output_path)


def cut_sheet(
    path: str,
    output_dir: str,
    arrangement: str,
    frame_width: int,
    frame_height: int,
    offset_x: int,
    offset_y: int,
    spacing: int,
    include_partial: bool,
) -> dict[str, Any]:
    blank = {"written": False, "output_dir": output_dir, "width": 0, "height": 0, "paths": [], "error": ""}
    if not Path(path).is_file():
        return {**blank, "error": "not a file"}
    if not Path(output_dir).is_dir():
        return {**blank, "error": "output directory is missing"}
    try:
        rects, width, height = _rects(
            path, arrangement, frame_width, frame_height, offset_x, offset_y, spacing, include_partial
        )
        written = _write_crops(path, output_dir, rects)
    except (OSError, ValueError) as exc:
        return {**blank, "error": str(exc)}
    return {
        "written": True,
        "output_dir": output_dir,
        "width": width,
        "height": height,
        "paths": written,
        "error": "",
    }


def _file_result(output_path: str, error: str) -> dict[str, Any]:
    return {"written": False, "output_path": output_path, "error": error}


def _media_ready(path: str, output_path: str, start: float, end: float | None) -> str:
    if not Path(path).is_file():
        return "not a file"
    if Path(output_path).resolve() == Path(path).resolve():
        return "output matches an input"
    if not Path(output_path).parent.is_dir():
        return "output directory is missing"
    if isinstance(start, bool) or not isinstance(start, (int, float)) or start < 0:
        return "start is invalid"
    if end is not None and (isinstance(end, bool) or not isinstance(end, (int, float)) or end <= start):
        return "end must be after start"
    return ""


def _ffmpeg_bin() -> str:
    return shutil.which("ffmpeg") or ""


def _run_ffmpeg(command: list[str], output_path: str) -> dict[str, Any]:
    destination = Path(output_path)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.stem}.",
        suffix=destination.suffix,
        dir=destination.parent,
    )
    os.close(fd)
    temporary = Path(temporary_name)
    staged = [*command[:-1], str(temporary)]
    try:
        try:
            completed = subprocess.run(staged, capture_output=True, check=False, timeout=120)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return _file_result(output_path, str(exc))
        if completed.returncode != 0 or not temporary.is_file() or temporary.stat().st_size == 0:
            return _file_result(output_path, "ffmpeg failed")
        temporary.replace(destination)
        temporary = None
        return {"written": True, "output_path": output_path, "error": ""}
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _rects(
    path: str,
    arrangement: str,
    frame_width: int,
    frame_height: int,
    offset_x: int,
    offset_y: int,
    spacing: int,
    include_partial: bool,
) -> tuple[list[tuple[int, int, int, int]], int, int]:
    from PIL import Image

    with Image.open(path) as image:
        img_w, img_h = image.size
    if img_w < 1 or img_h < 1 or img_w > _MAX_EDGE or img_h > _MAX_EDGE or img_w * img_h > _MAX_PIXELS:
        raise ValueError("image is too large")
    frames, leftover = _frame_lists(arrangement, img_w, img_h, frame_width, frame_height, offset_x, offset_y, spacing)
    rects = list(frames)
    if include_partial:
        rects.extend(rect for rect in (_clip(item, img_w, img_h) for item in leftover) if rect is not None)
    if not rects:
        raise ValueError("no frames")
    return rects, img_w, img_h


def _frame_lists(
    arrangement: str,
    img_w: int,
    img_h: int,
    frame_width: int,
    frame_height: int,
    offset_x: int,
    offset_y: int,
    spacing: int,
) -> tuple[list[tuple[int, int, int, int]], list[tuple[int, int, int, int]]]:
    if arrangement == "vertical":
        frame_w, frame_h = img_w - offset_x, frame_height
    elif arrangement == "horizontal":
        frame_w, frame_h = frame_width, img_h - offset_y
    elif arrangement == "grid":
        frame_w, frame_h = frame_width, frame_height
    else:
        raise ValueError("arrangement must be grid, vertical, or horizontal")
    if frame_w <= 0 or frame_h <= 0:
        raise ValueError("frame size is empty")
    xs = [offset_x] if arrangement == "vertical" else _axis_steps(offset_x, frame_w, spacing, img_w)
    ys = [offset_y] if arrangement == "horizontal" else _axis_steps(offset_y, frame_h, spacing, img_h)
    frames = [(x, y, frame_w, frame_h) for y in ys for x in xs]
    leftover: list[tuple[int, int, int, int]] = []
    # No complete step still leaves a positive span from the offset. Those rects
    # stay in leftover so _rects can clip them only when include_partial is set.
    missing_x = arrangement != "vertical" and not xs and img_w - offset_x > 0
    missing_y = arrangement != "horizontal" and not ys and img_h - offset_y > 0
    if missing_x and missing_y:
        leftover.append((offset_x, offset_y, frame_w, frame_h))
    elif missing_x:
        leftover.extend((offset_x, y, frame_w, frame_h) for y in ys)
    elif missing_y:
        leftover.extend((x, offset_y, frame_w, frame_h) for x in xs)
    if not xs or not ys:
        return frames, leftover
    partial_w = 0
    partial_h = 0
    last_x = xs[-1]
    last_y = ys[-1]
    if arrangement != "vertical":
        last_x_end = last_x + frame_w
        partial_w = img_w - last_x_end - spacing
        if partial_w > 0 and last_x_end + spacing < img_w:
            leftover.extend((last_x_end + spacing, y, partial_w, frame_h) for y in ys)
        else:
            partial_w = 0
    if arrangement != "horizontal":
        last_y_end = last_y + frame_h
        partial_h = img_h - last_y_end - spacing
        if partial_h > 0 and last_y_end + spacing < img_h:
            leftover.extend((x, last_y_end + spacing, frame_w, partial_h) for x in xs)
        else:
            partial_h = 0
    if arrangement == "grid" and partial_w > 0 and partial_h > 0:
        leftover.append((last_x + frame_w + spacing, last_y + frame_h + spacing, partial_w, partial_h))
    return frames, leftover


def _axis_steps(offset: int, size: int, gap: int, limit: int) -> list[int]:
    steps: list[int] = []
    pos = offset
    while pos + size <= limit:
        steps.append(pos)
        pos += size + gap
    return steps


def _clip(rect: tuple[int, int, int, int], img_w: int, img_h: int) -> tuple[int, int, int, int] | None:
    x, y, width, height = rect
    x1 = max(0, x)
    y1 = max(0, y)
    x2 = min(img_w, x + width)
    y2 = min(img_h, y + height)
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2 - x1, y2 - y1


def _write_crops(path: str, output_dir: str, rects: list[tuple[int, int, int, int]]) -> list[str]:
    from PIL import Image

    written: list[str] = []
    destination = Path(output_dir)
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        try:
            for index, (x, y, width, height) in enumerate(rects, start=1):
                crop = rgb.crop((x, y, x + width, y + height))
                try:
                    target = destination / f"frame_{index:03d}.png"
                    crop.save(target, format="PNG")
                    written.append(str(target))
                finally:
                    crop.close()
        finally:
            if rgb is not image:
                rgb.close()
    return written

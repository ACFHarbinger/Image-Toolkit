"""Video snapshot, range extract, and image-sheet cuts (#1107).

ffmpeg is resolved when a video action runs. A missing binary is an error.
This module does not invent frame bytes and does not open library.db.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

_MAX_PIXELS = 4_000_000
_MAX_EDGE = 8192
_MAX_CROPS = 1024


def snapshot_frame(
    path: str,
    time_seconds: float,
    output_path: str,
    *,
    raise_if_cancelled: Callable[[], None] | None = None,
) -> dict[str, Any]:
    error = _media_ready(path, output_path, time_seconds, None)
    if error:
        return _file_result(output_path, error)
    command = [_ffmpeg_bin(), "-y", "-ss", str(time_seconds), "-i", path, "-frames:v", "1", output_path]
    if command[0] == "":
        return _file_result(output_path, "ffmpeg is not available")
    return _run_ffmpeg(command, output_path, raise_if_cancelled)


def extract_range(
    path: str,
    start_seconds: float,
    end_seconds: float,
    output_path: str,
    *,
    raise_if_cancelled: Callable[[], None] | None = None,
) -> dict[str, Any]:
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
    return _run_ffmpeg(command, output_path, raise_if_cancelled)


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
    *,
    raise_if_cancelled: Callable[[], None] | None = None,
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
        _checkpoint(raise_if_cancelled, None)
        written = _write_crops(path, output_dir, rects, raise_if_cancelled)
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


def _run_ffmpeg(
    command: list[str],
    output_path: str,
    raise_if_cancelled: Callable[[], None] | None = None,
) -> dict[str, Any]:
    destination = Path(output_path)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.stem}.",
        suffix=destination.suffix,
        dir=destination.parent,
    )
    os.close(fd)
    temporary = Path(temporary_name)
    staged = [*command[:-1], str(temporary)]
    process: subprocess.Popen[bytes] | None = None
    try:
        try:
            process = subprocess.Popen(
                staged,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            _wait_ffmpeg(process, raise_if_cancelled)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return _file_result(output_path, str(exc))
        _checkpoint(raise_if_cancelled, process)
        if process.returncode != 0 or not temporary.is_file() or temporary.stat().st_size == 0:
            return _file_result(output_path, "ffmpeg failed")
        _checkpoint(raise_if_cancelled, process)
        temporary.replace(destination)
        temporary = None
        return {"written": True, "output_path": output_path, "error": ""}
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _wait_ffmpeg(process: subprocess.Popen[bytes], raise_if_cancelled: Callable[[], None] | None) -> None:
    """Poll ffmpeg so a cancel can stop it before the temporary file is published."""
    deadline = time.monotonic() + 120
    while process.poll() is None:
        _checkpoint(raise_if_cancelled, process)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            _stop_process(process)
            raise subprocess.TimeoutExpired(process.args, 120)
        try:
            process.wait(timeout=min(0.2, remaining))
        except subprocess.TimeoutExpired:
            continue


def _checkpoint(raise_if_cancelled: Callable[[], None] | None, process: subprocess.Popen[bytes] | None) -> None:
    if raise_if_cancelled is None:
        return
    try:
        raise_if_cancelled()
    except Exception:
        if process is not None:
            _stop_process(process)
        raise


def _stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    pid = getattr(process, "pid", None)
    if isinstance(pid, int) and pid > 0:
        try:
            os.killpg(pid, signal.SIGTERM)
        except OSError:
            process.terminate()
    else:
        process.terminate()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        if isinstance(pid, int) and pid > 0:
            try:
                os.killpg(pid, signal.SIGKILL)
            except OSError:
                process.kill()
        else:
            process.kill()
        process.wait(timeout=2)


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
    frames, leftover = _frame_lists(arrangement, img_w, img_h, frame_width, frame_height, offset_x, offset_y, spacing, include_partial)
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
    include_partial: bool = True,
) -> tuple[list[tuple[int, int, int, int]], list[tuple[int, int, int, int]]]:
    if min(offset_x, offset_y, spacing) < 0:
        raise ValueError("offset and spacing must be nonnegative")
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
    x_stop = img_w if include_partial else img_w - frame_w + 1
    y_stop = img_h if include_partial else img_h - frame_h + 1
    xs = range(offset_x, x_stop, frame_w + spacing)
    ys = range(offset_y, y_stop, frame_h + spacing)
    # range lengths are constant-space; reject before allocating the product.
    if len(xs) * len(ys) > _MAX_CROPS:
        raise ValueError(f"sheet exceeds the {_MAX_CROPS} crop limit")
    frames = []
    leftover = []
    for y in ys:
        for x in xs:
            target = frames if x + frame_w <= img_w and y + frame_h <= img_h else leftover
            target.append((x, y, frame_w, frame_h))
    return frames, leftover


def _clip(rect: tuple[int, int, int, int], img_w: int, img_h: int) -> tuple[int, int, int, int] | None:
    x, y, width, height = rect
    x1 = max(0, x)
    y1 = max(0, y)
    x2 = min(img_w, x + width)
    y2 = min(img_h, y + height)
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2 - x1, y2 - y1


def _crop_targets(path: str, output_dir: str, count: int) -> list[Path]:
    """Name every crop first. Any collision with the source rejects the whole cut."""
    source = Path(path).resolve()
    destination = Path(output_dir)
    targets: list[Path] = []
    for index in range(1, count + 1):
        target = destination / f"frame_{index:03d}.png"
        if target.resolve() == source:
            raise ValueError("output matches an input")
        targets.append(target)
    return targets


def _has_alpha(image: Any) -> bool:
    if image.mode in {"RGBA", "LA", "PA"}:
        return True
    return image.mode == "P" and "transparency" in image.info


def _write_crops(
    path: str, output_dir: str, rects: list[tuple[int, int, int, int]],
    raise_if_cancelled: Callable[[], None] | None = None,
) -> list[str]:
    from PIL import Image

    targets = _crop_targets(path, output_dir, len(rects))
    written: list[str] = []
    with Image.open(path) as image:
        sheet = image.convert("RGBA") if _has_alpha(image) else image.convert("RGB")
        try:
            for target, (x, y, width, height) in zip(targets, rects, strict=True):
                _checkpoint(raise_if_cancelled, None)
                crop = sheet.crop((x, y, x + width, y + height))
                try:
                    with tempfile.NamedTemporaryFile(dir=target.parent, suffix=".png", delete=False) as handle:
                        temporary = Path(handle.name)
                    try:
                        crop.save(temporary, format="PNG")
                        _checkpoint(raise_if_cancelled, None)
                        temporary.replace(target)
                        written.append(str(target))
                    finally:
                        temporary.unlink(missing_ok=True)
                finally:
                    crop.close()
        finally:
            if sheet is not image:
                sheet.close()
    return written

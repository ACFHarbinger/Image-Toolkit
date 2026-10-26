"""Selected-file convert, resample, and re-encode (#1107).

One loop checks the caller's cancel hook before each file after the first.
PIL and ffmpeg are imported or resolved inside the file that needs them.
"""

from __future__ import annotations

import shutil
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from middleware.src.services.convert.handlers import SUPPORTED_FORMATS

_IMAGE_EXTS = frozenset({"png", "jpg", "jpeg", "webp", "bmp", "tiff", "tif", "gif", "ico"})
_VIDEO_EXTS = frozenset({"mp4", "mkv", "webm", "mov", "avi", "m4v"})
_LIST_EXTS = _IMAGE_EXTS | _VIDEO_EXTS
_MAX_LIST = 2000
_VIDEO_ENCODERS = {
    "h264": "libx264",
    "hevc": "libx265",
    "av1": "libaom-av1",
    "vp9": "libvpx-vp9",
    "copy": "copy",
}
_AUDIO_ENCODERS = {
    "aac": "aac",
    "opus": "libopus",
    "mp3": "libmp3lame",
    "flac": "flac",
    "copy": "copy",
}
_PIL_FORMATS = {
    "jpg": "JPEG",
    "jpeg": "JPEG",
    "png": "PNG",
    "webp": "WEBP",
    "bmp": "BMP",
    "tif": "TIFF",
    "tiff": "TIFF",
    "gif": "GIF",
    "ico": "ICO",
}
_OPAQUE_FORMATS = frozenset({"jpg", "jpeg", "bmp"})


def list_directory(directory: str) -> dict[str, Any]:
    root = Path(directory)
    if not root.is_dir():
        return {"files": [], "error": "not a directory"}
    found = [
        str(path)
        for path in sorted(root.iterdir(), key=lambda item: item.name.lower())
        if path.is_file() and path.suffix.lower().lstrip(".") in _LIST_EXTS
    ]
    error = ""
    if len(found) > _MAX_LIST:
        found = found[:_MAX_LIST]
        error = "directory listing truncated"
    return {"files": found, "error": error}


def run_selected(params: dict[str, Any], before_file: Callable[[int, int], None]) -> dict[str, Any]:
    """Process selected files. ``before_file(done, total)`` runs before each file."""
    started = time.monotonic()
    action = str(params.get("action") or "convert")
    paths = _selected_paths(params)
    total = len(paths)
    before_file(0, total)
    succeeded = 0
    failed = 0
    outputs: list[str] = []
    errors: list[str] = []
    for index, src in enumerate(paths):
        if index:
            before_file(index, total)
        output, error = _one(params, action, src)
        if error:
            failed += 1
            errors.append(f"{Path(src).name}: {error}")
        else:
            succeeded += 1
            outputs.append(output)
    return {
        "total_discovered": total,
        "succeeded": succeeded,
        "failed": failed,
        "output_paths": outputs,
        "elapsed_seconds": round(time.monotonic() - started, 4),
        "errors": errors,
        "cancelled": False,
    }


def _selected_paths(params: dict[str, Any]) -> list[str]:
    raw = params.get("paths")
    if raw is None:
        return _discover(params)
    root = Path(str(params["input_dir"])).resolve()
    chosen: list[str] = []
    for item in raw:
        path = Path(str(item)).resolve()
        if path.parent != root:
            raise ValueError(f"selected file is outside the directory: {item}")
        chosen.append(str(path))
    return chosen


def _discover(params: dict[str, Any]) -> list[str]:
    listed = list_directory(str(params["input_dir"]))
    if listed["error"] == "not a directory":
        raise ValueError("not a directory")
    action = str(params.get("action") or "convert")
    if action == "convert" and params.get("input_formats"):
        wanted = {str(fmt).lower().lstrip(".") for fmt in params["input_formats"]}
    elif action == "reencode":
        wanted = set(_LIST_EXTS)
    else:
        wanted = set(_IMAGE_EXTS)
    return [path for path in listed["files"] if Path(path).suffix.lower().lstrip(".") in wanted]


def _one(params: dict[str, Any], action: str, src: str) -> tuple[str, str]:
    if action == "resample":
        return _resample(params, src)
    if action == "reencode":
        return _reencode(params, src)
    if action != "convert":
        return "", f"unknown action {action}"
    return _convert(params, src)


def _destination(params: dict[str, Any], src: str, suffix: str) -> Path:
    out_dir = Path(str(params["output_dir"]))
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{Path(src).stem}.{suffix.lstrip('.')}"


def _convert(params: dict[str, Any], src: str) -> tuple[str, str]:
    from middleware.src.services.convert.commands import ConvertSingleCommand
    from middleware.src.services.convert.handlers import ConvertSingleHandler

    fmt = str(params.get("output_format") or "png").lower().lstrip(".")
    dest = _destination(params, src, fmt)
    result = ConvertSingleHandler().handle(
        ConvertSingleCommand(
            input_path=src,
            output_path=str(dest),
            output_format=fmt,
            quality=int(params.get("quality") or 95),
            overwrite=bool(params.get("overwrite", True)),
        )
    )
    if not result.success:
        return "", result.error or "convert failed"
    return result.output_path, ""


def _resample(params: dict[str, Any], src: str) -> tuple[str, str]:
    ext = Path(src).suffix.lower().lstrip(".")
    if ext not in _IMAGE_EXTS:
        return "", "not an image"
    if params.get("width") is None and params.get("height") is None:
        return "", "resample needs width or height"
    fmt = str(params.get("output_format") or ext or "png").lower().lstrip(".")
    if fmt not in SUPPORTED_FORMATS:
        return "", "unsupported output format"
    dest = _destination(params, src, fmt)
    if dest.exists() and not params.get("overwrite", True):
        return "", "output exists"
    if dest.resolve() == Path(src).resolve():
        return "", "input and output must be different files"
    try:
        _resize_image(src, dest, params.get("width"), params.get("height"), str(params.get("algorithm") or "lanczos"), fmt)
    except (OSError, ValueError) as exc:
        return "", str(exc)
    return str(dest), ""


def _resize_image(src: str, dest: Path, width: Any, height: Any, algorithm: str, fmt: str) -> None:
    from PIL import Image

    resampling = {
        "nearest": Image.Resampling.NEAREST,
        "bilinear": Image.Resampling.BILINEAR,
        "bicubic": Image.Resampling.BICUBIC,
        "lanczos": Image.Resampling.LANCZOS,
    }
    if algorithm not in resampling:
        raise ValueError("unsupported resample algorithm")
    with Image.open(src) as image:
        target_w, target_h = _target_size(*image.size, width, height)
        working = _for_format(image, fmt)
        try:
            resized = working.resize((target_w, target_h), resampling[algorithm])
            try:
                resized.save(dest, format=_PIL_FORMATS[fmt])
            finally:
                resized.close()
        finally:
            if working is not image:
                working.close()


def _for_format(image: Any, fmt: str) -> Any:
    if fmt not in _OPAQUE_FORMATS and _has_alpha(image):
        return image.convert("RGBA")
    return image.convert("RGB")


def _has_alpha(image: Any) -> bool:
    if "A" in image.getbands():
        return True
    return image.mode == "P" and "transparency" in image.info


def _target_size(source_w: int, source_h: int, width: Any, height: Any) -> tuple[int, int]:
    target_w = int(width) if isinstance(width, int) and not isinstance(width, bool) else 0
    target_h = int(height) if isinstance(height, int) and not isinstance(height, bool) else 0
    if target_w < 1 and target_h < 1:
        raise ValueError("resample needs width or height")
    if source_w < 1 or source_h < 1:
        raise ValueError("image is empty")
    if target_w < 1:
        target_w = max(1, round(source_w * (target_h / source_h)))
    if target_h < 1:
        target_h = max(1, round(source_h * (target_w / source_w)))
    if target_w > 8192 or target_h > 8192:
        raise ValueError("resample target is too large")
    return target_w, target_h


def _reencode(params: dict[str, Any], src: str) -> tuple[str, str]:
    ext = Path(src).suffix.lower().lstrip(".")
    if ext in _IMAGE_EXTS:
        return _reencode_image(params, src, ext)
    if ext not in _VIDEO_EXTS:
        return "", "unsupported file"
    return _reencode_video(params, src, ext)


def _reencode_image(params: dict[str, Any], src: str, ext: str) -> tuple[str, str]:
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(src) as image:
            width, height = image.size
    except (UnidentifiedImageError, OSError) as exc:
        return "", str(exc)
    cloned = dict(params)
    cloned["width"] = int(width)
    cloned["height"] = int(height)
    cloned["algorithm"] = "nearest"
    if not cloned.get("output_format"):
        cloned["output_format"] = ext
    return _resample(cloned, src)


def _reencode_video(params: dict[str, Any], src: str, ext: str) -> tuple[str, str]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return "", "ffmpeg is not available"
    fmt = str(params.get("output_format") or ext).lower().lstrip(".")
    if fmt not in _VIDEO_EXTS:
        fmt = ext
    dest = _destination(params, src, fmt)
    if dest.exists() and not params.get("overwrite", True):
        return "", "output exists"
    if dest.resolve() == Path(src).resolve():
        return "", "input and output must be different files"
    video = _VIDEO_ENCODERS.get(str(params.get("video_codec") or "h264"))
    audio = _AUDIO_ENCODERS.get(str(params.get("audio_codec") or "aac"))
    if video is None or audio is None:
        return "", "unsupported codec"
    command = [ffmpeg, "-y", "-i", src, "-c:v", video, "-c:a", audio]
    crf = params.get("crf")
    if isinstance(crf, int) and not isinstance(crf, bool) and video != "copy":
        command.extend(["-crf", str(crf)])
    command.append(str(dest))
    try:
        completed = subprocess.run(command, capture_output=True, check=False, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        dest.unlink(missing_ok=True)
        return "", str(exc)
    if completed.returncode != 0 or not dest.is_file() or dest.stat().st_size == 0:
        dest.unlink(missing_ok=True)
        return "", "ffmpeg failed"
    return str(dest), ""

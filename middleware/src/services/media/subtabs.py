"""Codec re-encode, image resample, and sheet cutting. Params arrive on stdin."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def reencode(params: dict[str, Any]) -> dict[str, Any]:
    from middleware.src.core.video.video_converter import VideoFormatConverter

    input_path = str(params.get("input_path") or "")
    output_path = str(params.get("output_path") or "")
    if not input_path or not output_path:
        raise ValueError("input and output paths are required")
    ok = VideoFormatConverter.convert_codec(
        input_path,
        output_path,
        video_codec=str(params.get("video_codec") or "copy"),
        audio_codec=str(params.get("audio_codec") or "copy"),
        crf=int(params.get("crf") if params.get("crf") is not None else 28),
        speed=int(params.get("speed") if params.get("speed") is not None else 2),
    )
    if not ok:
        return {"success": False, "message": "Re-encode failed. Check that ffmpeg can read the file."}
    return {"success": True, "message": f"Wrote {output_path}"}


def resample(params: dict[str, Any]) -> dict[str, Any]:
    from PIL import Image

    input_path = str(params.get("input_path") or "")
    output_path = str(params.get("output_path") or "")
    if not input_path or not output_path:
        raise ValueError("input and output paths are required")
    image = Image.open(input_path)
    width, height = image.size
    mode = str(params.get("mode") or "factor")
    if mode == "dimensions":
        width = int(params.get("width") or 0)
        height = int(params.get("height") or 0)
    else:
        factor = float(params.get("factor") or 1)
        width = max(1, round(width * factor))
        height = max(1, round(height * factor))
    if width < 1 or height < 1:
        raise ValueError("target size must be positive")
    algorithms = {
        "lanczos": Image.Resampling.LANCZOS,
        "bicubic": Image.Resampling.BICUBIC,
        "bilinear": Image.Resampling.BILINEAR,
        "nearest": Image.Resampling.NEAREST,
    }
    algorithm = algorithms.get(str(params.get("algorithm") or "lanczos").lower(), Image.Resampling.LANCZOS)
    resized = image.resize((width, height), algorithm)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    resized.save(output_path)
    return {"success": True, "message": f"Wrote {width}x{height} {output_path}", "width": width, "height": height}


def cut_image(params: dict[str, Any]) -> dict[str, Any]:
    from PIL import Image

    input_path = str(params.get("input_path") or "")
    output_dir = str(params.get("output_dir") or "")
    frame_width = int(params.get("frame_width") or 0)
    frame_height = int(params.get("frame_height") or 0)
    if not input_path or not output_dir:
        raise ValueError("input path and output directory are required")
    if frame_width < 1 or frame_height < 1:
        raise ValueError("frame size must be positive")
    image = Image.open(input_path)
    width, height = image.size
    arrangement = str(params.get("arrangement") or "grid").lower()
    if arrangement == "vertical":
        frame_height = height
    elif arrangement == "horizontal":
        frame_width = width
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    index = 0
    for top in range(0, height - frame_height + 1, frame_height):
        for left in range(0, width - frame_width + 1, frame_width):
            frame = image.crop((left, top, left + frame_width, top + frame_height))
            path = destination / f"frame_{index:04d}.png"
            frame.save(path)
            written.append(str(path))
            index += 1
    if not written:
        return {"success": False, "message": "Frame size is larger than the image.", "count": 0}
    return {"success": True, "message": f"Wrote {index} frames", "count": index, "paths": written}


def convert_file(params: dict[str, Any]) -> dict[str, Any]:
    input_path = str(params.get("input_path") or "")
    output_path = str(params.get("output_path") or "")
    output_format = str(params.get("output_format") or "").lower().lstrip(".")
    if not input_path or not output_path or not output_format:
        raise ValueError("input, output, and format are required")
    videos = {"mp4", "mkv", "webm", "mov", "avi", "wmv"}
    ratios = {"16:9": 16 / 9, "4:3": 4 / 3, "1:1": 1.0, "9:16": 9 / 16, "3:2": 3 / 2}
    aspect = ratios.get(str(params.get("aspect_ratio") or ""))
    ar_mode = str(params.get("ar_mode") or "crop").lower()
    try:
        if output_format in videos:
            from middleware.src.core.video.video_converter import VideoFormatConverter

            ok = VideoFormatConverter.convert_video(
                input_path,
                output_path,
                aspect_ratio=aspect,
                ar_mode=ar_mode,
            )
        else:
            from middleware.src.core.image.image_converter import ImageFormatConverter

            ok = ImageFormatConverter.convert_single_image(
                input_path,
                output_path,
                format=output_format,
                aspect_ratio=aspect,
                ar_mode=ar_mode,
            )
    except ImportError as exc:
        return {"success": False, "message": str(exc)}
    if not ok:
        return {"success": False, "message": "Conversion failed."}
    return {"success": True, "message": f"Wrote {output_path}"}


def dispatch(payload: dict[str, Any]) -> dict[str, Any]:
    action = payload.get("action")
    if action == "preview":
        from middleware.src.services.library_preview.preview import describe_paths, frame_png

        path = str(payload.get("path") or "")
        frame = frame_png(path)
        if not frame["error"]:
            description = describe_paths([path])["items"][0]
            frame["width"], frame["height"] = description["width"], description["height"]
        return frame
    if action == "codec":
        return reencode(payload)
    if action == "resample":
        return resample(payload)
    if action == "image_cut":
        input_path = str(payload.get("input_path") or "")
        output_dir = str(payload.get("output_dir") or "")
        arrangement = str(payload.get("arrangement") or "grid").lower()
        frame_width = int(payload.get("frame_width") or 0)
        frame_height = int(payload.get("frame_height") or 0)
        offset_x = int(payload.get("offset_x") or 0)
        offset_y = int(payload.get("offset_y") or 0)
        spacing = int(payload.get("spacing") or 0)
        include_raw = payload.get("include_partial")
        include_partial = include_raw is True or include_raw == "true"
        # cut_sheet refuses a missing directory; the previous cutter created it.
        if output_dir and not Path(output_dir).is_dir():
            try:
                Path(output_dir).mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                return {"success": False, "message": str(exc), "count": 0, "paths": []}
        from middleware.src.services.extractor.actions import cut_sheet

        cut = cut_sheet(
            input_path,
            output_dir,
            arrangement,
            frame_width,
            frame_height,
            offset_x,
            offset_y,
            spacing,
            include_partial,
        )
        paths = cut.get("paths") or []
        error = cut.get("error") or ""
        if error or cut.get("written") is not True:
            return {"success": False, "message": error or "cut failed", "count": 0, "paths": paths or []}
        count = len(paths)
        return {"success": True, "message": f"Wrote {count} frames", "count": count, "paths": paths}
    if action == "snapshot":
        from middleware.src.services.extractor.actions import snapshot_frame

        return snapshot_frame(
            str(payload.get("path") or ""),
            payload.get("time_seconds", 0),
            str(payload.get("output_path") or ""),
        )
    if action == "extract_range":
        from middleware.src.services.extractor.actions import extract_range

        return extract_range(
            str(payload.get("path") or ""),
            payload.get("start_seconds", 0),
            payload.get("end_seconds", 0),
            str(payload.get("output_path") or ""),
        )
    if action == "merge":
        from middleware.src.services.merge.modes import run_merge

        return run_merge(payload)
    if action == "convert_file":
        return convert_file(payload)
    return {"success": False, "message": "Unknown action."}


def _write_result(out: Any, result: dict[str, Any]) -> None:
    """JSON is the only stdout. ffmpeg diagnostics from the converters stay on stderr."""
    json.dump(result, out)
    out.write("\n")
    out.flush()


def main() -> int:
    reply = sys.stdout
    sys.stdout = sys.stderr
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        _write_result(reply, {"success": False, "message": "Invalid request."})
        return 0
    try:
        result = dispatch(payload if isinstance(payload, dict) else {})
    except (OSError, ValueError) as exc:
        result = {"success": False, "message": str(exc)}
    _write_result(reply, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

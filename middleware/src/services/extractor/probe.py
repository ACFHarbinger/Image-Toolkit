"""Probe one caller video path (#905).

ffprobe is invoked with an argument list. This module does not open
library.db and does not extract frames.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


def probe_video(path: str) -> dict[str, Any]:
    blank = {
        "available": False,
        "path": path,
        "width": 0,
        "height": 0,
        "duration_seconds": 0.0,
        "codec": "",
        "error": "not a file",
    }
    if not Path(path).is_file():
        return blank
    try:
        completed = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                path,
            ],
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {**blank, "error": str(exc)}
    if completed.returncode != 0:
        return {**blank, "error": "ffprobe failed"}
    try:
        payload = json.loads(completed.stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return {**blank, "error": "ffprobe failed"}
    stream = _video_stream(payload)
    if stream is None:
        return {**blank, "error": "no video stream"}
    duration = _duration(payload, stream)
    return {
        "available": True,
        "path": path,
        "width": _nonnegative_int(stream.get("width")),
        "height": _nonnegative_int(stream.get("height")),
        "duration_seconds": duration,
        "codec": str(stream.get("codec_name") or ""),
        "error": "",
    }


def _video_stream(payload: dict[str, Any]) -> dict[str, Any] | None:
    streams = payload.get("streams")
    if not isinstance(streams, list):
        return None
    for stream in streams:
        if isinstance(stream, dict) and stream.get("codec_type") == "video":
            return stream
    return None


def _duration(payload: dict[str, Any], stream: dict[str, Any]) -> float:
    format_block = payload.get("format")
    raw = stream.get("duration")
    if raw in (None, "") and isinstance(format_block, dict):
        raw = format_block.get("duration")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0.0
    return value if value >= 0 else 0.0


def _nonnegative_int(value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return number if number > 0 else 0

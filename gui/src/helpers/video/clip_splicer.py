"""Non-destructive timeline export for ordered video clip segments."""

from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from gui.src.helpers.video.video_thumbnailer import media_backend_spawn_guard


@dataclass(frozen=True)
class ClipSegment:
    """A half-open source range in milliseconds."""

    source_path: str
    in_ms: int = 0
    out_ms: int | None = None

    def __post_init__(self) -> None:
        if not self.source_path:
            raise ValueError("source_path must not be empty")
        if self.in_ms < 0 or (self.out_ms is not None and self.out_ms <= self.in_ms):
            raise ValueError("segment range must satisfy 0 <= in_ms < out_ms")


def _probe_streams(path: str, ffprobe_bin: str) -> tuple[tuple[str, ...], ...]:
    command = [
        ffprobe_bin,
        "-v",
        "error",
        "-show_entries",
        "stream=codec_type,codec_name,profile,pix_fmt,width,height,sample_rate,channels",
        "-of",
        "json",
        path,
    ]
    with media_backend_spawn_guard():
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
    payload = json.loads(completed.stdout)
    streams = payload.get("streams", [])
    return tuple(
        tuple(str(stream.get(key, "")) for key in (
            "codec_type", "codec_name", "profile", "pix_fmt", "width",
            "height", "sample_rate", "channels",
        ))
        for stream in streams
    )


def _compatible_streams(profiles: Sequence[tuple[tuple[str, ...], ...]]) -> bool:
    return bool(profiles) and all(profile == profiles[0] for profile in profiles[1:])


def splice_clips(
    segments: Sequence[ClipSegment],
    output_path: str | Path,
    *,
    force_reencode: bool = False,
    ffmpeg_bin: str = "ffmpeg",
    ffprobe_bin: str = "ffprobe",
) -> Path:
    """Export ordered ranges without modifying their source files.

    Stream copy is used only when all source stream profiles match. Any mixed
    video/GIF or otherwise incompatible input is re-encoded by ffmpeg.
    """
    if not segments:
        raise ValueError("at least one clip segment is required")

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    normalized = tuple(segments)
    profiles = [_probe_streams(segment.source_path, ffprobe_bin) for segment in normalized]
    copy_streams = not force_reencode and _compatible_streams(profiles)

    with tempfile.TemporaryDirectory(prefix="image-toolkit-splice-") as temp_dir:
        concat_path = Path(temp_dir) / "segments.ffconcat"
        lines = ["ffconcat version 1.0"]
        for segment in normalized:
            # ffconcat paths use single-quoted escaping, not shell quoting.
            escaped = segment.source_path.replace("\\", "\\\\").replace("'", "\\'")
            lines.append(f"file '{escaped}'")
            if segment.in_ms:
                lines.append(f"inpoint {segment.in_ms / 1000:.6f}")
            if segment.out_ms is not None:
                lines.append(f"outpoint {segment.out_ms / 1000:.6f}")
        concat_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        command = [
            ffmpeg_bin,
            "-y",
            "-safe",
            "0",
            "-f",
            "concat",
            "-i",
            str(concat_path),
        ]
        if copy_streams:
            command.extend(["-c", "copy"])
        else:
            command.extend(["-c:v", "libx264", "-c:a", "aac"])
        command.append(str(destination))

        with media_backend_spawn_guard():
            completed = subprocess.run(command, check=False, capture_output=True, text=True)
        if completed.returncode:
            detail = (completed.stderr or completed.stdout).strip()[-1000:]
            raise RuntimeError(f"ffmpeg clip splice failed: {detail}")

    return destination


__all__ = ["ClipSegment", "splice_clips"]

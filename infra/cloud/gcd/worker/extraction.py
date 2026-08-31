"""Slim FFmpeg-only extraction path used by the Cloud Run worker."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ExtractionJob:
    job_id: str
    source_uri: str
    mode: str
    start_ms: int
    end_ms: int
    fps: int
    output_prefix: str
    target_size: tuple[int, int] | None = None

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> "ExtractionJob":
        source_uri = str(payload.get("source_uri") or payload.get("input_uri") or "")
        if not source_uri.startswith("gs://"):
            raise ValueError("source_uri must be a gs:// object URI")
        mode = str(payload.get("mode", "range")).lower()
        if mode not in {"range", "gif", "video"}:
            raise ValueError("mode must be range, gif, or video")
        start_ms, end_ms = int(payload.get("start_ms", 0)), int(payload.get("end_ms", 0))
        if start_ms < 0 or end_ms <= start_ms:
            raise ValueError("end_ms must be greater than start_ms")
        size = payload.get("target_size")
        target_size = None
        if size is not None:
            if not isinstance(size, (list, tuple)) or len(size) != 2:
                raise ValueError("target_size must be [width, height]")
            target_size = (max(1, int(size[0])), max(1, int(size[1])))
        job_id = re.sub(r"[^A-Za-z0-9_.-]", "_", str(payload.get("job_id", "job")))
        return cls(
            job_id=job_id,
            source_uri=source_uri,
            mode=mode,
            start_ms=start_ms,
            end_ms=end_ms,
            fps=max(1, min(int(payload.get("fps", 24)), 120)),
            output_prefix=str(payload.get("output_prefix", f"cloud-jobs/{job_id}")),
            target_size=target_size,
        )


def build_commands(job: ExtractionJob, source: Path, output_dir: Path) -> list[list[str]]:
    """Return bounded-memory FFmpeg command(s) for a validated cloud job."""
    start, duration = job.start_ms / 1000, (job.end_ms - job.start_ms) / 1000
    common = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-nostats", "-threads", "2"]
    scale = [f"scale={job.target_size[0]}:{job.target_size[1]}:flags=lanczos"] if job.target_size else []
    seek = ["-ss", str(start), "-t", str(duration), "-i", str(source)]
    if job.mode == "range":
        filters = [*scale, f"fps={job.fps}"]
        return [[*common, *seek, "-vf", ",".join(filters), str(output_dir / "frame_%06d.png")]]
    if job.mode == "video":
        filters = scale + [f"fps=min(fps\\,{job.fps})"]
        return [[
            *common, *seek, "-vf", ",".join(filters), "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-an", str(output_dir / "clip.mp4"),
        ]]

    base_filters = ",".join([f"fps={job.fps}", *scale])
    palette = output_dir / "palette.png"
    return [
        [*common, *seek, "-vf", f"{base_filters},palettegen=max_colors=256:stats_mode=diff", str(palette)],
        [
            *common, *seek, "-i", str(palette), "-lavfi",
            f"{base_filters}[x];[x][1:v]paletteuse=dither=bayer", str(output_dir / "clip.gif"),
        ],
    ]


def run_commands(commands: list[list[str]], timeout_seconds: int = 1700) -> None:
    """Run each FFmpeg phase inside the Cloud Run request-time budget."""
    for command in commands:
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )

"""Shared extraction pipeline mechanics (ui-arch-41 / #563, R2.a).

One implementation of the ffmpeg launch/wait/cancel/progress mechanics
previously copied across ``video_extractor_worker``,
``gif_extractor_worker``, and the nested helpers in
``queue_execution_worker.run_extraction_in_process``. Workers keep their
constructors, moviepy paths, and command construction; they delegate the
shared mechanics here with no behavior change.

Cancellation: ``is_cancelled`` is polled while ffmpeg runs; a cancel
terminates the process (``terminate`` → bounded ``wait`` → ``kill``) and
raises :class:`ExtractionCancelled`. ``stderr`` always goes to a temp
file — never a PIPE drained only after exit (the #484 deadlock class).
"""

from __future__ import annotations

import contextlib
import os
import select
import subprocess
import tempfile
import time
from typing import Callable, Optional


class ExtractionCancelled(Exception):
    """Raised when the user cancels mid-ffmpeg."""


def _never_cancelled() -> bool:
    return False


def _ffmpeg_thread_count(requested: int) -> int:
    """Cap libx264 thread fan-out. 0 (Auto) → min(4, CPUs); never above CPU count."""
    cpus = os.cpu_count() or 2
    if requested <= 0:
        return max(1, min(4, cpus))
    return max(1, min(int(requested), cpus))


def parse_ffmpeg_progress_line(line: str, duration_s: float) -> Optional[int]:
    """Map an ffmpeg ``-progress`` ``out_time_us=`` line to 0–99 percent."""
    if duration_s <= 0:
        return None
    text = line.strip()
    if not text.startswith("out_time_us="):
        return None
    raw = text.split("=", 1)[1]
    if raw in ("N/A", ""):
        return None
    try:
        us = int(raw)
    except ValueError:
        return None
    if us < 0:
        return None
    return int(min(99, max(0, (us / 1_000_000.0) / duration_s * 100)))


def get_keep_regions(cuts_ms, t_start: float, t_end: float) -> list:
    """Merge cut ranges and return the kept ``(start, end)`` regions."""
    if not cuts_ms:
        return [(0.0, t_end - t_start)]
    sorted_cuts = sorted([(max(t_start, c[0] / 1000.0), min(t_end, c[1] / 1000.0)) for c in cuts_ms])
    merged_cuts = []
    for c in sorted_cuts:
        if c[0] >= c[1]:
            continue
        if not merged_cuts:
            merged_cuts.append(c)
        else:
            last = merged_cuts[-1]
            if c[0] <= last[1]:
                merged_cuts[-1] = (last[0], max(last[1], c[1]))
            else:
                merged_cuts.append(c)
    keep = []
    current = t_start
    for c_start, c_end in merged_cuts:
        if c_start > current:
            keep.append((current - t_start, c_start - t_start))
        current = max(current, c_end)
    if current < t_end:
        keep.append((current - t_start, t_end - t_start))
    return keep


def _terminate(proc: "subprocess.Popen[str]") -> None:
    proc.terminate()
    with contextlib.suppress(subprocess.TimeoutExpired):
        proc.wait(timeout=3)
    if proc.poll() is None:
        proc.kill()


def run_ffmpeg(
    cmd: list,
    error_prefix: str,
    duration_s: float = 0.0,
    progress: Optional[Callable[[int, int], None]] = None,
    is_cancelled: Optional[Callable[[], bool]] = None,
) -> None:
    """Run one ffmpeg command with deadlock-free IO and cancel support.

    ``progress`` None → quiet mode (stdout to DEVNULL, poll loop);
    otherwise stdout ``-progress`` lines are parsed and reported as
    ``(percent, 100)``. ``error_prefix`` keeps each caller's exact
    failure text: the raised message is
    ``f"{error_prefix}{returncode}\\n{stderr_tail}"``.
    """
    from gui.src.helpers.video.video_thumbnailer import media_backend_spawn_guard

    cancelled = is_cancelled or _never_cancelled
    last_pct = -1

    def _report(pct: Optional[int]) -> None:
        nonlocal last_pct
        if progress is not None and pct is not None and pct != last_pct:
            last_pct = pct
            progress(pct, 100)

    with tempfile.TemporaryFile(mode="w+") as errf:
        with media_backend_spawn_guard():
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE if progress is not None else subprocess.DEVNULL,
                stderr=errf,
                stdin=subprocess.DEVNULL,
                text=True,
                bufsize=1,
            )
        stdout = proc.stdout
        while True:
            if cancelled():
                _terminate(proc)
                raise ExtractionCancelled()
            if proc.poll() is not None:
                if progress is not None and stdout is not None:
                    for line in stdout.read().splitlines():
                        _report(parse_ffmpeg_progress_line(line, duration_s))
                break
            if progress is None or stdout is None:
                time.sleep(0.3)
                continue
            ready, _, _ = select.select([stdout], [], [], 0.2)
            if not ready:
                continue
            line = stdout.readline()
            if not line:
                continue
            _report(parse_ffmpeg_progress_line(line, duration_s))
        if proc.returncode != 0:
            errf.seek(0)
            tail = errf.read()[-2000:]
            raise RuntimeError(f"{error_prefix}{proc.returncode}\n{tail}")


__all__ = [
    "ExtractionCancelled",
    "_ffmpeg_thread_count",
    "parse_ffmpeg_progress_line",
    "get_keep_regions",
    "run_ffmpeg",
]

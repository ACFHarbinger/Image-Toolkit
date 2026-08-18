"""Video-duration probing helpers for the "Smart Video Slideshow" interval.

Extracted from ``system_display_subtab.py`` -- pure code motion, no logic
change, to keep the file under the codebase's 500-code-line convention
(§5.17).
"""

from __future__ import annotations

import os
import subprocess
from typing import Optional
from gui.src.constants.elements import _VIDEO_DURATION_CACHE


def _is_video(path: str) -> bool:
    from backend.src.constants import SUPPORTED_VIDEO_FORMATS

    return os.path.splitext(path)[1].lower() in SUPPORTED_VIDEO_FORMATS


def _get_video_duration(path: str) -> Optional[float]:
    """Return video duration in seconds via ffprobe, falling back to cv2."""
    if path in _VIDEO_DURATION_CACHE:
        return _VIDEO_DURATION_CACHE[path]
    try:
        # Issue #81 crash family: this ffprobe fork can race the first
        # QMediaPlayer construction (slideshow start / app startup).
        from gui.src.helpers.video.video_thumbnailer import media_backend_spawn_guard

        with media_backend_spawn_guard():
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", path],
                capture_output=True, text=True, timeout=10,
            )
        val = result.stdout.strip()
        if val:
            dur = float(val)
            _VIDEO_DURATION_CACHE[path] = dur
            return dur
    except Exception:
        pass
    try:
        import cv2  # type: ignore

        cap = cv2.VideoCapture(path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        cap.release()
        if fps > 0:
            dur = frames / fps
            _VIDEO_DURATION_CACHE[path] = dur
            return dur
    except Exception:
        pass
    return None


__all__ = ["_is_video", "_get_video_duration", "_VIDEO_DURATION_CACHE"]

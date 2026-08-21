"""Qt Multimedia backend pinning (issue #374).

PySide6's bundled Qt ships ONLY the FFmpeg multimedia backend
(``Qt/plugins/multimedia/libffmpegmediaplugin.so``); there is no GStreamer
backend plugin in the wheel. A machine-wide ``QT_MEDIA_BACKEND=gstreamer``
(e.g. left over from the #373 KDE-smart-video-wallpaper investigation, set in
``/etc/environment``) therefore makes every ``QMediaPlayer`` fail to
initialize ("No QtMultimedia backends found ... Failed to initialize
QMediaPlayer") and the Extractor tab's in-app video player shows black for
every video.

This helper must run before the first ``QMediaPlayer``/``QGraphicsVideoItem``
is constructed (Qt Multimedia selects its backend lazily at first use), so it
is invoked at the very top of both app entry points (``backend/main.py`` and
``gui/__main__.py``) before any Qt import.
"""

from __future__ import annotations

import os


def pin_qt_media_backend() -> str:
    """Force ``QT_MEDIA_BACKEND=ffmpeg`` (the only backend the PySide6 wheel
    ships) and return the effective value.

    Unconditional: even an unset variable defaults to FFmpeg in this Qt
    build, and any other value (e.g. the broken ``gstreamer``) cannot work
    with the bundled plugin set.
    """
    os.environ["QT_MEDIA_BACKEND"] = "ffmpeg"
    return os.environ["QT_MEDIA_BACKEND"]


__all__ = ["pin_qt_media_backend"]

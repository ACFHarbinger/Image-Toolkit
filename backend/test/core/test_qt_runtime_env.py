"""Tests for the Qt Multimedia backend pinning helper (issue #374).

PySide6's bundled Qt ships only the FFmpeg multimedia backend plugin
(``libffmpegmediaplugin.so``); there is no GStreamer backend in the wheel. A
machine-wide ``QT_MEDIA_BACKEND=gstreamer`` (left over from the #373
KDE-wallpaper investigation in ``/etc/environment``) therefore makes every
``QMediaPlayer`` fail to initialize ("No QtMultimedia backends found") and the
Extractor tab's video player shows black for every video. The helper pins the
backend to the one this distribution actually ships.
"""

import os

from backend.src.qt_runtime_env import pin_qt_media_backend


def test_pin_qt_media_backend_overrides_gstreamer(monkeypatch):
    monkeypatch.setenv("QT_MEDIA_BACKEND", "gstreamer")
    assert pin_qt_media_backend() == "ffmpeg"
    assert os.environ["QT_MEDIA_BACKEND"] == "ffmpeg"


def test_pin_qt_media_backend_when_unset(monkeypatch):
    monkeypatch.delenv("QT_MEDIA_BACKEND", raising=False)
    assert pin_qt_media_backend() == "ffmpeg"
    assert os.environ["QT_MEDIA_BACKEND"] == "ffmpeg"


def test_pin_qt_media_backend_keeps_ffmpeg(monkeypatch):
    monkeypatch.setenv("QT_MEDIA_BACKEND", "ffmpeg")
    assert pin_qt_media_backend() == "ffmpeg"
    assert os.environ["QT_MEDIA_BACKEND"] == "ffmpeg"

"""Recent-extraction -> queue-config conversion (pure logic, no Qt)."""

from __future__ import annotations

from gui.src.tabs.core.extractor_tab._video_session_history import (
    _VideoSessionHistoryMixin,
)


class _Host(_VideoSessionHistoryMixin):
    extraction_dir = "/tmp/extract-out"


def test_range_run_maps_all_fields():
    cfg = _Host()._recent_run_to_queue_config(
        {
            "video_path": "/v/a.mp4",
            "start_ms": 1000,
            "end_ms": 5000,
            "output_size": "1280x720",
            "engine": "MoviePy",
            "frame_interval": 3,
            "smart_extract": True,
            "smart_method": "mpdecimate",
            "gif_fps": 30,
            "mute_audio": True,
            "speed": "2x",
            "cuts_ms": [[1, 2]],
        }
    )
    assert cfg["type"] == "range"
    assert cfg["target_resolution"] == (1280, 720)
    assert cfg["use_ffmpeg"] is False  # MoviePy
    assert cfg["frame_interval"] == 3
    assert cfg["fps"] == 30
    assert cfg["mute_audio"] is True
    assert cfg["output_dir"] == "/tmp/extract-out"
    assert cfg["cuts_ms"] == [[1, 2]]


def test_single_frame_run_and_defaults():
    cfg = _Host()._recent_run_to_queue_config(
        {"video_path": "x", "start_ms": 7, "end_ms": 7, "engine": "FFmpeg"}
    )
    assert cfg["type"] == "single"
    assert cfg["target_resolution"] is None
    assert cfg["use_ffmpeg"] is True
    assert cfg["frame_interval"] == 1
    assert cfg["speed"] == "1.0"


def test_bad_output_size_falls_back_to_none():
    cfg = _Host()._recent_run_to_queue_config(
        {"video_path": "x", "output_size": "garbage", "start_ms": 0, "end_ms": 1}
    )
    assert cfg["target_resolution"] is None

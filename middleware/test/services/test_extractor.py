from __future__ import annotations

import json
import subprocess

import pytest
from middleware.src.services.extractor.probe import probe_video


def test_missing_file_does_not_launch_ffprobe(tmp_path, monkeypatch) -> None:
    def refuse(*_args, **_kwargs):
        raise AssertionError("ffprobe must not run")

    monkeypatch.setattr(subprocess, "run", refuse)
    result = probe_video(str(tmp_path / "missing.mp4"))
    assert result["available"] is False
    assert result["error"] == "not a file"


def test_probe_reads_the_first_video_stream(tmp_path, monkeypatch) -> None:
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"not a real video")
    payload = {
        "streams": [
            {"codec_type": "audio", "codec_name": "aac"},
            {"codec_type": "video", "codec_name": "h264", "width": 320, "height": 240, "duration": "1.5"},
        ],
        "format": {"duration": "9"},
    }

    def fake_run(args, **_kwargs):
        assert args[0] == "ffprobe"
        assert args[-1] == str(video)
        assert "-show_streams" in args

        class Completed:
            returncode = 0
            stdout = json.dumps(payload).encode()

        return Completed()

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = probe_video(str(video))
    assert result["available"] is True
    assert result["width"] == 320
    assert result["height"] == 240
    assert result["duration_seconds"] == 1.5
    assert result["codec"] == "h264"
    assert result["error"] == ""


@pytest.mark.parametrize("duration", ["inf", "nan", "1e999"])
def test_probe_never_returns_nonfinite_duration(tmp_path, monkeypatch, duration):
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"placeholder")
    payload = {"streams": [{"codec_type": "video", "duration": duration, "width": 320, "height": 240}]}
    monkeypatch.setattr(
        subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess([], 0, json.dumps(payload).encode())
    )
    result = probe_video(str(path))
    assert result["duration_seconds"] == 0.0
    json.dumps(result, allow_nan=False)


def test_probe_rejects_a_nonobject_document(tmp_path, monkeypatch):
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"placeholder")
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess([], 0, b"[]"))
    result = probe_video(str(path))
    assert result["available"] is False
    assert result["error"] == "ffprobe failed"

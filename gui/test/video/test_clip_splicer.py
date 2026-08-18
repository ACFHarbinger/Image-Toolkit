from __future__ import annotations

import json
from types import SimpleNamespace

from gui.src.helpers.video import clip_splicer


def test_splice_uses_concat_copy_for_matching_streams(monkeypatch, tmp_path):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        if command[0] == "ffprobe":
            return SimpleNamespace(stdout=json.dumps({"streams": [{"codec_type": "video", "codec_name": "h264"}]}))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(clip_splicer.subprocess, "run", fake_run)
    output = clip_splicer.splice_clips(
        [clip_splicer.ClipSegment("a.mp4", 1000, 3000), clip_splicer.ClipSegment("b.mp4")],
        tmp_path / "out.mp4",
    )

    ffmpeg = calls[-1][0]
    assert output == tmp_path / "out.mp4"
    assert ffmpeg[ffmpeg.index("-c") : ffmpeg.index("-c") + 2] == ["-c", "copy"]


def test_splice_reencodes_incompatible_streams(monkeypatch, tmp_path):
    probe_count = 0
    calls = []

    def fake_run(command, **kwargs):
        nonlocal probe_count
        calls.append(command)
        if command[0] == "ffprobe":
            probe_count += 1
            codec = "h264" if probe_count == 1 else "vp9"
            return SimpleNamespace(stdout=json.dumps({"streams": [{"codec_type": "video", "codec_name": codec}]}))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(clip_splicer.subprocess, "run", fake_run)
    clip_splicer.splice_clips(
        [clip_splicer.ClipSegment("a.mp4"), clip_splicer.ClipSegment("b.webm")],
        tmp_path / "out.mp4",
    )

    ffmpeg = calls[-1]
    assert "-c:v" in ffmpeg
    assert ffmpeg[ffmpeg.index("-c:v") : ffmpeg.index("-c:a") + 2] == [
        "-c:v", "libx264", "-c:a", "aac",
    ]

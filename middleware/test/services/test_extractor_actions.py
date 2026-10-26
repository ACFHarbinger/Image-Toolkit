from __future__ import annotations

import subprocess
from pathlib import Path

from middleware.src.services.extractor.actions import cut_sheet, extract_range, snapshot_frame
from PIL import Image


def test_snapshot_reports_missing_ffmpeg_without_writing(tmp_path, monkeypatch) -> None:
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"video")
    output = tmp_path / "frame.png"

    def refuse(*_args, **_kwargs):
        raise AssertionError("ffmpeg must not run")

    monkeypatch.setattr("middleware.src.services.extractor.actions.shutil.which", lambda _name: None)
    monkeypatch.setattr(subprocess, "run", refuse)
    result = snapshot_frame(str(video), 1.25, str(output))
    assert result == {"written": False, "output_path": str(output), "error": "ffmpeg is not available"}
    assert not output.exists()


def test_snapshot_writes_the_ffmpeg_output(tmp_path, monkeypatch) -> None:
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"video")
    output = tmp_path / "frame.png"

    def fake_run(args, **_kwargs):
        assert args[0] == "/usr/bin/ffmpeg"
        assert args[-1] != str(output)
        assert "-frames:v" in args
        Path(args[-1]).write_bytes(b"frame-bytes")
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr("middleware.src.services.extractor.actions.shutil.which", lambda _name: "/usr/bin/ffmpeg")
    monkeypatch.setattr(subprocess, "run", fake_run)
    result = snapshot_frame(str(video), 0.5, str(output))
    assert result["written"] is True
    assert output.read_bytes() == b"frame-bytes"


def test_range_extract_cleans_up_a_failed_ffmpeg(tmp_path, monkeypatch) -> None:
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"video")
    output = tmp_path / "clip-out.mp4"

    def fake_run(args, **_kwargs):
        assert args[-1] != str(output)
        Path(args[-1]).write_bytes(b"")
        return subprocess.CompletedProcess(args, 1)

    monkeypatch.setattr("middleware.src.services.extractor.actions.shutil.which", lambda _name: "/usr/bin/ffmpeg")
    monkeypatch.setattr(subprocess, "run", fake_run)
    result = extract_range(str(video), 0, 1.5, str(output))
    assert result["written"] is False
    assert result["error"] == "ffmpeg failed"
    assert not output.exists()


def test_failed_extract_keeps_an_existing_destination(tmp_path, monkeypatch) -> None:
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"video")
    output = tmp_path / "clip-out.mp4"
    output.write_bytes(b"keep-me")

    def fake_run(args, **_kwargs):
        assert args[-1] != str(output)
        return subprocess.CompletedProcess(args, 1)

    monkeypatch.setattr("middleware.src.services.extractor.actions.shutil.which", lambda _name: "/usr/bin/ffmpeg")
    monkeypatch.setattr(subprocess, "run", fake_run)
    result = extract_range(str(video), 0, 1.5, str(output))
    assert result["written"] is False
    assert output.read_bytes() == b"keep-me"
    assert list(tmp_path.glob("*.partial")) == []


def test_cut_honors_offset_spacing_and_partial_last_frame(tmp_path) -> None:
    sheet = tmp_path / "sheet.png"
    with Image.new("RGB", (10, 4), (0, 0, 255)) as image:
        for y in range(4):
            image.putpixel((0, y), (255, 0, 0))
        image.save(sheet)
    output = tmp_path / "frames"
    output.mkdir()
    whole = cut_sheet(str(sheet), str(output), "horizontal", 3, 1, 1, 0, 1, False)
    assert whole["written"] is True
    assert whole["width"] == 10
    assert whole["height"] == 4
    assert len(whole["paths"]) == 2
    with Image.open(whole["paths"][0]) as frame:
        assert frame.size == (3, 4)
        assert frame.getpixel((0, 0)) == (0, 0, 255)
    partial = cut_sheet(str(sheet), str(output), "horizontal", 3, 1, 1, 0, 1, True)
    assert len(partial["paths"]) == 3
    with Image.open(partial["paths"][-1]) as frame:
        assert frame.size == (1, 4)


def test_grid_partial_includes_the_bottom_right_intersection(tmp_path) -> None:
    sheet = tmp_path / "sheet.png"
    with Image.new("RGB", (25, 25), (0, 0, 0)) as image:
        image.putpixel((24, 24), (255, 0, 0))
        image.save(sheet)
    output = tmp_path / "frames"
    output.mkdir()
    result = cut_sheet(str(sheet), str(output), "grid", 10, 10, 0, 0, 0, True)
    assert result["written"] is True
    assert len(result["paths"]) == 9
    with Image.open(result["paths"][-1]) as frame:
        assert frame.size == (5, 5)
        assert frame.getpixel((4, 4)) == (255, 0, 0)

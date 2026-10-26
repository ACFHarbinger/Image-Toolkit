from __future__ import annotations

import subprocess
from pathlib import Path

from middleware.src.bridge import Cancelled
from middleware.src.services.extractor.actions import cut_sheet, extract_range, snapshot_frame
from PIL import Image


class _Finished:
    def __init__(self, args: list[str], *, code: int = 0, payload: bytes = b"frame-bytes") -> None:
        self.args = args
        self.pid = None
        self.returncode: int | None = None
        self.payload = payload
        self.code = code

    def poll(self) -> int | None:
        return self.returncode

    def wait(self, timeout: float | None = None) -> int:
        del timeout
        if self.returncode is None:
            if self.code == 0 and self.payload:
                Path(self.args[-1]).write_bytes(self.payload)
            self.returncode = self.code
        return self.returncode

    def terminate(self) -> None:
        self.returncode = -15

    def kill(self) -> None:
        self.terminate()


class _Running:
    def __init__(self, args: list[str]) -> None:
        self.args = args
        self.pid = None
        self.returncode: int | None = None
        self.terminated = False
        Path(args[-1]).write_bytes(b"partial")

    def poll(self) -> int | None:
        return self.returncode

    def wait(self, timeout: float | None = None) -> int:
        if self.terminated:
            self.returncode = -15
            return self.returncode
        raise subprocess.TimeoutExpired(self.args, timeout or 0.2)

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.terminate()


def test_snapshot_reports_missing_ffmpeg_without_writing(tmp_path, monkeypatch) -> None:
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"video")
    output = tmp_path / "frame.png"

    def refuse(*_args, **_kwargs):
        raise AssertionError("ffmpeg must not run")

    monkeypatch.setattr("middleware.src.services.extractor.actions.shutil.which", lambda _name: None)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    result = snapshot_frame(str(video), 1.25, str(output))
    assert result == {"written": False, "output_path": str(output), "error": "ffmpeg is not available"}
    assert not output.exists()


def test_snapshot_writes_the_ffmpeg_output(tmp_path, monkeypatch) -> None:
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"video")
    output = tmp_path / "frame.png"

    def fake_popen(args, **_kwargs):
        assert args[0] == "/usr/bin/ffmpeg"
        assert Path(args[-1]).suffix == output.suffix
        assert args[-1] != str(output)
        assert "-frames:v" in args
        return _Finished(args)

    monkeypatch.setattr("middleware.src.services.extractor.actions.shutil.which", lambda _name: "/usr/bin/ffmpeg")
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    result = snapshot_frame(str(video), 0.5, str(output))
    assert result["written"] is True
    assert output.read_bytes() == b"frame-bytes"


def test_range_extract_cleans_up_a_failed_ffmpeg(tmp_path, monkeypatch) -> None:
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"video")
    output = tmp_path / "clip-out.mp4"

    def fake_popen(args, **_kwargs):
        assert Path(args[-1]).suffix == ".mp4"
        assert args[-1] != str(output)
        return _Finished(args, code=1, payload=b"")

    monkeypatch.setattr("middleware.src.services.extractor.actions.shutil.which", lambda _name: "/usr/bin/ffmpeg")
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    result = extract_range(str(video), 0, 1.5, str(output))
    assert result["written"] is False
    assert result["error"] == "ffmpeg failed"
    assert not output.exists()


def test_failed_extract_keeps_an_existing_destination(tmp_path, monkeypatch) -> None:
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"video")
    output = tmp_path / "clip-out.mp4"
    output.write_bytes(b"keep-me")

    def fake_popen(args, **_kwargs):
        assert Path(args[-1]).suffix == ".mp4"
        assert args[-1] != str(output)
        return _Finished(args, code=1, payload=b"")

    monkeypatch.setattr("middleware.src.services.extractor.actions.shutil.which", lambda _name: "/usr/bin/ffmpeg")
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
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


def test_grid_partial_clips_when_no_full_frame_fits(tmp_path) -> None:
    sheet = tmp_path / "sheet.png"
    with Image.new("RGB", (100, 100), (255, 0, 0)) as image:
        with Image.new("RGB", (100, 50), (0, 255, 0)) as lower:
            image.paste(lower, (0, 50))
        image.save(sheet)
    output = tmp_path / "frames"
    output.mkdir()
    skipped = cut_sheet(str(sheet), str(output), "grid", 200, 50, 0, 0, 0, False)
    assert skipped["written"] is False
    assert skipped["paths"] == []
    assert skipped["error"] == "no frames"
    assert list(output.glob("*.png")) == []
    result = cut_sheet(str(sheet), str(output), "grid", 200, 50, 0, 0, 0, True)
    assert result["written"] is True
    assert len(result["paths"]) == 2
    with Image.open(result["paths"][0]) as frame:
        assert frame.size == (100, 50)
        assert frame.getpixel((0, 0)) == (255, 0, 0)
        assert frame.getpixel((99, 49)) == (255, 0, 0)
    with Image.open(result["paths"][1]) as frame:
        assert frame.size == (100, 50)
        assert frame.getpixel((0, 0)) == (0, 255, 0)
        assert frame.getpixel((99, 49)) == (0, 255, 0)


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


def test_cut_rejects_every_crop_that_would_replace_the_source(tmp_path) -> None:
    output = tmp_path / "frames"
    output.mkdir()
    sheet = output / "frame_002.png"
    with Image.new("RGB", (4, 2), (255, 0, 0)) as image:
        image.save(sheet)
    original = sheet.read_bytes()
    result = cut_sheet(str(sheet), str(output), "grid", 2, 2, 0, 0, 0, False)
    assert result["written"] is False
    assert result["paths"] == []
    assert result["error"] == "output matches an input"
    assert sheet.read_bytes() == original
    assert not (output / "frame_001.png").exists()


def test_cut_preserves_alpha_and_indexed_transparency(tmp_path) -> None:
    output = tmp_path / "frames"
    output.mkdir()
    rgba = tmp_path / "rgba.png"
    with Image.new("RGBA", (4, 2), (0, 0, 0, 0)) as image:
        image.putpixel((0, 0), (10, 20, 30, 255))
        image.save(rgba)
    result = cut_sheet(str(rgba), str(output), "grid", 2, 2, 0, 0, 0, False)
    assert result["written"] is True
    with Image.open(result["paths"][0]) as frame:
        assert frame.mode == "RGBA"
        assert frame.getpixel((0, 0)) == (10, 20, 30, 255)
        assert frame.getpixel((1, 1))[3] == 0

    indexed = tmp_path / "indexed.png"
    with Image.new("P", (2, 2)) as image:
        image.putpalette([0, 0, 0, 255, 0, 0] + [0] * (768 - 6))
        image.putpixel((0, 0), 1)
        image.putpixel((1, 0), 0)
        image.putpixel((0, 1), 0)
        image.putpixel((1, 1), 0)
        image.save(indexed, transparency=0)
    indexed_out = tmp_path / "indexed-frames"
    indexed_out.mkdir()
    cut = cut_sheet(str(indexed), str(indexed_out), "grid", 2, 2, 0, 0, 0, False)
    assert cut["written"] is True
    with Image.open(cut["paths"][0]) as frame:
        assert frame.mode == "RGBA"
        assert frame.getpixel((0, 0))[3] == 255
        assert frame.getpixel((1, 0))[3] == 0


def test_cancel_stops_ffmpeg_and_keeps_the_destination(tmp_path, monkeypatch) -> None:
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"video")
    output = tmp_path / "frame.png"
    output.write_bytes(b"keep-me")
    running: list[_Running] = []

    def fake_popen(args, **_kwargs):
        process = _Running(args)
        running.append(process)
        return process

    monkeypatch.setattr("middleware.src.services.extractor.actions.shutil.which", lambda _name: "/usr/bin/ffmpeg")
    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    def cancel() -> None:
        raise Cancelled("job")

    try:
        snapshot_frame(str(video), 0.5, str(output), raise_if_cancelled=cancel)
    except Cancelled:
        pass
    else:
        raise AssertionError("cancel must leave the snapshot")
    assert running[0].terminated is True
    assert output.read_bytes() == b"keep-me"
    assert list(tmp_path.glob(".*")) == []


def test_cancel_after_ffmpeg_does_not_publish(tmp_path, monkeypatch) -> None:
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"video")
    output = tmp_path / "frame.png"
    output.write_bytes(b"keep-me")
    checks = {"count": 0}

    def fake_popen(args, **_kwargs):
        return _Finished(args, payload=b"new-frame")

    def cancel() -> None:
        checks["count"] += 1
        if checks["count"] >= 2:
            raise Cancelled("job")

    monkeypatch.setattr("middleware.src.services.extractor.actions.shutil.which", lambda _name: "/usr/bin/ffmpeg")
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    try:
        snapshot_frame(str(video), 0.5, str(output), raise_if_cancelled=cancel)
    except Cancelled:
        pass
    else:
        raise AssertionError("cancel must win before publish")
    assert output.read_bytes() == b"keep-me"

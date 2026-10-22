"""S-01 stills stay inside the caller cache and do not return pixels."""

from __future__ import annotations

import shutil
import subprocess
import threading
from pathlib import Path

import pytest
from middleware.src.shell.render_cache import (
    PreviewCancelled,
    request_animated_preview,
    write_render_stills,
)


def _ppm(path: Path, width: int = 80, height: int = 40) -> None:
    header = f"P6\n{width} {height}\n255\n".encode()
    path.write_bytes(header + bytes([40, 80, 120]) * (width * height))


def _clip(path: Path, frames: int = 9) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        pytest.skip("ffmpeg is not installed")
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=green:s=64x48:r=1",
            "-frames:v",
            str(frames),
            str(path),
        ],
        check=True,
        capture_output=True,
    )


def _jpeg_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    index = 2
    while index + 8 < len(data):
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        if marker in (0xC0, 0xC1, 0xC2):
            height = int.from_bytes(data[index + 5 : index + 7], "big")
            width = int.from_bytes(data[index + 7 : index + 9], "big")
            return width, height
        if marker == 0xD8 or marker == 0xD9:
            index += 2
            continue
        length = int.from_bytes(data[index + 2 : index + 4], "big")
        index += 2 + length
    raise AssertionError(f"no JPEG frame header in {path}")


def test_image_still_is_bounded_and_stays_in_the_cache(tmp_path: Path):
    source = tmp_path / "wide.ppm"
    cache = tmp_path / "render"
    _ppm(source, width=400, height=100)
    stills = write_render_stills([str(source)], cache_dir=cache, max_edge=64)
    assert len(stills) == 1
    still = stills[0]
    assert still.error == ""
    assert still.kind == "image"
    assert still.frame_index == -1
    written = Path(still.cache_path)
    assert written.is_file()
    assert cache.resolve() in written.resolve().parents
    width, height = _jpeg_size(written)
    assert max(width, height) <= 64
    assert written.stat().st_size < source.stat().st_size


def test_video_still_uses_the_middle_reported_frame(tmp_path: Path):
    source = tmp_path / "clip.mp4"
    _clip(source, frames=9)
    stills = write_render_stills([str(source)], cache_dir=tmp_path / "render", max_edge=32)
    still = stills[0]
    assert still.error == ""
    assert still.kind == "video"
    assert still.frame_index == 4
    width, height = _jpeg_size(Path(still.cache_path))
    assert max(width, height) <= 32


def test_missing_source_reports_an_error_without_a_cache_path(tmp_path: Path):
    stills = write_render_stills([str(tmp_path / "missing.png")], cache_dir=tmp_path / "render")
    assert stills[0].cache_path == ""
    assert stills[0].error


def test_animated_preview_cancel_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    home_cache = tmp_path / "home-cache"
    monkeypatch.setattr(
        "middleware.src.shell.render_cache.default_render_cache",
        lambda: home_cache,
    )
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(PreviewCancelled):
        request_animated_preview(str(tmp_path / "clip.mp4"), cancel)
    assert not home_cache.exists()

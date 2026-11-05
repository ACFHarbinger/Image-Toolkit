"""SCANS fallback must not crash the batch when OpenCV returns status=1."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from middleware.src.stitching.alignment.canvas import _reuse_simple_stitch, _scan_stitch_fallback
from middleware.src.errors import CanvasError


def test_reuse_simple_stitch_copies_sibling(tmp_path: Path) -> None:
    from PIL import Image

    src = tmp_path / "opencv_stitch.png"
    dest = tmp_path / "panorama.png"
    Image.new("RGB", (6, 6), (1, 2, 3)).save(src)
    reused = _reuse_simple_stitch(str(dest))
    assert reused is not None
    assert dest.is_file()
    assert dest.stat().st_size == src.stat().st_size


def test_reuse_simple_stitch_missing_returns_none(tmp_path: Path) -> None:
    dest = tmp_path / "panorama.png"
    assert _reuse_simple_stitch(str(dest)) is None


def test_scan_fallback_reuses_simple_stitch_when_stitcher_fails(tmp_path: Path) -> None:
    """One tiny frame cannot stitch (status=1); sibling opencv_stitch is used."""
    from PIL import Image

    simple = tmp_path / "opencv_stitch.png"
    Image.new("RGB", (8, 8), (20, 40, 60)).save(simple)
    dest = tmp_path / "panorama.png"
    frames = [np.zeros((4, 4, 3), dtype=np.uint8)]
    out = _scan_stitch_fallback(frames, str(dest))
    assert dest.is_file()
    assert out.size == (8, 8)


def test_reuse_simple_stitch_finds_parent_output_dir(tmp_path: Path) -> None:
    """Bench writes run_output.png under panorama_stages/; stitch is one level up."""
    from PIL import Image

    out_dir = tmp_path / "output"
    stages = out_dir / "panorama_stages"
    stages.mkdir(parents=True)
    Image.new("RGB", (10, 10), (9, 8, 7)).save(out_dir / "opencv_stitch.png")
    dest = stages / "run_output.png"
    reused = _reuse_simple_stitch(str(dest))
    assert reused is not None
    assert dest.is_file()


def test_scan_fallback_raises_when_no_retry_and_no_sibling(tmp_path: Path) -> None:
    dest = tmp_path / "panorama.png"
    with pytest.raises(CanvasError, match="SCANS fallback failed"):
        _scan_stitch_fallback([], str(dest))


def _record_attempts(monkeypatch) -> list[int]:
    """Patch the Stitcher attempt to fail and record each frame-set size."""
    from middleware.src.stitching.alignment import canvas

    seen: list[int] = []

    def fake(frames, mode, resol):
        seen.append(len(frames))
        return 1, None

    monkeypatch.setattr(canvas, "_try_opencv_stitch", fake)
    return seen


def test_scan_fallback_tries_full_set_first_when_dedup_left_too_few(
    tmp_path: Path, monkeypatch
) -> None:
    """asp_test79: dedup on bad edges left 2 of 27 frames; SCANS needs the rest."""
    seen = _record_attempts(monkeypatch)
    full = [np.zeros((8, 8, 3), np.uint8) for _ in range(27)]
    with pytest.raises(CanvasError):
        _scan_stitch_fallback(full[:2], str(tmp_path / "p.png"), full_frames=full)
    assert seen[0] == 27 and 2 in seen


def test_scan_fallback_keeps_dedup_set_first_when_it_is_substantial(
    tmp_path: Path, monkeypatch
) -> None:
    seen = _record_attempts(monkeypatch)
    full = [np.zeros((8, 8, 3), np.uint8) for _ in range(16)]
    with pytest.raises(CanvasError):
        _scan_stitch_fallback(full[:13], str(tmp_path / "p.png"), full_frames=full)
    assert seen[0] == 13 and 16 in seen


def test_scan_fallback_without_full_set_is_unchanged(tmp_path: Path, monkeypatch) -> None:
    seen = _record_attempts(monkeypatch)
    frames = [np.zeros((8, 8, 3), np.uint8) for _ in range(5)]
    with pytest.raises(CanvasError):
        _scan_stitch_fallback(frames, str(tmp_path / "p.png"))
    assert set(seen) <= {5, 3}

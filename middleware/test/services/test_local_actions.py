"""Local vault and media actions used by the Tauri shell."""

from __future__ import annotations

from pathlib import Path

import pytest
from middleware.src.services.auth.session import unlock
from middleware.src.services.media.subtabs import dispatch
from middleware.src.services.merge.modes import run_merge
from PIL import Image


def test_blank_password_does_not_open_the_vault(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("vault opened")

    monkeypatch.setattr("middleware.src.services.auth.session.VaultManager", refuse)
    with pytest.raises(ValueError, match="password is empty"):
        unlock("keeper", "")


def test_resample_and_sheet_cut(tmp_path: Path) -> None:
    source = tmp_path / "sheet.png"
    Image.new("RGB", (4, 2), (10, 20, 30)).save(source)
    resized = tmp_path / "small.png"
    scaled = dispatch(
        {
            "action": "resample",
            "input_path": str(source),
            "output_path": str(resized),
            "mode": "factor",
            "factor": 0.5,
        }
    )
    assert scaled["success"] is True
    assert Image.open(resized).size == (2, 1)

    refused = dispatch(
        {
            "action": "resample",
            "input_path": str(source),
            "output_path": str(source),
            "mode": "factor",
            "factor": 0.5,
        }
    )
    assert refused["success"] is False
    assert Image.open(source).size == (4, 2)

    frames = tmp_path / "frames"
    cut = dispatch(
        {
            "action": "image_cut",
            "input_path": str(source),
            "output_dir": str(frames),
            "frame_width": 2,
            "frame_height": 2,
        }
    )
    assert cut["count"] == 2
    assert len(list(frames.glob("frame_*.png"))) == 2

    too_big = dispatch(
        {
            "action": "image_cut",
            "input_path": str(source),
            "output_dir": str(tmp_path / "none"),
            "frame_width": 8,
            "frame_height": 8,
        }
    )
    assert too_big["success"] is False
    assert too_big["count"] == 0


def test_canvas_places_both_images(tmp_path: Path) -> None:
    left = tmp_path / "a.png"
    right = tmp_path / "b.png"
    Image.new("RGB", (2, 2), (255, 0, 0)).save(left)
    Image.new("RGB", (2, 2), (0, 0, 255)).save(right)
    output = tmp_path / "canvas.png"
    result = run_merge(
        {
            "direction": "canvas",
            "paths": [str(left), str(right)],
            "output_path": str(output),
            "background": "white",
            "spacing": 0,
        }
    )
    assert result["written"] is True
    assert Image.open(output).size == (4, 2)

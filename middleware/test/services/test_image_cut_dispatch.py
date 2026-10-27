from __future__ import annotations

from pathlib import Path

from middleware.src.services.media.subtabs import dispatch
from PIL import Image


def test_image_cut_writes_frames_into_a_new_directory(tmp_path: Path) -> None:
    source = tmp_path / "sheet.png"
    Image.new("RGB", (8, 4), (1, 2, 3)).save(source)
    output_dir = tmp_path / "frames"
    result = dispatch(
        {
            "action": "image_cut",
            "input_path": str(source),
            "output_dir": str(output_dir),
            "arrangement": "grid",
            "frame_width": 4,
            "frame_height": 4,
            "offset_x": 0,
            "offset_y": 0,
            "spacing": 0,
            "include_partial": False,
        }
    )
    assert result["success"] is True
    assert result["count"] >= 1
    assert result["paths"]
    for path in result["paths"]:
        assert Path(path).is_file()
        assert path.endswith(".png")


def test_image_cut_missing_input_is_not_a_file(tmp_path: Path) -> None:
    result = dispatch(
        {
            "action": "image_cut",
            "input_path": str(tmp_path / "missing.png"),
            "output_dir": str(tmp_path / "frames"),
            "frame_width": 4,
            "frame_height": 4,
            "offset_x": 0,
            "offset_y": 0,
            "spacing": 0,
            "include_partial": False,
        }
    )
    assert result["success"] is False
    assert "not a file" in result["message"]

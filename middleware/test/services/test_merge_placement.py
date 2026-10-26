from __future__ import annotations

from middleware.src.services.merge.placement import place
from PIL import Image


def _png(path, color: tuple[int, int, int], size: tuple[int, int]) -> None:
    with Image.new("RGB", size, color) as image:
        image.save(path)


def test_placement_writes_rectangles(tmp_path) -> None:
    left = tmp_path / "left.png"
    right = tmp_path / "right.png"
    output = tmp_path / "out.png"
    _png(left, (255, 0, 0), (2, 2))
    _png(right, (0, 0, 255), (2, 2))
    result = place(
        [
            {"path": str(left), "x": 0, "y": 0, "width": 2, "height": 2},
            {"path": str(right), "x": 3, "y": 1, "width": 2, "height": 2},
        ],
        str(output),
    )
    assert result["written"] is True
    assert result["error"] == ""
    assert result["width"] == 5
    assert result["height"] == 3
    assert result["output_path"] == str(output)
    with Image.open(output) as image:
        assert image.size == (5, 3)
        assert image.getpixel((0, 0)) == (255, 0, 0)
        assert image.getpixel((2, 0)) == (255, 255, 255)
        assert image.getpixel((3, 1)) == (0, 0, 255)


def test_placement_refuses_a_missing_output_directory(tmp_path) -> None:
    image = tmp_path / "a.png"
    _png(image, (0, 0, 0), (1, 1))
    missing = tmp_path / "missing" / "out.png"
    result = place([{"path": str(image), "x": 0, "y": 0, "width": 1, "height": 1}], str(missing))
    assert result["written"] is False
    assert result["error"] == "output directory is missing"
    assert not missing.exists()

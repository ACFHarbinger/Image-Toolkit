from __future__ import annotations

import pytest
from middleware.src.services.similarity.compare import compare_paths, scan_directory
from PIL import Image


def _png(path, color: tuple[int, int, int]) -> None:
    with Image.new("RGB", (4, 4), color) as image:
        image.save(path)


def test_scan_lists_pairs_and_does_not_delete(tmp_path) -> None:
    _png(tmp_path / "a.png", (10, 20, 30))
    _png(tmp_path / "b.png", (10, 20, 30))
    with Image.new("RGB", (4, 4), (255, 255, 255)) as image:
        for x in range(2):
            for y in range(4):
                image.putpixel((x, y), (0, 0, 0))
        image.save(tmp_path / "c.png")
    (tmp_path / "notes.txt").write_text("keep")
    before = sorted(path.name for path in tmp_path.iterdir())
    result = scan_directory(str(tmp_path), 0)
    after = sorted(path.name for path in tmp_path.iterdir())
    assert before == after
    assert result["pairs"] == [{"left": str(tmp_path / "a.png"), "right": str(tmp_path / "b.png"), "distance": 0}]
    assert {item["path"] for item in result["items"]} == {str(tmp_path / "a.png"), str(tmp_path / "b.png"), str(tmp_path / "c.png")}


def test_scan_refuses_a_missing_directory(tmp_path) -> None:
    with pytest.raises(ValueError, match="not a directory"):
        scan_directory(str(tmp_path / "missing"), 8)


def test_compare_still_rejects_more_than_32_paths(tmp_path) -> None:
    paths = [str(tmp_path / f"{index}.png") for index in range(33)]
    with pytest.raises(ValueError, match="32"):
        compare_paths(paths, 0)

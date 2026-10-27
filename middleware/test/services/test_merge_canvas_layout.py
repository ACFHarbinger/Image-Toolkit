"""Canvas merge writes the editor's tile positions."""

from __future__ import annotations

from middleware.src.services.merge.modes import run_merge
from PIL import Image


def _png(path, color: tuple[int, int, int, int], size: tuple[int, int]) -> None:
    with Image.new("RGBA", size, color) as image:
        image.save(path)


def test_canvas_layout_pastes_where_the_editor_placed_each_tile(tmp_path) -> None:
    red = tmp_path / "red.png"
    blue = tmp_path / "blue.png"
    output = tmp_path / "out.png"
    _png(red, (255, 0, 0, 255), (2, 2))
    _png(blue, (0, 0, 255, 255), (2, 2))
    result = run_merge({
        "direction": "canvas",
        "paths": [str(red), str(blue)],
        "output_path": str(output),
        "background": "white",
        "canvas_width": 6,
        "canvas_height": 2,
        "canvas_layout": [
            {"path": str(red), "x": 0, "y": 0, "w": 2, "h": 2},
            {"path": str(blue), "x": 4, "y": 0, "w": 2, "h": 2},
        ],
    })
    assert result["written"] is True
    assert result["width"] == 6
    assert result["height"] == 2
    with Image.open(output) as image:
        assert image.getpixel((0, 0)) == (255, 0, 0, 255)
        assert image.getpixel((2, 0)) == (255, 255, 255, 255)
        assert image.getpixel((4, 0)) == (0, 0, 255, 255)


def test_canvas_preserves_translucent_pixels_with_and_without_layout(tmp_path):
    for layout in (False, True):
        source = tmp_path / "red.png"
        other = tmp_path / "clear.png"
        output = tmp_path / "out.png"
        _png(source, (255, 0, 0, 128), (1, 1))
        _png(other, (0, 0, 0, 0), (1, 1))
        params = {"direction": "canvas", "paths": [str(source), str(other)],
                  "output_path": str(output), "canvas_width": 2, "canvas_height": 1}
        if layout:
            params["canvas_layout"] = [{"path": str(source), "x": 0, "y": 0, "w": 1, "h": 1}]
        run_merge(params)
        with Image.open(output) as image:
            assert image.getpixel((0, 0)) == (255, 0, 0, 128)


def test_canvas_refuses_to_overwrite_an_input(tmp_path):
    import pytest

    source, other = tmp_path / "a.png", tmp_path / "b.png"
    _png(source, (255, 0, 0, 255), (2, 2))
    _png(other, (0, 0, 0, 255), (2, 2))
    before = source.read_bytes()
    with pytest.raises(ValueError, match="output matches an input"):
        run_merge({"direction": "canvas", "paths": [str(source), str(other)], "output_path": str(source)})
    assert source.read_bytes() == before


def test_canvas_failed_encode_preserves_destination(tmp_path, monkeypatch):
    import pytest

    source, other, output = tmp_path / "a.png", tmp_path / "b.png", tmp_path / "out.png"
    _png(source, (255, 0, 0, 255), (2, 2))
    _png(other, (0, 0, 0, 255), (2, 2))
    output.write_bytes(b"existing")
    original = Image.Image.save

    def fail(image, destination, *args, **kwargs):
        from pathlib import Path
        if isinstance(destination, Path):
            destination.write_bytes(b"partial")
            raise OSError("encoder failed")
        return original(image, destination, *args, **kwargs)

    monkeypatch.setattr(Image.Image, "save", fail)
    with pytest.raises(OSError, match="encoder failed"):
        run_merge({"direction": "canvas", "paths": [str(source), str(other)], "output_path": str(output)})
    assert output.read_bytes() == b"existing"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["a.png", "b.png", "out.png"]

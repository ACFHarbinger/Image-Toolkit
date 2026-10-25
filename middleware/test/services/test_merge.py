from __future__ import annotations

import base64
import io
import struct
import zlib

from middleware.src.services.merge.concatenate import concatenate
from PIL import Image


def _png(path, color: tuple[int, int, int], size: tuple[int, int] = (2, 2)) -> None:
    with Image.new("RGB", size, color) as image:
        image.save(path)


def _png_header(path, width: int, height: int) -> None:
    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IEND", b""))


def test_horizontal_concat_writes_png_and_preview(tmp_path) -> None:
    left = tmp_path / "left.png"
    right = tmp_path / "right.png"
    output = tmp_path / "out.png"
    _png(left, (255, 0, 0), (2, 1))
    _png(right, (0, 0, 255), (2, 2))
    result = concatenate([str(left), str(right)], str(output), "horizontal", 1, "end")
    assert result["written"] is True
    assert result["width"] == 5
    assert result["height"] == 2
    assert result["error"] == ""
    with Image.open(output) as image:
        assert image.size == (5, 2)
        assert image.getpixel((0, 1)) == (255, 0, 0)
        assert image.getpixel((2, 0)) == (255, 255, 255)
        assert image.getpixel((3, 0)) == (0, 0, 255)
    with Image.open(io.BytesIO(base64.b64decode(result["preview_png_base64"]))) as preview:
        assert preview.size == (5, 2)


def test_oversized_header_is_refused_before_decode(tmp_path, monkeypatch) -> None:
    left = tmp_path / "left.png"
    right = tmp_path / "right.png"
    output = tmp_path / "out.png"
    _png(left, (0, 0, 0), (2, 2))
    _png_header(right, 8000, 8000)

    def refuse_decode(*_args, **_kwargs):
        raise AssertionError("pixel decoding must not occur")

    monkeypatch.setattr(Image.Image, "convert", refuse_decode)
    result = concatenate([str(left), str(right)], str(output), "vertical", 0, "start")
    assert result["written"] is False
    assert result["error"] == "image is too large"
    assert output.exists() is False


def test_output_must_not_be_an_input(tmp_path) -> None:
    left = tmp_path / "left.png"
    right = tmp_path / "right.png"
    _png(left, (0, 0, 0))
    _png(right, (1, 1, 1))
    result = concatenate([str(left), str(right)], str(left), "horizontal", 0, "start")
    assert result["written"] is False
    assert result["error"] == "output matches an input"

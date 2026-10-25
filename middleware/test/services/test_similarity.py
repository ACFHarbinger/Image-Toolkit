from __future__ import annotations

import struct
import zlib

from middleware.src.services.similarity.compare import compare_paths
from PIL import Image


def _png(path, color: tuple[int, int, int]) -> None:
    with Image.new("RGB", (4, 4), color) as image:
        image.save(path)


def _png_header(path, width: int, height: int) -> None:
    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IEND", b""))


def test_identical_images_are_distance_zero(tmp_path) -> None:
    left = tmp_path / "left.png"
    right = tmp_path / "right.png"
    _png(left, (10, 20, 30))
    _png(right, (10, 20, 30))
    result = compare_paths([str(left), str(right)], 0)
    assert result["items"][0]["ahash"] == result["items"][1]["ahash"]
    assert result["pairs"] == [{"left": str(left), "right": str(right), "distance": 0}]


def test_missing_file_is_not_paired(tmp_path) -> None:
    left = tmp_path / "left.png"
    _png(left, (0, 0, 0))
    missing = tmp_path / "missing.png"
    result = compare_paths([str(left), str(missing)], 64)
    assert result["items"][1]["error"] == "not a file"
    assert result["pairs"] == []


def test_oversized_header_is_refused(tmp_path, monkeypatch) -> None:
    path = tmp_path / "big.png"
    _png_header(path, 8000, 8000)

    def refuse_decode(*_args, **_kwargs):
        raise AssertionError("pixel decoding must not occur")

    monkeypatch.setattr(Image.Image, "convert", refuse_decode)
    result = compare_paths([str(path)], 8)
    assert result["items"][0]["error"] == "image is too large"
    assert result["items"][0]["ahash"] == ""

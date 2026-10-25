"""Library preview inspection (#895). Paths only; no library.db."""

from __future__ import annotations

import base64
import io

from middleware.src.bridge import PROTOCOL_NAME
from middleware.src.services.library_preview.preview import describe_paths, difference_map, frame_png
from middleware.src.sidecar.server import SidecarServer
from PIL import Image


def _png(path, color: tuple[int, int, int], size: tuple[int, int] = (2, 1)) -> None:
    Image.new("RGB", size, color).save(path)


def test_missing_path_is_not_a_file(tmp_path) -> None:
    missing = tmp_path / "gone.png"
    item = describe_paths([str(missing)])["items"][0]
    assert item["exists"] is False
    assert item["error"] == "not a file"
    assert item["width"] == 0


def test_describe_reports_size_and_animation(tmp_path) -> None:
    still = tmp_path / "still.png"
    _png(still, (10, 20, 30), (3, 2))
    item = describe_paths([str(still)])["items"][0]
    assert item["exists"] is True
    assert item["width"] == 3
    assert item["height"] == 2
    assert item["animated"] is False
    assert item["error"] == ""


def test_identical_images_have_a_zero_mean(tmp_path) -> None:
    left = tmp_path / "left.png"
    right = tmp_path / "right.png"
    _png(left, (8, 8, 8))
    _png(right, (8, 8, 8))
    result = difference_map(str(left), str(right), 1)
    assert result["available"] is True
    assert result["mean_abs"] == 0
    assert result["width"] == 2
    png = base64.b64decode(result["png_base64"])
    assert png.startswith(b"\x89PNG")


def test_changed_pixel_is_a_positive_mean_and_boost_stays_in_the_png(tmp_path) -> None:
    left = tmp_path / "left.png"
    right = tmp_path / "right.png"
    _png(left, (0, 0, 0))
    _png(right, (10, 0, 0))
    plain = difference_map(str(left), str(right), 1)
    boosted = difference_map(str(left), str(right), 8)
    assert plain["mean_abs"] == 10 / 3
    assert boosted["mean_abs"] == plain["mean_abs"]
    plain_image = Image.open(io.BytesIO(base64.b64decode(plain["png_base64"])))
    boosted_image = Image.open(io.BytesIO(base64.b64decode(boosted["png_base64"])))
    assert plain_image.getpixel((0, 0)) == (10, 0, 0)
    assert boosted_image.getpixel((0, 0)) == (80, 0, 0)


def test_frame_caps_the_longest_edge(tmp_path) -> None:
    wide = tmp_path / "wide.png"
    _png(wide, (4, 5, 6), (600, 10))
    result = frame_png(str(wide))
    assert result["error"] == ""
    assert result["width"] == 512
    assert result["height"] < 512
    assert base64.b64decode(result["png_base64"]).startswith(b"\x89PNG")


def test_sidecar_describe_does_not_require_a_database(tmp_path) -> None:
    still = tmp_path / "still.png"
    _png(still, (1, 2, 3))
    server = SidecarServer(stdout=io.StringIO())
    server.handle_frame(
        {
            "jsonrpc": "2.0",
            "id": "handshake",
            "method": "system.handshake",
            "params": {"protocol": PROTOCOL_NAME, "client": {"name": "pytest", "version": "1.0.0"}},
        }
    )
    response = server.handle_frame(
        {
            "jsonrpc": "2.0",
            "id": "describe",
            "method": "library_preview.describe",
            "params": {"paths": [str(still)]},
        }
    )
    assert response["result"]["items"][0]["width"] == 2


def test_size_mismatch_does_not_resize(tmp_path) -> None:
    left = tmp_path / "left.png"
    right = tmp_path / "right.png"
    _png(left, (0, 0, 0), (2, 1))
    _png(right, (0, 0, 0), (2, 2))
    result = difference_map(str(left), str(right), 1)
    assert result["available"] is False
    assert result["reason"] == "size mismatch"
    assert result["png_base64"] == ""

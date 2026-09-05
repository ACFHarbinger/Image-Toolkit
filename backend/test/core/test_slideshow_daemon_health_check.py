"""Unit tests for slideshow daemon health check before rotation (new_features.md §4.7E)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from backend.src.utils.display.slideshow_daemon import _advance_all, _is_valid_image


def test_is_valid_image():
    with tempfile.NamedTemporaryFile("wb", delete=False) as f:
        f.write(b"valid image data")
        valid_path = f.name

    with tempfile.NamedTemporaryFile("wb", delete=False) as f:
        empty_path = f.name  # 0 bytes

    try:
        assert _is_valid_image(valid_path) is True
        assert _is_valid_image(empty_path) is False
        assert _is_valid_image("/nonexistent/file/path.png") is False
    finally:
        Path(valid_path).unlink(missing_ok=True)
        Path(empty_path).unlink(missing_ok=True)


def test_advance_all_skips_invalid_images():
    with tempfile.NamedTemporaryFile("wb", delete=False) as f1:
        f1.write(b"img1")
        img1 = f1.name
    with tempfile.NamedTemporaryFile("wb", delete=False) as f2:
        f2.write(b"img2")
        img2 = f2.name
    missing_img = "/nonexistent/missing_img.png"

    try:
        # Paths: img1, missing_img, img2
        monitor_state = {
            "0": {
                "paths": [img1, missing_img, img2],
                "index": 0,
            }
        }

        # Advancing from index 0 should skip index 1 (missing) and land on index 2 (img2)
        _advance_all(monitor_state)
        assert monitor_state["0"]["index"] == 2

        # Advancing from index 2 should loop around to index 0 (img1)
        _advance_all(monitor_state)
        assert monitor_state["0"]["index"] == 0
    finally:
        Path(img1).unlink(missing_ok=True)
        Path(img2).unlink(missing_ok=True)


def test_advance_all_all_invalid():
    # If all items are invalid, it cycles through without crashing or infinite loop
    monitor_state = {
        "0": {
            "paths": ["/missing/a.png", "/missing/b.png"],
            "index": 0,
        }
    }
    _advance_all(monitor_state)
    assert monitor_state["0"]["index"] == 0

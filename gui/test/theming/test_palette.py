from __future__ import annotations

import numpy as np

from gui.src.theming import base_defaults, extract_palette


def test_extract_palette_returns_schema_tokens_for_colorful_image():
    image = np.zeros((32, 32, 3), dtype=np.uint8)
    image[:, :16] = (24, 50, 150)
    image[:, 16:] = (220, 120, 40)

    result = extract_palette(image, base="dark", n_colors=3)

    assert not result.used_fallback
    assert 2 <= len(result.colors) <= 3
    assert result.tokens.as_dict() == result.overrides
    assert result.tokens.accent != base_defaults("dark").accent


def test_extract_palette_falls_back_for_monochrome_image():
    image = np.full((32, 32, 3), 100, dtype=np.uint8)

    result = extract_palette(image, base="light")

    assert result.used_fallback
    assert result.tokens == base_defaults("light")


def test_extract_palette_accepts_image_path(tmp_path):
    from PIL import Image

    path = tmp_path / "background.png"
    Image.fromarray(np.tile([[[20, 120, 220]]], (24, 24, 1)).astype(np.uint8)).save(path)

    result = extract_palette(path, base="light")

    assert result.tokens.accent.startswith("#")

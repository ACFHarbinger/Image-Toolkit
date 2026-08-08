import pytest

from colorization.style_bible import MaterialPalette
from editor import LayerStack, apply_palette_color_to_region, resolve_palette_color


def _palette(accent=None):
    return MaterialPalette("#332233", "#665566", "#110F18", accent)


def test_resolve_palette_color_parses_hex_roles():
    palette = _palette()
    assert resolve_palette_color(palette, "local") == (0x33, 0x22, 0x33)
    assert resolve_palette_color(palette, "light") == (0x66, 0x55, 0x66)
    assert resolve_palette_color(palette, "shadow") == (0x11, 0x0F, 0x18)


def test_resolve_palette_color_supports_accent_when_present():
    palette = _palette(accent="#FF00FF")
    assert resolve_palette_color(palette, "accent") == (0xFF, 0x00, 0xFF)


def test_resolve_palette_color_rejects_absent_accent():
    palette = _palette()
    with pytest.raises(ValueError, match="no accent color"):
        resolve_palette_color(palette, "accent")


def test_resolve_palette_color_rejects_unsupported_role():
    with pytest.raises(ValueError, match="unsupported palette role"):
        resolve_palette_color(_palette(), "highlight")


def test_apply_palette_color_to_region_recolors_opaque_pixels_only():
    stack = LayerStack(2, 2)
    layer = stack.add_layer("region-1", "Region 1")
    layer.pixels[0, 0] = [1, 2, 3, 255]
    layer.pixels[0, 1] = [1, 2, 3, 0]  # transparent, must stay untouched

    assert apply_palette_color_to_region(stack, "region-1", _palette(), "local") is True
    assert layer.pixels[0, 0].tolist() == [0x33, 0x22, 0x33, 255]
    assert layer.pixels[0, 1].tolist() == [1, 2, 3, 0]


def test_apply_palette_color_to_region_returns_false_for_missing_layer():
    stack = LayerStack(2, 2)
    assert apply_palette_color_to_region(stack, "missing", _palette(), "local") is False


def test_apply_palette_color_to_region_preserves_alpha():
    stack = LayerStack(2, 2)
    layer = stack.add_layer("region-1", "Region 1")
    layer.pixels[0, 0] = [1, 2, 3, 128]
    apply_palette_color_to_region(stack, "region-1", _palette(), "shadow")
    assert layer.pixels[0, 0, 3] == 128

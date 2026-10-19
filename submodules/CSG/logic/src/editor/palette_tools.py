"""Palette-application tools connecting the standalone editor's
``LayerStack`` to the existing deterministic ``colorization.style_bible``
format (roadmap milestone 2, issue #15) -- reused rather than
reimplemented, the same way ``segmentation_tools.py`` reuses
``colorization.segmentation``. Qt-free.

A region layer (from ``segmentation_tools.segment_layer_into_regions``, or
any hand-painted layer an artist treats as one) already carries its shape
in its alpha channel. Applying a material's palette color only ever
recolors that layer's currently-opaque pixels, leaving the shape/alpha
untouched -- the same "shape from segmentation/painting, color from the
bible" split the Krita Character Colors Docker's material masks use.
"""

from __future__ import annotations

from colorization.style_bible import MaterialPalette

from .layer_stack import LayerStack

__all__ = ["PALETTE_ROLES", "resolve_palette_color", "apply_palette_color_to_region"]

PALETTE_ROLES = ("local", "light", "shadow", "accent")


def resolve_palette_color(palette: MaterialPalette, role: str) -> tuple[int, int, int]:
    """RGB int tuple for one of a material's palette roles.

    Raises ``ValueError`` for an unsupported role, or an accent role the
    material doesn't define -- matching the Krita Character Colors
    Docker's existing "absent accents are not offered as preview roles"
    rule rather than silently substituting another role's color.
    """
    if role not in PALETTE_ROLES:
        raise ValueError(f"unsupported palette role: {role}")
    hex_color = getattr(palette, role)
    if hex_color is None:
        raise ValueError(f"material palette has no {role} color")
    red, green, blue = (int(hex_color[index : index + 2], 16) for index in (1, 3, 5))
    return red, green, blue


def apply_palette_color_to_region(
    layer_stack: LayerStack, region_layer_id: str, palette: MaterialPalette, role: str
) -> bool:
    """Recolor ``region_layer_id``'s currently-opaque pixels to a
    material's palette role color, in place, leaving its alpha/shape
    untouched. Returns ``False`` if the layer doesn't exist."""
    layer = layer_stack.layer(region_layer_id)
    if layer is None:
        return False
    color = resolve_palette_color(palette, role)
    opaque = layer.pixels[:, :, 3] > 0
    layer.pixels[opaque, 0] = color[0]
    layer.pixels[opaque, 1] = color[1]
    layer.pixels[opaque, 2] = color[2]
    return True

"""Host-neutral conventions and rasterization for semantic material masks."""

import re

MASK_GROUP_NAME = "Material Masks"
MASK_PREFIX = "Material — "
ACCEPTED_GROUP_NAME = "Character Colors"
ACCEPTED_PREFIX = "Color — "
PREVIEW_PREFIX = "Color Preview — "


def material_mask_name(material_id, variant=None):
    if not isinstance(material_id, str) or not material_id:
        raise ValueError("material id must not be empty")
    if variant is not None and (not isinstance(variant, str) or not variant.strip()):
        raise ValueError("mask variant must not be empty")
    return MASK_PREFIX + material_id + (" — " + variant.strip() if variant else "")


def selected_material_id(node):
    if node is None:
        raise ValueError("select a named material mask layer")
    name = node.name() if callable(getattr(node, "name", None)) else node.name
    suffix = name[len(MASK_PREFIX) :] if name.startswith(MASK_PREFIX) else ""
    if not suffix:
        raise ValueError("active layer is not a named material mask")
    return suffix.split(" — ", 1)[0]


def material_mask_parts(node):
    """Return ``(material_id, variant)`` from a canonical mask-layer name."""
    if node is None:
        raise ValueError("select a named material mask layer")
    name = node.name() if callable(getattr(node, "name", None)) else node.name
    if not name.startswith(MASK_PREFIX) or not name[len(MASK_PREFIX) :]:
        raise ValueError("active layer is not a named material mask")
    parts = name[len(MASK_PREFIX) :].split(" — ", 1)
    return parts[0], parts[1] if len(parts) == 2 else None


def palette_preview_bgra(alpha_bytes, color):
    """Fill each mask alpha with one #RRGGBB color in Krita BGRA order."""
    if not isinstance(alpha_bytes, (bytes, bytearray)):
        raise ValueError("mask alpha must be bytes")
    if not isinstance(color, str) or len(color) != 7 or not color.startswith("#"):
        raise ValueError("palette color must use #RRGGBB notation")
    try:
        red, green, blue = (int(color[index : index + 2], 16) for index in (1, 3, 5))
    except ValueError as error:
        raise ValueError("palette color must use #RRGGBB notation") from error
    pixels = bytearray(len(alpha_bytes) * 4)
    for index, alpha in enumerate(alpha_bytes):
        offset = index * 4
        pixels[offset : offset + 4] = bytes((blue, green, red, alpha))
    return bytes(pixels)


def overlapping_materials(active_id, masks):
    """Return other material IDs whose alpha intersects the active mask."""
    if active_id not in masks:
        raise ValueError("active material mask is missing")
    active = masks[active_id]
    if not isinstance(active, (bytes, bytearray)):
        raise ValueError("material masks must be bytes")
    conflicts = {}
    for material_id, alpha in masks.items():
        if not isinstance(alpha, (bytes, bytearray)) or len(alpha) != len(active):
            raise ValueError("material masks must be equal-length byte buffers")
        if material_id == active_id:
            continue
        count = sum(bool(left and right) for left, right in zip(active, alpha, strict=True))
        if count:
            conflicts[material_id] = count
    return conflicts


def region_id_from_layer_name(name):
    """Return a normalized kebab-case correspondence region id from a layer name."""
    if not isinstance(name, str) or not name.strip():
        raise ValueError("layer name must not be empty")
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    if not slug:
        raise ValueError("layer name has no usable identifier characters")
    return slug


def union_alpha_buffers(buffers):
    """Union variant alpha buffers without weakening partial-opacity values."""
    if not buffers:
        raise ValueError("at least one alpha buffer is required")
    if any(not isinstance(buffer, (bytes, bytearray)) for buffer in buffers):
        raise ValueError("material masks must be bytes")
    size = len(buffers[0])
    if any(len(buffer) != size for buffer in buffers):
        raise ValueError("material masks must be equal-length byte buffers")
    result = bytearray(size)
    for buffer in buffers:
        for index, value in enumerate(buffer):
            result[index] = max(result[index], value)
    return bytes(result)

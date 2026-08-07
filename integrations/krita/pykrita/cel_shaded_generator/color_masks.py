"""Host-neutral conventions and rasterization for semantic material masks."""

MASK_GROUP_NAME = "Material Masks"
MASK_PREFIX = "Material — "
ACCEPTED_GROUP_NAME = "Character Colors"
ACCEPTED_PREFIX = "Color — "
PREVIEW_PREFIX = "Color Preview — "


def material_mask_name(material_id):
    if not isinstance(material_id, str) or not material_id:
        raise ValueError("material id must not be empty")
    return MASK_PREFIX + material_id


def selected_material_id(node):
    if node is None:
        raise ValueError("select a named material mask layer")
    name = node.name() if callable(getattr(node, "name", None)) else node.name
    if not name.startswith(MASK_PREFIX) or not name[len(MASK_PREFIX) :]:
        raise ValueError("active layer is not a named material mask")
    return name[len(MASK_PREFIX) :]


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

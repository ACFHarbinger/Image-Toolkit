"""Krita adapter for bounded alpha-only cel-value masks."""

MASK_SIDE = 64


def find_named_node(root, name):
    for node in root.childNodes():
        if node.name() == name:
            return node
        found = find_named_node(node, name)
        if found is not None:
            return found
    return None


def sampled_alpha_mask(node, crop_index, document_width, document_height, side=MASK_SIDE):
    """Read one matrix cell and return alpha occupancy, never color or pixels."""
    if not 0 <= crop_index < 6 or not 2 <= side <= 128:
        raise ValueError("invalid value-mask sampling request")
    column, row = crop_index % 3, crop_index // 3
    x0, x1 = column * document_width // 3, (column + 1) * document_width // 3
    y0, y1 = row * document_height // 2, (row + 1) * document_height // 2
    width, height = x1 - x0, y1 - y0
    raw = bytes(node.pixelData(x0, y0, width, height))
    if len(raw) != width * height * 4:
        raise ValueError("Krita returned an unexpected RGBA mask buffer")
    result = []
    for sample_y in range(side):
        source_y = min(height - 1, sample_y * height // side)
        for sample_x in range(side):
            source_x = min(width - 1, sample_x * width // side)
            result.append(int(raw[(source_y * width + source_x) * 4 + 3] > 0))
    return result

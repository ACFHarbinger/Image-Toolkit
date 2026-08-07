"""Host-neutral, pure-Python line-art gap closing and region segmentation.

Mirrors ``colorization.segmentation``'s numpy/scipy algorithm (same
single-radius trapped-ball-style narrowing, same border-exclusion rule, same
region-adjacency/statistics contracts) but operates on flat byte/list
buffers with no numpy dependency, matching this package's existing
Krita-boundary modules (``color_masks.py``, ``value_masks.py``) that
deliberately avoid assuming a numpy-equipped Krita Python environment so the
Docker can act on pixel data in-process without an engine round trip.
"""

from __future__ import annotations

REGION_GROUP_NAME = "Regions"
REGION_PREFIX = "Region — "
LINE_ART_GROUP_NAME = "Line Art"
GAP_CLOSED_PREFIX = "Line Art — Gap Closed"


def close_line_gaps_bytes(ink_bytes, width, height, max_gap_px):
    """Bridge ink gaps up to ``max_gap_px`` wide via iterative dilate/erode."""
    _validate_buffer(ink_bytes, width, height, "ink buffer")
    if not isinstance(max_gap_px, int) or isinstance(max_gap_px, bool) or max_gap_px < 0:
        raise ValueError("max_gap_px must be a non-negative integer")
    mask = bytearray(1 if value else 0 for value in ink_bytes)
    for _ in range(max_gap_px):
        mask = _dilate(mask, width, height)
    for _ in range(max_gap_px):
        mask = _erode(mask, width, height)
    return bytes(mask)


def segment_regions_bytes(ink_bytes, width, height):
    """Label enclosed background regions; ``0`` marks ink or non-enclosed background."""
    _validate_buffer(ink_bytes, width, height, "ink buffer")
    size = width * height
    labels = [0] * size
    visited = bytearray(size)
    next_label = 0
    for start in range(size):
        if ink_bytes[start] or visited[start]:
            continue
        next_label += 1
        queue = [start]
        visited[start] = 1
        component = [start]
        touches_border = False
        while queue:
            index = queue.pop()
            row, col = divmod(index, width)
            if row in (0, height - 1) or col in (0, width - 1):
                touches_border = True
            for neighbor in _neighbors8(index, width, height):
                if not ink_bytes[neighbor] and not visited[neighbor]:
                    visited[neighbor] = 1
                    queue.append(neighbor)
                    component.append(neighbor)
        if touches_border:
            continue
        for index in component:
            labels[index] = next_label
    return labels


def region_adjacency_bytes(labels, width, height):
    """Return unordered ``(smaller, larger)`` label pairs that share a border."""
    if len(labels) != width * height:
        raise ValueError("labels length must equal width * height")
    pairs = set()
    for index, value in enumerate(labels):
        if not value:
            continue
        row, col = divmod(index, width)
        if col + 1 < width:
            other = labels[index + 1]
            if other and other != value:
                pairs.add((value, other) if value < other else (other, value))
        if row + 1 < height:
            other = labels[index + width]
            if other and other != value:
                pairs.add((value, other) if value < other else (other, value))
    return pairs


def region_statistics_bytes(labels, width, height):
    """Return area, centroid, and bounding box per labeled region."""
    if len(labels) != width * height:
        raise ValueError("labels length must equal width * height")
    accumulators = {}
    for index, value in enumerate(labels):
        if not value:
            continue
        row, col = divmod(index, width)
        entry = accumulators.setdefault(
            value,
            {
                "area": 0,
                "row_sum": 0,
                "col_sum": 0,
                "min_row": row,
                "max_row": row,
                "min_col": col,
                "max_col": col,
            },
        )
        entry["area"] += 1
        entry["row_sum"] += row
        entry["col_sum"] += col
        entry["min_row"] = min(entry["min_row"], row)
        entry["max_row"] = max(entry["max_row"], row)
        entry["min_col"] = min(entry["min_col"], col)
        entry["max_col"] = max(entry["max_col"], col)
    return {
        label: {
            "area": entry["area"],
            "centroid": (entry["row_sum"] / entry["area"], entry["col_sum"] / entry["area"]),
            "bbox": (entry["min_row"], entry["min_col"], entry["max_row"], entry["max_col"]),
        }
        for label, entry in accumulators.items()
    }


def _validate_buffer(buffer, width, height, label):
    if not isinstance(buffer, (bytes, bytearray, list)):
        raise ValueError(f"{label} must be a byte buffer or list")
    if not isinstance(width, int) or not isinstance(height, int) or width <= 0 or height <= 0:
        raise ValueError("width and height must be positive integers")
    if len(buffer) != width * height:
        raise ValueError(f"{label} length must equal width * height")


def _neighbors8(index, width, height):
    row, col = divmod(index, width)
    for delta_row in (-1, 0, 1):
        for delta_col in (-1, 0, 1):
            if delta_row == 0 and delta_col == 0:
                continue
            neighbor_row, neighbor_col = row + delta_row, col + delta_col
            if 0 <= neighbor_row < height and 0 <= neighbor_col < width:
                yield neighbor_row * width + neighbor_col


def _dilate(mask, width, height):
    result = bytearray(mask)
    for index, value in enumerate(mask):
        if value:
            continue
        if any(mask[neighbor] for neighbor in _neighbors8(index, width, height)):
            result[index] = 1
    return result


def _erode(mask, width, height):
    result = bytearray(mask)
    for index, value in enumerate(mask):
        if not value:
            continue
        if any(not mask[neighbor] for neighbor in _neighbors8(index, width, height)):
            result[index] = 0
    return result

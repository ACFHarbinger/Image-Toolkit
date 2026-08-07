import importlib.util
import sys
import types
from pathlib import Path

import pytest


def _module():
    package_dir = Path(__file__).parents[2] / "integrations/krita/pykrita/cel_shaded_generator"
    package_name = "cel_shaded_generator"
    if package_name not in sys.modules:
        package = types.ModuleType(package_name)
        package.__path__ = [str(package_dir)]
        sys.modules[package_name] = package

    module_name = f"{package_name}.segmentation_masks"
    spec = importlib.util.spec_from_file_location(
        module_name, package_dir / "segmentation_masks.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _two_room_line_art(gap=False):
    """10x10 flat ink buffer: a bordered square split by a wall at column 5,
    with an optional 1px gap in the wall at row 4."""
    width = height = 10
    ink = bytearray(width * height)
    for col in range(width):
        ink[col] = 1
        ink[(height - 1) * width + col] = 1
    for row in range(height):
        ink[row * width] = 1
        ink[row * width + (width - 1)] = 1
    for row in range(1, 9):
        ink[row * width + 5] = 1
    if gap:
        ink[4 * width + 5] = 0
    return bytes(ink), width, height


def test_close_line_gaps_bridges_small_gaps_but_not_zero_radius():
    module = _module()
    ink, width, height = _two_room_line_art(gap=True)
    assert ink[4 * width + 5] == 0
    closed = module.close_line_gaps_bytes(ink, width, height, 1)
    assert closed[4 * width + 5] == 1
    unchanged = module.close_line_gaps_bytes(ink, width, height, 0)
    assert unchanged[4 * width + 5] == 0


def test_close_line_gaps_rejects_invalid_input():
    module = _module()
    ink, width, height = _two_room_line_art()
    with pytest.raises(ValueError, match="non-negative integer"):
        module.close_line_gaps_bytes(ink, width, height, -1)
    with pytest.raises(ValueError, match="length must equal"):
        module.close_line_gaps_bytes(ink[:-1], width, height, 1)


def test_segment_regions_labels_two_enclosed_rooms_distinctly():
    module = _module()
    ink, width, height = _two_room_line_art()
    labels = module.segment_regions_bytes(ink, width, height)

    def region_at(row, col):
        return labels[row * width + col]

    left = region_at(4, 2)
    right = region_at(4, 7)
    assert left != 0
    assert right != 0
    assert left != right
    assert region_at(0, 0) == 0


def test_segment_regions_excludes_border_touching_background():
    module = _module()
    width = height = 6
    ink = bytearray(width * height)
    for col in range(4):
        ink[2 * width + col] = 1
    labels = module.segment_regions_bytes(bytes(ink), width, height)
    assert all(value == 0 for value in labels)


def test_segment_regions_gap_leaks_rooms_into_one_region():
    module = _module()
    ink, width, height = _two_room_line_art(gap=True)
    labels = module.segment_regions_bytes(ink, width, height)
    assert labels[4 * width + 2] == labels[4 * width + 7]
    assert labels[4 * width + 2] != 0


def test_filter_small_regions_clears_only_regions_below_threshold():
    module = _module()
    labels = [
        1, 1, 0, 2,
        1, 1, 0, 0,
        0, 0, 0, 0,
        3, 3, 3, 0,
    ]
    filtered = module.filter_small_regions(labels, 3)
    assert set(filtered) == {0, 1, 3}
    assert filtered[3] == 0


def test_filter_small_regions_zero_threshold_is_a_noop_copy():
    module = _module()
    labels = [1, 0, 0, 2]
    filtered = module.filter_small_regions(labels, 0)
    assert filtered == labels
    assert filtered is not labels


def test_filter_small_regions_rejects_negative_threshold():
    module = _module()
    with pytest.raises(ValueError, match="non-negative integer"):
        module.filter_small_regions([1, 0], -1)


def test_region_adjacency_finds_touching_labels_only():
    module = _module()
    width, height = 4, 4
    labels = [
        1, 1, 2, 2,
        1, 1, 2, 2,
        0, 0, 0, 0,
        3, 3, 0, 0,
    ]
    assert module.region_adjacency_bytes(labels, width, height) == {(1, 2)}


def test_region_adjacency_rejects_wrong_length():
    module = _module()
    with pytest.raises(ValueError, match="length must equal"):
        module.region_adjacency_bytes([0, 1], 2, 2)


def test_region_statistics_reports_area_centroid_and_bbox():
    module = _module()
    width, height = 3, 3
    labels = [
        1, 1, 0,
        1, 1, 0,
        0, 0, 2,
    ]
    stats = module.region_statistics_bytes(labels, width, height)
    assert stats[1] == {"area": 4, "centroid": (0.5, 0.5), "bbox": (0, 0, 1, 1)}
    assert stats[2] == {"area": 1, "centroid": (2.0, 2.0), "bbox": (2, 2, 2, 2)}


def test_region_statistics_rejects_wrong_length():
    module = _module()
    with pytest.raises(ValueError, match="length must equal"):
        module.region_statistics_bytes([0, 1], 2, 2)

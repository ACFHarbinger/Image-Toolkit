import numpy as np
import pytest

from colorization.segmentation import (
    close_line_gaps,
    filter_small_regions,
    region_adjacency,
    region_statistics,
    segment_regions,
)


def _two_room_line_art(gap: bool = False) -> np.ndarray:
    """10x10 line-art mask: a bordered square split by a wall at column 5,
    with an optional 1px gap in the wall at row 4."""
    mask = np.zeros((10, 10), dtype=bool)
    mask[0, :] = mask[-1, :] = True
    mask[:, 0] = mask[:, -1] = True
    mask[1:9, 5] = True
    if gap:
        mask[4, 5] = False
    return mask


def test_close_line_gaps_bridges_small_gaps_but_not_zero_radius():
    gapped = _two_room_line_art(gap=True)
    assert not gapped[4, 5]
    closed = close_line_gaps(gapped, 1)
    assert closed[4, 5]
    unchanged = close_line_gaps(gapped, 0)
    assert not unchanged[4, 5]


def test_close_line_gaps_rejects_invalid_input():
    with pytest.raises(ValueError, match="2D array"):
        close_line_gaps(np.zeros((2, 2, 2)), 1)
    with pytest.raises(ValueError, match="non-negative integer"):
        close_line_gaps(_two_room_line_art(), -1)
    with pytest.raises(ValueError, match="non-negative integer"):
        close_line_gaps(_two_room_line_art(), 1.5)


def test_segment_regions_labels_two_enclosed_rooms_distinctly():
    labels = segment_regions(_two_room_line_art())
    left_labels = set(np.unique(labels[1:9, 1:5])) - {0}
    right_labels = set(np.unique(labels[1:9, 6:9])) - {0}
    assert len(left_labels) == 1
    assert len(right_labels) == 1
    assert left_labels != right_labels
    assert np.all(labels[0, :] == 0)
    assert np.all(labels[:, 5][1:9] == 0)


def test_segment_regions_excludes_border_touching_background():
    open_mask = np.zeros((6, 6), dtype=bool)
    open_mask[2, :4] = True
    labels = segment_regions(open_mask)
    assert np.all(labels == 0)


def test_segment_regions_gap_leaks_rooms_into_one_region():
    labels = segment_regions(_two_room_line_art(gap=True))
    left = set(np.unique(labels[1:9, 1:5])) - {0}
    right = set(np.unique(labels[1:9, 6:9])) - {0}
    assert left == right
    assert len(left) == 1


def test_filter_small_regions_clears_only_regions_below_threshold():
    labels = np.array(
        [
            [1, 1, 0, 2],
            [1, 1, 0, 0],
            [0, 0, 0, 0],
            [3, 3, 3, 0],
        ]
    )
    filtered = filter_small_regions(labels, 3)
    assert set(np.unique(filtered)) == {0, 1, 3}
    assert np.array_equal(filtered[0:2, 0:2], np.full((2, 2), 1))
    assert np.array_equal(filtered[3, 0:3], np.full(3, 3))
    assert filtered[0, 3] == 0


def test_filter_small_regions_zero_threshold_is_a_noop_copy():
    labels = np.array([[1, 0], [0, 2]])
    filtered = filter_small_regions(labels, 0)
    assert np.array_equal(filtered, labels)
    assert filtered is not labels


def test_filter_small_regions_rejects_invalid_input():
    labels = np.array([[1, 0], [0, 2]])
    with pytest.raises(ValueError, match="2D array"):
        filter_small_regions(np.zeros((2, 2, 2)), 1)
    with pytest.raises(ValueError, match="non-negative integer"):
        filter_small_regions(labels, -1)


def test_region_adjacency_finds_touching_labels_only():
    labels = np.array(
        [
            [1, 1, 2, 2],
            [1, 1, 2, 2],
            [0, 0, 0, 0],
            [3, 3, 0, 0],
        ]
    )
    assert region_adjacency(labels) == {(1, 2)}


def test_region_adjacency_rejects_non_2d_input():
    with pytest.raises(ValueError, match="2D array"):
        region_adjacency(np.zeros((2, 2, 2)))


def test_region_statistics_reports_area_centroid_and_bbox():
    labels = np.array(
        [
            [1, 1, 0],
            [1, 1, 0],
            [0, 0, 2],
        ]
    )
    stats = region_statistics(labels)
    assert stats[1] == {"area": 4, "centroid": (0.5, 0.5), "bbox": (0, 0, 1, 1)}
    assert stats[2] == {"area": 1, "centroid": (2.0, 2.0), "bbox": (2, 2, 2, 2)}


def test_region_statistics_rejects_non_2d_input():
    with pytest.raises(ValueError, match="2D array"):
        region_statistics(np.zeros((2, 2, 2)))

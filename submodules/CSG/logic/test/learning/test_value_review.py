import pytest

from learning.value_review import analyze_binary_mask, review_value_masks


def _block(width=8, height=8, offset=0):
    return [
        int(2 + offset <= x < 6 + offset and 2 <= y < 6)
        for y in range(height)
        for x in range(width)
    ]


def test_binary_geometry_reports_area_components_and_edges():
    stats = analyze_binary_mask(_block(), 8, 8)
    assert stats.shadow_area_ratio == 0.25
    assert stats.component_count == 1
    assert stats.fragmentation == 0
    assert stats.edge_complexity > 0


def test_review_combines_confirmation_geometry_consistency_and_optional_third_value():
    review = review_value_masks(
        _block(),
        [0] * 64,
        _block(),
        [0] * 64,
        8,
        8,
        "top_left",
        "hard",
        "value-1",
        [int(i == 0) for i in range(64)],
    )
    assert review.measurements["front_turned_consistency"] == 1
    assert review.measurements["front_cast_shadow_area_ratio"] == 0
    assert "third_value_to_primary_ratio" in review.measurements
    assert {item.source.value for item in review.evidence} == {"artist_confirmation", "heuristic"}
    assert any("descriptive evidence" in item for item in review.explanations)


def test_mask_input_is_strictly_bounded_and_binary():
    with pytest.raises(ValueError, match="0/1"):
        analyze_binary_mask([2, 0, 0, 0], 2, 2)
    with pytest.raises(ValueError, match="128x128"):
        analyze_binary_mask([0] * (129 * 2), 129, 2)


def test_review_rejects_empty_form_masks_but_allows_empty_cast_masks():
    with pytest.raises(ValueError, match="form-shadow masks must not be empty"):
        review_value_masks(
            [0] * 64,
            [0] * 64,
            _block(),
            [0] * 64,
            8,
            8,
            "top",
            "hard",
            "value-empty",
        )

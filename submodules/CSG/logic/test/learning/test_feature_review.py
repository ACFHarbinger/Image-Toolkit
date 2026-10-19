"""Tests for isolated and combined feature-placement critique."""

from learning.feature_review import review_feature_set, review_feature_study


def _nose(scale=1.0):
    return {
        "axis_top": (0.5, 0.1),
        "chin": (0.5, 0.9),
        "bridge_top": (0.5, 0.3),
        "tip": (0.5, 0.48),
        "base_left": (0.4, 0.52),
        "base_right": (0.4 + 0.2 * scale, 0.52),
        "nostril_left": (0.43, 0.51),
        "nostril_right": (0.57, 0.51),
        "muzzle_left": (0.32, 0.57),
        "muzzle_right": (0.68, 0.57),
    }


def _mouth(scale=1.0, opening=0.08):
    return {
        "axis_top": (0.5, 0.1),
        "chin": (0.5, 0.9),
        "nose_base": (0.5, 0.45),
        "mouth_center": (0.5, 0.62),
        "corner_left": (0.35, 0.62),
        "corner_right": (0.35 + 0.3 * scale, 0.62),
        "upper_peak": (0.5, 0.62 - opening / 2),
        "lower_peak": (0.5, 0.62 + opening / 2),
        "muzzle_left": (0.28, 0.58),
        "muzzle_right": (0.72, 0.58),
    }


def _front_ear():
    values = {"eye_line_left": (0.2, 0.4), "eye_line_right": (0.8, 0.4)}
    for side, x in (("left", 0.18), ("right", 0.82)):
        values |= {
            f"{side}_top": (x, 0.32),
            f"{side}_bottom": (x, 0.62),
            f"{side}_outer": (x + (-0.05 if side == "left" else 0.05), 0.47),
            f"{side}_inner": (x, 0.47),
            f"{side}_attach_top": (x, 0.36),
            f"{side}_attach_bottom": (x, 0.58),
        }
    return values


def _turned_ear():
    return {
        "side_plane_top": (0.75, 0.2),
        "side_plane_bottom": (0.75, 0.7),
        "near_top": (0.75, 0.32),
        "near_bottom": (0.75, 0.62),
        "near_outer": (0.86, 0.47),
        "near_inner": (0.75, 0.47),
        "near_attach_top": (0.75, 0.35),
        "near_attach_bottom": (0.75, 0.58),
        "skull_edge": (0.68, 0.47),
        "far_evidence": (0.67, 0.47),
    }


def test_isolated_feature_review_uses_feature_specific_rubric():
    review = review_feature_study(_front_ear(), "ear", "front", "ear-1")
    assert review.rubric_id == "anime-head-features-ear"
    assert "ear_height_balance" in review.measurements
    assert "ear_bowl_balance" in review.measurements


def test_combined_review_includes_expression_and_all_feature_families():
    review = review_feature_set(
        {"nose": _nose(), "mouth": _mouth(), "ear": _front_ear()},
        {"nose": _nose(0.78), "mouth": _mouth(0.78), "ear": _turned_ear()},
        "set-1",
    )
    assert review.rubric_id == "anime-head-features-paired"
    assert "nose_design_retention" in review.measurements
    assert "mouth_design_retention" in review.measurements
    assert "ear_design_retention" in review.measurements
    assert "feature_expression_consistency" in review.measurements


def test_failed_feature_study_emits_reversible_preview_guides():
    mouth = _mouth()
    mouth["mouth_center"] = (0.75, 0.62)
    mouth["corner_right"] = (0.95, 0.78)
    review = review_feature_study(mouth, "mouth", "front", "mouth-2")
    assert review.redlines
    assert review.suggestions[0].id == "feature-study-guides"
    assert all(redline.explanation for redline in review.redlines)

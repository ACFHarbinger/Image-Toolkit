import pytest

from colorization.confidence import name_similarity, score_candidate


def test_name_similarity_exact_single_token_match_is_one():
    assert name_similarity("hair", "hair") == 1.0


def test_name_similarity_partial_token_overlap():
    # region tokens {hair, front, large}; material tokens {hair}
    # intersection = {hair}; union = {hair, front, large} -> 1/3
    assert name_similarity("hair-front-large", "hair") == pytest.approx(1 / 3)


def test_name_similarity_uses_aliases():
    # region tokens {bangs}; material tokens {hair, bangs, ponytail}
    # intersection = {bangs}; union = {hair, bangs, ponytail} -> 1/3
    assert name_similarity("bangs", "hair", aliases=("bangs", "ponytail")) == pytest.approx(1 / 3)


def test_name_similarity_no_overlap_is_zero():
    assert name_similarity("skin-face", "hair") == 0.0


def test_name_similarity_rejects_empty_identifiers():
    with pytest.raises(ValueError, match="region id"):
        name_similarity("", "hair")
    with pytest.raises(ValueError, match="material id"):
        name_similarity("hair", "")


def test_score_candidate_is_a_weighted_sum():
    assert score_candidate(1.0, 0.0, 0.6, 0.4) == pytest.approx(0.6)
    assert score_candidate(0.0, 1.0, 0.6, 0.4) == pytest.approx(0.4)
    assert score_candidate(0.5, 0.5, 0.5, 0.5) == pytest.approx(0.5)


@pytest.mark.parametrize(
    "adjacency,name,adjacency_weight,name_weight",
    [
        (-0.1, 0.5, 0.5, 0.5),
        (1.1, 0.5, 0.5, 0.5),
        (0.5, -0.1, 0.5, 0.5),
        (0.5, 0.5, -0.1, 0.5),
        (0.5, 0.5, 0.5, 1.1),
    ],
)
def test_score_candidate_rejects_out_of_range_inputs(
    adjacency, name, adjacency_weight, name_weight
):
    with pytest.raises(ValueError, match="between zero and one"):
        score_candidate(adjacency, name, adjacency_weight, name_weight)

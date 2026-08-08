import pytest

from colorization.correspondence import CorrespondenceSet, RegionCorrespondence
from colorization.style_bible import CharacterStyleBible, MaterialPalette, StyleMaterial
from editor import (
    adjacency_agreement_by_material,
    adjacent_region_ids,
    assign_region_correspondence,
    rank_material_candidates,
)


def _bible():
    return CharacterStyleBible(
        "aiko",
        "Aiko",
        "TV cel",
        [
            StyleMaterial("hair-front", "Hair", MaterialPalette("#332233", "#665566", "#110F18")),
            StyleMaterial("skin", "Skin", MaterialPalette("#EEDDCC", "#FFEEDD", "#AA8866")),
        ],
    )


def _correspondence_set(*correspondences):
    return CorrespondenceSet(
        id="editor-correspondence", style_bible_id="aiko", correspondences=list(correspondences)
    )


def test_adjacent_region_ids_finds_both_directions():
    pairs = {("region-x", "region-a"), ("region-b", "region-x"), ("region-a", "region-b")}
    assert adjacent_region_ids("region-x", pairs) == {"region-a", "region-b"}


def test_adjacent_region_ids_empty_without_adjacency():
    assert adjacent_region_ids("region-x", set()) == set()


def test_adjacency_agreement_by_material_scores_partial_agreement():
    correspondence_set = _correspondence_set(
        RegionCorrespondence(id="c1", region_id="region-a", material_id="hair-front"),
    )
    pairs = {("region-x", "region-a"), ("region-x", "region-b")}
    scores = adjacency_agreement_by_material("region-x", pairs, correspondence_set)
    assert scores == {"hair-front": 0.5}


def test_adjacency_agreement_by_material_empty_without_adjacency():
    correspondence_set = _correspondence_set()
    assert adjacency_agreement_by_material("region-x", set(), correspondence_set) == {}


def test_adjacency_agreement_by_material_ignores_unassigned_neighbors():
    correspondence_set = _correspondence_set()
    pairs = {("region-x", "region-a")}
    assert adjacency_agreement_by_material("region-x", pairs, correspondence_set) == {}


def test_rank_material_candidates_orders_by_confidence():
    correspondence_set = _correspondence_set(
        RegionCorrespondence(id="c1", region_id="region-hair-front", material_id="hair-front"),
    )
    pairs = {("region-x", "region-hair-front")}
    agreements = adjacency_agreement_by_material("region-x", pairs, correspondence_set)
    ranked = rank_material_candidates("region-x", _bible(), agreements)
    assert ranked[0]["material_id"] == "hair-front"
    assert ranked[0]["confidence"] >= ranked[1]["confidence"]
    assert {item["material_id"] for item in ranked} == {"hair-front", "skin"}


def test_rank_material_candidates_uses_name_similarity_with_no_adjacency():
    ranked = rank_material_candidates("skin", _bible(), {})
    assert ranked[0]["material_id"] == "skin"
    assert ranked[0]["name_score"] > 0.0


def test_assign_region_correspondence_adds_entry():
    correspondence_set = _correspondence_set()
    updated = assign_region_correspondence(
        correspondence_set,
        region_id="region-a",
        material_id="hair-front",
        role="local",
        new_id="correspondence-1",
    )
    assert len(updated.correspondences) == 1
    assert updated.correspondences[0].region_id == "region-a"
    assert updated.correspondences[0].material_id == "hair-front"
    assert len(correspondence_set.correspondences) == 0  # original untouched


def test_assign_region_correspondence_rejects_conflicting_assignment():
    correspondence_set = _correspondence_set(
        RegionCorrespondence(id="c1", region_id="region-a", material_id="hair-front"),
    )
    with pytest.raises(ValueError, match="competing"):
        assign_region_correspondence(
            correspondence_set,
            region_id="region-a",
            material_id="skin",
            role="local",
            new_id="correspondence-2",
        )

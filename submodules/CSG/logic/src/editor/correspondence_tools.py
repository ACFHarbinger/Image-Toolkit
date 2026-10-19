"""Standalone editor: region-to-material correspondence assignment
(roadmap: standalone editor, gate-5 exception, slice 7; see
``docs/moon/roadmaps/engine_architecture.md``).

Reuses ``colorization.correspondence`` and ``colorization.confidence``
directly, the same way ``segmentation_tools.py``/``palette_tools.py`` reuse
``colorization.segmentation``/``colorization.style_bible`` -- there is
nothing standalone-editor-specific about the deterministic contract itself.

This mirrors the Krita Character Colors Docker's confidence-ranked material
dropdown (roadmap milestone 4, issue #24:
``color_docker.py``'s ``_adjacency_agreement_by_material``/
``_assign_correspondence`` and ``project.service.rank_correspondence_materials``)
but stops short of that flow's ``SignalWeights`` learning step: the
standalone editor has no project binding yet, so ``rank_material_candidates``
always starts from the same 0.5/0.5 weights ``SignalWeights`` itself starts
from, and nothing here persists a correction-learning update. Wiring this to
a project's learned weights is a later slice, after the standalone editor
gains project persistence at all.
"""

from __future__ import annotations

from colorization.confidence import name_similarity, score_candidate
from colorization.correspondence import CorrespondenceSet, RegionCorrespondence
from colorization.style_bible import CharacterStyleBible

_DEFAULT_ADJACENCY_WEIGHT = 0.5
_DEFAULT_NAME_WEIGHT = 0.5

__all__ = [
    "adjacency_agreement_by_material",
    "adjacent_region_ids",
    "rank_material_candidates",
    "assign_region_correspondence",
]


def adjacent_region_ids(region_id: str, adjacency_pairs: set[tuple[str, str]]) -> set[str]:
    """The other region ids ``region_id`` appears paired with in
    ``adjacency_pairs`` (e.g.
    ``segmentation_tools.region_adjacency_for_regions``'s return value).
    """
    return {
        other
        for left, right in adjacency_pairs
        for other in ((right,) if left == region_id else (left,) if right == region_id else ())
    }


def adjacency_agreement_by_material(
    region_id: str,
    adjacency_pairs: set[tuple[str, str]],
    correspondence_set: CorrespondenceSet,
) -> dict[str, float]:
    """Per-material adjacency-agreement fraction for ``region_id``.

    Mirrors the Krita docker's ``_adjacency_agreement_by_material``: how
    many of ``region_id``'s adjacent regions -- from ``adjacency_pairs``
    (e.g. ``segmentation_tools.region_adjacency_for_regions``'s return
    value) -- are already assigned to a material in ``correspondence_set``,
    out of all adjacent regions. Returns an empty dict (every material
    scores zero) when ``region_id`` has no adjacency information.
    """
    adjacent_ids = adjacent_region_ids(region_id, adjacency_pairs)
    if not adjacent_ids:
        return {}
    assigned = {item.region_id: item.material_id for item in correspondence_set.correspondences}
    counts: dict[str, int] = {}
    for other_id in adjacent_ids:
        material_id = assigned.get(other_id)
        if material_id is not None:
            counts[material_id] = counts.get(material_id, 0) + 1
    return {material_id: count / len(adjacent_ids) for material_id, count in counts.items()}


def rank_material_candidates(
    region_id: str,
    style_bible: CharacterStyleBible,
    adjacency_agreements: dict[str, float],
    *,
    adjacency_weight: float = _DEFAULT_ADJACENCY_WEIGHT,
    name_weight: float = _DEFAULT_NAME_WEIGHT,
) -> list[dict]:
    """Rank a style bible's materials by deterministic confidence for one region.

    Combines each material's adjacency agreement with
    ``colorization.confidence.name_similarity`` via
    ``colorization.confidence.score_candidate``, matching
    ``project.service.rank_correspondence_materials``'s signal combination.
    Never assigns anything; the caller presents this as a ranked suggestion
    the artist reviews and explicitly confirms.
    """
    ranked = []
    for material in style_bible.materials:
        adjacency_score = adjacency_agreements.get(material.id, 0.0)
        name_score = name_similarity(region_id, material.id, material.aliases)
        confidence = score_candidate(adjacency_score, name_score, adjacency_weight, name_weight)
        ranked.append(
            {
                "material_id": material.id,
                "confidence": confidence,
                "adjacency_score": adjacency_score,
                "name_score": name_score,
            }
        )
    ranked.sort(key=lambda item: item["confidence"], reverse=True)
    return ranked


def assign_region_correspondence(
    correspondence_set: CorrespondenceSet,
    *,
    region_id: str,
    material_id: str,
    role: str,
    new_id: str,
) -> CorrespondenceSet:
    """Return a copy of ``correspondence_set`` with one new region assignment.

    Raises ``ValueError`` (via ``CorrespondenceSet.validate``) if
    ``region_id`` is already assigned to a different material -- the same
    "resolve conflicts explicitly instead of guessing" rule
    ``CorrespondenceSet.propagate`` enforces. Assigning the same region to
    the same material again is a harmless no-op duplicate entry rejected by
    the same validation, so callers should check for an existing identical
    assignment first if they want to silently skip it.
    """
    updated = CorrespondenceSet(
        id=correspondence_set.id,
        style_bible_id=correspondence_set.style_bible_id,
        correspondences=[
            *correspondence_set.correspondences,
            RegionCorrespondence(
                id=new_id, region_id=region_id, material_id=material_id, role=role
            ),
        ],
        recovery_revisions=correspondence_set.recovery_revisions,
        schema_version=correspondence_set.schema_version,
    )
    updated.validate()
    return updated

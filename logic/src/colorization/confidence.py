"""Deterministic confidence scoring for suggested region correspondences
(roadmap milestone 4, issue #24).

Combines a small set of deterministic per-material signals -- adjacency
agreement with already-assigned neighboring regions (the same signal C4.1's
material-default suggestion already computes) and region-name/material-alias
token similarity -- into one confidence score per candidate material via a
weighted sum. This module only computes scores from already-known component
values; it holds no state and knows nothing about Krita, style bibles, or
project persistence, matching the "portable contract first" pattern of
``correspondence.py``/``style_bible.py``.

Deliberately not a learned/ML signal yet: per the owner's explicit scoping,
this milestone starts with weighted deterministic signals whose weights
adapt from artist corrections via ``project.update_signal_weights``'s
multiplicative-weights step (see ``project/model.py``'s ``SignalWeights``),
not a trained model, gradient, or optimization loop -- preserving the
"no reinforcement learning / no optimization loop" boundary every earlier
C-issue drew. A future slice may add a learned visual-similarity signal to
this same weighted-signal framework, loaded through the local model
registry, fully offline.
"""

from __future__ import annotations

__all__ = ["name_similarity", "score_candidate"]


def name_similarity(region_id: str, material_id: str, aliases: tuple[str, ...] = ()) -> float:
    """Jaccard token similarity between a region id and a material's id/aliases.

    Region and material identifiers are kebab-case (``hair-front-large``);
    tokens are the hyphen-separated components. Returns a value in
    ``[0, 1]``; two identifiers sharing no tokens score ``0.0``, an exact
    single-token match scores ``1.0``.
    """
    if not isinstance(region_id, str) or not region_id.strip():
        raise ValueError("region id must not be empty")
    if not isinstance(material_id, str) or not material_id.strip():
        raise ValueError("material id must not be empty")
    region_tokens = set(region_id.split("-"))
    material_tokens: set[str] = set()
    for name in (material_id, *aliases):
        material_tokens.update(name.split("-"))
    union = region_tokens | material_tokens
    if not union:
        return 0.0
    return len(region_tokens & material_tokens) / len(union)


def score_candidate(
    adjacency_agreement: float,
    name_score: float,
    adjacency_weight: float,
    name_weight: float,
) -> float:
    """Weighted-sum confidence combining two already-computed signal scores."""
    for label, value in (
        ("adjacency agreement", adjacency_agreement),
        ("name score", name_score),
        ("adjacency weight", adjacency_weight),
        ("name weight", name_weight),
    ):
        if not isinstance(value, (int, float)) or not 0 <= value <= 1:
            raise ValueError(f"{label} must be between zero and one")
    return adjacency_weight * adjacency_agreement + name_weight * name_score

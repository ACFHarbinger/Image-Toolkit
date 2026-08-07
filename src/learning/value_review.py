"""Deterministic, local review of explicit binary cel-shadow masks."""

from __future__ import annotations

from dataclasses import dataclass

from .model import Evidence, EvidenceSource, Review

MAX_MASK_PIXELS = 128 * 128


@dataclass(frozen=True, slots=True)
class BinaryMaskStats:
    shadow_area_ratio: float
    fragmentation: float
    isolated_islands: float
    edge_complexity: float
    component_count: int

    def to_dict(self, prefix: str = "") -> dict[str, float]:
        return {
            prefix + "shadow_area_ratio": self.shadow_area_ratio,
            prefix + "fragmentation": self.fragmentation,
            prefix + "isolated_islands": self.isolated_islands,
            prefix + "edge_complexity": self.edge_complexity,
            prefix + "component_count": float(self.component_count),
        }


def analyze_binary_mask(mask: list[int], width: int, height: int) -> BinaryMaskStats:
    """Measure a bounded 0/1 mask without retaining or reconstructing artwork."""
    if width < 2 or height < 2 or width > 128 or height > 128 or width * height > MAX_MASK_PIXELS:
        raise ValueError("binary mask dimensions must be between 2x2 and 128x128")
    if len(mask) != width * height or any(value not in (0, 1) for value in mask):
        raise ValueError("binary mask must contain exactly width*height 0/1 values")
    shadow = sum(mask)
    area = shadow / len(mask)
    components = _components(mask, width, height)
    island_pixels = sum(size for size in components if size <= max(2, shadow * 0.01))
    transitions = 0
    comparisons = 0
    for y in range(height):
        for x in range(width):
            index = y * width + x
            if x + 1 < width:
                transitions += mask[index] != mask[index + 1]
                comparisons += 1
            if y + 1 < height:
                transitions += mask[index] != mask[index + width]
                comparisons += 1
    fragmentation = min(1.0, max(0, len(components) - 1) / 12.0)
    return BinaryMaskStats(
        shadow_area_ratio=area,
        fragmentation=fragmentation,
        isolated_islands=island_pixels / max(1, shadow),
        edge_complexity=transitions / comparisons,
        component_count=len(components),
    )


def review_value_masks(
    front_form_mask: list[int],
    front_cast_mask: list[int],
    turned_form_mask: list[int],
    turned_cast_mask: list[int],
    width: int,
    height: int,
    light_direction: str,
    boundary_hardness: str,
    review_id: str,
    third_value_mask: list[int] | None = None,
) -> Review:
    """Combine artist-confirmed lighting with mask geometry and limited pixels."""
    if light_direction not in {"top_left", "top", "top_right", "left", "right"}:
        raise ValueError("unsupported light direction")
    if boundary_hardness not in {"hard", "moderate"}:
        raise ValueError("unsupported boundary hardness")
    front_form = analyze_binary_mask(front_form_mask, width, height)
    front_cast = analyze_binary_mask(front_cast_mask, width, height)
    turned_form = analyze_binary_mask(turned_form_mask, width, height)
    turned_cast = analyze_binary_mask(turned_cast_mask, width, height)
    if front_form.shadow_area_ratio == 0 or turned_form.shadow_area_ratio == 0:
        raise ValueError("front and turned form-shadow masks must not be empty")
    front = analyze_binary_mask(_union(front_form_mask, front_cast_mask), width, height)
    turned = analyze_binary_mask(_union(turned_form_mask, turned_cast_mask), width, height)
    consistency = max(
        0.0,
        1.0
        - abs(front.shadow_area_ratio - turned.shadow_area_ratio)
        - abs(front.fragmentation - turned.fragmentation) * 0.5
        - abs(front.edge_complexity - turned.edge_complexity) * 0.5,
    )
    measurements = (
        front.to_dict("front_combined_")
        | turned.to_dict("turned_combined_")
        | front_form.to_dict("front_form_")
        | front_cast.to_dict("front_cast_")
        | turned_form.to_dict("turned_form_")
        | turned_cast.to_dict("turned_cast_")
    )
    measurements["front_turned_consistency"] = consistency
    explanations = [
        f"The artist confirmed a {light_direction.replace('_', ' ')} light with a "
        f"{boundary_hardness} boundary.",
        "The review measured only binary mask geometry: occupied area, connected "
        "fragments, small islands, boundary complexity, and front/turned consistency.",
        "Form and cast shadows were measured separately, then combined to audit the "
        "large shadow-family read. An empty cast mask is valid; an empty form mask is not.",
    ]
    targeted = []
    if max(front.fragmentation, turned.fragmentation) > 0.35:
        targeted.append("cel-value-mask-consolidation")
        explanations.append(
            "The shadow family is fragmented; inspect whether nearby islands share one cause."
        )
    if max(front.isolated_islands, turned.isolated_islands) > 0.10:
        targeted.append("cel-value-island-audit")
    if consistency < 0.70:
        targeted.append("cel-value-light-transfer")
        explanations.append(
            "Front and turned masks differ enough to warrant a light-transfer audit."
        )
    if third_value_mask is not None:
        third = analyze_binary_mask(third_value_mask, width, height)
        ratio = third.shadow_area_ratio / max(front.shadow_area_ratio, 1 / (width * height))
        measurements |= third.to_dict("third_value_")
        measurements["third_value_to_primary_ratio"] = ratio
        if ratio > 0.25:
            targeted.append("cel-value-third-value-restraint")
            explanations.append(
                "The optional third value is competing with the primary shadow family."
            )
    return Review(
        id=review_id,
        exercise_id="anime-head-cel-values",
        exercise_version="1.0.0",
        method_id="anime-head-construction-v1",
        rubric_id="anime-head-cel-value-mask",
        rubric_version="1.0.0",
        evidence=[
            Evidence((0, 0, 1, 1), EvidenceSource.ARTIST_CONFIRMATION, 1.0, "light statement"),
            Evidence((0, 0, 1, 1), EvidenceSource.HEURISTIC, 1.0, "binary mask geometry"),
        ],
        explanations=explanations,
        measurements=measurements,
        targeted_exercise_ids=list(dict.fromkeys(targeted)),
    )


def _components(mask: list[int], width: int, height: int) -> list[int]:
    unseen = {index for index, value in enumerate(mask) if value}
    sizes = []
    while unseen:
        pending = [unseen.pop()]
        size = 0
        while pending:
            index = pending.pop()
            size += 1
            x, y = index % width, index // width
            for neighbor in (index - 1, index + 1, index - width, index + width):
                if (
                    neighbor in unseen
                    and abs(neighbor % width - x) + abs(neighbor // width - y) == 1
                ):
                    unseen.remove(neighbor)
                    pending.append(neighbor)
        sizes.append(size)
    return sizes


def _union(first: list[int], second: list[int]) -> list[int]:
    return [int(left or right) for left, right in zip(first, second, strict=True)]

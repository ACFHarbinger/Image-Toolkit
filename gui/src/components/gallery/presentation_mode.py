"""Gallery Presentation Modes and Thumbnail Overlay Badges (§2.40, #508, #514)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GalleryPresentationMode(str, Enum):
    """Layout presentation modes for image galleries."""

    UNIFORM_GRID = "uniform_grid"
    MASONRY = "masonry"
    COMPACT_LIST = "compact_list"


RATING_COLORS: dict[str, str] = {
    "g": "#55c57a",  # General - Green
    "s": "#38bdf8",  # Sensitive - Cyan
    "q": "#fb923c",  # Questionable - Orange
    "e": "#f87171",  # Explicit - Red
}


@dataclass(slots=True)
class GalleryOverlayConfig:
    """Configuration toggles for thumbnail card overlays and badges."""

    show_rating: bool = True
    show_resolution: bool = True
    show_format: bool = True
    show_star_rating: bool = True
    show_tag_count: bool = True


__all__ = [
    "GalleryOverlayConfig",
    "GalleryPresentationMode",
    "RATING_COLORS",
]

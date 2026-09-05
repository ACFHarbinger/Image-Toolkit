"""gui/src/modules/descriptor.py
=============================
Declarative ModuleDescriptor contract (§1.3, #527).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

from PySide6.QtWidgets import QWidget


class ModuleCategory(str, Enum):
    """Functional categories for application modules."""

    SYSTEM = "System Tools"
    LIBRARY = "Library Database"
    WEB = "Web Integration"
    DEEP_LEARNING = "Deep Learning"
    STITCHING = "Image Stitching"
    MANGA = "Manga"
    EDITOR = "Image Editor"
    DEVELOPER = "Developer / Diagnostics"


class ConstructionPolicy(str, Enum):
    """Defines when a module's UI widget tree is constructed."""

    LAZY = "lazy"
    EAGER = "eager"


@dataclass(frozen=True)
class ModuleRoute:
    """Child route specification within a module workspace."""

    route_id: str
    title: str
    description: str = ""


@dataclass
class ModuleDescriptor:
    """Declarative descriptor defining metadata, construction, and routes for a tool/workspace."""

    id: str
    title: str
    category: ModuleCategory
    japanese_subtext: Optional[str] = None
    icon_name: str = "box"
    construction_policy: ConstructionPolicy = ConstructionPolicy.LAZY
    view_factory: Optional[Callable[[], QWidget]] = None
    instance: Optional[QWidget] = None
    child_routes: list[ModuleRoute] = field(default_factory=list)
    singleton: bool = True
    order_index: int = 0
    shortcut: Optional[str] = None
    badge_provider: Optional[Callable[[], Optional[str]]] = None
    pinned_default: bool = True

    def get_widget(self) -> QWidget:
        """Get or lazily construct the module view widget."""
        if self.instance is not None:
            return self.instance

        if self.view_factory is not None:
            widget = self.view_factory()
            if self.singleton:
                self.instance = widget
            return widget

        raise RuntimeError(f"Module '{self.id}' has neither active instance nor view_factory")

    def has_child_route(self, route_id: str) -> bool:
        """Check if this module supports a given child route."""
        return any(r.route_id == route_id for r in self.child_routes)

    def get_child_route(self, route_id: str) -> Optional[ModuleRoute]:
        """Retrieve child route specification by id."""
        for r in self.child_routes:
            if r.route_id == route_id:
                return r
        return None


__all__ = [
    "ConstructionPolicy",
    "ModuleCategory",
    "ModuleDescriptor",
    "ModuleRoute",
]

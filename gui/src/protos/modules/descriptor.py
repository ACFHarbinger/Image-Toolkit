"""Declarative module descriptor protocol (#438, gui_ux.md §2.36)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

from PySide6.QtWidgets import QWidget


class ModuleCategory(str, Enum):
    SYSTEM = "System Tools"
    LIBRARY = "Library Database"
    WEB = "Web Integration"
    DEEP_LEARNING = "Deep Learning"
    STITCHING = "Image Stitching"
    MANGA = "Manga"
    EDITOR = "Image Editor"


@dataclass
class ModuleDescriptor:
    """Declarative descriptor for an application tool or tab."""

    id: str
    title: str
    category: ModuleCategory
    japanese_subtext: Optional[str] = None
    icon_name: str = "box"
    view_factory: Optional[Callable[[], QWidget]] = None
    instance: Optional[QWidget] = None
    shortcut: Optional[str] = None
    badge_provider: Optional[Callable[[], Optional[str]]] = None
    pinned_default: bool = True
    order_index: int = 0

    def get_widget(self) -> QWidget:
        """Get or lazily construct the tool widget."""
        if self.instance is not None:
            return self.instance
        if self.view_factory is not None:
            self.instance = self.view_factory()
            return self.instance
        raise RuntimeError(f"Module {self.id} has neither instance nor view_factory")


__all__ = ["ModuleCategory", "ModuleDescriptor"]

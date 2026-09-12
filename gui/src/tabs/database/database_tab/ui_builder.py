"""UI Builder coordinating DatabaseTab section layouts via composition (§5.17, #544)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QGroupBox, QScrollArea, QVBoxLayout

from ....theming.theme_api import qss
from ._ui_connection import build_connection_section
from ._ui_groups import build_groups_section
from ._ui_registry import build_registry_section
from ._ui_subgroups import build_subgroups_section
from ._ui_tags import build_tags_section

if TYPE_CHECKING:
    from .manager import DatabaseTab


class DatabaseUIBuilder:
    """Builds and attaches visual sections to a DatabaseTab instance."""

    def __init__(self, tab: DatabaseTab) -> None:
        self.tab = tab

    def build_ui(self, main_layout: QVBoxLayout) -> None:
        build_connection_section(self.tab, main_layout)

        self.tab.populate_group = QGroupBox("Populate Database")
        populate_layout = QVBoxLayout(self.tab.populate_group)

        build_groups_section(self.tab, populate_layout)
        build_subgroups_section(self.tab, populate_layout)
        build_tags_section(self.tab, populate_layout)
        build_registry_section(self.tab, populate_layout)

        populate_scroll_area = QScrollArea()
        populate_scroll_area.setWidgetResizable(True)
        populate_scroll_area.setWidget(self.tab.populate_group)
        populate_scroll_area.setStyleSheet(qss("scroll_area_borderless"))

        main_layout.addWidget(populate_scroll_area)


__all__ = ["DatabaseUIBuilder"]

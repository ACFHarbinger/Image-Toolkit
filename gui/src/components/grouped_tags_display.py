"""Read-only "all tags, grouped by category" section (Danbooru-style tag
overhaul). Shared by the Series and Entity detail panels: genres, freeform
tags, and tags carried transitively through associated entities/series (see
``MediaRepo.get_grouped_tags`` / ``EntityRepo.get_grouped_tags``) all render
here as colored chips under a category header, ordered by
``tag_categories.sort_order``.
"""

from __future__ import annotations

from typing import Dict, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from gui.src.components.tag_chip_widget import FlowLayout, TagChipWidget
from gui.src.theming.theme_api import color, qss


class GroupedTagsDisplay(QWidget):
    """``set_grouped_tags({category_name: [{"name":..., "color":...}, ...]})``."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(8)
        self._empty_label = QLabel("No tags yet.")
        self._empty_label.setStyleSheet(qss("muted_label"))
        self._layout.addWidget(self._empty_label)
        self._section_widgets: List[QWidget] = []

    def clear(self) -> None:
        for widget in self._section_widgets:
            self._layout.removeWidget(widget)
            widget.deleteLater()
        self._section_widgets.clear()
        self._empty_label.setVisible(True)

    def set_grouped_tags(self, grouped: Dict[str, List[Dict[str, str]]]) -> None:
        self.clear()
        if not grouped:
            return
        self._empty_label.setVisible(False)

        for category in sorted(grouped.keys(), key=lambda c: (c == "General", c)):
            tags = grouped[category]
            if not tags:
                continue

            section = QWidget(self)
            section_layout = QVBoxLayout(section)
            section_layout.setContentsMargins(0, 0, 0, 0)
            section_layout.setSpacing(4)

            header = QLabel(category)
            tag_color = tags[0].get("color", color("muted_text"))
            header.setStyleSheet(qss("grouped_tags_header", TAG_COLOR=tag_color))
            section_layout.addWidget(header)

            chip_row = QWidget(section)
            flow = FlowLayout(chip_row, spacing=4)
            for tag in sorted(tags, key=lambda t: t["name"].lower()):
                chip = TagChipWidget(tag["name"], category=category, parent=chip_row)
                chip.setStyleSheet(
                    qss(
                        "grouped_tags_chip",
                        TAG_COLOR=tag_color,
                        TAG_BG=f"{tag_color}22",
                    )
                )
                # Read-only display: TagChipWidget.mousePressEvent toggles
                # active state (and overwrites our category-color
                # stylesheet) on click -- suppress that entirely here.
                chip.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                chip.setCursor(Qt.CursorShape.ArrowCursor)
                flow.addWidget(chip)
            section_layout.addWidget(chip_row)

            self._layout.addWidget(section)
            self._section_widgets.append(section)


__all__ = ["GroupedTagsDisplay"]

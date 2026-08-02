"""Read-only "all tags, grouped by category" section (Danbooru-style tag
overhaul). Shared by the Series and Entity detail panels: genres, freeform
tags, and tags carried transitively through associated entities/series (see
``MediaRepo.get_grouped_tags`` / ``EntityRepo.get_grouped_tags``) all render
here as colored chips under a category header, ordered by
``tag_categories.sort_order``.
"""

from __future__ import annotations

from typing import Dict, List

from gui.src.components.tag_chip_widget import FlowLayout, TagChipWidget
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class GroupedTagsDisplay(QWidget):
    """``set_grouped_tags({category_name: [{"name":..., "color":...}, ...]})``."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(8)
        self._empty_label = QLabel("No tags yet.")
        self._empty_label.setStyleSheet("color:#888; font-style:italic;")
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
            header.setStyleSheet(
                f"color:{tags[0].get('color', '#95a5a6')}; font-weight:bold; font-size:11px;"
            )
            section_layout.addWidget(header)

            chip_row = QWidget(section)
            flow = FlowLayout(chip_row, spacing=4)
            for tag in sorted(tags, key=lambda t: t["name"].lower()):
                chip = TagChipWidget(tag["name"], category=category, parent=chip_row)
                chip.setStyleSheet(
                    f"QWidget {{ background-color: {tag.get('color', '#95a5a6')}22; "
                    f"color: {tag.get('color', '#95a5a6')}; "
                    f"border: 1px solid {tag.get('color', '#95a5a6')}; "
                    "border-radius: 10px; font-size: 11px; font-weight: 500; }}"
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

"""``FilteredTagList`` -- a checkable tag list filterable by tag type.

Extracted from ``metadata_editor_window.py`` -- pure code motion, no logic
change.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ._shared import _LIST_STYLE, _TAG_COLORS


class FilteredTagList(QWidget):
    """A widget wrapping a QListWidget and horizontal checkboxes to filter by tag type."""
    def __init__(self, tags_data: List[Dict[str, str]], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._tags_data = tags_data

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Master checkbox toggle for filtering
        self.master_filter_layout = QHBoxLayout()
        self.master_filter_layout.setSpacing(10)
        self.master_cb = QCheckBox("Filter by Type")
        self.master_cb.setChecked(False)
        self.master_cb.stateChanged.connect(self._toggle_filter_visibility)
        self.master_filter_layout.addWidget(self.master_cb)

        # Container for the individual type checkboxes
        self.type_container = QWidget()
        self.type_layout = QHBoxLayout(self.type_container)
        self.type_layout.setContentsMargins(0, 0, 0, 0)
        self.type_layout.setSpacing(10)

        self.checkboxes: Dict[str, QCheckBox] = {}
        # Order the types: Artist, Series, Character, General, Meta, then others, then empty/Other
        standard_types = ["Artist", "Series", "Character", "General", "Meta"]
        all_types = []
        for t in standard_types:
            if any((td.get("type") or "") == t for td in tags_data):
                all_types.append(t)
        # Check for others
        for td in tags_data:
            t = td.get("type") or ""
            if t not in all_types and t != "":
                all_types.append(t)
        # Empty/uncategorized type
        if any((td.get("type") or "") == "" for td in tags_data):
            all_types.append("")

        for t in all_types:
            label = t if t != "" else "Other"
            cb = QCheckBox(label)
            color = _TAG_COLORS.get(t, _TAG_COLORS[""])
            cb.setStyleSheet(f"color: {color}; font-weight: bold;")
            cb.setChecked(True)
            cb.stateChanged.connect(self._apply_filter)
            self.type_layout.addWidget(cb)
            self.checkboxes[t] = cb

        self.master_filter_layout.addWidget(self.type_container)
        self.master_filter_layout.addStretch()
        layout.addLayout(self.master_filter_layout)

        # List widget
        self.list_widget = QListWidget()
        self.list_widget.setMinimumHeight(160)
        self.list_widget.setStyleSheet(_LIST_STYLE)

        self._all_items: List[Tuple[QListWidgetItem, str]] = []
        for td in tags_data:
            name = td["name"]
            ttype = td.get("type") or ""
            item = QListWidgetItem(name.replace("_", " ").title())
            item.setData(Qt.ItemDataRole.UserRole, name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setForeground(QColor(_TAG_COLORS.get(ttype, _TAG_COLORS[""])))
            self.list_widget.addItem(item)
            self._all_items.append((item, ttype))

        layout.addWidget(self.list_widget)

        # Initial visibility toggle
        self._toggle_filter_visibility()

    def _toggle_filter_visibility(self) -> None:
        self.type_container.setVisible(self.master_cb.isChecked())
        self._apply_filter()

    def _apply_filter(self) -> None:
        filter_enabled = self.master_cb.isChecked()
        for item, ttype in self._all_items:
            if not filter_enabled:
                item.setHidden(False)
            else:
                cb = self.checkboxes.get(ttype)
                visible = cb.isChecked() if cb else True
                item.setHidden(not visible)

    def checked_tags(self) -> List[str]:
        return [
            item.data(Qt.ItemDataRole.UserRole)
            for item, _ in self._all_items
            if item.checkState() == Qt.CheckState.Checked
        ]

    def set_checked_tags(self, tags: List[str]) -> None:
        tag_set = set(tags)
        for item, _ in self._all_items:
            item.setCheckState(
                Qt.CheckState.Checked
                if item.data(Qt.ItemDataRole.UserRole) in tag_set
                else Qt.CheckState.Unchecked
            )


__all__ = ["FilteredTagList"]

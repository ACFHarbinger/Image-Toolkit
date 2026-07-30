"""
TagChipWidget and TagChipGroup components (§2.22 Option A).
============================================================
Modern chip/badge widgets and flow-style group containers for interactive tag display.
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


class TagChipWidget(QWidget):
    """
    Individual tag chip widget with rounded pill styling, optional close button, and toggle state.

    Signals
    -------
    clicked(str)
        Emitted when the chip is clicked.
    toggled(str, bool)
        Emitted when the chip active state changes.
    removed(str)
        Emitted when the close button is clicked.
    """

    clicked = Signal(str)
    toggled = Signal(str, bool)
    removed = Signal(str)

    def __init__(
        self,
        tag_text: str,
        active: bool = False,
        removable: bool = False,
        category: str = "general",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.tag_text = tag_text
        self._active = active
        self._removable = removable
        self.category = category

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(4)

        self.label = QLabel(self.tag_text, self)
        layout.addWidget(self.label)

        if self._removable:
            self.close_btn = QPushButton("×", self)
            self.close_btn.setFixedSize(14, 14)
            self.close_btn.setFlat(True)
            self.close_btn.setStyleSheet("border: none; font-weight: bold; padding: 0px;")
            self.close_btn.clicked.connect(self._on_remove)
            layout.addWidget(self.close_btn)

        self.setCursor(Qt.PointingHandCursor)
        self._update_style()

    def _update_style(self) -> None:
        bg_color = "#3A3D4E" if not self._active else "#2D6CBE"
        text_color = "#E0E0E0" if not self._active else "#FFFFFF"
        border_color = "#555A70" if not self._active else "#4A90E2"

        self.setStyleSheet(
            f"QWidget {{"
            f"  background-color: {bg_color};"
            f"  color: {text_color};"
            f"  border: 1px solid {border_color};"
            f"  border-radius: 10px;"
            f"  font-size: 11px;"
            f"  font-weight: 500;"
            f"}}"
        )

    def is_active(self) -> bool:
        return self._active

    def set_active(self, active: bool) -> None:
        if self._active != active:
            self._active = active
            self._update_style()
            self.toggled.emit(self.tag_text, self._active)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.set_active(not self._active)
            self.clicked.emit(self.tag_text)
        super().mousePressEvent(event)

    def _on_remove(self) -> None:
        self.removed.emit(self.tag_text)


class TagChipGroup(QWidget):
    """
    Container widget managing a group of interactive TagChipWidget badges.

    Signals
    -------
    tag_clicked(str)
        Emitted when any tag chip in the group is clicked.
    selection_changed(list)
        Emitted when active selection changes, passing list of selected tag strings.
    """

    tag_clicked = Signal(str)
    selection_changed = Signal(list)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._chips: List[TagChipWidget] = []
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(6)

    def set_tags(self, tags: List[str], selected: Optional[List[str]] = None, removable: bool = False) -> None:
        """Populate chip group with a list of tag strings."""
        self.clear()
        selected_set = set(selected or [])
        for tag in tags:
            chip = TagChipWidget(tag, active=(tag in selected_set), removable=removable, parent=self)
            chip.clicked.connect(self._on_chip_clicked)
            chip.toggled.connect(self._on_chip_toggled)
            chip.removed.connect(self.remove_tag)
            self._chips.append(chip)
            self._layout.addWidget(chip)

    def clear(self) -> None:
        """Remove all tag chips from container."""
        for chip in self._chips:
            self._layout.removeWidget(chip)
            chip.deleteLater()
        self._chips.clear()

    def get_selected_tags(self) -> List[str]:
        """Return list of currently active/selected tag strings."""
        return [c.tag_text for c in self._chips if c.is_active()]

    def remove_tag(self, tag_text: str) -> None:
        """Remove a specific tag chip from the group."""
        to_remove = [c for c in self._chips if c.tag_text == tag_text]
        for chip in to_remove:
            self._chips.remove(chip)
            self._layout.removeWidget(chip)
            chip.deleteLater()
        self.selection_changed.emit(self.get_selected_tags())

    def _on_chip_clicked(self, tag_text: str) -> None:
        self.tag_clicked.emit(tag_text)

    def _on_chip_toggled(self, tag_text: str, active: bool) -> None:
        self.selection_changed.emit(self.get_selected_tags())

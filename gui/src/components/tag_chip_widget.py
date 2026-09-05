"""
TagChipWidget and TagChipGroup components (§2.22 Option A).
============================================================
Modern chip/badge widgets and flow-style group containers for interactive tag display.
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QWidgetItem,
)


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


class FlowLayout(QLayout):
    """Minimal wrapping row layout (the standard Qt "Flow Layout" example
    pattern) -- QHBoxLayout doesn't wrap, and a real tag list needs to
    span multiple rows instead of overflowing horizontally."""

    def __init__(self, parent: Optional[QWidget] = None, spacing: int = 6) -> None:
        super().__init__(parent)
        self._items: List[QWidgetItem] = []
        self.setSpacing(spacing)

    def addItem(self, item) -> None:  # noqa: N802 -- Qt override
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):  # noqa: N802 -- Qt override
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int):  # noqa: N802 -- Qt override
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):  # noqa: N802 -- Qt override
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802 -- Qt override
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802 -- Qt override
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect) -> None:  # noqa: N802 -- Qt override
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(
            margins.left() + margins.right(), margins.top() + margins.bottom()
        )
        return size

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        x, y = rect.x(), rect.y()
        line_height = 0
        spacing = self.spacing()

        for item in self._items:
            widget = item.widget()
            if widget is not None and not widget.isVisible():
                continue
            hint = item.sizeHint()
            next_x = x + hint.width() + spacing
            if next_x - spacing > rect.right() and line_height > 0:
                x = rect.x()
                y = y + line_height + spacing
                next_x = x + hint.width() + spacing
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))

            x = next_x
            line_height = max(line_height, hint.height())

        return y + line_height - rect.y()


class TagChipEditor(QWidget):
    """Per-entry tag editor: a wrapping row of removable ``TagChipWidget``
    chips plus a single-tag "add" input with autocomplete (issue #127).

    Every chip present IS a tag on this entry -- unlike ``TagChipGroup``
    (built for filter-picker use cases, where ``active``/toggle state
    selects a subset of a fixed vocabulary), there's no toggle semantics
    here: a chip's only two states are "present" and "removed via its
    little x button".

    Exposes ``setText()``/``text()``/``clear()`` matching the plain
    ``QLineEdit`` (comma-separated string) contract this widget replaces,
    so callers that load/save a CSV string need no other changes.
    """

    changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None, placeholder: str = "") -> None:
        super().__init__(parent)
        self._tags: List[str] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._chip_container = QWidget(self)
        self._flow = FlowLayout(self._chip_container)
        self._chip_container.setMinimumHeight(28)
        layout.addWidget(self._chip_container)

        self.add_edit = QLineEdit(self)
        if placeholder:
            self.add_edit.setPlaceholderText(placeholder)
        self.add_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.add_edit.returnPressed.connect(self._commit_input)
        layout.addWidget(self.add_edit)

    # ---- QLineEdit-compatible contract ---------------------------------

    def setText(self, csv_text: str) -> None:  # noqa: N802 -- Qt-style API
        tags = [t.strip() for t in (csv_text or "").split(",") if t.strip()]
        self._set_tags(tags)

    def text(self) -> str:
        return ", ".join(self._tags)

    def clear(self) -> None:
        self._set_tags([])
        self.add_edit.clear()

    # ---- Autocomplete wiring --------------------------------------------

    def attach_completer(self, completer) -> None:
        """Attach a ``TagCompleter`` to the add-input. Selecting a
        completion commits it as a chip immediately (rather than the
        completer's own comma-joining behavior, built for a plain
        multi-tag QLineEdit -- this widget is single-tag-per-commit)."""
        self.add_edit.setCompleter(completer)
        completer.activated.connect(self._on_completion_activated)

    # ---- Internals -------------------------------------------------------

    def _on_completion_activated(self, tag: str) -> None:
        self._add_tags([tag])
        self.add_edit.clear()

    def _commit_input(self) -> None:
        raw = self.add_edit.text()
        self._add_tags(part.strip() for part in raw.split(","))
        self.add_edit.clear()

    def _add_tags(self, tags) -> None:
        changed = False
        for tag in tags:
            if tag and tag not in self._tags:
                self._tags.append(tag)
                changed = True
        if changed:
            self._rebuild_chips()
            self.changed.emit()

    def _set_tags(self, tags: List[str]) -> None:
        seen = set()
        ordered = []
        for tag in tags:
            if tag not in seen:
                seen.add(tag)
                ordered.append(tag)
        self._tags = ordered
        self._rebuild_chips()

    def _on_chip_removed(self, tag_text: str) -> None:
        if tag_text in self._tags:
            self._tags.remove(tag_text)
            self._rebuild_chips()
            self.changed.emit()

    def _rebuild_chips(self) -> None:
        while self._flow.count():
            item = self._flow.takeAt(0)
            widget = item.widget() if item else None
            if widget is not None:
                widget.deleteLater()

        for tag in self._tags:
            chip = TagChipWidget(
                tag, active=True, removable=True, parent=self._chip_container
            )
            chip.removed.connect(self._on_chip_removed)
            self._flow.addWidget(chip)

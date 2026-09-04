"""Segmented control pill button group for modern creative suite layouts (§2.37)."""

from __future__ import annotations

from typing import Any, Optional
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QPushButton, QWidget


class SegmentedControl(QWidget):
    """Horizontal segmented button group with connected pill styling."""

    selection_changed = Signal(str)  # selected key or label

    def __init__(self, items: list[tuple[str, str]], parent: Optional[QWidget] = None) -> None:
        """items: list of (key, display_label) tuples."""
        super().__init__(parent)
        self._items = items
        self._buttons: dict[str, QPushButton] = {}
        self._active_key: Optional[str] = None
        self._build_ui()

    def _build_ui(self) -> None:
        self.setObjectName("segmented_control")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.group = QButtonGroup(self)
        n = len(self._items)

        for i, (key, label) in enumerate(self._items):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setObjectName(f"seg_btn_{key}")

            # Border radius styling for start/middle/end pills
            if n == 1:
                border_style = "border-radius: 6px;"
            elif i == 0:
                border_style = "border-top-left-radius: 6px; border-bottom-left-radius: 6px; border-right: none;"
            elif i == n - 1:
                border_style = "border-top-right-radius: 6px; border-bottom-right-radius: 6px; border-left: none;"
            else:
                border_style = "border-radius: 0px; border-right: none; border-left: none;"

            btn.setStyleSheet(f"QPushButton {{ padding: 6px 14px; font-size: 9pt; font-weight: 500; {border_style} }}")
            btn.clicked.connect(lambda _=False, k=key: self._on_btn_clicked(k))
            self.group.addButton(btn)
            self._buttons[key] = btn
            layout.addWidget(btn)

        if self._items:
            self.set_selected(self._items[0][0])

    def _on_btn_clicked(self, key: str) -> None:
        self._active_key = key
        for k, btn in self._buttons.items():
            btn.setChecked(k == key)
        self.selection_changed.emit(key)

    def set_selected(self, key: str) -> None:
        if key in self._buttons:
            self._active_key = key
            for k, btn in self._buttons.items():
                btn.setChecked(k == key)
            self.selection_changed.emit(key)

    @property
    def selected_key(self) -> Optional[str]:
        return self._active_key


__all__ = ["SegmentedControl"]

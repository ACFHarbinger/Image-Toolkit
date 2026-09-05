"""
Rating & Color Label Filter Bar Widget (GUI/UX §2.18D).

A compact toolbar widget for filtering gallery items by star rating (1–5)
and/or color labels (red, orange, yellow, green, blue, purple).
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QWidget,
)


class RatingFilterBar(QWidget):
    """Filter bar for star ratings and color labels."""

    # Emits (min_stars: int, color_label: Optional[str])
    filter_changed = Signal(int, object)

    _LABEL_COLORS = {
        "red": ("🔴", "#e74c3c"),
        "orange": ("🟠", "#e67e22"),
        "yellow": ("🟡", "#f1c40f"),
        "green": ("🟢", "#2ecc71"),
        "blue": ("🔵", "#3498db"),
        "purple": ("🟣", "#9b59b6"),
    }

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._min_rating: int = 0
        self._selected_color_label: Optional[str] = None

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        # Star Rating Group
        lbl_star = QLabel("Rating:")
        lbl_star.setStyleSheet("color: #888888; font-weight: bold; font-size: 11px;")
        layout.addWidget(lbl_star)

        self._star_group = QButtonGroup(self)
        self._star_group.setExclusive(True)

        star_options = [(0, "All"), (1, "★ 1+"), (2, "★ 2+"), (3, "★ 3+"), (4, "★ 4+"), (5, "★ 5")]
        for val, label in star_options:
            btn = QToolButton(self)
            btn.setText(label)
            btn.setCheckable(True)
            if val == 0:
                btn.setChecked(True)
            btn.clicked.connect(lambda checked=False, v=val: self._on_star_clicked(v))
            self._star_group.addButton(btn, val)
            layout.addWidget(btn)

        layout.addSpacing(8)

        # Color Label Group
        lbl_col = QLabel("Label:")
        lbl_col.setStyleSheet("color: #888888; font-weight: bold; font-size: 11px;")
        layout.addWidget(lbl_col)

        self._label_buttons: dict[str, QToolButton] = {}
        for key, (icon, _hex_col) in self._LABEL_COLORS.items():
            btn = QToolButton(self)
            btn.setText(icon)
            btn.setToolTip(f"Filter by {key.capitalize()} label")
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked=False, k=key: self._on_label_clicked(k))
            self._label_buttons[key] = btn
            layout.addWidget(btn)

        layout.addSpacing(6)

        # Reset button
        self.btn_reset = QToolButton(self)
        self.btn_reset.setText("✕ Reset")
        self.btn_reset.setToolTip("Clear all rating and label filters")
        self.btn_reset.clicked.connect(self.reset_filters)
        layout.addWidget(self.btn_reset)

        layout.addStretch()

    def _on_star_clicked(self, rating: int) -> None:
        self._min_rating = rating
        self._emit_change()

    def _on_label_clicked(self, key: str) -> None:
        if self._selected_color_label == key:
            # Uncheck
            self._selected_color_label = None
            if key in self._label_buttons:
                self._label_buttons[key].setChecked(False)
        else:
            self._selected_color_label = key
            for k, b in self._label_buttons.items():
                b.setChecked(k == key)
        self._emit_change()

    def reset_filters(self) -> None:
        """Reset all active filters to default (all visible)."""
        self._min_rating = 0
        self._selected_color_label = None
        all_btn = self._star_group.button(0)
        if all_btn:
            all_btn.setChecked(True)
        for b in self._label_buttons.values():
            b.setChecked(False)
        self._emit_change()

    def _emit_change(self) -> None:
        self.filter_changed.emit(self._min_rating, self._selected_color_label)

    @property
    def min_rating(self) -> int:
        return self._min_rating

    @property
    def selected_color_label(self) -> Optional[str]:
        return self._selected_color_label

    def matches(self, rating: Optional[float] = None, label: Optional[str] = None) -> bool:
        """Return True if an item with *rating* and *label* matches current filters."""
        if self._min_rating > 0 and (rating is None or rating < self._min_rating):
            return False
        return not (self._selected_color_label is not None and label != self._selected_color_label)


__all__ = ["RatingFilterBar"]

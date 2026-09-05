"""
Gallery Filter & Sort Controls Bar (§2.13 Options A, B, & E).
=============================================================
Reusable toolbar widget combining sort keys, asc/desc toggle, format chips, and search filtering.
"""

from __future__ import annotations

import os
from typing import Any, List, Optional, Set

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QWidget,
)


class GalleryFilterSortBar(QWidget):
    """
    Toolbar providing sort controls, format extension chips, and real-time query filtering.

    Signals
    -------
    sort_changed(str, bool)
        Emitted when sort key or direction changes: (sort_key, is_reversed).
    filter_changed(object, str, float)
        Emitted when extension, query, or min_rating changes: (extensions_set_or_none, query, min_rating).
    """

    sort_changed = Signal(str, bool)
    filter_changed = Signal(object, str, float)

    _SORT_MAP = {
        "Name": "name",
        "Date Modified": "date",
        "File Size": "size",
        "Extension": "extension",
        "Rating": "rating",
        "Resolution": "resolution",
    }

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._reverse_sort = False
        self._active_extensions: Optional[Set[str]] = None
        self._bound_target: Optional[Any] = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)

        # Sort label + combo
        sort_lbl = QLabel("Sort:", self)
        sort_lbl.setStyleSheet("font-size: 11px; color: #a0a0a0; font-weight: 500;")
        layout.addWidget(sort_lbl)

        self.sort_combo = QComboBox(self)
        self.sort_combo.addItems(list(self._SORT_MAP.keys()))
        self.sort_combo.setFixedWidth(110)
        self.sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        layout.addWidget(self.sort_combo)

        # Asc / Desc button
        self.sort_dir_btn = QPushButton("↑", self)
        self.sort_dir_btn.setFixedSize(26, 26)
        self.sort_dir_btn.setToolTip("Ascending (click to toggle descending)")
        self.sort_dir_btn.clicked.connect(self._toggle_sort_direction)
        layout.addWidget(self.sort_dir_btn)

        # Format chips container
        self._format_btn_group = QButtonGroup(self)
        self._format_btn_group.setExclusive(False)

        self.all_formats_btn = QPushButton("ALL", self)
        self.all_formats_btn.setCheckable(True)
        self.all_formats_btn.setChecked(True)
        self.all_formats_btn.setFixedHeight(24)
        self.all_formats_btn.clicked.connect(self._on_all_formats_clicked)
        layout.addWidget(self.all_formats_btn)

        self._ext_buttons: dict[str, QPushButton] = {}
        for ext in ("PNG", "JPG", "WEBP", "GIF"):
            btn = QPushButton(ext, self)
            btn.setCheckable(True)
            btn.setFixedHeight(24)
            btn.clicked.connect(self._on_extension_chip_clicked)
            self._ext_buttons[ext.lower()] = btn
            layout.addWidget(btn)

        # Search filter edit
        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText("Filter files (e.g. -draft, phrase, a|b)…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.search_edit.textChanged.connect(self._on_filter_changed)
        layout.addWidget(self.search_edit)

    # ---- Bind to Gallery or Model ---------------------------------------

    def bind_gallery(self, gallery: Any) -> None:
        """Auto-wire filter/sort signals to target VirtualGallery or VirtualGalleryModel."""
        self._bound_target = gallery
        self.sort_changed.connect(gallery.sort_by)
        self.filter_changed.connect(
            lambda exts, q, r: gallery.filter_by(extensions=exts, query=q, min_rating=r)
        )

    # ---- Slot handlers --------------------------------------------------

    @Slot()
    def _on_sort_changed(self) -> None:
        key_label = self.sort_combo.currentText()
        sort_key = self._SORT_MAP.get(key_label, "name")
        self.sort_changed.emit(sort_key, self._reverse_sort)

    @Slot()
    def _toggle_sort_direction(self) -> None:
        self._reverse_sort = not self._reverse_sort
        if self._reverse_sort:
            self.sort_dir_btn.setText("↓")
            self.sort_dir_btn.setToolTip("Descending (click to toggle ascending)")
        else:
            self.sort_dir_btn.setText("↑")
            self.sort_dir_btn.setToolTip("Ascending (click to toggle descending)")
        self._on_sort_changed()

    @Slot()
    def _on_all_formats_clicked(self) -> None:
        self.all_formats_btn.setChecked(True)
        for btn in self._ext_buttons.values():
            btn.setChecked(False)
        self._active_extensions = None
        self._on_filter_changed()

    @Slot()
    def _on_extension_chip_clicked(self) -> None:
        selected = {ext for ext, btn in self._ext_buttons.items() if btn.isChecked()}
        if not selected:
            self.all_formats_btn.setChecked(True)
            self._active_extensions = None
        else:
            self.all_formats_btn.setChecked(False)
            self._active_extensions = selected
        self._on_filter_changed()

    @Slot()
    def _on_filter_changed(self) -> None:
        query = self.search_edit.text()
        self.filter_changed.emit(self._active_extensions, query, 0.0)

    # ---- Dynamic format chips -------------------------------------------

    def update_formats_from_paths(self, paths: List[str]) -> None:
        """Scan paths and highlight/enable available format extensions."""
        present_exts = {
            os.path.splitext(p)[1].lower().lstrip(".") for p in paths if p
        }
        for ext, btn in self._ext_buttons.items():
            btn.setEnabled(ext in present_exts)


__all__ = ["GalleryFilterSortBar"]

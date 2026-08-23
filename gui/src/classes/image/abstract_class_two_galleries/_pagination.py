"""Pagination controls, page/thumb-size handlers, and page-indicator refresh.

Extracted from ``abstract_class_two_galleries.py`` -- pure code motion, no
logic change (see ``_navigation.py``'s docstring).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Optional, cast

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QWidget

if TYPE_CHECKING:
    from ..protos.abstract_class_two_galleries import AbstractClassTwoGalleriesHostProtocol


class _PaginationMixin:
    """Build pagination controls for both galleries and drive page/thumb changes."""

    def create_pagination_controls(self: "AbstractClassTwoGalleriesHostProtocol", is_found_gallery: bool) -> QWidget:
        """Creates pagination using shared logic, then binds contextual signals."""
        container, controls = self.common_create_pagination_ui()

        # Center the controls horizontally (User request: bottom center)
        if container.layout():
            container.layout().setAlignment(Qt.AlignmentFlag.AlignCenter)  # pyrefly: ignore [missing-attribute]

        # Bind signals depending on context
        controls["combo"].currentTextChanged.connect(
            lambda text: self._on_page_size_changed(text, is_found_gallery)
        )
        controls["btn_prev"].clicked.connect(
            lambda: self._change_page(-1, is_found_gallery)
        )
        controls["btn_next"].clicked.connect(
            lambda: self._change_page(1, is_found_gallery)
        )

        # §4.11 — thumbnail slider
        slider = controls["thumb_slider"]
        size_lbl = controls["thumb_size_lbl"]
        slider.setValue(self.thumbnail_size)
        size_lbl.setText(f"{self.thumbnail_size} px")
        slider.valueChanged.connect(
            lambda v, f=is_found_gallery: self._on_thumb_slider_changed(v, f)
        )
        slider.sliderReleased.connect(self._save_thumbnail_size)

        # §2.13A — sort controls (wire once on the found gallery; applies globally)
        if is_found_gallery:
            sc = controls["sort_combo"]
            sd = controls["sort_dir_btn"]
            sc.currentTextChanged.connect(self._on_sort_combo_changed)
            sd.clicked.connect(lambda: self._on_sort_dir_toggled(sd))

        # Store references
        if is_found_gallery:
            self.found_page_button = controls["btn_page"]
            self.found_prev_btn = controls["btn_prev"]
            self.found_next_btn = controls["btn_next"]
            self.found_item_range_lbl = controls["item_range_lbl"]
            self.found_thumb_slider = slider
            self.found_thumb_size_lbl = size_lbl
        else:
            self.selected_page_button = controls["btn_page"]
            self.selected_prev_btn = controls["btn_prev"]
            self.selected_next_btn = controls["btn_next"]
            self.selected_item_range_lbl = controls["item_range_lbl"]
            self.selected_thumb_slider = slider
            self.selected_thumb_size_lbl = size_lbl

        return container

    def _on_page_size_changed(self: "AbstractClassTwoGalleriesHostProtocol", text: str, is_found: bool):
        size = 999999 if text == "All" else int(text)
        if is_found:
            self.found_page_size = size
            self.found_current_page = 0
            self.refresh_found_gallery()
        else:
            self.selected_page_size = size
            self.selected_current_page = 0
            self.refresh_selected_panel()

    def _on_thumb_slider_changed(self: "AbstractClassTwoGalleriesHostProtocol", value: int, is_found: bool) -> None:
        """Live thumbnail resize via slider (§4.11). Snaps to nearest 16px step."""
        snapped = max(64, min(512, (value // 16) * 16))
        if snapped == self.thumbnail_size:
            return
        self.thumbnail_size = snapped
        self.approx_item_width = snapped + self.padding_width + 20
        # Keep both sliders in sync
        self._sync_thumb_slider()
        self._on_layout_change()
        self._recreate_galleries_on_zoom()

    def _change_page(self: "AbstractClassTwoGalleriesHostProtocol", delta: int, is_found: bool):
        if is_found:
            total = len(self.found_files)
            max_p = math.ceil(total / self.found_page_size) - 1
            new_p = max(0, min(self.found_current_page + delta, max_p))
            if new_p != self.found_current_page:
                self.found_current_page = new_p
                self.refresh_found_gallery()
        else:
            total = len(self.selected_files)
            max_p = math.ceil(total / self.selected_page_size) - 1
            new_p = max(0, min(self.selected_current_page + delta, max_p))
            if new_p != self.selected_current_page:
                self.selected_current_page = new_p
                self.refresh_selected_panel()

    def _jump_to_page(self: "AbstractClassTwoGalleriesHostProtocol", page_index: int, is_found: bool):
        if is_found:
            if page_index != self.found_current_page:
                self.found_current_page = page_index
                self.refresh_found_gallery()
        else:
            if page_index != self.selected_current_page:
                self.selected_current_page = page_index
                self.refresh_selected_panel()

    def _update_pagination_ui(self: "AbstractClassTwoGalleriesHostProtocol", is_found: bool, mode: Optional[str] = "scan"):
        if is_found:
            if not hasattr(self, "found_page_button"):
                return
            controls = {
                "btn_page": self.found_page_button,
                "btn_prev": self.found_prev_btn,
                "btn_next": self.found_next_btn,
            }
            total = len(self.found_files)
            size = self.found_page_size
            current = self.found_current_page
        else:
            if not hasattr(self, "selected_page_button"):
                return
            controls = {
                "btn_page": self.selected_page_button,
                "btn_prev": self.selected_prev_btn,
                "btn_next": self.selected_next_btn,
            }
            total = len(self.selected_files)
            size = self.selected_page_size
            current = self.selected_current_page

        # Shared State Update Logic
        corrected_page, total_pages = self.common_update_pagination_state(
            total, size, current, controls
        )

        if is_found:
            self.found_current_page = corrected_page
        else:
            self.selected_current_page = corrected_page

        # §3.9 — update item range label
        range_lbl = getattr(
            self, "found_item_range_lbl" if is_found else "selected_item_range_lbl", None
        )
        if range_lbl is not None:
            if total == 0:
                range_lbl.setText("0 images")
            else:
                first = corrected_page * size + 1
                last = min(first + size - 1, total)
                range_lbl.setText(f"Items {first}–{last} of {total}")

        # --- FIX: Prevent memory leak and crash by deleting the old menu safely ---
        old_menu = controls["btn_page"].menu()
        if old_menu:
            old_menu.deleteLater()

        # Update Menu
        menu = QMenu(cast(QWidget, self))
        for i in range(total_pages):
            action = QAction(f"Page {i + 1}", menu)  # Parent to menu instead of self
            action.setCheckable(True)
            action.setChecked(i == corrected_page)
            action.triggered.connect(
                lambda checked=False, p=i, f=is_found: self._jump_to_page(p, f)
            )
            menu.addAction(action)
        controls["btn_page"].setMenu(menu)


__all__ = ["_PaginationMixin"]

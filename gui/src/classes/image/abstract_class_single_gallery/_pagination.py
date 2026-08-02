"""Pagination controls: page-size/page navigation and the page-jump menu.

Extracted from ``abstract_class_single_gallery.py`` -- pure code motion, no
logic change.
"""

from __future__ import annotations

import math

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QWidget


class _PaginationMixin:
    """Builds the pagination bar and handles page/thumbnail-size changes."""

    def create_pagination_controls(self) -> QWidget:
        """Uses shared logic to create UI, then binds signals."""
        container, controls = self.common_create_pagination_ui()

        # Bind Controls
        self.page_combo = controls["combo"]
        self.prev_btn = controls["btn_prev"]
        self.next_btn = controls["btn_next"]
        self.page_button = controls["btn_page"]
        self.item_range_lbl = controls["item_range_lbl"]
        self.thumb_slider = controls["thumb_slider"]
        self.thumb_size_lbl = controls["thumb_size_lbl"]

        # Signal Connections
        self.page_combo.currentTextChanged.connect(self._on_page_size_changed)
        self.prev_btn.clicked.connect(lambda: self._change_page(-1))
        self.next_btn.clicked.connect(lambda: self._change_page(1))

        # §4.11 — thumbnail slider
        self.thumb_slider.setValue(self.thumbnail_size)
        self.thumb_size_lbl.setText(f"{self.thumbnail_size} px")
        self.thumb_slider.valueChanged.connect(self._on_thumb_slider_changed)
        self.thumb_slider.sliderReleased.connect(self._save_thumbnail_size)

        # §2.13A — sort controls
        sc = controls["sort_combo"]
        sd = controls["sort_dir_btn"]
        self.sort_combo = sc
        self.sort_dir_btn = sd
        sc.currentTextChanged.connect(self._on_sort_combo_changed)
        sd.clicked.connect(lambda: self._on_sort_dir_toggled(sd))

        # Initial UI update
        self._update_pagination_ui()

        return container

    def _on_page_size_changed(self, text: str):
        size = 999999 if text == "All" else int(text)
        self.page_size = size
        self.current_page = 0
        self.refresh_gallery_view()

    def _on_thumb_slider_changed(self, value: int) -> None:
        """Live thumbnail resize via slider (§4.11)."""
        snapped = max(64, min(512, (value // 16) * 16))
        if snapped == self.thumbnail_size:
            return
        self.thumbnail_size = snapped
        self.approx_item_width = snapped + self.padding_width + 20
        self._sync_thumb_slider()
        self._on_layout_change()
        paths = self.common_get_paginated_slice(
            self.master_image_paths, self.current_page, self.page_size
        )
        if paths:
            self.start_loading_gallery(paths)

    def _change_page(self, delta: int):
        total_items = len(self.gallery_image_paths)
        if total_items == 0:
            return

        max_page = math.ceil(total_items / self.page_size) - 1
        new_page = max(0, min(self.current_page + delta, max_page))

        if new_page != self.current_page:
            self.current_page = new_page
            self.refresh_gallery_view()

    def _jump_to_page(self, page_index: int):
        if page_index != self.current_page:
            self.current_page = page_index
            self.refresh_gallery_view()

    def _update_pagination_ui(self):
        if not hasattr(self, "page_button"):
            return

        controls = {
            "btn_page": self.page_button,
            "btn_prev": self.prev_btn,
            "btn_next": self.next_btn,
        }

        total = len(self.gallery_image_paths)

        # Use shared logic
        corrected_page, total_pages = self.common_update_pagination_state(
            total, self.page_size, self.current_page, controls
        )
        self.current_page = corrected_page

        # §3.9 — update item range label
        if hasattr(self, "item_range_lbl"):
            if total == 0:
                self.item_range_lbl.setText("0 images")
            else:
                first = corrected_page * self.page_size + 1
                last = min(first + self.page_size - 1, total)
                self.item_range_lbl.setText(f"Items {first}–{last} of {total}")

        # --- FIX: Prevent memory leak and crash by deleting the old menu safely ---
        old_menu = self.page_button.menu()
        if old_menu:
            old_menu.deleteLater()

        # Update Menu
        menu = QMenu(self)
        for i in range(total_pages):
            page_num = i + 1
            action = QAction(f"Page {page_num}", menu)  # Parent to menu instead of self
            action.setCheckable(True)
            action.setChecked(i == self.current_page)
            # Use a slightly safer way to connect signals to avoid capturing by reference issues
            action.triggered.connect(lambda checked=False, p=i: self._jump_to_page(p))
            menu.addAction(action)
        self.page_button.setMenu(menu)


__all__ = ["_PaginationMixin"]

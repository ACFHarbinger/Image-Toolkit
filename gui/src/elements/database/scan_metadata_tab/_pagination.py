"""Pagination handlers + page-indicator refresh for ``ScanMetadataTab``.

Extracted from ``scan_metadata_tab.py`` -- pure code motion, no logic
change (see ``_ui_builder.py``'s docstring).
"""

from __future__ import annotations

import math

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu


class _PaginationMixin:
    """Prev/next/page-size handlers for the scan and selected-images galleries."""

    def _on_scan_page_size_changed(self, text):
        if text == "All":
            self.scan_page_size = float("inf")  # pyrefly: ignore [bad-assignment]
        else:
            self.scan_page_size = int(text)
        self.scan_current_page = 0
        self._load_current_scan_page()

    def _on_scan_prev(self):
        if self.scan_current_page > 0:
            self.scan_current_page -= 1
            self._load_current_scan_page()

    def _on_scan_next(self):
        if self.scan_current_page < self.scan_total_pages - 1:
            self.scan_current_page += 1
            self._load_current_scan_page()

    def _on_scan_page_selected(self, index):
        if index >= 0 and index != self.scan_current_page:
            self.scan_current_page = index
            self._load_current_scan_page()

    def _on_sel_page_size_changed(self, text):
        if text == "All":
            self.selected_page_size = float("inf")  # pyrefly: ignore [bad-assignment]
        else:
            self.selected_page_size = int(text)
        self.selected_current_page = 0
        self.populate_selected_images_gallery()

    def _on_sel_prev(self):
        if self.selected_current_page > 0:
            self.selected_current_page -= 1
            self.populate_selected_images_gallery()

    def _on_sel_next(self):
        if self.selected_current_page < self.selected_total_pages - 1:
            self.selected_current_page += 1
            self.populate_selected_images_gallery()

    def _on_sel_page_selected(self, index):
        if index >= 0 and index != self.selected_current_page:
            self.selected_current_page = index
            self.populate_selected_images_gallery()

    def _update_pagination_ui(self, is_found: bool, mode="scan"):
        if mode == "scan":
            total = len(self.scan_filtered_list)
            size = self.scan_page_size
            current = self.scan_current_page
            btn_page = self.scan_pag_btn
            if size == float("inf"):
                self.scan_total_pages = 1
            else:
                self.scan_total_pages = math.ceil(total / size) if total > 0 else 1

            # Clamp
            if self.scan_current_page >= self.scan_total_pages:
                self.scan_current_page = max(0, self.scan_total_pages - 1)
                current = self.scan_current_page

            # Common State Update logic (reusing base class helper logic manually since state is separate)
            btn_page.setText(f"Page {current + 1} / {self.scan_total_pages}")

            self.scan_pag_prev.setEnabled(current > 0)
            self.scan_pag_next.setEnabled(current < self.scan_total_pages - 1)

            # Rebuild Menu
            menu = QMenu(self)
            for i in range(self.scan_total_pages):
                action = QAction(f"Page {i + 1}", self)
                action.setCheckable(True)
                action.setChecked(i == current)
                action.triggered.connect(
                    lambda checked=False, idx=i: self._on_scan_page_selected(idx)
                )
                menu.addAction(action)
            btn_page.setMenu(menu)
        else:
            total = len(self.selected_image_paths)
            size = self.selected_page_size
            current = self.selected_current_page
            btn_page = self.sel_pag_btn

            if size == float("inf"):
                self.selected_total_pages = 1
            else:
                self.selected_total_pages = math.ceil(total / size) if total > 0 else 1

            # Clamp
            if self.selected_current_page >= self.selected_total_pages:
                self.selected_current_page = max(0, self.selected_total_pages - 1)
                current = self.selected_current_page

            btn_page.setText(f"Page {current + 1} / {self.selected_total_pages}")

            self.sel_pag_prev.setEnabled(current > 0)
            self.sel_pag_next.setEnabled(current < self.selected_total_pages - 1)

            # Rebuild Menu
            menu = QMenu(self)
            for i in range(self.selected_total_pages):
                action = QAction(f"Page {i + 1}", self)
                action.setCheckable(True)
                action.setChecked(i == current)
                action.triggered.connect(
                    lambda checked=False, idx=i: self._on_sel_page_selected(idx)
                )
                menu.addAction(action)
            btn_page.setMenu(menu)


__all__ = ["_PaginationMixin"]

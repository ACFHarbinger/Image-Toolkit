"""Selection handling + the bottom "Selected Images" gallery for ``ScanMetadataTab``.

Extracted from ``scan_metadata_tab.py`` -- pure code motion, no logic
change (see ``_ui_builder.py``'s docstring).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QGridLayout, QLabel

from ....utils.sort_utils import natural_sort_key


class _SelectionGalleryMixin:
    """Toggle/marquee selection and rebuild the paginated selected-images gallery."""

    def on_selection_changed(self) -> None:
        """Required by AbstractClassTwoGalleries base class."""
        self.populate_selected_images_gallery()
        self.update_button_states(connected=(self.db_tab_ref.db is not None))

    def _columns(self) -> int:
        width = self.scan_scroll_area.viewport().width()
        if width <= 0:
            width = self.scan_scroll_area.width()
        if width <= 0:
            return 4
        columns = width // self.approx_item_width
        return max(1, columns)

    def _clear_gallery(self, layout: QGridLayout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()  # pyrefly: ignore [missing-attribute]

    def toggle_selection(self, path):
        if not path:
            self.update_button_states(connected=(self.db_tab_ref.db is not None))
            return

        if path in self.selected_image_paths:
            self.selected_image_paths.remove(path)
            selected = False
        else:
            self.selected_image_paths.add(path)
            selected = True

        if path in self.path_to_wrapper_map:
            wrapper = self.path_to_wrapper_map[path]
            inner_label = wrapper.findChild(QLabel)
            is_in_db = wrapper.property("in_db")
            if inner_label:
                self._update_card_style(inner_label, selected, is_in_db)

        self.populate_selected_images_gallery()
        self.update_button_states(connected=(self.db_tab_ref.db is not None))

    def handle_marquee_selection(self, paths_from_marquee: set, is_ctrl_pressed: bool):
        if not is_ctrl_pressed:
            self.selected_image_paths = paths_from_marquee
        else:
            self.selected_image_paths.update(paths_from_marquee)

        for path, wrapper in self.path_to_wrapper_map.items():
            inner_label = wrapper.findChild(QLabel)
            is_in_db = wrapper.property("in_db")
            if inner_label:
                self._update_card_style(
                    inner_label, path in self.selected_image_paths, is_in_db
                )

        self.populate_selected_images_gallery()
        self.update_button_states(connected=(self.db_tab_ref.db is not None))

    def populate_selected_images_gallery(self):
        """Rebuilds the bottom panel using the same card style, now with pagination."""
        self.selected_images_widget.setUpdatesEnabled(False)
        self._clear_gallery(self.selected_grid_layout)

        # 1. Sort all selected paths
        all_selected = sorted(list(self.selected_image_paths), key=natural_sort_key)

        # 2. Update Pagination UI info
        self._update_pagination_ui(is_found=False, mode="selected")

        # 3. Calculate Slice
        start_idx = self.selected_current_page * self.selected_page_size
        if self.selected_page_size == float("inf"):
            page_slice = all_selected
        else:
            end_idx = start_idx + self.selected_page_size
            page_slice = all_selected[start_idx:end_idx]

        # Use dynamic columns here
        widget_width = self.selected_images_area.viewport().width()
        if widget_width <= 0:
            widget_width = self.selected_images_area.width()
        columns = max(1, widget_width // self.approx_item_width)

        if not all_selected:
            empty_label = QLabel("Select images from the scan results above.")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_label.setStyleSheet("color: #b9bbbe; padding: 50px;")
            self.selected_grid_layout.addWidget(empty_label, 0, 0, 1, columns)
            self.selected_images_widget.setUpdatesEnabled(True)
            return

        if not page_slice and self.selected_current_page > 0:
            # Handle case where last item on page was removed, go back one page
            self.selected_current_page -= 1
            self.populate_selected_images_gallery()
            return

        for i, path in enumerate(page_slice):
            pixmap = None
            is_in_db = False

            # If the item is also visible in the top gallery, we can reuse the pixmap for speed
            if path in self.path_to_wrapper_map:
                wrapper = self.path_to_wrapper_map[path]
                is_in_db = wrapper.property("in_db")
                inner_label = wrapper.findChild(QLabel)
                if inner_label and inner_label.pixmap():
                    pixmap = inner_label.pixmap()

            # Fallback load
            if pixmap is None:
                pixmap = QPixmap(path)

            card = self._create_gallery_card(
                path, pixmap, is_selected=True, is_in_db=is_in_db
            )
            card.path_clicked.connect(lambda checked, p=path: self.toggle_selection(p))
            card.path_double_clicked.connect(self._view_single_image_preview)
            card.path_right_clicked.connect(self.show_image_context_menu)

            row = i // columns
            col = i % columns
            self.selected_grid_layout.addWidget(
                card, row, col, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
            )

        self.selected_images_widget.setUpdatesEnabled(True)
        self.selected_images_widget.adjustSize()


__all__ = ["_SelectionGalleryMixin"]

"""Canvas item selection/geometry sync + mode-visibility switching for ``MergeTab``.

Extracted from ``merge_tab.py`` -- pure code motion, no logic change
(see ``_ui_config.py``'s docstring).
"""

from __future__ import annotations

import os
from typing import Optional

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QVBoxLayout, QWidget

from ....classes.mixins import compute_reordered, install_drag_reorder
from ....components import ClickableLabel, MergeCanvasItem


class _CanvasControlsMixin:
    """Canvas per-item controls, mode visibility, and the read-only queue gallery."""

    @Slot(object)
    def _on_canvas_item_selected(self, item: Optional[MergeCanvasItem]):
        has_item = item is not None
        self.btn_remove_from_canvas.setEnabled(has_item)

        self._syncing_spinboxes = True
        for spin in self.spin_list:
            spin.setEnabled(has_item)

        if has_item:
            self.spin_list[0].setValue(int(item.x()))
            self.spin_list[1].setValue(int(item.y()))
            self.spin_list[2].setValue(item._w)
            self.spin_list[3].setValue(item._h)
        self._syncing_spinboxes = False

    def _on_item_spinbox_changed(self):
        if self._syncing_spinboxes:
            return
        item = self.canvas_widget.get_selected_item()
        if item is None:
            return
        self._syncing_spinboxes = True
        item.set_geometry(
            self.spin_list[0].value(),
            self.spin_list[1].value(),
            self.spin_list[2].value(),
            self.spin_list[3].value(),
        )
        self._syncing_spinboxes = False

    def _on_canvas_size_changed(self):
        w = self.canvas_w_spin.value()
        h = self.canvas_h_spin.value()
        self.canvas_widget.resize_canvas(w, h)

    def _remove_from_canvas(self):
        removed = self.canvas_widget.remove_selected()
        for path in removed:
            if path in self.selected_files:
                self.selected_files.remove(path)
            # Deselect in the gallery so the selection model stays consistent.
            sm = self.gallery.view.selectionModel()
            row = self.gallery.model.row_for_path(path)
            if row >= 0:
                sm.select(self.gallery.model.index(row, 0), sm.SelectionFlag.Deselect)
        if removed:
            self.on_selection_changed()

    def _clear_canvas(self):
        paths = self.canvas_widget.clear_canvas()
        for path in paths:
            if path in self.selected_files:
                self.selected_files.remove(path)
            sm = self.gallery.view.selectionModel()
            row = self.gallery.model.row_for_path(path)
            if row >= 0:
                sm.select(self.gallery.model.index(row, 0), sm.SelectionFlag.Deselect)
        if paths:
            self.on_selection_changed()

    # ─── Direction / mode visibility ────────────────────────────────────────────

    def handle_direction_change(self, direction: str):
        is_canvas = direction == "canvas"
        is_grid = direction == "grid"
        is_panorama = direction == "panorama"
        is_complex = direction in ("panorama", "sequential")
        is_gif = direction == "gif"
        is_traditional = not (is_canvas or is_complex or is_gif)

        was_canvas = self._prev_direction == "canvas"
        if was_canvas and not is_canvas:
            self._leave_canvas_mode()
        elif not was_canvas and is_canvas:
            self._enter_canvas_mode()
        self._prev_direction = direction

        self.grid_group.setVisible(is_grid)
        self.lbl_spacing.setVisible(is_traditional and not is_canvas)
        self.spacing.setVisible(is_traditional and not is_canvas)
        self.lbl_align.setVisible(is_traditional and not is_canvas)
        self.align_mode.setVisible(is_traditional and not is_canvas)
        self.lbl_duration.setVisible(is_gif)
        self.duration_spin.setVisible(is_gif)

        self.lbl_engine.setVisible(is_panorama)
        self.engine_combo.setVisible(is_panorama)
        self._update_engine_visibility()

        # Canvas widget (+ its header/per-item controls) only for "canvas"
        # mode; every other mode shows the read-only selection-order gallery.
        self.canvas_header_widget.setVisible(is_canvas)
        self.canvas_widget.setVisible(is_canvas)
        self.item_ctrl_widget.setVisible(is_canvas)
        self.queue_header_label.setVisible(not is_canvas)
        self.queue_gallery_scroll.setVisible(not is_canvas)

    def _leave_canvas_mode(self):
        """Resync the selection queue order from the canvas's current
        insertion order (ascending image index = order added to canvas),
        then switch the visible widget to the read-only queue gallery."""
        layout = self.canvas_widget.get_layout()
        self.selected_files = [entry["path"] for entry in layout]
        self._push_selection_to_gallery()
        self._refresh_queue_gallery()

    def _enter_canvas_mode(self):
        """Repopulate the canvas from the current selection queue, in queue
        order, every item stacked at (0, 0) — canvas drag positions from a
        previous canvas-mode visit are intentionally discarded so re-entry
        is always a clean, predictable reflection of the queue order."""
        self.canvas_widget.clear_canvas()
        for path in self.selected_files:
            thumb = self._thumbnail_for(path)
            item = self.canvas_widget.add_image(path, thumb)
            item.set_geometry(0, 0, item._w, item._h)

    def _thumbnail_for(self, path: str) -> QPixmap:
        cached = self.gallery.cached_image(path)
        if cached and not cached.isNull():
            return QPixmap.fromImage(cached)
        if os.path.isfile(path):
            return QPixmap(path)
        return QPixmap()

    def _refresh_queue_gallery(self):
        """Rebuild the ordered thumbnail strip from self.selected_files (the
        authoritative queue order for every non-canvas mode). Each cell is
        draggable (manual reorder) and right-clickable (preview/deselect/
        delete, via the same menu as the Image Library gallery)."""
        while self.queue_gallery_layout.count():
            item = self.queue_gallery_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        # Pagination: get the current page's slice
        page_size = self._queue_page_size
        current_page = self._queue_current_page
        start = current_page * page_size
        end = start + page_size
        page_entries = self.selected_files[start:end]

        size = self._queue_thumb_size
        cols = self._queue_gallery_cols
        for idx, path in enumerate(page_entries):
            cell = QWidget()
            cell_layout = QVBoxLayout(cell)
            cell_layout.setContentsMargins(2, 2, 2, 2)
            cell_layout.setSpacing(2)

            thumb_label = ClickableLabel(path)
            thumb_label.setFixedSize(size, size)
            thumb_label.setStyleSheet(
                " border-radius: 4px;"
            )
            pix = self._thumbnail_for(path)
            if pix.isNull() and os.path.isfile(path):
                pix = QPixmap(path)
            if not pix.isNull():
                thumb_label.setPixmap(
                    pix.scaled(
                        size,
                        size,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            thumb_label.path_double_clicked.connect(self.handle_full_image_preview)
            thumb_label.path_right_clicked.connect(self.show_image_context_menu)
            cell_layout.addWidget(thumb_label)

            # Use base class helper for filename label (#448)
            self._add_filename_label(thumb_label, path)

            install_drag_reorder(cell, path, self, "reorder_queue")

            self.queue_gallery_layout.addWidget(cell, idx // cols, idx % cols)

        # Update pagination controls
        self._update_queue_pagination_ui()

    def reorder_queue(self, dragged_path: str, target_path: str) -> None:
        """Drag-and-drop callback for the queue gallery. Canvas mode is the
        authoritative order source there (see _leave_canvas_mode), so this
        only runs meaningfully while the queue gallery -- not the canvas --
        is the visible widget, which is the only time the user can drag it."""
        self.selected_files = compute_reordered(
            self.selected_files, dragged_path, target_path
        )
        self._refresh_queue_gallery()

    @Slot()
    def _update_engine_visibility(self):
        """Show only the settings group for the currently-selected engine,
        and only while Mode is 'panorama' (the engine choice is meaningless
        for every other mode)."""
        is_panorama = self.direction.currentText() == "panorama"
        engine = self.engine_combo.currentData() if is_panorama else None

        self.opencv_group.setVisible(is_panorama and engine == "opencv")
        self.hugin_group.setVisible(is_panorama and engine == "hugin")
        self.overmix_group.setVisible(is_panorama and engine == "overmix")
        self.ai_options_group.setVisible(is_panorama and engine == "asp")



    def _update_queue_pagination_ui(self):
        """Update the queue gallery pagination controls."""
        if self._queue_pagination_widget is None:
            # Create pagination controls if they don't exist yet
            container, controls = self.common_create_pagination_ui()
            self._queue_pagination_widget = container
            self._queue_page_combo = controls["combo"]
            self._queue_prev_btn = controls["btn_prev"]
            self._queue_next_btn = controls["btn_next"]
            self._queue_page_btn = controls["btn_page"]
            self._queue_item_range_lbl = controls["item_range_lbl"]

            # Configure for queue gallery
            self._queue_page_combo.setCurrentText(str(self._queue_page_size))
            self._queue_page_combo.currentTextChanged.connect(self._on_queue_page_size_changed)
            self._queue_prev_btn.clicked.connect(lambda: self._change_queue_page(-1))
            self._queue_next_btn.clicked.connect(lambda: self._change_queue_page(1))

            # Insert pagination widget into the layout (after the queue gallery)
            # Find the queue gallery in the layout and add pagination after it
            if hasattr(self, "queue_gallery_scroll") and self.queue_gallery_scroll.parent():
                parent_layout = self.queue_gallery_scroll.parent().layout()
                if parent_layout:
                    parent_layout.addWidget(self._queue_pagination_widget, 0, Qt.AlignmentFlag.AlignCenter)

        total = len(self.selected_files)
        page_size = self._queue_page_size
        current_page = self._queue_current_page

        if total == 0:
            self._queue_page_btn.setText("Page 0 / 0")
            self._queue_page_btn.setEnabled(False)
            self._queue_prev_btn.setEnabled(False)
            self._queue_next_btn.setEnabled(False)
            self._queue_item_range_lbl.setText("0 items")
            return

        total_pages = max(1, (total + page_size - 1) // page_size)
        if current_page >= total_pages:
            current_page = max(0, total_pages - 1)
            self._queue_current_page = current_page

        self._queue_page_btn.setText(f"Page {current_page + 1} / {total_pages}")
        self._queue_page_btn.setEnabled(True)
        self._queue_prev_btn.setEnabled(current_page > 0)
        self._queue_next_btn.setEnabled(current_page < total_pages - 1)

        start = current_page * page_size + 1
        end = min(start + page_size - 1, total)
        self._queue_item_range_lbl.setText(f"Items {start}-{end} of {total}")

    @Slot(str)
    def _on_queue_page_size_changed(self, text: str):
        size = 999999 if text == "All" else int(text)
        self._queue_page_size = size
        self._queue_current_page = 0
        self._refresh_queue_gallery()

    def _change_queue_page(self, delta: int):
        total_items = len(self.selected_files)
        if total_items == 0:
            return

        page_size = self._queue_page_size
        max_page = max(0, (total_items + page_size - 1) // page_size - 1)
        new_page = max(0, min(self._queue_current_page + delta, max_page))

        if new_page != self._queue_current_page:
            self._queue_current_page = new_page
            self._refresh_queue_gallery()

__all__ = ["_CanvasControlsMixin"]

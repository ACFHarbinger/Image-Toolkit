"""Canvas item selection/geometry sync + mode-visibility switching for ``MergeTab``.

Extracted from ``merge_tab.py`` -- pure code motion, no logic change
(see ``_ui_config.py``'s docstring).
"""

from __future__ import annotations

import os
from typing import Optional

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ....components import MergeCanvasItem


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
            widget = self.path_to_card_widget.get(path)
            if widget:
                self.update_card_style(widget, False)
        if removed:
            self.on_selection_changed()

    def _clear_canvas(self):
        paths = self.canvas_widget.clear_canvas()
        for path in paths:
            if path in self.selected_files:
                self.selected_files.remove(path)
            widget = self.path_to_card_widget.get(path)
            if widget:
                self.update_card_style(widget, False)
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
        cached = self._initial_pixmap_cache.get(path)
        if cached and isinstance(cached, QImage) and not cached.isNull():
            return QPixmap.fromImage(cached)
        return QPixmap()

    def _refresh_queue_gallery(self):
        """Rebuild the read-only ordered thumbnail strip from
        self.selected_files (the authoritative queue order for every
        non-canvas mode)."""
        while self.queue_gallery_layout.count():
            item = self.queue_gallery_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        size = self._queue_thumb_size
        cols = self._queue_gallery_cols
        for idx, path in enumerate(self.selected_files):
            cell = QWidget()
            cell_layout = QVBoxLayout(cell)
            cell_layout.setContentsMargins(2, 2, 2, 2)
            cell_layout.setSpacing(2)

            thumb_label = QLabel()
            thumb_label.setFixedSize(size, size)
            thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            thumb_label.setStyleSheet(
                "background-color: #3a3d42; border-radius: 4px;"
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
            cell_layout.addWidget(thumb_label)

            caption = QLabel(f"{idx + 1}. {os.path.basename(path)}")
            caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
            caption.setStyleSheet("color: #b9bbbe; font-size: 10px;")
            caption.setWordWrap(True)
            caption.setFixedWidth(size)
            cell_layout.addWidget(caption)

            self.queue_gallery_layout.addWidget(cell, idx // cols, idx % cols)

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


__all__ = ["_CanvasControlsMixin"]

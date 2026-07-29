"""Viewport-driven lazy thumbnail loading for ``ScanMetadataTab``.

Extracted from ``scan_metadata_tab.py`` -- pure code motion, no logic
change (see ``_ui_builder.py``'s docstring).
"""

from __future__ import annotations

from typing import Any

from gui.src.helpers import ImageLoaderWorker
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel


class _LazyLoadingMixin:
    """Determine visible cards and dispatch ``ImageLoaderWorker`` jobs for them."""

    def _on_scroll_event(self, value):
        """Called whenever the user scrolls. Debounces the heavy calculation."""
        self._lazy_load_timer.start()

    def _process_visible_items(self):
        """Determines which widgets are in the viewport and triggers loading for them."""
        if self._loading_cancelled:
            return

        # 1. Get Viewport Geometry relative to the content widget
        # The visible area starts at the scroll bar value and extends for the viewport height
        scroll_y = self.scan_scroll_area.verticalScrollBar().value()
        viewport_height = self.scan_scroll_area.viewport().height()

        # Define a "buffer" so images start loading slightly before they enter the screen
        buffer_y = 200
        min_y = scroll_y - buffer_y
        max_y = scroll_y + viewport_height + buffer_y

        paths_to_fetch = []

        # 2. Iterate through managed widgets
        # (Using items ensures we don't crash if widgets were deleted)
        for path, widget in self.path_to_wrapper_map.items():
            # Skip if already loaded or currently loading
            if path in self.loaded_paths or path in self.loading_paths:
                continue

            # Get geometry relative to the parent widget (self.scan_thumbnail_widget)
            # widget.y() and widget.height() are lightweight calls
            y = widget.y()
            height = widget.height()

            # Check intersection
            # If the bottom of the widget is below min_y AND the top is above max_y
            if (y + height > min_y) and (y < max_y):
                paths_to_fetch.append(path)
                self.loading_paths.add(path)

        # 3. Batch start threads
        if paths_to_fetch:
            self._start_lazy_batch(paths_to_fetch)

    def _start_lazy_batch(self, paths: list[str]):
        """Starts workers for the identified visible paths."""
        for path in paths:
            if self._loading_cancelled:
                break

            # Re-verify logic to prevent race conditions
            if path in self.loaded_paths:
                continue

            worker = ImageLoaderWorker(path, self.thumbnail_size)
            worker.signals.result.connect(self.on_single_image_loaded)
            self.thread_pool.start(worker)

    def _start_image_loading_pool(self, paths_to_load: list[str]):
        if self._loading_cancelled:
            return

        self.thread_pool.clear()

        for path in paths_to_load:
            if self._loading_cancelled:
                break
            worker = ImageLoaderWorker(path, self.thumbnail_size)
            worker.signals.result.connect(self.on_single_image_loaded)
            self.thread_pool.start(worker)

    @Slot(str, object)
    def on_single_image_loaded(self, path: str, pixmap: Any):
        if self._loading_cancelled:
            return

        # Mark as fully loaded
        self.loaded_paths.add(path)
        if path in self.loading_paths:
            self.loading_paths.remove(path)

        # Buffer now stores QImage to reduce memory footprint
        q_img = None
        if pixmap and not pixmap.isNull():
            q_img = pixmap if isinstance(pixmap, QImage) else pixmap.toImage()

        self._loaded_results_buffer.append((path, q_img))  # pyrefly: ignore [bad-argument-type]

        # --- Update the specific card ---
        if path in self.path_to_wrapper_map:
            wrapper = self.path_to_wrapper_map[path]
            inner_label = wrapper.findChild(QLabel)
            if inner_label:
                # Update Image
                if pixmap and not pixmap.isNull():
                    thumb_size = self.thumbnail_size
                    if pixmap.width() > thumb_size or pixmap.height() > thumb_size:
                        scaled = pixmap.scaled(
                            thumb_size,
                            thumb_size,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.FastTransformation,
                        )
                        display_pixmap = QPixmap.fromImage(scaled) if isinstance(scaled, QImage) else scaled
                        inner_label.setPixmap(display_pixmap)
                    else:
                        display_pixmap = QPixmap.fromImage(pixmap) if isinstance(pixmap, QImage) else pixmap
                        inner_label.setPixmap(display_pixmap)
                else:
                    inner_label.setText("Error")
                    inner_label.setStyleSheet(
                        "color: #e74c3c; border: 1px solid #e74c3c;"
                    )

                # Update border style
                is_selected = path in self.selected_image_paths
                is_in_db = wrapper.property("in_db")
                self._update_card_style(inner_label, is_selected, is_in_db)

    def _finalize_batch_loading(self):
        """Called when all threads in the pool have reported back."""
        if self._loading_cancelled:
            return

        # Final UI adjustments or button state updates
        self.populate_selected_images_gallery()
        self.update_button_states(connected=(self.db_tab_ref.db is not None))


__all__ = ["_LazyLoadingMixin"]

"""Sort controls (GUI/UX §2.13A) and Ctrl+Scroll thumbnail zoom (§2.2).

Extracted from ``abstract_class_single_gallery.py`` -- pure code motion, no
logic change.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..protos.abstract_class_single_gallery import AbstractClassSingleGalleryHostProtocol


class _SortZoomMixin:
    """Sort-combo handling and Ctrl+wheel thumbnail-size zoom."""

    def _on_sort_combo_changed(self: "AbstractClassSingleGalleryHostProtocol", label: str) -> None:
        self._sort_key = self._SORT_KEY_MAP.get(label, "name")
        self.master_image_paths = self._apply_sort(self.master_image_paths)
        self._perform_search()

    def _on_sort_dir_toggled(self: "AbstractClassSingleGalleryHostProtocol", btn) -> None:
        self._sort_reverse = not self._sort_reverse
        btn.setText("↓" if self._sort_reverse else "↑")
        self.master_image_paths = self._apply_sort(self.master_image_paths)
        self._perform_search()

    def _sync_thumb_slider(self: "AbstractClassSingleGalleryHostProtocol") -> None:
        """Push current thumbnail_size to the pagination slider after Ctrl+scroll."""
        slider = getattr(self, "thumb_slider", None)
        if slider is not None:
            slider.blockSignals(True)
            slider.setValue(self.thumbnail_size)
            slider.blockSignals(False)
        lbl = getattr(self, "thumb_size_lbl", None)
        if lbl is not None:
            lbl.setText(f"{self.thumbnail_size} px")

    # --- CTRL+SCROLL ZOOM (GUI/UX §2.2) ---
    def _connect_scroll_zoom(self: "AbstractClassSingleGalleryHostProtocol") -> None:
        if self._scroll_zoom_connected:
            return
        if self.gallery_scroll_area is not None and hasattr(
            self.gallery_scroll_area, "ctrl_wheel"
        ):
            self.gallery_scroll_area.ctrl_wheel.connect(self._on_ctrl_wheel_zoom)
            self._scroll_zoom_connected = True

    def _on_ctrl_wheel_zoom(self: "AbstractClassSingleGalleryHostProtocol", delta: int) -> None:
        step = 16 if delta > 0 else -16
        new_size = max(64, min(512, self.thumbnail_size + step))
        if new_size == self.thumbnail_size:
            return
        self.thumbnail_size = new_size
        self.approx_item_width = new_size + self.padding_width + 20
        self._sync_thumb_slider()
        self._save_thumbnail_size()
        self._on_layout_change()
        current_page = self.common_get_paginated_slice(
            self.master_image_paths, self.current_page, self.page_size
        )
        if current_page:
            self.start_loading_gallery(current_page)


__all__ = ["_SortZoomMixin"]

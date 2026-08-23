"""Sort, thumbnail-zoom (Ctrl+scroll), and layout-reflow handling.

Extracted from ``abstract_class_two_galleries.py`` -- pure code motion, no
logic change (see ``_navigation.py``'s docstring).
"""

from __future__ import annotations

import contextlib
import hashlib
from typing import TYPE_CHECKING

from backend.src.constants import THUMBNAIL_CACHE_DIR

if TYPE_CHECKING:
    from ..protos.abstract_class_two_galleries import AbstractClassTwoGalleriesHostProtocol


class _SortZoomMixin:
    """§2.13A sort, §2.2 Ctrl+scroll zoom, and gallery layout-reflow triggers."""

    # --- SORT (GUI/UX §2.13A) — subclass-specific part ---

    def _on_sort_combo_changed(self: "AbstractClassTwoGalleriesHostProtocol", label: str) -> None:
        self._sort_key = self._SORT_KEY_MAP.get(label, "name")
        self.master_found_files = self._apply_sort(self.master_found_files)
        self._perform_found_search()

    def _on_sort_dir_toggled(self: "AbstractClassTwoGalleriesHostProtocol", btn) -> None:
        self._sort_reverse = not self._sort_reverse
        btn.setText("↓" if self._sort_reverse else "↑")
        self.master_found_files = self._apply_sort(self.master_found_files)
        self._perform_found_search()

    def _sync_thumb_slider(self: "AbstractClassTwoGalleriesHostProtocol") -> None:
        """Push current thumbnail_size to both pagination sliders (after Ctrl+scroll)."""
        for attr in ("found_thumb_slider", "selected_thumb_slider"):
            slider = getattr(self, attr, None)
            if slider is not None:
                slider.blockSignals(True)
                slider.setValue(self.thumbnail_size)
                slider.blockSignals(False)
        for attr in ("found_thumb_size_lbl", "selected_thumb_size_lbl"):
            lbl = getattr(self, attr, None)
            if lbl is not None:
                lbl.setText(f"{self.thumbnail_size} px")

    # --- CTRL+SCROLL ZOOM (GUI/UX §2.2) ---
    def _connect_scroll_zoom(self: "AbstractClassTwoGalleriesHostProtocol") -> None:
        """Wire Ctrl+scroll zoom on gallery scroll areas (called lazily on first layout)."""
        if self._scroll_zoom_connected:
            return
        connected = False
        for scroll in (self.found_gallery_scroll, self.selected_gallery_scroll):
            if scroll is not None and hasattr(scroll, "ctrl_wheel"):
                scroll.ctrl_wheel.connect(self._on_ctrl_wheel_zoom)
                connected = True
        if connected:
            self._scroll_zoom_connected = True

    def _on_ctrl_wheel_zoom(self: "AbstractClassTwoGalleriesHostProtocol", delta: int) -> None:
        step = 16 if delta > 0 else -16
        new_size = max(64, min(512, self.thumbnail_size + step))
        if new_size == self.thumbnail_size:
            return
        self.thumbnail_size = new_size
        self.approx_item_width = new_size + self.padding_width + 20
        self._sync_thumb_slider()
        self._save_thumbnail_size()
        self._on_layout_change()
        self._recreate_galleries_on_zoom()

    def _recreate_galleries_on_zoom(self: "AbstractClassTwoGalleriesHostProtocol") -> None:
        """Clears all caches and existing widgets, and fully recreates the galleries at the new thumbnail size."""
        self.cancel_loading()

        # Clear caches
        self._found_pixmap_cache.clear()
        self._selected_pixmap_cache.clear()

        # Clear existing widgets
        for widget in list(self.path_to_label_map.values()):
            with contextlib.suppress(RuntimeError):
                widget.deleteLater()
        self.path_to_label_map.clear()

        for widget in list(self.selected_card_map.values()):
            with contextlib.suppress(RuntimeError):
                widget.deleteLater()
        self.selected_card_map.clear()

        # Clear the layouts entirely so they start fresh
        if self.found_gallery_layout is not None:
            self._clear_layout(self.found_gallery_layout)
        if self.selected_gallery_layout is not None:
            self._clear_layout(self.selected_gallery_layout)

        # Recreate/Refresh both panels
        self.refresh_found_gallery()
        self.refresh_selected_panel()

    def _get_disk_cache_path(self: "AbstractClassTwoGalleriesHostProtocol", video_path: str) -> str:
        THUMBNAIL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path_hash = hashlib.md5(video_path.encode('utf-8')).hexdigest()
        return str(THUMBNAIL_CACHE_DIR / f"{path_hash}.jpg")

    # --- GEOMETRY and LAYOUT LOGIC ---

    def resizeEvent(self: "AbstractClassTwoGalleriesHostProtocol", event):
        super().resizeEvent(event)  # type: ignore[safe-super]
        self._resize_timer.start(100)  # 100ms debounce

    def _on_layout_change(self: "AbstractClassTwoGalleriesHostProtocol"):
        self._connect_scroll_zoom()
        # Shared Calculation
        if self.found_gallery_scroll:
            new_cols = self.common_calculate_columns(
                self.found_gallery_scroll, self.approx_item_width
            )
            if new_cols != self._current_found_cols:
                self._current_found_cols = new_cols
                self.common_reflow_layout(self.found_gallery_layout, new_cols)

        if self.selected_gallery_scroll:
            new_cols = self.common_calculate_columns(
                self.selected_gallery_scroll, self.approx_item_width
            )
            if new_cols != self._current_selected_cols:
                self._current_selected_cols = new_cols
                self.common_reflow_layout(self.selected_gallery_layout, new_cols)


__all__ = ["_SortZoomMixin"]

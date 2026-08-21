"""Pagination/sort/thumb-size overrides that also emit peer-sync signals.

Extracted from ``wallpaper_common_base.py`` -- pure code motion, no logic
change (see ``_monitor_selection.py``'s docstring).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ....protos.wallpaper_common_base import WallpaperCommonBaseHostProtocol


class _SyncOverridesMixin:
    """Wrap AbstractClassSingleGallery's gallery-control handlers with sync signals."""

    def _jump_to_page(self: "WallpaperCommonBaseHostProtocol", page_index: int, emit_signal: bool = True):
        if self.current_page == page_index:
            return
        super()._jump_to_page(page_index)  # type: ignore[safe-super]
        if emit_signal:
            self.sync_page_changed.emit(self.current_page)

    def _change_page(self: "WallpaperCommonBaseHostProtocol", delta: int, emit_signal: bool = True):
        old_page = self.current_page
        super()._change_page(delta)  # type: ignore[safe-super]
        if self.current_page != old_page and emit_signal:
            self.sync_page_changed.emit(self.current_page)

    def _on_page_size_changed(self: "WallpaperCommonBaseHostProtocol", text: str, emit_signal: bool = True):
        super()._on_page_size_changed(text)  # type: ignore[safe-super]
        if emit_signal:
            self.sync_page_size_changed.emit(text)

    def _on_thumb_slider_changed(self: "WallpaperCommonBaseHostProtocol", value: int, emit_signal: bool = True):
        super()._on_thumb_slider_changed(value)  # type: ignore[safe-super]
        if emit_signal:
            self.sync_thumb_size_changed.emit(value)

    def _on_sort_combo_changed(self: "WallpaperCommonBaseHostProtocol", label: str, emit_signal: bool = True):
        super()._on_sort_combo_changed(label)  # type: ignore[safe-super]
        if emit_signal:
            self.sync_sort_combo_changed.emit(label)

    def _on_sort_dir_toggled(self: "WallpaperCommonBaseHostProtocol", btn, emit_signal: bool = True):
        super()._on_sort_dir_toggled(btn)  # type: ignore[safe-super]
        if emit_signal:
            self.sync_sort_dir_changed.emit(self._sort_reverse)

    def sync_update_page(self: "WallpaperCommonBaseHostProtocol", page: int):
        self._jump_to_page(page, emit_signal=False)

    def sync_update_page_size(self: "WallpaperCommonBaseHostProtocol", text: str):
        if hasattr(self, "page_combo") and self.page_combo.currentText() != text:
            self.page_combo.blockSignals(True)
            self.page_combo.setCurrentText(text)
            self.page_combo.blockSignals(False)
            self._on_page_size_changed(text, emit_signal=False)

    def sync_update_thumb_size(self: "WallpaperCommonBaseHostProtocol", value: int):
        if hasattr(self, "thumb_slider") and self.thumb_slider.value() != value:
            self.thumb_slider.blockSignals(True)
            self.thumb_slider.setValue(value)
            self.thumb_slider.blockSignals(False)
            self._on_thumb_slider_changed(value, emit_signal=False)

    def sync_update_sort_combo(self: "WallpaperCommonBaseHostProtocol", label: str):
        if hasattr(self, "sort_combo") and self.sort_combo.currentText() != label:
            self.sort_combo.blockSignals(True)
            self.sort_combo.setCurrentText(label)
            self.sort_combo.blockSignals(False)
            self._on_sort_combo_changed(label, emit_signal=False)

    def sync_update_sort_dir(self: "WallpaperCommonBaseHostProtocol", reverse: bool):
        if self._sort_reverse != reverse and hasattr(self, "sort_dir_btn"):
            self._on_sort_dir_toggled(self.sort_dir_btn, emit_signal=False)


__all__ = ["_SyncOverridesMixin"]

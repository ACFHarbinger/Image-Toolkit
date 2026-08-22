"""Gallery surface + selection hook for SamplerSubTab.

The found/selected card grids are replaced by a ``VirtualDualGallery``
(GUI/UX §2.1 Option A); these overrides feed the base's ``found_files`` /
``selected_files`` lists into the dual and map selection changes back.
"""

from __future__ import annotations


class _GalleryCardsMixin:
    """Gallery refresh/selection mapping onto the virtual dual gallery."""

    def on_selection_changed(self):
        n = len(self.selected_files)
        self.btn_selected.setText(f"Resample Selected ({n})")
        self.btn_selected.setEnabled(n > 0)

    def _sync_selection_from_dual(self):
        self.selected_files = list(self.dual.selected_paths())
        self.on_selection_changed()

    def refresh_found_gallery(self):
        self.dual.set_found_paths(self.found_files)

    def refresh_selected_panel(self):
        self.dual.set_selected_paths(self.selected_files)

    def toggle_selection(self, path: str):
        self.dual.toggle_selection(path)

    def clear_galleries(self, clear_data=True):
        if clear_data:
            self.found_files = []
            self.selected_files = []
        self.dual.clear()
        self.cancel_loading()
        self.on_selection_changed()


__all__ = ["_GalleryCardsMixin"]

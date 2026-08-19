"""Gallery card selection hook for SamplerSubTab.

Card creation and styling are promoted to AbstractClassTwoGalleries (§Issue 446).
"""

from __future__ import annotations


class _GalleryCardsMixin:
    """Selection hook for SamplerSubTab."""

    def on_selection_changed(self):
        n = len(self.selected_files)
        self.btn_selected.setText(f"Resample Selected ({n})")
        self.btn_selected.setEnabled(n > 0)


__all__ = ["_GalleryCardsMixin"]

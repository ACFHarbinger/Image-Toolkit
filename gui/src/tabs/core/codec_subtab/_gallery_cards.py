"""Gallery card selection hook for CodecSubTab.

Card creation and styling are promoted to AbstractClassTwoGalleries (§Issue 446).
"""

from __future__ import annotations


class _GalleryCardsMixin:
    """Selection hook for CodecSubTab."""

    def on_selection_changed(self):
        count = len(self.selected_files)
        self.btn_convert_contents.setText(f"Convert Selected Files ({count})")
        self.btn_convert_contents.setEnabled(count > 0)


__all__ = ["_GalleryCardsMixin"]

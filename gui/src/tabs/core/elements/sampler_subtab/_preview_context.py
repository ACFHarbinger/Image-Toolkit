"""Full-size preview window and the per-card context menu.

Extracted from ``sampler_subtab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import os

from PySide6.QtCore import QPoint, Qt, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu

from .....utils.sort_utils import natural_sort_key
from .....windows import ImagePreviewWindow


class _PreviewContextMixin:
    """Full preview windows and the per-card right-click context menu."""

    @Slot(str)
    def _preview_image(self, path: str):
        if not os.path.exists(path):
            return
        all_paths = (
            sorted(self.found_files, key=natural_sort_key)
            if self.found_files
            else [path]
        )
        try:
            idx = all_paths.index(path)
        except ValueError:
            idx = 0
        preview = ImagePreviewWindow(
            image_path=path,
            db_tab_ref=None,
            parent=self,
            all_paths=all_paths,
            start_index=idx,
        )
        preview.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        preview.show()
        self.open_preview_windows.append(preview)

    @Slot(QPoint, str)
    def _context_menu(self, pos: QPoint, path: str):
        menu = QMenu(self)
        view = QAction("View Full Size Preview", self)
        view.triggered.connect(lambda: self._preview_image(path))
        menu.addAction(view)
        menu.addSeparator()
        is_sel = path in self.selected_files
        tog = QAction("Deselect" if is_sel else "Select for resampling", self)
        tog.triggered.connect(lambda: self.toggle_selection(path))
        menu.addAction(tog)
        menu.exec(pos)


__all__ = ["_PreviewContextMixin"]

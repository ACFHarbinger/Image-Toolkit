"""Full-size preview window and the per-card context menu.

Extracted from ``sampler_subtab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu

from ....services import PreviewContext, get_preview_service
from ....utils.sort_utils import natural_sort_key
from ._tab_bound import TabBoundController


class SamplerPreviewController(TabBoundController):
    """Full preview windows and the per-card right-click context menu."""

    @Slot(str)
    def _preview_image(self, path: str):
        all_paths = sorted(self.found_files, key=natural_sort_key) if self.found_files else [path]
        context = PreviewContext(
            path=path,
            items=all_paths,
            parent=self.tab,
            on_path_changed=getattr(self.tab, "update_preview_highlight", None),
        )
        preview = get_preview_service().open_preview(context)
        if preview and hasattr(self.tab, "open_preview_windows") and preview not in self.open_preview_windows:
            self.open_preview_windows.append(preview)

    @Slot(QPoint, str)
    def _context_menu(self, pos: QPoint, path: str):
        menu = QMenu(self.tab)
        view = QAction("View Full Size Preview", self.tab)
        view.triggered.connect(lambda: self._preview_image(path))
        menu.addAction(view)
        menu.addSeparator()
        is_sel = path in self.selected_files
        tog = QAction("Deselect" if is_sel else "Select for resampling", self.tab)
        tog.triggered.connect(lambda: self.toggle_selection(path))
        menu.addAction(tog)
        menu.exec(pos)


# COMPAT(ui-arch-23): legacy mixin alias
_PreviewContextMixin = SamplerPreviewController

__all__ = ["SamplerPreviewController", "_PreviewContextMixin"]

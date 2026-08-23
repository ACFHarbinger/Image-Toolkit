"""QStyledItemDelegate that paints state borders — GUI/UX §2.1.

Reads ``VirtualGalleryModel``'s ``InDbRole`` / ``SelectedRole`` / ``PreviewRole``
off the model instance (no module-level import of the model, avoiding any
cycle) and draws a color-coded border:

* amber border for rows whose preview window is currently open,
* indigo border for selected rows (two-gallery Selected panel, wallpaper
  click-selection),
* green border for rows the tab marks as already present in the library DB
  (scan-metadata) or queued for a monitor (wallpaper display queue).

Preview takes precedence over selected, which takes precedence over in-db.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import QStyledItemDelegate


class VirtualGalleryDelegate(QStyledItemDelegate):
    """Draws a state border on rows based on the model's role flags."""

    _IN_DB_COLOR = QColor("#2ecc71")
    _SELECTED_COLOR = QColor("#5865f2")
    _PREVIEW_COLOR = QColor("#f39c12")

    def paint(self, painter, option, index) -> None:
        super().paint(painter, option, index)
        model = index.model()
        if model is None:
            return
        try:
            preview = bool(model.data(index, model.PreviewRole))
            selected = bool(model.data(index, model.SelectedRole))
            in_db = bool(model.data(index, model.InDbRole))
        except (AttributeError, TypeError):
            return

        if preview:
            color, width = self._PREVIEW_COLOR, 4
        elif selected:
            color, width = self._SELECTED_COLOR, 3
        elif in_db:
            color, width = self._IN_DB_COLOR, 3
        else:
            return

        d = width // 2
        painter.save()
        painter.setPen(QPen(color, width))
        painter.drawRect(option.rect.adjusted(d, d, -d, -d))
        painter.restore()


__all__ = ["VirtualGalleryDelegate"]

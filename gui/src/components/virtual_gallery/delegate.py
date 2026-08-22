"""QStyledItemDelegate that paints an in-database border — GUI/UX §2.1.

Reads ``VirtualGalleryModel.InDbRole`` off the model instance (no module-level
import of the model, avoiding any cycle) and draws a green border for rows the
tab marks as already present in the library DB. The scan-metadata tab uses this
to show which scanned images already exist.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import QStyledItemDelegate


class VirtualGalleryDelegate(QStyledItemDelegate):
    """Draws a green border on rows whose model reports ``InDbRole``."""

    _IN_DB_COLOR = QColor("#2ecc71")

    def paint(self, painter, option, index) -> None:
        super().paint(painter, option, index)
        model = index.model()
        if model is None:
            return
        try:
            in_db = bool(model.data(index, model.InDbRole))
        except (AttributeError, TypeError):
            return
        if not in_db:
            return
        painter.save()
        painter.setPen(QPen(self._IN_DB_COLOR, 3))
        painter.drawRect(option.rect.adjusted(1, 1, -1, -1))
        painter.restore()


__all__ = ["VirtualGalleryDelegate"]

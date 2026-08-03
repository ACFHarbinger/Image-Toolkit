"""Shared drag-and-drop manual reordering for card-based thumbnail galleries.

Used by ``AbstractClassTwoGalleries``'s Selected panel, ``ScanMetadataTab``'s
bespoke selected gallery, and ``MergeTab``'s "Merge Order" queue gallery --
anywhere a grid of custom card widgets (not a ``QListWidget``) needs the
"drag a thumbnail to a new position" interaction that ``QListWidget``'s
``InternalMove`` drag/drop mode gives you for free.
"""

from __future__ import annotations

from typing import List

from PySide6.QtCore import QEvent, QObject, QPoint, Qt
from PySide6.QtGui import QDrag, QMouseEvent
from PySide6.QtWidgets import QApplication, QWidget
from gui.src.constants.classes import _MIME_TYPE


def compute_reordered(paths: List[str], dragged: str, target: str) -> List[str]:
    """Return ``paths`` with ``dragged`` moved to sit just before ``target``."""
    if dragged == target or dragged not in paths or target not in paths:
        return paths
    reordered = [p for p in paths if p != dragged]
    reordered.insert(reordered.index(target), dragged)
    return reordered


class _DragReorderFilter(QObject):
    """Starts a QDrag on mouse-drag and calls back into ``owner`` on drop."""

    def __init__(self, path: str, owner, reorder_slot_name: str, parent=None):
        super().__init__(parent)
        self.path = path
        self.owner = owner
        self.reorder_slot_name = reorder_slot_name
        self._press_pos: QPoint | None = None

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        et = event.type()

        if et == QEvent.Type.MouseButtonPress:
            assert isinstance(event, QMouseEvent)
            if event.button() == Qt.MouseButton.LeftButton:
                self._press_pos = event.pos()
            return False

        if et == QEvent.Type.MouseMove:
            assert isinstance(event, QMouseEvent)
            if (
                self._press_pos is not None
                and event.buttons() & Qt.MouseButton.LeftButton
                and (event.pos() - self._press_pos).manhattanLength()
                >= QApplication.startDragDistance()
            ):
                self._press_pos = None
                self._start_drag(watched)
            return False

        if et == QEvent.Type.DragEnter:
            if event.mimeData().hasFormat(_MIME_TYPE):
                event.acceptProposedAction()
                return True
            return False

        if et == QEvent.Type.DragMove:
            if event.mimeData().hasFormat(_MIME_TYPE):
                event.acceptProposedAction()
                return True
            return False

        if et == QEvent.Type.Drop:
            mime = event.mimeData()
            if mime.hasFormat(_MIME_TYPE):
                dragged_path = bytes(mime.data(_MIME_TYPE)).decode("utf-8")
                event.acceptProposedAction()
                slot = getattr(self.owner, self.reorder_slot_name, None)
                if callable(slot) and dragged_path != self.path:
                    slot(dragged_path, self.path)
                return True
            return False

        return False

    def _start_drag(self, widget: QWidget) -> None:
        from PySide6.QtCore import QMimeData

        drag = QDrag(widget)
        mime = QMimeData()
        mime.setData(_MIME_TYPE, self.path.encode("utf-8"))
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.MoveAction)


def install_drag_reorder(card: QWidget, path: str, owner, reorder_slot_name: str) -> None:
    """Make ``card`` a drag source/drop target for manual reordering.

    On drop, calls ``owner.<reorder_slot_name>(dragged_path, path)`` where
    ``path`` is this card's own path (the drop target).
    """
    card.setAcceptDrops(True)
    card_filter = _DragReorderFilter(path, owner, reorder_slot_name, parent=card)
    card.installEventFilter(card_filter)
    # Keep a strong reference alongside Qt's own parent-child ownership so the
    # filter can't be garbage-collected out from under the widget.
    card._drag_reorder_filter = card_filter  # type: ignore[attr-defined]


__all__ = ["compute_reordered", "install_drag_reorder"]

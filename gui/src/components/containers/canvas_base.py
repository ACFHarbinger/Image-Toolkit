"""Shared QGraphicsView pan / rubber-band-drag mouse handling.

Both the merge tab's canvas (``MergeCanvas``) and the wallpaper tab's node
graph (``WallpaperGraphView``) are interactive ``QGraphicsView`` widgets that
implement the exact same mouse-handling scheme:

* Left-click on empty canvas starts a hand-drag pan; left-click on an
  "interactive" item (a movable/selectable graphics item, or an item of a
  known class) falls through to Qt's default handling so the item itself can
  be dragged/selected.
* Right-click is remapped to a synthetic left-click so Qt's built-in
  ``RubberBandDrag`` selection (normally only bound to the left button) can
  be triggered from the right button as well.

``CanvasBase`` factors that identical logic out into one place. Behavior
that differs between the two canvases (drag-and-drop of files, "connection
mode" wire-dragging, scene-rect growth, etc.) is left to subclasses via the
``_handle_special_*`` and ``_on_*`` hooks below.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QGraphicsItem, QGraphicsView


class CanvasBase(QGraphicsView):
    """Common pan / rubber-band-drag ``QGraphicsView`` base."""

    # Class names of items that should be treated as "interactive" (i.e.
    # clicking them should NOT start a canvas pan) even when, for whatever
    # reason, their item flags don't already mark them movable/selectable.
    _INTERACTIVE_CLASS_NAMES = ("NodeItem", "EdgeItem", "MergeCanvasItem")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._is_panning = False
        self._pan_start_pos = None

    # ── Hooks for subclasses ─────────────────────────────────────────────

    def _handle_special_press(self, event: QMouseEvent) -> bool:
        """Return True if the press was fully handled by a subclass (skips
        the default pan/rubber-band logic below)."""
        return False

    def _handle_special_move(self, event: QMouseEvent) -> bool:
        """Return True if the move was fully handled by a subclass."""
        return False

    def _handle_special_release(self, event: QMouseEvent) -> bool:
        """Return True if the release was fully handled by a subclass."""
        return False

    def _on_pan_step(self) -> None:
        """Called on every pan-drag move, before the scrollbars are
        adjusted. Subclasses can use this to grow the scene rect first."""

    def _on_drag_step(self, event: QMouseEvent) -> None:
        """Called at the end of every mouseMoveEvent while any button is
        held -- covers dragging an item, not just background panning."""

    def _is_interactive_item(self, item) -> bool:
        curr = item
        bg = getattr(self, "_bg", None)
        while curr is not None:
            if curr.__class__.__name__ in self._INTERACTIVE_CLASS_NAMES:
                return True
            flags = curr.flags()
            movable_or_selectable = (
                QGraphicsItem.GraphicsItemFlag.ItemIsMovable
                | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            )
            if flags and (flags & movable_or_selectable) and curr is not bg:
                return True
            curr = curr.parentItem()
        return False

    @staticmethod
    def _as_left_button_event(event: QMouseEvent, buttons) -> QMouseEvent:
        """Build a synthetic copy of `event` reported as a left-button
        event, used to feed right-click drags into Qt's rubber-band
        selection machinery (which only binds to the left button)."""
        return QMouseEvent(
            event.type(),
            event.position(),
            event.globalPosition(),
            Qt.MouseButton.LeftButton,
            buttons,
            event.modifiers(),
        )

    # ── Mouse handling ───────────────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent):
        if self._handle_special_press(event):
            return

        if event.button() == Qt.MouseButton.LeftButton:
            item = self.itemAt(event.position().toPoint())
            if self._is_interactive_item(item):
                super().mousePressEvent(event)
            else:
                self._pan_start_pos = event.position().toPoint()
                self._is_panning = True
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            fake_event = self._as_left_button_event(
                event, event.buttons() | Qt.MouseButton.LeftButton
            )
            super().mousePressEvent(fake_event)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._handle_special_move(event):
            return

        if self._is_panning:
            self._on_pan_step()
            delta = event.position().toPoint() - self._pan_start_pos
            self._pan_start_pos = event.position().toPoint()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
        elif event.buttons() & Qt.MouseButton.RightButton:
            fake_event = self._as_left_button_event(
                event, (event.buttons() & ~Qt.MouseButton.RightButton) | Qt.MouseButton.LeftButton
            )
            super().mouseMoveEvent(fake_event)
            event.accept()
        else:
            super().mouseMoveEvent(event)

        if event.buttons():
            self._on_drag_step(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._handle_special_release(event):
            return

        if self._is_panning:
            self._is_panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            fake_event = self._as_left_button_event(
                event, event.buttons() & ~Qt.MouseButton.LeftButton
            )
            super().mouseReleaseEvent(fake_event)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

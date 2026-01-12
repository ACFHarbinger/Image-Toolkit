from PySide6.QtGui import QMouseEvent
from PySide6.QtCore import Qt, Signal, QPoint, QRect, QSize
from PySide6.QtWidgets import QScrollArea, QRubberBand, QApplication
from . import ClickableLabel, OpaqueViewport


class MarqueeScrollArea(QScrollArea):
    """
    A custom QScrollArea that enables marquee (rubber-band) selection.
    Fixes nested widget selection by mapping coordinates correctly.
    """

    # Signal: (set_of_selected_paths, is_ctrl_modifier_pressed)
    selection_changed = Signal(set, bool)

    def __init__(self, parent=None):
        super().__init__(parent)

        # Use custom viewport for cleaner rendering
        self.setViewport(OpaqueViewport(self))
        self.viewport().setMouseTracking(True)

        self.rubber_band = QRubberBand(QRubberBand.Rectangle, self.viewport())
        self.origin = QPoint()
        self.last_selected_paths = set()

        # Apply style to viewport
        self.setStyleSheet(
            "QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }"
        )

    def mousePressEvent(self, event: QMouseEvent):
        content_widget = self.widget()
        if not content_widget:
            super().mousePressEvent(event)
            return

        # Map click to content coordinates to check if we clicked blank space or an item
        mapped_pos = content_widget.mapFrom(self.viewport(), event.position().toPoint())
        child = content_widget.childAt(mapped_pos)

        # Start marquee only if left-clicking on empty space (not on a ClickableLabel)
        # We check if the child found is NOT a ClickableLabel (or part of one)
        is_on_item = False
        if child:
            # Walk up the tree slightly to see if we clicked a label or its wrapper
            curr = child
            while curr and curr != content_widget:
                if isinstance(curr, ClickableLabel):
                    is_on_item = True
                    break
                curr = curr.parentWidget()

        if event.button() == Qt.LeftButton and not is_on_item:
            self.origin = event.position().toPoint()
            self.rubber_band.setGeometry(QRect(self.origin, QSize()))
            self.rubber_band.show()
            self.last_selected_paths = set()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.rubber_band.isVisible():
            # 1. Update RubberBand geometry
            self.rubber_band.setGeometry(
                QRect(self.origin, event.position().toPoint()).normalized()
            )

            # 2. Calculate selection rect in Content Coordinates
            selection_rect_viewport = self.rubber_band.geometry()
            h_offset = self.horizontalScrollBar().value()
            v_offset = self.verticalScrollBar().value()
            selection_rect_content = selection_rect_viewport.translated(
                h_offset, v_offset
            )

            current_selected_paths = set()
            content_widget = self.widget()

            if content_widget:
                # 3. Iterate over all ClickableLabels
                for label in content_widget.findChildren(ClickableLabel):
                    if not label.isVisible():
                        continue

                    # --- CRITICAL FIX START ---
                    # Map the label's (0,0) to the content_widget's coordinate system.
                    # This handles cases where labels are nested inside other layout widgets.
                    label_top_left = label.mapTo(content_widget, QPoint(0, 0))
                    label_rect = QRect(label_top_left, label.size())
                    # --- CRITICAL FIX END ---

                    if selection_rect_content.intersects(label_rect):
                        if hasattr(label, "path"):
                            current_selected_paths.add(label.path)

            mods = QApplication.keyboardModifiers()
            is_ctrl_pressed = bool(mods & Qt.ControlModifier)

            if current_selected_paths != self.last_selected_paths:
                self.selection_changed.emit(current_selected_paths, is_ctrl_pressed)
                self.last_selected_paths = current_selected_paths

            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and self.rubber_band.isVisible():
            self.rubber_band.hide()
            self.last_selected_paths = set()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

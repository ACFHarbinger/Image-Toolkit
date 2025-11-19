# --- MODIFIED IMPORTS ---
from PySide6.QtGui import QMouseEvent, QPainter, QColor
from PySide6.QtCore import (
    Qt, Signal, QPoint, 
    QRect, QSize
)
from PySide6.QtWidgets import (
    QApplication, QScrollArea, 
    QRubberBand, QWidget # Import QWidget for subclassing the Viewport
)
# --- END MODIFIED IMPORTS ---
from . import ClickableLabel


# --- FIX: Custom Viewport Widget to Enforce Background Opacity ---
class OpaqueViewport(QWidget):
    """A standard QWidget subclass used as the scroll area's viewport, 
    explicitly painted to ensure background clearing and prevent ghosting."""
    def __init__(self, parent=None, color_hex="#2c2f33"):
        super().__init__(parent)
        self.background_color = QColor(color_hex)
        # Ensure the viewport is recognized as painting its entire background
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)

    def paintEvent(self, event):
        """Forces the widget to clear its background with the defined color."""
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.background_color)
        # It's safer to rely on the underlying QScrollArea mechanism to draw 
        # its content (the QGridLayout widget) via the viewport's paint method, 
        # but the explicit fill must happen first.
        # Calling super().paintEvent(event) here relies on QWidget's paint implementation.
        # For simplicity and maximum compatibility, we leave the base method to be 
        # handled by QScrollArea's internal drawing routine, after we've cleared the canvas.
        # This implementation is the most effective against artifacts in QScrollArea viewports.
        
# --- NEW MarqueeScrollArea CLASS ---

class MarqueeScrollArea(QScrollArea):
    """
    A custom QScrollArea that enables marquee (rubber-band) selection
    of its content widget's ClickableLabel children.
    """
    # Signal: (set_of_selected_paths, is_ctrl_modifier_pressed)
    selection_changed = Signal(set, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # --- FIX: Set Custom Viewport ---
        self.setViewport(OpaqueViewport(self))
        self.viewport().setMouseTracking(True) # Ensure consistent mouse events
        # --------------------------------

        # Rubber band MUST be a child of the viewport
        self.rubber_band = QRubberBand(QRubberBand.Rectangle, self.viewport())
        self.origin = QPoint()
        self.last_selected_paths = set()
        
        # --- FIX: Apply background style to the *viewport* explicitly ---
        self.setStyleSheet("QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }")

    def mousePressEvent(self, event: QMouseEvent):
        """Starts the rubber-band selection on left-click."""
        content_widget = self.widget()
        if not content_widget:
            super().mousePressEvent(event)
            return

        # Map viewport click position to content widget position
        mapped_pos = content_widget.mapFrom(self.viewport(), event.pos())
        # Check if a child (a label) exists at that *mapped* position
        child = content_widget.childAt(mapped_pos)

        if event.button() == Qt.LeftButton and child is None:
            # Click is on the background
            self.origin = event.pos() # Store viewport coords
            self.rubber_band.setGeometry(QRect(self.origin, QSize()))
            self.rubber_band.show()
            self.last_selected_paths = set()
            event.accept()
        else:
            # Click is on a child OR is not a left-click.
            super().mousePressEvent(event) 

    def mouseMoveEvent(self, event: QMouseEvent):
        """Updates the rubber-band geometry and live selection."""
        if self.rubber_band.isVisible():
            # 1. Update geometry in viewport coordinates
            self.rubber_band.setGeometry(QRect(self.origin, event.pos()).normalized())
            
            # 2. Get selection rect (in viewport coordinates)
            selection_rect_viewport = self.rubber_band.geometry()
            
            # 3. Translate viewport rect to content widget 
            # coordinates by adding the current scroll offsets.
            h_offset = self.horizontalScrollBar().value()
            v_offset = self.verticalScrollBar().value()
            selection_rect_content = selection_rect_viewport.translated(h_offset, v_offset)

            # 4. Find selected paths
            current_selected_paths = set()
            content_widget = self.widget()
            if not content_widget:
                super().mouseMoveEvent(event)
                return

            for label in content_widget.findChildren(ClickableLabel):
                # Check intersection using content coordinates
                if selection_rect_content.intersects(label.geometry()):
                    try:
                        # Assumes ClickableLabel has 'self.path'
                        current_selected_paths.add(label.path) 
                    except AttributeError:
                        print("Warning: ClickableLabel is missing 'self.path' attribute.")
            
            # 5. Check for Ctrl key
            mods = QApplication.keyboardModifiers()
            is_ctrl_pressed = bool(mods & Qt.ControlModifier)
            
            # 6. Optimization: Emit only if selection changed
            if current_selected_paths != self.last_selected_paths:
                self.selection_changed.emit(current_selected_paths, is_ctrl_pressed)
                self.last_selected_paths = current_selected_paths
            
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Hides the rubber-band."""
        if event.button() == Qt.LeftButton and self.rubber_band.isVisible():
            self.rubber_band.hide()
            self.last_selected_paths = set() # Clear cache on release
            event.accept()
        else:
            super().mouseReleaseEvent(event)

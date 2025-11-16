import os

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap, QKeySequence, QShortcut, QWheelEvent # Import QWheelEvent
from PySide6.QtWidgets import (
    QMessageBox, QLabel, QApplication,
    QScrollArea, QVBoxLayout, QDialog,
)


class ImagePreviewWindow(QDialog):
    """A dialog to display an image at its original size, with scrolling if needed."""
    
    ZOOM_STEP = 0.1  # 10% change per zoom step

    def __init__(self, image_path: str, db_tab_ref=None, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.setWindowTitle(f"Full-Size Image Preview: {os.path.basename(image_path)}")
        self.setMinimumSize(400, 300)

        # State tracking for zooming
        self.original_pixmap: QPixmap = QPixmap()
        self.current_zoom_factor: float = 1.0 
        self.image_label: QLabel = QLabel()
        
        # ----------------------------------------------------------------------
        # NEW: Set Window Flags
        self.setWindowFlags(
            Qt.Window |
            Qt.WindowSystemMenuHint |
            Qt.WindowCloseButtonHint |
            Qt.WindowMinimizeButtonHint | 
            Qt.WindowMaximizeButtonHint   
        )
        # ----------------------------------------------------------------------

        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        # 1. Load the image and check for errors
        self.original_pixmap = QPixmap(image_path)
        if self.original_pixmap.isNull():
            QMessageBox.critical(self, "Error", f"Could not load image file: {image_path}")
            self.deleteLater()
            return

        # 2. Initial Setup
        self._initial_scale_and_layout()
        
        # 3. Setup Shortcuts (Ctrl++ and Ctrl+-)
        self.zoom_in_shortcut = QShortcut(QKeySequence(Qt.CTRL | Qt.Key_Plus), self)
        self.zoom_out_shortcut = QShortcut(QKeySequence(Qt.CTRL | Qt.Key_Minus), self)
        
        # Also bind Ctrl+= for systems where Ctrl++ is Ctrl+=
        self.zoom_in_shortcut_eq = QShortcut(QKeySequence(Qt.CTRL | Qt.Key_Equal), self)
        
        self.zoom_in_shortcut.activated.connect(lambda: self.adjust_zoom(self.ZOOM_STEP))
        self.zoom_out_shortcut.activated.connect(lambda: self.adjust_zoom(-self.ZOOM_STEP))
        self.zoom_in_shortcut_eq.activated.connect(lambda: self.adjust_zoom(self.ZOOM_STEP))
        
        # 4. Final layout
        vbox = QVBoxLayout(self)
        vbox.addWidget(self.scroll_area)


    def _initial_scale_and_layout(self):
        """Initializes the display size and layout structure."""
        screen = QApplication.primaryScreen()
        screen_geo = screen.availableGeometry()
        
        self.max_width = int(screen_geo.width() * 0.95)
        self.max_height = int(screen_geo.height() * 0.95)
        
        # Determine initial scaling factor to fit the screen
        width_ratio = self.max_width / self.original_pixmap.width()
        height_ratio = self.max_height / self.original_pixmap.height()
        
        if self.original_pixmap.width() > self.max_width or self.original_pixmap.height() > self.max_height:
            # If the image is larger than the screen, scale it down initially
            self.current_zoom_factor = min(width_ratio, height_ratio)
        else:
            # If smaller, start at 100% (zoom factor 1.0)
            self.current_zoom_factor = 1.0 
            
        # 4. Setup the image label
        self.image_label.setAlignment(Qt.AlignCenter)
        
        # 5. Use QScrollArea
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.image_label)
        
        # Apply initial scale
        self.update_image_display()

        # Set initial window size based on the currently displayed pixmap size
        scaled_pixmap = self.image_label.pixmap()
        target_width = min(scaled_pixmap.width() + 50, self.max_width + 50)
        target_height = min(scaled_pixmap.height() + 50, self.max_height + 50)
        self.resize(QSize(target_width, target_height))

    def adjust_zoom(self, delta: float):
        """Increments or decrements the zoom factor and updates the display."""
        
        new_zoom = self.current_zoom_factor + delta
        
        # Clamp zoom factor: Minimum 0.1x, Maximum 5.0x
        if new_zoom < 0.1:
            new_zoom = 0.1
        elif new_zoom > 5.0:
            new_zoom = 5.0

        self.current_zoom_factor = new_zoom
        self.update_image_display()

    def update_image_display(self):
        """Applies the current zoom factor to the original pixmap and updates the label."""
        
        # Calculate new dimensions based on the original size and zoom factor
        new_width = int(self.original_pixmap.width() * self.current_zoom_factor)
        new_height = int(self.original_pixmap.height() * self.current_zoom_factor)
        
        # Scale the original pixmap
        scaled_pixmap = self.original_pixmap.scaled(
            QSize(new_width, new_height),
            Qt.IgnoreAspectRatio,  # We ignore aspect ratio here as we calculate new dimensions directly
            Qt.SmoothTransformation
        )
        
        self.image_label.setPixmap(scaled_pixmap)
        self.image_label.setFixedSize(scaled_pixmap.size()) # Set fixed size to allow scrolling
        
        # Update title with zoom level for feedback
        zoom_percent = int(self.current_zoom_factor * 100)
        self.setWindowTitle(f"Full-Size Image Preview: {os.path.basename(self.image_path)} ({zoom_percent}%)")

    def wheelEvent(self, event: QWheelEvent):
        """
        Overrides the wheel event to handle zooming when the Ctrl key is pressed.
        """
        # Check if the Ctrl key is pressed
        if event.modifiers() & Qt.ControlModifier:
            # Determine the wheel direction
            # If delta is positive (usually wheel up/forward), zoom in
            if event.angleDelta().y() > 0:
                self.adjust_zoom(self.ZOOM_STEP)
            # If delta is negative (usually wheel down/backward), zoom out
            elif event.angleDelta().y() < 0:
                self.adjust_zoom(-self.ZOOM_STEP)
            
            # Accept the event to stop propagation (prevent scrolling the QScrollArea)
            event.accept()
        else:
            # If Ctrl is not pressed, pass the event to the base class (allowing normal scrolling)
            super().wheelEvent(event)

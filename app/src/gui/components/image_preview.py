import os

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QMessageBox, QLabel, QApplication,
    QScrollArea, QVBoxLayout, QDialog,
)


class ImagePreviewWindow(QDialog):
    """A dialog to display an image at its original size, with scrolling if needed."""
    def __init__(self, image_path: str, db_tab_ref, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.setWindowTitle(f"Full-Size Image Preview: {os.path.basename(image_path)}")
        self.setMinimumSize(400, 300)

        # ----------------------------------------------------------------------
        # NEW: Set Window Flags to show native Minimize and Maximize buttons.
        # This replaces the custom buttons and achieves the standard OS layout.
        # Qt.WindowSystemMenuHint ensures the title bar is present.
        self.setWindowFlags(
            Qt.Window |
            Qt.WindowSystemMenuHint |
            Qt.WindowCloseButtonHint |
            Qt.WindowMinimizeButtonHint | # Enable native Minimize button
            Qt.WindowMaximizeButtonHint   # Enable native Maximize/Restore button
        )
        # ----------------------------------------------------------------------

        # Ensure the window is deleted on close to free resources
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        # 1. Load the image
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            QMessageBox.critical(self, "Error", f"Could not load image file: {image_path}")
            self.deleteLater()
            return

        # 2. Determine screen size and scale limits
        screen = QApplication.primaryScreen()
        screen_geo = screen.availableGeometry()
        
        self.max_width = int(screen_geo.width() * 0.95)
        self.max_height = int(screen_geo.height() * 0.95)
        
        self.original_pixmap_size = pixmap.size()
        
        # 3. Scale the pixmap only if it is larger than the screen size
        if pixmap.width() > self.max_width or pixmap.height() > self.max_height:
            scaled_pixmap = pixmap.scaled(
                self.max_width, self.max_height, 
                Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
        else:
            scaled_pixmap = pixmap
        
        # Determine the initial dialog size based on the scaled pixmap size (with padding)
        target_width = min(scaled_pixmap.width() + 50, self.max_width + 50)
        target_height = min(scaled_pixmap.height() + 50, self.max_height + 50)
        
        self.resize(QSize(target_width, target_height))
        
        # 4. Setup the image label
        image_label = QLabel()
        image_label.setPixmap(scaled_pixmap)
        image_label.setAlignment(Qt.AlignCenter)
        image_label.setMinimumSize(scaled_pixmap.size())
        
        # 5. Use QScrollArea
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(image_label)

        # 6. Main layout
        vbox = QVBoxLayout(self)
        # REMOVED: Custom control_widget (now handled by native title bar)
        vbox.addWidget(self.scroll_area)
        
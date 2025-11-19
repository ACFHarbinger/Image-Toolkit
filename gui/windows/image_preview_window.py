import os
from typing import List, Any

from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import (
    QShortcut, QWheelEvent, QAction,
    QPixmap, QKeySequence, QKeyEvent, 
)
from PySide6.QtWidgets import (
    QMenu, QMessageBox, QLabel, QApplication,
    QScrollArea, QVBoxLayout, QDialog, QHBoxLayout, QPushButton,
)


class ImagePreviewWindow(QDialog):
    """
    A dialog to display an image with zooming, scrolling, and navigation
    between images in a selected batch.
    
    All images are initially scaled to fit the window upon load/navigation,
    and resized automatically upon window resize.
    """
    
    ZOOM_STEP = 0.1  # 10% change per zoom step

    def __init__(self, image_path: str, db_tab_ref=None, parent=None, 
                 all_paths: List[str] = None, start_index: int = 0):
        super().__init__(parent)
        
        # Navigation State
        self.all_paths = all_paths if all_paths is not None else [image_path]
        self.current_index = start_index
        
        self.image_path = self.all_paths[self.current_index] 
        self.db_tab_ref = db_tab_ref
        self.parent_tab = parent
        
        # Flag to prevent recursion/initial noise during setup
        self._is_handling_resize = False 

        self.setMinimumSize(400, 300)
        self.setWindowFlags(
            Qt.Window | Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint |
            Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint   
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        # Zoom State
        self.original_pixmap: QPixmap = QPixmap()
        self.current_zoom_factor: float = 1.0 
        self.image_label: QLabel = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        
        # 1. Load initial image (handles error checks)
        if not self.load_image(self.image_path, initial_load=True):
             QMessageBox.critical(self, "Error", f"Could not load initial image file: {self.image_path}")
             QTimer.singleShot(0, self.deleteLater)
             return
        
        # 2. Initial Scaling and Layout Setup
        self._initial_scale_and_layout()
        
        # 3. Navigation Buttons (Arrows)
        self.btn_prev = QPushButton("◀")
        self.btn_next = QPushButton("▶")
        
        # New Arrow Design (Larger, more visible, but minimally intrusive)
        arrow_style = """
            QPushButton { 
                font-size: 40px; 
                font-weight: bold;
                color: rgba(255, 255, 255, 0.9); 
                background: rgba(30, 33, 36, 0.3); 
                border: none;
                padding: 10px;
                margin: 0 10px;
            }
            QPushButton:hover { 
                background: rgba(30, 33, 36, 0.7); 
                color: #7289da; 
            }
            QPushButton:disabled { 
                color: rgba(255, 255, 255, 0.2); 
                background: transparent; 
            }
        """
        self.btn_prev.setStyleSheet(arrow_style)
        self.btn_next.setStyleSheet(arrow_style)

        self.btn_prev.clicked.connect(lambda: self._navigate(-1))
        self.btn_next.clicked.connect(lambda: self._navigate(1))
        
        # Layout for image display and navigation controls
        main_content_layout = QHBoxLayout()
        main_content_layout.setContentsMargins(0, 0, 0, 0)
        
        # Add navigation buttons and image area
        main_content_layout.addWidget(self.btn_prev, 0, Qt.AlignVCenter)
        main_content_layout.addWidget(self.scroll_area, 1)
        main_content_layout.addWidget(self.btn_next, 0, Qt.AlignVCenter)
        
        # Final layout (VBox to hold everything)
        vbox = QVBoxLayout(self)
        vbox.addLayout(main_content_layout)

        # 4. Setup Shortcuts
        self.zoom_in_shortcut = QShortcut(QKeySequence(Qt.CTRL | Qt.Key_Plus), self)
        self.zoom_out_shortcut = QShortcut(QKeySequence(Qt.CTRL | Qt.Key_Minus), self)
        self.zoom_in_shortcut_eq = QShortcut(QKeySequence(Qt.CTRL | Qt.Key_Equal), self)
        
        self.zoom_in_shortcut.activated.connect(lambda: self.adjust_zoom(self.ZOOM_STEP))
        self.zoom_out_shortcut.activated.connect(lambda: self.adjust_zoom(-self.ZOOM_STEP))
        self.zoom_in_shortcut_eq.activated.connect(lambda: self.adjust_zoom(self.ZOOM_STEP))
        
        self._update_navigation_button_state()

    # --- NEW: Resize Event Handler ---
    def resizeEvent(self, event):
        """
        Overrides the resize event to automatically rescale the image to fit the new window size.
        """
        super().resizeEvent(event)
        
        # Prevent initial noise and recursive calls
        if self._is_handling_resize:
            return
            
        self._is_handling_resize = True
        
        # Recalculate fit scale based on the new dimensions
        self.current_zoom_factor = self._calculate_fit_scale()
        self.update_image_display()

        # Reset flag after processing
        self._is_handling_resize = False 
    # --- END NEW ---


    def _calculate_fit_scale(self) -> float:
        """
        Calculates the zoom factor needed to fit the original image within the 
        current window size (minus margins for controls).
        """
        if self.original_pixmap.isNull() or self.original_pixmap.width() == 0:
            return 1.0

        # Approximate usable area of the scroll area within the window (subtracting arrow buttons/margins)
        current_inner_width = self.width() - 100 
        current_inner_height = self.height() - 50 

        if current_inner_width <= 0 or current_inner_height <= 0:
            return 1.0 

        width_ratio = current_inner_width / self.original_pixmap.width()
        height_ratio = current_inner_height / self.original_pixmap.height()
        
        # The new factor is the maximum ratio that keeps the whole image visible (always <= 1.0)
        return min(width_ratio, height_ratio, 1.0)


    def _initial_scale_and_layout(self):
        """Initializes the display size and layout structure based on the first image."""
        
        # 4. Setup the image label
        self.image_label.setAlignment(Qt.AlignCenter)
        
        # 5. Use QScrollArea
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.image_label)
        
        # Apply initial scale (Fit-to-window zoom)
        self.update_image_display()

        # Get screen size bounds
        screen = QApplication.primaryScreen()
        screen_geo = screen.availableGeometry()
        self.max_width = int(screen_geo.width() * 0.95)
        self.max_height = int(screen_geo.height() * 0.95)
        
        # --- FIX: Determine initial size based on the SCALED (fit-to-window) size ---
        
        scaled_pixmap = self.image_label.pixmap()
        
        # Calculate target window size (Scaled Image size + padding for arrows/margins)
        target_width = min(scaled_pixmap.width() + 100, self.max_width) # 100 is padding + arrows
        target_height = min(scaled_pixmap.height() + 50, self.max_height) # 50 is padding/title bar
        
        # Schedule the resize to ensure it happens after the layout is fully built
        QTimer.singleShot(0, lambda: self.resize(QSize(target_width, target_height)))


    def load_image(self, path: str, initial_load: bool = False) -> bool:
        """
        Loads and displays the image from the given path.
        Sets the zoom factor to 'fit-to-window' for all loads.
        Returns True on success, False on failure.
        """
        new_pixmap = QPixmap(path)
        
        if new_pixmap.isNull():
             self.setWindowTitle(f"Image Preview - Error Loading {os.path.basename(path)}")
             return False

        self.image_path = path
        self.original_pixmap = new_pixmap

        # FIX: All images, regardless of initial_load or navigation, must fit the preview window
        self.current_zoom_factor = self._calculate_fit_scale()
            
        self.update_image_display()
        return True


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
        
        if self.original_pixmap.isNull():
            return
            
        # Calculate new dimensions based on the original size and zoom factor
        new_width = int(self.original_pixmap.width() * self.current_zoom_factor)
        new_height = int(self.original_pixmap.height() * self.current_zoom_factor)
        
        # Scale the original pixmap
        scaled_pixmap = self.original_pixmap.scaled(
            QSize(new_width, new_height),
            Qt.KeepAspectRatio, 
            Qt.SmoothTransformation
        )
        
        self.image_label.setPixmap(scaled_pixmap)
        self.image_label.setFixedSize(scaled_pixmap.size()) # Set fixed size to allow scrolling
        
        # Update title with zoom level and navigation index
        zoom_percent = int(self.current_zoom_factor * 100)
        
        nav_info = ""
        if len(self.all_paths) > 1:
            nav_info = f" ({self.current_index + 1}/{len(self.all_paths)})"
            
        self.setWindowTitle(f"Full-Size Image Preview: {os.path.basename(self.image_path)} [{zoom_percent}%]{nav_info}")

    def _update_navigation_button_state(self):
        """Enables/Disables navigation buttons based on batch size."""
        can_navigate = len(self.all_paths) > 1
        self.btn_prev.setEnabled(can_navigate)
        self.btn_next.setEnabled(can_navigate)


    def wheelEvent(self, event: QWheelEvent):
        """
        Overrides the wheel event to handle zooming when the Ctrl key is pressed.
        """
        if event.modifiers() & Qt.ControlModifier:
            if event.angleDelta().y() > 0:
                self.adjust_zoom(self.ZOOM_STEP)
            elif event.angleDelta().y() < 0:
                self.adjust_zoom(-self.ZOOM_STEP)
            
            event.accept()
        else:
            super().wheelEvent(event)
            
    def contextMenuEvent(self, event):
        """
        Overrides the context menu event (right-click) to display management options.
        """
        menu = QMenu(self)

        close_action = QAction("Close This Preview (Ctrl+W)", self)
        close_action.triggered.connect(self.close)
        menu.addAction(close_action)
        
        if self.parent_tab and hasattr(self.parent_tab, 'open_preview_windows'):
            
            other_windows_count = len([w for w in self.parent_tab.open_preview_windows if w is not self])
            
            if other_windows_count > 0:
                menu.addSeparator()
                
                close_all_action = QAction(f"Close All {other_windows_count} Other Previews", self)
                close_all_action.triggered.connect(self._close_all_other_previews)
                menu.addAction(close_all_action)
                
        menu.exec(event.globalPos())
        
    def _close_all_other_previews(self):
        """
        Helper method to close all other open ImagePreviewWindow instances 
        managed by the parent tab.
        """
        if self.parent_tab and hasattr(self.parent_tab, 'open_preview_windows'):
            windows_to_close = [w for w in list(self.parent_tab.open_preview_windows) if w is not self and w.isVisible()]
            
            for window in windows_to_close:
                window.close()
                
            QMessageBox.information(self.parent_tab, "Previews Closed", f"Closed {len(windows_to_close)} other preview windows.")

    def keyPressEvent(self, event: QKeyEvent):
        """
        Handles key presses for navigation (Left/Right) and closing (Ctrl+W).
        """
        if event.key() == Qt.Key.Key_Right:
            self._navigate(1)
            event.accept()
        elif event.key() == Qt.Key.Key_Left:
            self._navigate(-1)
            event.accept()
        elif event.key() == Qt.Key.Key_W and event.modifiers() & Qt.ControlModifier:
            self.close()
            event.accept()
        else:
            super().keyPressEvent(event)

    def _navigate(self, direction: int):
        """Cycles the current image index and loads the new image."""
        if len(self.all_paths) <= 1:
            return
            
        new_index = self.current_index + direction
        
        # Cycle logic (wraps around)
        if new_index >= len(self.all_paths):
            new_index = 0
        elif new_index < 0:
            new_index = len(self.all_paths) - 1
            
        if new_index != self.current_index:
            self.current_index = new_index
            new_path = self.all_paths[self.current_index]
            self.load_image(new_path)

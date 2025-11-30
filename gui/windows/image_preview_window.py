import os

from typing import List
from PySide6.QtCore import Qt, QSize, QTimer, Signal
from PySide6.QtGui import (
    QShortcut, QWheelEvent, QAction,
    QPixmap, QKeySequence, QKeyEvent, QMovie, QMouseEvent
)
from PySide6.QtWidgets import (
    QMenu, QMessageBox, QLabel, QApplication,
    QScrollArea, QVBoxLayout, QDialog, QHBoxLayout, QPushButton,
)


class ImagePreviewWindow(QDialog):
    """
    A dialog to display an image with zooming, scrolling, and navigation
    between images in a selected batch.
    
    Now supports GIF animation via QMovie.
    """
    # --- Define a signal to notify the parent when the path changes ---
    path_changed = Signal(str, str)
    
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
        
        # State trackers for animation and scaling
        self.current_movie: QMovie = None # NEW: QMovie object for GIFs
        self.original_pixmap: QPixmap = QPixmap() # QPixmap object for static images
        self.is_animated: bool = False # NEW: Flag if current file is a GIF

        # Flag to prevent recursion/initial noise during setup
        self._is_handling_resize = False 

        self.setMinimumSize(400, 300)
        self.setWindowFlags(
            Qt.Window | Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint |
            Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint   
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        # Zoom State
        self.current_zoom_factor: float = 1.0 
        self.image_label: QLabel = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        
        # --- FIX: Prevent image label from stealing focus ---
        self.image_label.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        
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
        
        # --- FIX: Prevent buttons from stealing focus ---
        self.btn_prev.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_next.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        
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

        self.showMaximized()
        self.setFocusPolicy(Qt.StrongFocus) # Ensure window can receive focus
        
        # --- FIX: Emit the deferred signal emission for initial highlighting ---
        QTimer.singleShot(100, lambda: self.path_changed.emit('INITIAL_LOAD_TRIGGER', self.image_path))
        
        self.setFocus() # Initial focus 

    # --- MODIFIED: Resize Event Handler ---
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
    # --- END MODIFIED ---

    # --- MODIFIED: Get Original Size based on Image Type ---
    def _get_original_size(self) -> QSize:
        """Returns the size of the static pixmap or the QMovie base size."""
        if self.is_animated and self.current_movie:
            return self.current_movie.currentPixmap().size()
        return self.original_pixmap.size()
    # --- END MODIFIED ---

    def _calculate_fit_scale(self) -> float:
        """
        Calculates the zoom factor needed to fit the image within the 
        current window size (minus margins for controls).
        """
        original_size = self._get_original_size()

        if original_size.isNull() or original_size.width() == 0:
            return 1.0

        # Approximate usable area of the scroll area within the window (subtracting arrow buttons/margins)
        current_inner_width = self.width() - 100 
        current_inner_height = self.height() - 50 

        if current_inner_width <= 0 or current_inner_height <= 0:
            return 1.0 

        width_ratio = current_inner_width / original_size.width()
        height_ratio = current_inner_height / original_size.height()
        
        # The new factor is the maximum ratio that keeps the whole image visible (always <= 1.0)
        return min(width_ratio, height_ratio, 1.0)


    def _initial_scale_and_layout(self):
        """Initializes the display size and layout structure based on the first image."""
        
        # Setup the image label
        self.image_label.setAlignment(Qt.AlignCenter)
        
        # Use QScrollArea
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.image_label)
        
        # --- FIX: Prevent scroll area from stealing focus ---
        self.scroll_area.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        
        # Apply initial scale (Fit-to-window zoom)
        self.update_image_display()
        
        # Get screen size bounds
        screen = QApplication.primaryScreen()
        screen_geo = screen.availableGeometry()
        self.max_width = int(screen_geo.width() * 0.95)
        self.max_height = int(screen_geo.height() * 0.95)
        
        # --- Determine initial size based on the SCALED (fit-to-window) size ---
        
        # Use size from the currently displayed content (pixmap or movie)
        current_size = self.image_label.size()
        
        # Calculate target window size (Scaled Image size + padding for arrows/margins)
        target_width = min(current_size.width() + 100, self.max_width) # 100 is padding + arrows
        target_height = min(current_size.height() + 50, self.max_height) # 50 is padding/title bar
        
        # Schedule the resize to ensure it happens after the layout is fully built
        QTimer.singleShot(0, lambda: self.resize(QSize(target_width, target_height)))


    # --- MODIFIED: load_image supports GIF ---
    def load_image(self, path: str, initial_load: bool = False) -> bool:
        """
        Loads and displays the image or GIF from the given path.
        Sets the zoom factor to 'fit-to-window' for all loads.
        Returns True on success, False on failure.
        """
        file_extension = os.path.splitext(path)[1].lower()
        self.is_animated = (file_extension == '.gif')
        
        # Stop and clear any previous movie
        if self.current_movie:
            self.current_movie.stop()
            self.current_movie.deleteLater()
            self.current_movie = None
            self.image_label.clear()

        if self.is_animated:
            # --- Handle GIF (QMovie) ---
            new_movie = QMovie(path)
            
            if not new_movie.isValid():
                self.setWindowTitle(f"Image Preview - Error Loading {os.path.basename(path)}")
                return False
                
            self.current_movie = new_movie
            self.image_label.setMovie(self.current_movie)
            
            # Since QMovie scaling is handled differently, we start it now
            self.current_movie.start() 
            
            # Get the base size of the GIF for scaling calculation
            self.original_pixmap = QPixmap() # Clear static pixmap state
            
        else:
            # --- Handle Static Image (QPixmap) ---
            new_pixmap = QPixmap(path)
            
            if new_pixmap.isNull():
                 self.setWindowTitle(f"Image Preview - Error Loading {os.path.basename(path)}")
                 return False

            self.original_pixmap = new_pixmap
            self.current_movie = None # Clear movie state
            
        self.image_path = path

        # All images, regardless of initial_load or navigation, must fit the preview window
        self.current_zoom_factor = self._calculate_fit_scale()
            
        self.update_image_display()
        return True
    # --- END MODIFIED load_image ---


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

    # --- MODIFIED: update_image_display supports GIF ---
    def update_image_display(self):
        """Applies the current zoom factor to the image (Pixmap or Movie) and updates the label."""
        
        original_size = self._get_original_size()

        if original_size.isNull() or original_size.width() == 0:
            return
            
        # Calculate new dimensions based on the original size and zoom factor
        new_width = int(original_size.width() * self.current_zoom_factor)
        new_height = int(original_size.height() * self.current_zoom_factor)
        
        new_size = QSize(new_width, new_height)
        
        if self.is_animated and self.current_movie:
            # --- GIF Scaling ---
            self.current_movie.setScaledSize(new_size)
            self.image_label.setFixedSize(new_size)
            
        elif not self.original_pixmap.isNull():
            # --- Static Image Scaling ---
            scaled_pixmap = self.original_pixmap.scaled(
                new_size,
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
    # --- END MODIFIED update_image_display ---

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
    
    # --- FIX: Override mousePressEvent to restore focus explicitly ---
    def mousePressEvent(self, event: QMouseEvent):
        """
        Overrides mouse click event to ensure the dialog immediately regains focus.
        This is a necessary workaround for focus propagation issues when controls lose focus.
        """
        super().mousePressEvent(event)
        
        # Defer the focus call slightly to allow the mouse event chain to complete
        QTimer.singleShot(0, self.setFocus)
    # --- END FIX ---
            
    def closeEvent(self, event):
        """
        Overrides the close event to emit a cleanup signal to the parent tab.
        """
        # --- FIX: Emit signal to de-highlight the current image in the parent gallery ---
        # Ensure synchronous emission to guarantee the parent processes the style reset
        # before this object is destroyed (by WA_DeleteOnClose).
        self.path_changed.emit(self.image_path, 'WINDOW_CLOSED')

        super().closeEvent(event)
        
    def contextMenuEvent(self, event):
        """
        Overrides the context menu event (right-click) to display management options.
        """
        menu = QMenu(self)

        # --- COPY ACTION ---
        copy_action = QAction("Copy Image (Ctrl+C)", self)
        copy_action.triggered.connect(self.copy_image_to_clipboard)
        menu.addAction(copy_action)
        menu.addSeparator()
        # -------------------

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

    def copy_image_to_clipboard(self):
        """Copies the currently displayed image frame to the system clipboard."""
        target_pixmap = None
        if self.is_animated and self.current_movie:
            target_pixmap = self.current_movie.currentPixmap()
        elif not self.original_pixmap.isNull():
            target_pixmap = self.original_pixmap
            
        if target_pixmap and not target_pixmap.isNull():
            QApplication.clipboard().setPixmap(target_pixmap)

    def keyPressEvent(self, event: QKeyEvent):
        """
        Handles key presses for navigation (Left/Right), closing (Ctrl+W), and Copy (Ctrl+C).
        """
        # Ensure that if we press an arrow key, we navigate and accept the event.
        if event.key() == Qt.Key.Key_Right:
            self._navigate(1)
            event.accept()
        elif event.key() == Qt.Key.Key_Left:
            self._navigate(-1)
            event.accept()
        elif event.key() == Qt.Key.Key_W and event.modifiers() & Qt.ControlModifier:
            self.close()
            event.accept()
        elif event.key() == Qt.Key.Key_C and event.modifiers() & Qt.ControlModifier:
            self.copy_image_to_clipboard()
            event.accept()
        else:
            super().keyPressEvent(event)

    def _navigate(self, direction: int):
        """Cycles the current image index and loads the new image."""
        if len(self.all_paths) <= 1:
            return
        
        # --- Capture the path we are navigating AWAY from ---
        old_path = self.image_path
            
        new_index = self.current_index + direction
        
        # Cycle logic (wraps around)
        if new_index >= len(self.all_paths):
            new_index = 0
        elif new_index < 0:
            new_index = len(self.all_paths) - 1
            
        if new_index != self.current_index:
            self.current_index = new_index
            new_path = self.all_paths[self.current_index]
            
            # --- EMIT Signal: Notify parent of the change ---
            self.path_changed.emit(old_path, new_path) 
            
            self.load_image(new_path)
        
        # --- FIX: Restore focus after navigation ---
        QTimer.singleShot(0, self.setFocus)
import os

from typing import Set
from pathlib import Path
from PySide6.QtGui import QPixmap
from PySide6.QtCore import (
    Qt, QThreadPool, QThread, Slot
)
from PySide6.QtWidgets import (
    QApplication, QMessageBox, QGridLayout,
    QHBoxLayout, QVBoxLayout, QScrollArea, 
    QComboBox, QLineEdit, QFileDialog, 
    QPushButton, QLabel, QFormLayout,
    QWidget, QGroupBox, QCheckBox, QFrame,
)
from .base_tab import BaseTab
from ..components import ImagePreviewWindow, ClickableLabel, MarqueeScrollArea
from ..helpers import ImageScannerWorker, BatchThumbnailLoaderWorker
from ..styles.style import apply_shadow_effect


class ScanMetadataTab(BaseTab):
    """
    Manages file and directory metadata scanning, image preview gallery, and batch database operations.
    Requires a reference to the main DatabaseTab for database connection access.
    """
    def __init__(self, db_tab_ref, dropdown=True):
        super().__init__()
        self.db_tab_ref = db_tab_ref
        self.dropdown = dropdown
        
        self.scan_image_list: list[str] = []
        self.selected_image_paths: Set[str] = set()
        self.selected_scan_image_path: str = None
        self.open_preview_windows: list[ImagePreviewWindow] = [] 

        # Current thumbnail size (200x200)
        self.thumbnail_size = 200
        self.padding_width = 10
        self.approx_item_width = self.thumbnail_size + self.padding_width
        
        # New dictionary to track selection in the bottom panel for styling
        self.selected_card_map = {} 
        
        main_layout = QVBoxLayout(self)

        # ------------------------------------------------------------------
        # --- NEW: Scrollable Content Setup ---
        # ------------------------------------------------------------------
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        # ESCAPED NEWLINE FIX: Ensuring stylesheet is parseable
        scroll_area.setStyleSheet("QScrollArea { border: none; }")
        
        scroll_content = QWidget()
        scroll_content_layout = QVBoxLayout(scroll_content)
        scroll_content_layout.setContentsMargins(0, 0, 0, 0)
        
        # --- Scan Directory Section ---
        scan_group = QGroupBox("Scan Directory")
        # ESCAPED NEWLINE FIX: Adding minimal QGroupBox styles
        scan_group.setStyleSheet("""
            QGroupBox {  
                border: 1px solid #4f545c; \n
                border-radius: 8px; \n
                margin-top: 10px; \n
            }
            QGroupBox::title { 
                subcontrol-origin: margin; \n
                subcontrol-position: top left; \n
                padding: 4px 10px; \n
                color: white; \n
                border-radius: 4px; \n
            }
        """)
        
        scan_layout = QVBoxLayout()
        scan_layout.setContentsMargins(10, 20, 10, 10) 
        
        scan_dir_layout = QHBoxLayout()
        self.scan_directory_path = QLineEdit()
        self.scan_directory_path.setPlaceholderText("Select directory to scan...")
        btn_browse_scan = QPushButton("Browse...")
        btn_browse_scan.clicked.connect(self.browse_scan_directory)
        
        # NEW: Connect Enter key on Linedit to custom handler
        self.scan_directory_path.returnPressed.connect(self.handle_scan_directory_return)

        apply_shadow_effect(btn_browse_scan, color_hex="#000000", radius=8, x_offset=0, y_offset=3)

        scan_dir_layout.addWidget(self.scan_directory_path)
        scan_dir_layout.addWidget(btn_browse_scan)
        scan_layout.addLayout(scan_dir_layout)
        
        scan_group.setLayout(scan_layout)
        scroll_content_layout.addWidget(scan_group) # ADDED TO SCROLL CONTENT

        self.threadpool = QThreadPool.globalInstance()
        self.scanned_dir = None
        try:
            base_dir = Path.cwd()
            while base_dir.name != 'Image-Toolkit' and base_dir.parent != base_dir:
                base_dir = base_dir.parent
            if base_dir.name == 'Image-Toolkit':
                self.last_browsed_scan_dir = str(base_dir / 'data')
            else:
                self.last_browsed_scan_dir = str(Path.cwd() / 'data')
        except Exception:
            self.last_browsed_scan_dir = os.getcwd() 
        
        self.current_thumbnail_loader_thread = None
        self.current_thumbnail_loader_worker = None
        self.path_to_label_map = {}

        # View Image button
        self.scan_view_image_btn = QPushButton("View Full Size Selected Image(s)")
        self.scan_view_image_btn.clicked.connect(self.view_selected_scan_image)
        self.scan_view_image_btn.setEnabled(False) 
        self.scan_view_image_btn.setStyleSheet("""
            QPushButton { 
                background-color: #5865f2; \n
                color: white; \n
                padding: 10px; \n
                border-radius: 8px; \n
            } 
            QPushButton:hover { 
                background-color: #4754c4; \n
            }
            QPushButton:disabled {
                background-color: #4f545c; \n
                color: #a0a0a0; \n
            }
        """)
        apply_shadow_effect(self.scan_view_image_btn, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        scroll_content_layout.addWidget(self.scan_view_image_btn) # ADDED TO SCROLL CONTENT

        # Scroll Area for image thumbnails (Main Gallery)
        self.scan_scroll_area = MarqueeScrollArea() 
        self.scan_scroll_area.setWidgetResizable(True)
        # ESCAPED NEWLINE FIX: Ensuring stylesheet is parseable
        self.scan_scroll_area.setStyleSheet("QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }")

        # Set minimum height for the main gallery scroll area (half of 1200, matching merge_tab)
        self.scan_scroll_area.setMinimumHeight(600) 

        self.scan_thumbnail_widget = QWidget()
        self.scan_thumbnail_widget.setStyleSheet("QWidget { background-color: #2c2f33; }")

        self.scan_thumbnail_layout = QGridLayout(self.scan_thumbnail_widget)
        
        self.scan_scroll_area.selection_changed.connect(self.handle_marquee_selection)
        
        self.scan_thumbnail_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        
        self.scan_scroll_area.setWidget(self.scan_thumbnail_widget)
        
        scroll_content_layout.addWidget(self.scan_scroll_area, 1) # ADDED TO SCROLL CONTENT, with stretch
        
        # --- Selected Images Area --- (Bottom Gallery)
        self.selected_images_area = MarqueeScrollArea() 
        self.selected_images_area.setWidgetResizable(True)
        # ESCAPED NEWLINE FIX: Ensuring stylesheet is parseable
        self.selected_images_area.setStyleSheet("QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }")
        self.selected_images_area.selection_changed.connect(self.handle_marquee_selection) 
        
        # Set minimum height for the selected images scroll area (half of 1200, matching merge_tab)
        self.selected_images_area.setMinimumHeight(600)

        self.selected_images_widget = QWidget()
        self.selected_images_widget.setStyleSheet("QWidget { background-color: #2c2f33; }")
        self.selected_grid_layout = QGridLayout(self.selected_images_widget)
        self.selected_grid_layout.setSpacing(10)
        self.selected_grid_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter) 
        
        self.selected_images_area.setWidget(self.selected_images_widget)
        
        self.selected_images_area.setVisible(True) 
        scroll_content_layout.addWidget(self.selected_images_area, 1) # ADDED TO SCROLL CONTENT, with stretch
        
        # --- Metadata Group Box ---
        self.metadata_group = QGroupBox("Batch Metadata (Applies to ALL Selected Images)")
        self.metadata_group.setVisible(False) 
        metadata_vbox = QVBoxLayout(self.metadata_group)
        
        form_layout = QFormLayout()
        
        series_layout = QHBoxLayout()
        self.series_combo = QComboBox()
        self.series_combo.setEditable(True)
        self.series_combo.setPlaceholderText("Enter or select series name...")
        # NEW: Connect Enter key on combo box line edit to upsert button
        self.series_combo.lineEdit().returnPressed.connect(lambda: self.upsert_button.click())
        series_layout.addWidget(self.series_combo)
        form_layout.addRow("Series Name:", series_layout)
        
        char_layout = QVBoxLayout()
        self.characters_edit = QLineEdit()
        self.characters_edit.setPlaceholderText("Enter character names (comma-separated)...")
        # NEW: Connect Enter key
        self.characters_edit.returnPressed.connect(lambda: self.upsert_button.click())
        char_layout.addWidget(self.characters_edit)
        self.char_suggestions = QLabel()
        self.char_suggestions.setStyleSheet("font-size: 9px; color: #b9bbbe;")
        char_layout.addWidget(self.char_suggestions)
        form_layout.addRow("Characters:", char_layout)
        
        tags_scroll = QScrollArea()
        tags_scroll.setMaximumHeight(150)
        tags_scroll.setWidgetResizable(True)
        self.tags_widget = QWidget()
        self.tags_layout = QGridLayout(self.tags_widget)
        tags_scroll.setWidget(self.tags_widget)
        
        self.common_tags = sorted([
            "landscape", "night", "day", "indoor", "outdoor",
            "solo", "multiple", "fanart", "official", "cosplay",
            "portrait", "full_body", "action", "close_up", "nsfw",
            "color", "monochrome", "sketch", "digital", "traditional"
        ])
        self.tag_checkboxes = {}
        columns = 4
        for i, tag in enumerate(self.common_tags):
            checkbox = QCheckBox(tag.replace("_", " ").title())
            checkbox.setStyleSheet("""
                QCheckBox::indicator {
                    width: 16px; height: 16px; border: 1px solid #555; \n
                    border-radius: 3px; background-color: #333; \n
                }
                QCheckBox::indicator:checked {
                    background-color: #4CAF50; border: 1px solid #4CAF50; \n
                    image: url(./src/gui/assets/check.png); \n
                }
            """)
            self.tag_checkboxes[tag] = checkbox
            row = i // columns
            col = i % columns
            self.tags_layout.addWidget(checkbox, row, col)

        form_layout.addRow("Tags:", tags_scroll)
        
        metadata_vbox.addLayout(form_layout)
        
        scroll_content_layout.addWidget(self.metadata_group) # ADDED TO SCROLL CONTENT

        # Add scroll content to scroll area
        scroll_area.setWidget(scroll_content)
        # Add scroll area to the main layout
        main_layout.addWidget(scroll_area, 1)

        # --- Action buttons (Fixed at the bottom) ---
        
        self.view_batch_button = QPushButton("View Selected")
        self.view_batch_button.setStyleSheet("""
            QPushButton { 
                background-color: #3498db; \n
                color: white; \n
                padding: 10px 8px; \n
                border-radius: 8px; \n
                font-weight: bold; \n
            } 
            QPushButton:hover { 
                background-color: #2980b9; \n
            }
            QPushButton:disabled {
                background-color: #4f545c; \n
                color: #a0a0a0; \n
            }
        """)
        apply_shadow_effect(self.view_batch_button, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.view_batch_button.clicked.connect(self.toggle_selected_images_view) 

        self.upsert_button = QPushButton("Add/Update Database Data")
        self.upsert_button.setStyleSheet("""
            QPushButton { 
                background-color: #2ecc71; \n
                color: white; \n
                padding: 10px 8px; \n
                border-radius: 8px; \n
                font-weight: bold; \n
            } 
            QPushButton:hover { 
                background-color: #1e8449; \n
            }
            QPushButton:disabled {
                background-color: #4f545c; \n
                color: #a0a0a0; \n
            }
        """)
        apply_shadow_effect(self.upsert_button, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.upsert_button.clicked.connect(self.perform_upsert_operation)

        self.refresh_image_button = QPushButton("Refresh Image Directory")
        self.refresh_image_button.setStyleSheet("""
            QPushButton { 
                background-color: #f1c40f; \n
                color: white; \n
                padding: 10px 8px; \n
                border-radius: 8px; \n
                font-weight: bold; \n
            } 
            QPushButton:hover { 
                background-color: #d4ac0d; \n
            }
            QPushButton:disabled {
                background-color: #4f545c; \n
                color: #a0a0a0; \n
            }
        """)
        apply_shadow_effect(self.refresh_image_button, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.refresh_image_button.clicked.connect(self.refresh_image_directory) 

        self.delete_selected_button = QPushButton("Delete Images Data from Database")
        self.delete_selected_button.setStyleSheet("""
            QPushButton { 
                background-color: #e74c3c; \n
                color: white; \n
                padding: 10px 8px; \n
                border-radius: 8px; \n
                font-weight: bold; \n
            } 
            QPushButton:hover { 
                background-color: #c0392b; \n
            }
            QPushButton:disabled {
                background-color: #4f545c; \n
                color: #a0a0a0; \n
            }
        """)
        apply_shadow_effect(self.delete_selected_button, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.delete_selected_button.clicked.connect(self.delete_selected_images)
        
        scan_action_layout = QHBoxLayout()
        scan_action_layout.addWidget(self.view_batch_button)
        scan_action_layout.addWidget(self.upsert_button)
        scan_action_layout.addWidget(self.refresh_image_button)
        scan_action_layout.addWidget(self.delete_selected_button)
        
        main_layout.addLayout(scan_action_layout) 
        
        self.setLayout(main_layout)
        
        self.update_button_states(connected=False) 
        # Initial population of the selected gallery to show a placeholder
        self.populate_selected_images_gallery()
    
    @Slot()
    def _cleanup_thumbnail_thread_ref(self):
        """Slot to clear the QThread and QObject references after the thread finishes its work."""
        self.current_thumbnail_loader_thread = None
        self.current_thumbnail_loader_worker = None

    @Slot(int, str)
    def _create_thumbnail_placeholder(self, index: int, path: str):
        columns = self.calculate_columns()
        row = index // columns
        col = index % columns

        clickable_label = ClickableLabel(path) 
        clickable_label.setText("Loading...")
        clickable_label.setAlignment(Qt.AlignCenter)
        clickable_label.setFixedSize(self.thumbnail_size, self.thumbnail_size)
        clickable_label.setStyleSheet("border: 1px dashed #4f545c; color: #b9bbbe;") 
        clickable_label.path_clicked.connect(self.select_scan_image)
        clickable_label.path_double_clicked.connect(self.view_selected_scan_image_from_double_click) 

        self.scan_thumbnail_layout.addWidget(clickable_label, row, col)
        self.path_to_label_map[path] = clickable_label 
        
        self.scan_thumbnail_widget.update()
        QApplication.processEvents()

    def display_scan_results(self, image_paths: list[str]):
        """Receives image paths from the worker thread, creates placeholders, and starts thumbnail loader."""
        
        # Clear only the top gallery, preserving selection state
        if self.current_thumbnail_loader_thread and self.current_thumbnail_loader_thread.isRunning():
            self.current_thumbnail_loader_thread.quit()
        
        self.current_thumbnail_loader_thread = None
        self.current_thumbnail_loader_worker = None
        self.path_to_label_map = {} 

        while self.scan_thumbnail_layout.count():
            item = self.scan_thumbnail_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.scan_image_list = []
        
        self.scan_image_list = image_paths
        
        columns = self.calculate_columns()
        
        if not self.scan_image_list:
            no_images_label = QLabel("No supported images found.")
            no_images_label.setAlignment(Qt.AlignCenter)
            no_images_label.setStyleSheet("color: #b9bbbe;")
            self.scan_thumbnail_layout.addWidget(no_images_label, 0, 0, 1, columns)
            return
        
        worker = BatchThumbnailLoaderWorker(self.scan_image_list, self.thumbnail_size)
        thread = QThread()

        self.current_thumbnail_loader_worker = worker
        self.current_thumbnail_loader_thread = thread
        
        worker.moveToThread(thread)
        thread.started.connect(worker.run_load_batch)
        worker.create_placeholder.connect(self._create_thumbnail_placeholder)
        worker.thumbnail_loaded.connect(self._update_thumbnail_slot)
        
        worker.loading_finished.connect(thread.quit)
        worker.loading_finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._cleanup_thumbnail_thread_ref) 
        
        thread.start()
        
    @Slot(int, QPixmap, str)
    def _update_thumbnail_slot(self, index: int, pixmap: QPixmap, path: str):
        label = self.path_to_label_map.get(path)
        if label is None:
            return

        is_selected = path in self.selected_image_paths
        
        if not pixmap.isNull():
            label.setPixmap(pixmap) 
            label.setText("") 
            if is_selected:
                label.setStyleSheet("border: 3px solid #5865f2;")
            else:
                label.setStyleSheet("border: 1px solid #4f545c;")
        else:
            label.setText("Load Error")
            if is_selected:
                label.setStyleSheet("border: 3px solid #5865f2; background-color: #4f545c; font-size: 8px;") 
            else:
                label.setStyleSheet("border: 1px solid #e74c3c; background-color: #4f545c; font-size: 8px;")

    def clear_scan_image_gallery(self):
        """Performs a FULL clear of the gallery AND the selection state (used by DB ops)."""
        if self.current_thumbnail_loader_thread and self.current_thumbnail_loader_thread.isRunning():
            self.current_thumbnail_loader_thread.quit()
        
        self.current_thumbnail_loader_thread = None
        self.current_thumbnail_loader_worker = None
        self.path_to_label_map = {} 

        while self.scan_thumbnail_layout.count():
            item = self.scan_thumbnail_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        
        while self.selected_grid_layout.count():
            item = self.selected_grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        # self.selected_images_area.setVisible(False) # Keep visible
        self.selected_card_map = {} # Clear map on full clear
        
        self.scan_image_list = []
        self.selected_image_paths = set()
        self.selected_scan_image_path = None
        self.update_button_states(connected=(self.db_tab_ref.db is not None))
        self.metadata_group.setVisible(False) 
        self.populate_selected_images_gallery() # Repopulate to show placeholder

    def handle_scan_error(self, message: str):
        self.clear_scan_image_gallery() 
        QMessageBox.warning(self, "Error Scanning", message)
        ready_label = QLabel("Browse for a directory.")
        ready_label.setAlignment(Qt.AlignCenter)
        ready_label.setStyleSheet("color: #b9bbbe;")
        self.scan_thumbnail_layout.addWidget(ready_label, 0, 0, 1, 1)

    def handle_scan_directory_return(self):
        """Custom handler for Enter key press on the scan directory path input."""
        directory = self.scan_directory_path.text().strip()
        if directory and Path(directory).is_dir():
            self.populate_scan_image_gallery(directory)
        else:
            # If text is empty or invalid, behave like clicking the Browse... button
            self.browse_scan_directory()

    def browse_scan_directory(self):
        start_dir = self.last_browsed_scan_dir
        options = QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
        directory = QFileDialog.getExistingDirectory(self, "Select directory to scan", start_dir, options)
        
        if directory:
            self.last_browsed_scan_dir = directory
            self.scan_directory_path.setText(directory)
            self.populate_scan_image_gallery(directory)

    def calculate_columns(self) -> int:
        widget_width = self.scan_thumbnail_widget.width()
        if widget_width <= 0:
            widget_width = self.scan_thumbnail_widget.parentWidget().width()
        
        if widget_width <= 0:
            return 4 
        
        columns = widget_width // self.approx_item_width
        return max(1, columns)

    def populate_scan_image_gallery(self, directory: str):
        """
        Initiates scanning. Only clears the top gallery to preserve current selection state.
        """
        self.scanned_dir = directory
        
        # --- CLEAR TOP GALLERY ONLY START ---
        if self.current_thumbnail_loader_thread and self.current_thumbnail_loader_thread.isRunning():
            self.current_thumbnail_loader_thread.quit()
        
        self.current_thumbnail_loader_thread = None
        self.current_thumbnail_loader_worker = None
        self.path_to_label_map = {} 

        while self.scan_thumbnail_layout.count():
            item = self.scan_thumbnail_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.scan_image_list = []
        # --- CLEAR TOP GALLERY ONLY END ---
        
        self.scan_view_image_btn.setEnabled(False)
        
        loading_label = QLabel("Scanning directory, please wait...")
        loading_label.setAlignment(Qt.AlignCenter)
        loading_label.setStyleSheet("color: #b9bbbe;")
        self.scan_thumbnail_layout.addWidget(loading_label, 0, 0, 1, 10) 
        
        self.worker = ImageScannerWorker(directory)
        self.thread = QThread() 
        self.worker.moveToThread(self.thread) 
        
        self.thread.started.connect(self.worker.run_scan)
        self.worker.scan_finished.connect(self.display_scan_results)
        self.worker.scan_error.connect(self.handle_scan_error)
        
        self.worker.scan_finished.connect(self.thread.quit)
        self.worker.scan_finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        
        self.thread.start()

    def select_scan_image(self, file_path: str):
        """
        Toggles selection state of an image in the main gallery. 
        Defaults to additive selection.
        """
        clicked_widget = self.path_to_label_map.get(file_path)
        if not clicked_widget:
            return

        # Toggle the selection state
        if file_path in self.selected_image_paths:
            self.selected_image_paths.remove(file_path)
        else:
            self.selected_image_paths.add(file_path)

        is_selected = file_path in self.selected_image_paths

        # Update styling for the clicked item in the main gallery
        if is_selected:
            if "Error" in clicked_widget.text():
                clicked_widget.setStyleSheet("border: 3px solid #5865f2; background-color: #4f545c; font-size: 8px;")
            else:
                clicked_widget.setStyleSheet("border: 3px solid #5865f2;")
        else:
            if not clicked_widget.pixmap().isNull():
                clicked_widget.setStyleSheet("border: 1px solid #4f545c;")
            else:
                if "Error" in clicked_widget.text():
                     clicked_widget.setStyleSheet("border: 1px solid #e74c3c; background-color: #4f545c; font-size: 8px;")
                else:
                     clicked_widget.setStyleSheet("border: 1px dashed #4f545c; color: #b9bbbe;") 

        self.selected_scan_image_path = file_path
        self.update_button_states(connected=(self.db_tab_ref.db is not None))
        
        # Auto-refresh selected section if visible
        if self.selected_images_area.isVisible():
            self.populate_selected_images_gallery()
            
    def select_selected_image_card(self, file_path: str):
        """
        Handles single-click events in the bottom 'Selected Images' panel.
        Toggles selection status in the master set and updates styling.
        Does NOT automatically hide the image; allows users to see what they deselected.
        """
        card_clickable_wrapper = self.selected_card_map.get(file_path)
        if not card_clickable_wrapper:
            return
            
        # Toggle selection in the master set
        if file_path in self.selected_image_paths:
            self.selected_image_paths.remove(file_path)
            is_selected = False
        else:
            self.selected_image_paths.add(file_path)
            is_selected = True
            
        # Get the QFrame (the visual card) inside the clickable wrapper
        card_frame = card_clickable_wrapper.findChild(QFrame)
        if card_frame:
            # Update the styling of the card itself
            # ESCAPED NEWLINE FIX: Escaping newlines in multiline QFrame style
            if is_selected:
                card_frame.setStyleSheet("""
                    QFrame {
                        background-color: #2c2f33; \n
                        border-radius: 8px; \n
                        border: 3px solid #5865f2; \n
                    }
                """)
            else:
                card_frame.setStyleSheet("""
                    QFrame {
                        background-color: #2c2f33; \n
                        border-radius: 8px; \n
                        border: 1px solid #4f545c; \n
                    }
                """)
            
        # Also update the styling in the main gallery if the image is loaded there
        main_label = self.path_to_label_map.get(file_path)
        if main_label:
            if is_selected:
                main_label.setStyleSheet("border: 3px solid #5865f2;")
            else:
                if not main_label.pixmap().isNull():
                    main_label.setStyleSheet("border: 1px solid #4f545c;")
                else:
                    main_label.setStyleSheet("border: 1px dashed #4f545c; color: #b9bbbe;")
        
        self.update_button_states(connected=(self.db_tab_ref.db is not None))
        
        # NOTE: We skip calling populate_selected_images_gallery() here to keep the deselected card visible.

    def view_selected_image_from_card(self, path: str):
        """Handles double-click event on a card in the selected panel to open the full preview."""
        # Ensure the image is in the selection set (as we intend to view it)
        if path not in self.selected_image_paths:
            self.selected_image_paths.add(path)
            # Update styling to reflect it is selected again
            self.select_selected_image_card(path)
            
        self.selected_scan_image_path = path
        self.view_selected_scan_image()


    def handle_marquee_selection(self, paths_from_marquee: set, is_ctrl_pressed: bool):
        # Marquee selection logic
        if not is_ctrl_pressed:
            paths_to_deselect = self.selected_image_paths - paths_from_marquee
            paths_to_select = paths_from_marquee - self.selected_image_paths
            self.selected_image_paths = paths_from_marquee
            paths_to_update = paths_to_deselect.union(paths_to_select)
        else:
            paths_to_update = paths_from_marquee - self.selected_image_paths
            self.selected_image_paths.update(paths_from_marquee)

        # Update styling in the main gallery
        for path in paths_to_update:
            label = self.path_to_label_map.get(path)
            if not label:
                continue
            
            is_selected = path in self.selected_image_paths
            if is_selected:
                if "Error" in label.text():
                    label.setStyleSheet("border: 3px solid #5865f2; background-color: #4f545c; font-size: 8px;")
                else:
                    label.setStyleSheet("border: 3px solid #5865f2;")
            else:
                if not label.pixmap().isNull():
                    label.setStyleSheet("border: 1px solid #4f545c;")
                else:
                    if "Error" in label.text():
                         label.setStyleSheet("border: 1px solid #e74c3c; background-color: #4f545c; font-size: 8px;")
                    else:
                         label.setStyleSheet("border: 1px dashed #4f545c; color: #b9bbbe;") 

        self.update_button_states(connected=(self.db_tab_ref.db is not None))

        # Auto-refresh selected section if visible
        if self.selected_images_area.isVisible():
            self.populate_selected_images_gallery()

    def view_selected_scan_image_from_double_click(self, path: str):
        if path not in self.selected_image_paths:
            self.select_scan_image(path)
        self.selected_scan_image_path = path
        self.view_selected_scan_image()

    def remove_preview_window(self, window_instance: ImagePreviewWindow):
        """Removes a preview window from the tracking list when it's closed."""
        try:
            if window_instance in self.open_preview_windows:
                self.open_preview_windows.remove(window_instance)
        except (RuntimeError, ValueError):
            pass

    def view_selected_scan_image(self):
        """Opens non-modal, full-size image preview windows for ALL currently selected scan images."""
        if not self.selected_image_paths:
            if self.selected_scan_image_path:
                self.selected_image_paths.add(self.selected_scan_image_path)
                self.update_button_states(connected=(self.db_tab_ref.db is not None))
            else:
                QMessageBox.warning(self, "No Images Selected", "Please select one or more image thumbnails from the gallery first.")
                return

        for path in self.selected_image_paths:
            if not (path and os.path.exists(path) and os.path.isfile(path)):
                QMessageBox.warning(self, "Invalid Path", f"The path '{path}' is invalid or not a file. Skipping.")
                continue

            already_open = False
            for window in self.open_preview_windows:
                if isinstance(window, ImagePreviewWindow) and window.image_path == path:
                    window.activateWindow() 
                    already_open = True
                    break
            
            if not already_open:
                preview = ImagePreviewWindow(path, self.db_tab_ref, parent=self) 
                preview.finished.connect(lambda result, p=preview: self.remove_preview_window(p))
                preview.show() 
                self.open_preview_windows.append(preview)

    def toggle_selected_images_view(self):
        """Toggles the visibility of the selected images grid, populating it if it's being shown."""
        selection_count = len(self.selected_image_paths)
        if selection_count == 0:
            # We don't hide the group automatically anymore, just update the button text
            self.update_button_states(connected=(self.db_tab_ref.db is not None))
            return

        if self.selected_images_area.isVisible():
            self.selected_images_area.setVisible(False)
            self.view_batch_button.setText(f"View {selection_count} Selected")
        else:
            # Always populate when showing to ensure fresh content
            self.populate_selected_images_gallery()
            self.selected_images_area.setVisible(True)
            self.view_batch_button.setText(f"Hide {selection_count} Selected")
            
    def populate_selected_images_gallery(self):
        """
        Clears and repopulates the grid layout in the 'Selected Images' group box.
        Ensures consistent thumbnail size and centering.
        """
        # Clear existing widgets and the tracking map
        while self.selected_grid_layout.count():
            item = self.selected_grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.selected_card_map = {}
        
        paths = sorted(list(self.selected_image_paths))
        
        # Use the main thumbnail size for consistency
        thumb_size = self.thumbnail_size 
        padding = 10
        # Calculate approximation based on the main size
        approx_width = thumb_size + padding + 10 
        
        widget_width = self.selected_images_widget.width()
        if widget_width <= 0:
            widget_width = self.parentWidget().width()
        
        columns = max(1, widget_width // approx_width)
        
        # Calculate the fixed size for the wrapper to hold the image + path label comfortably
        wrapper_height = self.thumbnail_size + 30 # Image height + room for path label
        wrapper_width = self.thumbnail_size + 10 # Image width + minor padding/margin
        
        if not paths:
            # Add a placeholder when no images are selected, since the section is visible by default
            empty_label = QLabel("Select images from the scan directory above to view them here.")
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setStyleSheet("color: #b9bbbe; padding: 50px;")
            self.selected_grid_layout.addWidget(empty_label, 0, 0, 1, columns)
            # self.selected_images_area.setTitle("Selected Images (0)") # No title
            return

        for i, path in enumerate(paths):
            # Use ClickableLabel to wrap the card content for selection/click
            card_clickable_wrapper = ClickableLabel(path)
            
            # Set explicit size constraints on the wrapper to ensure it holds the content
            card_clickable_wrapper.setFixedSize(wrapper_width, wrapper_height) 

            card_clickable_wrapper.path_clicked.connect(self.select_selected_image_card)
            card_clickable_wrapper.path_double_clicked.connect(self.view_selected_image_from_card)
            
            # --- Card Frame Styling ---
            card = QFrame()
            
            # The card should always reflect its true selection status in the master set
            is_master_selected = path in self.selected_image_paths
            
            # ESCAPED NEWLINE FIX: Escaping newlines in multiline QFrame style
            if is_master_selected:
                 card_style = (
                     "QFrame { \n"
                     "    background-color: #2c2f33; \n"
                     "    border-radius: 8px; \n"
                     "    border: 3px solid #5865f2; \n"
                     "}"
                 )
            else:
                card_style = (
                    "QFrame { \n"
                    "    background-color: #2c2f33; \n"
                    "    border-radius: 8px; \n"
                    "    border: 1px solid #4f545c; \n"
                    "}"
                )

            card.setStyleSheet(card_style)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(0, 0, 0, 0) 
            
            img_label = QLabel()
            img_label.setAlignment(Qt.AlignCenter)
            # Explicitly use self.thumbnail_size (200) for fixed size container
            img_label.setFixedSize(self.thumbnail_size, self.thumbnail_size) 
            
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    self.thumbnail_size, self.thumbnail_size, 
                    Qt.KeepAspectRatio, 
                    Qt.SmoothTransformation
                )
                img_label.setPixmap(scaled)
            else:
                img_label.setText("Failed to Load")
                img_label.setStyleSheet("color: #e74c3c;")

            path_label = QLabel(os.path.basename(path)) 
            path_label.setStyleSheet("color: #b9bbbe; font-size: 10px; border: none; padding: 2px 0;")
            path_label.setAlignment(Qt.AlignCenter)
            path_label.setWordWrap(True)

            card_layout.addWidget(img_label)
            card_layout.addWidget(path_label)
            
            # Set the card frame as the content of the clickable wrapper
            card_clickable_wrapper.setLayout(card_layout)
            
            row = i // columns
            col = i % columns
            
            # Store the wrapper to track the actual selection state of the item within the panel
            self.selected_card_map[path] = card_clickable_wrapper
            
            # Use Qt.AlignCenter on the QGridLayout to center the individual items
            self.selected_grid_layout.addWidget(card_clickable_wrapper, row, col, Qt.AlignCenter) 

    def perform_upsert_operation(self):
        """Performs the Add/Update (Upsert) operation on selected image paths."""
        db = self.db_tab_ref.db
        if not db:
            QMessageBox.warning(self, "Error", "Please connect to a database first (in Database tab)")
            return
        
        selected_paths = list(self.selected_image_paths)
        if not selected_paths:
            QMessageBox.warning(self, "Error", "No images selected.")
            return

        if not self.metadata_group.isVisible():
            self.metadata_group.setVisible(True)
            self.upsert_button.setText(f"Confirm & Upsert {len(selected_paths)} Images")
            return
            
        self.upsert_button.setText(f"Processing {len(selected_paths)}...")
        self.upsert_button.setEnabled(False)
        QApplication.processEvents() 
        
        try:
            added_count = 0
            updated_count = 0
            
            series = self.series_combo.currentText().strip() or None
            characters = [c.strip() for c in self.characters_edit.text().split(',') if c.strip()] or None
            tags = [tag for tag, cb in self.tag_checkboxes.items() if cb.isChecked()] or None

            for path in selected_paths:
                existing_data = db.get_image_by_path(path)
                
                if existing_data:
                    db.update_image(
                        image_id=existing_data['id'],
                        series_name=series,
                        characters=characters,
                        tags=tags
                    )
                    updated_count += 1
                else:
                    db.add_image(
                        file_path=path,
                        embedding=None, 
                        series_name=series,
                        characters=characters,
                        tags=tags
                    )
                    added_count += 1
            
            self.clear_scan_image_gallery()
            if self.scanned_dir:
                self.populate_scan_image_gallery(self.scanned_dir) 
            
            self.db_tab_ref.update_statistics()
            self.db_tab_ref.refresh_autocomplete_data()
            
            QMessageBox.information(self, "Success", f"Operation Complete:\nAdded: {added_count}\nUpdated: {updated_count}")
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to process images:\n{str(e)}")
        
        finally:
            self.metadata_group.setVisible(False) 
            self.update_button_states(connected=True)

    def refresh_image_directory(self):
        """
        Clears the directory path and the main scan preview gallery, 
        but preserves the selected images panel and selection list.
        """
        self.scan_directory_path.clear()
        self.scanned_dir = None
        
        # Stop any active thumbnail loading for the top gallery
        if self.current_thumbnail_loader_thread and self.current_thumbnail_loader_thread.isRunning():
            self.current_thumbnail_loader_thread.quit()
        
        self.current_thumbnail_loader_thread = None
        self.current_thumbnail_loader_worker = None
        self.path_to_label_map = {} 

        # Clear only the top (scan) gallery layout
        while self.scan_thumbnail_layout.count():
            item = self.scan_thumbnail_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        
        self.scan_image_list = []
        
        ready_label = QLabel("Image preview cleared. Browse for a new directory.")
        ready_label.setAlignment(Qt.AlignCenter)
        ready_label.setStyleSheet("color: #b9bbbe;")
        columns = self.calculate_columns()
        self.scan_thumbnail_layout.addWidget(ready_label, 0, 0, 1, columns)

        self.update_button_states(connected=(self.db_tab_ref.db is not None))

    def delete_selected_images(self):
        """Confirms and performs the DELETE operation on selected image paths."""
        db = self.db_tab_ref.db
        if not db:
            QMessageBox.warning(self, "Error", "Please connect to a database first (in Database tab)")
            return
            
        selected_paths = list(self.selected_image_paths)
        if not selected_paths:
            QMessageBox.warning(self, "Error", "No images selected for deletion.")
            return

        confirm = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete **{len(selected_paths)}** selected image entries from the database?\nThis action is irreversible.",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            self.delete_selected_button.setText(f"Deleting {len(selected_paths)}...")
            self.delete_selected_button.setEnabled(False)
            QApplication.processEvents() 
            
            try:
                image_ids = []
                for path in selected_paths:
                    img_data = db.get_image_by_path(path)
                    if img_data:
                        image_ids.append(img_data['id'])
                        
                count = 0
                for img_id in image_ids:
                    db.delete_image(img_id)
                    count += 1
                
                self.clear_scan_image_gallery()
                if self.scanned_dir:
                    self.populate_scan_image_gallery(self.scanned_dir)

                self.db_tab_ref.update_statistics()
                QMessageBox.information(self, "Deleted", f"Deleted {count} image entries from database.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete images:\n{str(e)}")
            finally:
                self.update_button_states(connected=True)
        else:
            QMessageBox.information(self, "Aborted", "Delete operation aborted by user.")

    def update_button_states(self, connected: bool):
        """Enable or disable buttons based on database connection status and current selection."""
        selection_count = len(self.selected_image_paths)
        
        self.scan_view_image_btn.setEnabled(selection_count > 0)
        self.scan_view_image_btn.setText(f"View Full Size {selection_count} Selected Image(s)")
        
        self.refresh_image_button.setEnabled(True) 

        # Since the selected group is always visible, we just update the text and enable/disable the toggle button
        if self.selected_images_area.isVisible():
            self.view_batch_button.setText(f"Hide {selection_count} Selected")
            # self.selected_images_area.setTitle(f"Selected Images ({selection_count})") # No title
        else:
            self.view_batch_button.setText(f"View {selection_count} Selected")
            
        self.view_batch_button.setEnabled(selection_count > 0 or self.selected_images_area.isVisible())

        if self.metadata_group.isVisible() and self.upsert_button.text().startswith("Confirm & Upsert"):
             self.upsert_button.setText(f"Confirm & Upsert {selection_count} Images")
        else:
            self.upsert_button.setText(f"Add/Update {selection_count} Selected Images")
        
        self.upsert_button.setEnabled(connected and selection_count > 0)

        self.delete_selected_button.setText(f"Delete {selection_count} Images from DB")
        self.delete_selected_button.setEnabled(connected and selection_count > 0)

    def collect(self) -> dict:
        """Collect current inputs from the Scan Directory tab as a dict."""
        out = {
            "scan_directory": self.scan_directory_path.text().strip() or None,
            "selected_images": list(self.selected_image_paths) 
        }
        return out

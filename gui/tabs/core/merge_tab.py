import os
import cv2
import shutil
import tempfile

from typing import Dict, Any, Optional
from PySide6.QtGui import QPixmap, QAction
from PySide6.QtCore import Qt, QTimer, QThread, Slot, QPoint, QEventLoop
from PySide6.QtWidgets import (
    QMenu, QPushButton, QFormLayout,
    QLineEdit, QFileDialog, QWidget, QLabel,
    QComboBox, QSpinBox, QGroupBox, QHBoxLayout,
    QVBoxLayout, QMessageBox, QGridLayout, QScrollArea,
)
from ...classes import AbstractClassTwoGalleries
from ...windows import ImagePreviewWindow
from ...components import ClickableLabel, MarqueeScrollArea
from ...helpers import MergeWorker, ImageScannerWorker
from ...styles.style import apply_shadow_effect, SHARED_BUTTON_STYLE
from backend.src.utils.definitions import SUPPORTED_IMG_FORMATS


class MergeTab(AbstractClassTwoGalleries):
    """
    GUI tab for merging images, now structured with a clear 'Merge Targets' section.
    Inherits core gallery and threading logic from BaseTwoGalleriesTab.
    """
    def __init__(self):
        super().__init__()
        self.thumbnail_size = 150 

        # --- State ---
        self.scanned_dir: str | None = None
        self.open_preview_windows: list[ImagePreviewWindow] = [] 
        
        self.current_scan_thread: QThread | None = None
        self.current_scan_worker: ImageScannerWorker | None = None
        self.current_merge_thread: QThread | None = None
        self.current_merge_worker: MergeWorker | None = None
        self.temp_file_path: Optional[str] = None

        # --- UI Setup ---
        main_layout = QVBoxLayout(self)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; }")

        scroll_content = QWidget()
        content_layout = QVBoxLayout(scroll_content)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # === 1. Merge Targets Group ===
        target_group = QGroupBox("Merge Targets")
        target_layout = QFormLayout(target_group)
        v_input_group = QVBoxLayout()

        scan_dir_layout = QHBoxLayout()
        self.scan_directory_path = QLineEdit() 
        self.scan_directory_path.setPlaceholderText("Path to directory containing images for merging...")
        self.scan_directory_path.returnPressed.connect(self.handle_scan_directory_return)
        
        btn_browse_scan = QPushButton("Browse...")
        btn_browse_scan.clicked.connect(self.browse_and_scan_directory)
        apply_shadow_effect(btn_browse_scan, color_hex="#000000", radius=8, x_offset=0, y_offset=3)

        scan_dir_layout.addWidget(self.scan_directory_path)
        scan_dir_layout.addWidget(btn_browse_scan)
        
        v_input_group.addLayout(scan_dir_layout)
        
        target_layout.addRow("Input path:", v_input_group)
        content_layout.addWidget(target_group)
        
        # === 2. Merge Settings ===
        config_group = QGroupBox("Merge Settings")
        config_layout = QFormLayout(config_group)

        self.direction = QComboBox()
        # ADDED "panorama" and "sequential" options here
        self.direction.addItems(["horizontal", "vertical", "grid", "panorama", "stitch", "sequential"])
        self.direction.currentTextChanged.connect(self.handle_direction_change)
        config_layout.addRow("Direction:", self.direction)

        # Spacing and Align are grouped so they can be hidden for panorama
        self.lbl_spacing = QLabel("Spacing (px):")
        self.spacing = QSpinBox()
        self.spacing.setRange(0, 1000)
        self.spacing.setValue(10)
        config_layout.addRow(self.lbl_spacing, self.spacing)

        self.lbl_align = QLabel("Alignment/Resize:")
        self.align_mode = QComboBox()
        self.align_mode.addItems([
            "Default (Top/Center)", "Align Top/Left", "Align Bottom/Right", 
            "Center", "Scaled (Grow Smallest)", "Squish (Shrink Largest)"
        ])
        config_layout.addRow(self.lbl_align, self.align_mode)

        self.grid_group = QGroupBox("Grid Size")
        grid_layout = QHBoxLayout()
        self.grid_rows = QSpinBox()
        self.grid_rows.setRange(1, 100)
        self.grid_cols = QSpinBox()
        self.grid_cols.setRange(1, 100)
        grid_layout.addWidget(QLabel("Rows:"))
        grid_layout.addWidget(self.grid_rows)
        grid_layout.addWidget(QLabel("Cols:"))
        grid_layout.addWidget(self.grid_cols)
        self.grid_group.setLayout(grid_layout)
        config_layout.addRow(self.grid_group)
        self.grid_group.hide()
        content_layout.addWidget(config_group)

        # === 3. Galleries ===
        
        self.selection_label = QLabel("0 images selected.")
        self.selection_label.setStyleSheet("padding: 5px 0; font-weight: bold;")
        content_layout.addWidget(self.selection_label)

        # --- Found Gallery ---
        self.found_gallery_scroll = MarqueeScrollArea()
        self.found_gallery_scroll.setWidgetResizable(True)
        self.found_gallery_scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }"
        )
        self.found_gallery_scroll.setMinimumHeight(600)
        
        self.found_thumbnail_widget = QWidget()
        self.found_thumbnail_widget.setStyleSheet("background-color: #2c2f33;")
        self.found_gallery_layout = QGridLayout(self.found_thumbnail_widget)
        self.found_gallery_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.found_gallery_scroll.setWidget(self.found_thumbnail_widget)
        self.found_gallery_scroll.selection_changed.connect(self.handle_marquee_selection)
        content_layout.addWidget(self.found_gallery_scroll, 1)

        # Add Pagination Widget (Created in Base Class)
        if hasattr(self, 'found_pagination_widget'):
            content_layout.addWidget(self.found_pagination_widget, 0, Qt.AlignmentFlag.AlignCenter)

        # --- Selected Gallery ---
        self.selected_gallery_scroll = MarqueeScrollArea()
        self.selected_gallery_scroll.setWidgetResizable(True)
        self.selected_gallery_scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }"
        )
        self.selected_gallery_scroll.setMinimumHeight(400)
        
        self.selected_images_widget = QWidget()
        self.selected_images_widget.setStyleSheet("background-color: #2c2f33;")
        self.selected_gallery_layout = QGridLayout(self.selected_images_widget)
        self.selected_gallery_layout.setSpacing(10)
        self.selected_gallery_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.selected_gallery_scroll.setWidget(self.selected_images_widget)
        content_layout.addWidget(self.selected_gallery_scroll, 1)

        # Add Pagination Widget (Created in Base Class)
        if hasattr(self, 'selected_pagination_widget'):
            content_layout.addWidget(self.selected_pagination_widget, 0, Qt.AlignmentFlag.AlignCenter)

        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)

        # === 4. Action Buttons ===
        action_vbox = QVBoxLayout()
        self.run_button = QPushButton("Run Merge")
        self.run_button.setStyleSheet(SHARED_BUTTON_STYLE)
        apply_shadow_effect(self.run_button, "#000000", 8, 0, 3)
        self.run_button.clicked.connect(self.start_merge)
        action_vbox.addWidget(self.run_button)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #b9bbbe; font-style: italic; padding: 10px;")
        action_vbox.addWidget(self.status_label)
        main_layout.addLayout(action_vbox)

        self.on_selection_changed()
        self.handle_direction_change(self.direction.currentText())
        self.clear_galleries()

    # --- IMPLEMENTING ABSTRACT METHODS ---
    def create_card_widget(self, path: str, pixmap: Optional[QPixmap], is_selected: bool) -> QWidget:
        thumb_size = self.thumbnail_size
        clickable_label = ClickableLabel(path) 
        clickable_label.setFixedSize(thumb_size + 10, thumb_size + 10)
        
        clickable_label.get_pixmap = lambda: img_label.pixmap()
        clickable_label.set_selected_style = lambda s: self._update_label_style(img_label, path, s)

        layout = QVBoxLayout(clickable_label)
        layout.setContentsMargins(0, 0, 0, 0)
        
        img_label = QLabel()
        img_label.setAlignment(Qt.AlignCenter)
        img_label.setFixedSize(thumb_size, thumb_size)
        layout.addWidget(img_label)

        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(thumb_size, thumb_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            img_label.setPixmap(scaled)
        else:
            img_label.setText("Loading...")
            img_label.setStyleSheet("color: #999; border: 1px dashed #666;")

        self._update_label_style(img_label, path, is_selected)

        clickable_label.path_double_clicked.connect(self.handle_full_image_preview)
        clickable_label.path_right_clicked.connect(self.show_image_context_menu)
        
        return clickable_label

    def update_card_pixmap(self, widget: QWidget, pixmap: Optional[QPixmap]):
        """Lazy loading callback for MergeTab. Unloads image if pixmap is None."""
        if not isinstance(widget, ClickableLabel): return
        
        img_label = widget.findChild(QLabel)
        if not img_label: return

        if pixmap and not pixmap.isNull():
            # Load Image
            thumb_size = self.thumbnail_size
            scaled = pixmap.scaled(thumb_size, thumb_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            img_label.setPixmap(scaled)
            img_label.setText("") 
        else:
            # Unload/Placeholder
            img_label.clear()
            img_label.setText("Loading...")
            
        # Reapply style
        is_selected = widget.path in self.selected_files
        self._update_label_style(img_label, widget.path, is_selected)

    def _update_label_style(self, label: QLabel, path: str, selected: bool):
        is_error = (label.text() == "Error")
        is_loading = (label.text() == "Loading...")
        
        if selected:
            if is_error:
                label.setStyleSheet("border: 3px solid #5865f2; background-color: #4f545c;")
            else:
                label.setStyleSheet("border: 3px solid #5865f2; background-color: #36393f;")
        else:
            if is_error:
                label.setStyleSheet("border: 1px solid #e74c3c; background-color: #4f545c;")
            elif is_loading:
                label.setStyleSheet("border: 1px dashed #666; color: #999;")
            else:
                label.setStyleSheet("border: 1px solid #4f545c;")

    def on_selection_changed(self):
        count = len(self.selected_files)
        self.selection_label.setText(f"{count} images selected.")
        if count < 2:
            self.run_button.setEnabled(False)
            self.run_button.setText("Run Merge (Select 2+ images)")
        else:
            self.run_button.setEnabled(True)
            self.run_button.setText(f"Run Merge ({count} images)")
        self.status_label.setText("" if count < 2 else f"Ready to merge {count} images.")

    # --- INPUT LOGIC ---
    @Slot()
    def handle_scan_directory_return(self):
        d = self.scan_directory_path.text().strip()
        if d and os.path.isdir(d):
            self.populate_scan_gallery(d)
        else:
            QMessageBox.warning(self, "Invalid Path", "The entered path is not a valid directory.")

    @Slot()
    def browse_and_scan_directory(self):
        d = QFileDialog.getExistingDirectory(self, "Select Directory to Scan", self.last_browsed_dir)
        if d:
            self.scan_directory_path.setText(d)
            self.last_browsed_dir = d
            self.populate_scan_gallery(d)
            
    def populate_scan_gallery(self, directory: str):
        self.scanned_dir = directory
        if self.current_scan_thread and self.current_scan_thread.isRunning():
            self.current_scan_thread.quit()
            self.current_scan_thread.wait(2000)
            
        self.cancel_loading()
        
        loop = QEventLoop()
        QTimer.singleShot(1, loop.quit)
        loop.exec()
        
        worker = ImageScannerWorker(directory)
        thread = QThread()
        
        self.current_scan_worker = worker
        self.current_scan_thread = thread
        worker.moveToThread(thread)

        thread.started.connect(worker.run_scan)
        worker.scan_finished.connect(self.on_scan_finished)
        worker.scan_finished.connect(thread.quit)
        thread.finished.connect(self.cleanup_scan_thread_ref)
        thread.start()

    @Slot()
    def cleanup_scan_thread_ref(self):
        self.current_scan_thread = None
        self.current_scan_worker = None
        
    @Slot(list)
    def on_scan_finished(self, paths):
        if not paths:
            QMessageBox.information(self, "No Files", f"No supported images found in {self.scanned_dir}")
            self.clear_galleries()
            return
            
        self.start_loading_thumbnails(sorted(paths))
        self.status_label.setText(f"Scan complete. Loaded {len(paths)} files.")

    # --- MERGING ---
    @Slot(str)
    def handle_full_image_preview(self, image_path: str):
        # 1. Prepare Navigation List
        full_list = self.found_files 
        target_list = full_list if full_list else self.selected_files.copy()
        
        if not target_list:
            target_list = [image_path]
        elif image_path not in target_list:
            target_list.append(image_path)

        try:
            start_index = target_list.index(image_path)
        except ValueError:
            start_index = 0
            
        # --- Track Current Path for Update Logic ---
        # This reference will track the path currently shown in the preview window
        current_preview_path = image_path 

        # --- Apply Temporary Highlight Style to the starting card ---
        target_card = self.path_to_label_map.get(image_path)
        if target_card:
            # 1. Ensure the card is in its canonical (non-highlight) state first.
            self.update_card_style(target_card, image_path in self.selected_files)
            
            # 2. Store the resulting canonical style on the card itself
            target_card.setProperty("original_style", target_card.styleSheet())
            
            # 3. Apply a distinctive blue border style for viewing
            target_card.setStyleSheet(f"{target_card.styleSheet().strip()}; border: 4px solid #3498db;")


        # 2. Create Preview Window
        window = ImagePreviewWindow(
            image_path=image_path, 
            db_tab_ref=None, 
            parent=self,
            all_paths=target_list, 
            start_index=start_index
        )
        
        # --- NEW CONNECTION ---
        # Connect the preview window's internal navigation signal to our external update slot
        window.path_changed.connect(self.update_preview_highlight)
        # ----------------------
        
        window.setAttribute(Qt.WA_DeleteOnClose)
        
        # 4. Handle Closure and Reset Style (inside handle_full_image_preview)
        def remove_closed_win(event: Any):
            # Restore the style of the image that was VISIBLE when the window closed
            last_card = self.path_to_label_map.get(current_preview_path)
            if last_card:
                # Retrieve the original style stored as a property
                original_style = last_card.property("original_style")
                if original_style:
                    last_card.setStyleSheet(original_style)
                else:
                    # Fallback to general style update if property wasn't set correctly
                    self.update_card_style(last_card, current_preview_path in self.selected_files)

            if window in self.open_preview_windows:
                 self.open_preview_windows.remove(window)
            event.accept()

        window.closeEvent = remove_closed_win
        window.show()
        
        window.activateWindow()
        window.setFocus()
        
        self.open_preview_windows.append(window)

    @Slot(str, str)
    def update_preview_highlight(self, old_path: str, new_path: str):
        """
        Updates the highlight style on the main gallery cards when navigation occurs in the preview window.
        """
        # --- Reset Old Card Style (Use saved original_style property) ---
        old_card = self.path_to_label_map.get(old_path)
        if old_card:
            # 1. Retrieve the original style saved when it was highlighted
            original_style = old_card.property("original_style")
            if original_style:
                old_card.setStyleSheet(original_style)
            else:
                # Fallback to standard style reset
                self.update_card_style(old_card, old_path in self.selected_files)
            
            # Clear the property to signal it's no longer highlighted
            old_card.setProperty("original_style", None)

        # --- Apply Highlight to New Card ---
        new_card = self.path_to_label_map.get(new_path)
        if new_card:
            # 1. Ensure the card is in its canonical (non-highlight) state first.
            # This calls _update_label_style based on its current selection state.
            self.update_card_style(new_card, new_path in self.selected_files)
            
            # 2. Save this canonical style to the property for future reset/closure.
            # This prevents saving the blue style as the "original."
            new_card.setProperty("original_style", new_card.styleSheet())
            
            # 3. Apply the temporary blue highlight.
            new_card.setStyleSheet(f"{new_card.styleSheet().strip()}; border: 4px solid #3498db;")

    @Slot(QPoint, str)
    def show_image_context_menu(self, global_pos: QPoint, path: str):
        menu = QMenu(self)
        view_action = QAction("View Full Size Preview", self)
        view_action.triggered.connect(lambda: self.handle_full_image_preview(path))
        menu.addAction(view_action)
        menu.addSeparator()

        is_selected = path in self.selected_files
        toggle_text = "Deselect Image (Remove from Merge List)" if is_selected else "Select Image (Add to Merge List)"
        toggle_action = QAction(toggle_text, self)
        toggle_action.triggered.connect(lambda: self.toggle_selection(path))
        menu.addAction(toggle_action)
        
        # Check if the context menu is being shown in the Selected Gallery (Bottom)
        if is_selected: 
            menu.addSeparator()
            
            # Add Move Up/Down actions
            move_up_action = QAction("⬆️ Move Up in Merge Order", self)
            move_up_action.triggered.connect(lambda: self._move_selected_image_up(path))
            menu.addAction(move_up_action)
            
            move_down_action = QAction("⬇️ Move Down in Merge Order", self)
            move_down_action.triggered.connect(lambda: self._move_selected_image_down(path))
            menu.addAction(move_down_action)
        
        menu.addSeparator()
        delete_action = QAction("🗑️ Delete Image File (Permanent)", self)
        delete_action.triggered.connect(lambda: self.handle_delete_image(path))
        menu.addAction(delete_action)
        
        menu.exec(global_pos)

    def _move_selected_image_up(self, path: str):
        """Moves the given path one position earlier in the selected_files list."""
        try:
            current_index = self.selected_files.index(path)
            if current_index > 0:
                # Swap elements
                self.selected_files[current_index], self.selected_files[current_index - 1] = \
                    self.selected_files[current_index - 1], self.selected_files[current_index]
                self.refresh_selected_panel()
                self.on_selection_changed() # Update button states if necessary (e.g., if re-ordering changed visibility)
        except ValueError:
            pass # Path not found

    def _move_selected_image_down(self, path: str):
        """Moves the given path one position later in the selected_files list."""
        try:
            current_index = self.selected_files.index(path)
            if current_index < len(self.selected_files) - 1:
                # Swap elements
                self.selected_files[current_index], self.selected_files[current_index + 1] = \
                    self.selected_files[current_index + 1], self.selected_files[current_index]
                self.refresh_selected_panel()
                self.on_selection_changed() # Update button states if necessary
        except ValueError:
            pass # Path not found

    def handle_delete_image(self, path: str):
        if QMessageBox.question(self, "Delete", f"Permanently delete {os.path.basename(path)}?") == QMessageBox.Yes:
            try:
                os.remove(path)
                
                # Update Data Lists in parent class
                if hasattr(self, 'found_files') and path in self.found_files:
                    self.found_files.remove(path)
                if hasattr(self, 'selected_files') and path in self.selected_files:
                    self.selected_files.remove(path)
                
                # Update UI: Remove from internal map and layout
                if hasattr(self, 'path_to_label_map') and path in self.path_to_label_map:
                     widget = self.path_to_label_map.pop(path)
                     widget.deleteLater()
                     
                self.on_selection_changed()
                
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))
        
    def start_merge(self):
        if len(self.selected_files) < 2: 
            QMessageBox.warning(self, "Invalid", "Select at least 2 images.")
            return
        
        # --- NEW: Create Temporary Output File Path ---
        temp_dir = tempfile.gettempdir()
        temp_filename = next(tempfile._get_candidate_names()) + ".png" 
        self.temp_file_path = os.path.join(temp_dir, temp_filename)
        
        # Worker config must use the temporary path
        temp_output_config = self.collect(self.temp_file_path)
        
        # Lock UI
        self.run_button.setEnabled(False)
        self.run_button.setText("Merging...")
        
        # --- NEW: Force OpenCL Cleanup ---
        # This attempts to force the GPU to finish all pending tasks and flush buffers, 
        # which can resolve lazy allocation/eviction issues when switching gallery pages.
        if cv2.ocl.haveOpenCL():
            cv2.ocl.finish()
        # --- END NEW ---
        
        worker = MergeWorker(temp_output_config)
        thread = QThread()
        self.current_merge_worker = worker
        self.current_merge_thread = thread
        worker.moveToThread(thread)
        
        thread.started.connect(worker.run)
        worker.progress.connect(lambda c, t: self.status_label.setText(f"Merging {c}/{t}"))
        
        # --- NEW CONNECTION ---
        worker.finished.connect(self.show_preview_and_confirm) 
        
        worker.error.connect(self.on_merge_error)
        
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(thread.deleteLater)
        thread.start()

    def on_merge_done(self, path):
        self.on_selection_changed()
        self.status_label.setText("Done.")
        QMessageBox.information(self, "Success", f"Saved to {path}")

    def cleanup_temp_file(self):
        """Safely removes the temporary merged file."""
        if self.temp_file_path and os.path.exists(self.temp_file_path):
            try:
                os.remove(self.temp_file_path)
            except Exception as e:
                print(f"Error cleaning up temp file {self.temp_file_path}: {e}")
        self.temp_file_path = None

    @Slot(str)
    def show_preview_and_confirm(self, temp_path: str):
        self.on_selection_changed() # Unlock UI
        self.temp_file_path = temp_path # Worker confirmed the file exists here
        
        if not os.path.exists(temp_path):
            self.on_merge_error(f"Failed to create temporary merge file at: {temp_path}")
            return

        self.status_label.setText("Merge complete. Showing preview...")

        # 1. Show Preview Window
        # Note: We do NOT set WA_DeleteOnClose because we need to check isVisible() later.
        # We will manually close/delete it.
        preview_window = ImagePreviewWindow(
            image_path=temp_path, 
            db_tab_ref=None, 
            parent=self, 
            all_paths=[temp_path], 
            start_index=0,
        )
        preview_window.setWindowTitle("Merged Image Preview")
        preview_window.show()
        preview_window.activateWindow()

        # 2. Get Confirmation Dialog (using custom buttons)
        confirm = QMessageBox(self)
        confirm.setWindowTitle("Save Merged Image?")
        confirm.setText("The merged image is ready. Choose an action:")
        
        save_btn = confirm.addButton("Save Only", QMessageBox.ButtonRole.AcceptRole)
        save_add_btn = confirm.addButton("Save & Add to Selection", QMessageBox.ButtonRole.AcceptRole)
        discard_btn = confirm.addButton("Discard Image", QMessageBox.ButtonRole.DestructiveRole)
        confirm.addButton(QMessageBox.StandardButton.Cancel)

        # Block here until user chooses
        confirm.exec()
        
        # 3. Handle Confirmation Result
        clicked_button = confirm.clickedButton()
        
        saved_path = None

        if clicked_button == save_btn or clicked_button == save_add_btn:
            out, _ = QFileDialog.getSaveFileName(self, "Save Merged Image", self.last_browsed_dir, "PNG (*.png)")
            if out:
                if not out.lower().endswith('.png'): out += '.png'
                try:
                    # Move the temporary file to the final destination
                    shutil.move(temp_path, out)
                    self.last_browsed_dir = os.path.dirname(out)
                    saved_path = out
                    QMessageBox.information(self, "Success", f"Saved to {out}")
                except Exception as e:
                    QMessageBox.critical(self, "Save Error", f"Failed to save image: {e}")
        
        if saved_path:
            self.temp_file_path = None # File saved, no need for cleanup
            
            # Logic for "Save & Add to Selection"
            if clicked_button == save_add_btn:
                self._inject_new_image(saved_path)
        else:
            self.cleanup_temp_file()
            if clicked_button == discard_btn:
                QMessageBox.information(self, "Discarded", "Merged image discarded.")
            elif clicked_button in [save_btn, save_add_btn]:
                # If save failed or dialog cancelled, notify the discard.
                QMessageBox.warning(self, "Cancelled", "Image save cancelled/failed. Merged image discarded.")

        # 4. Close Preview Window safely
        # Use try-except to avoid RuntimeError if C++ object is gone (though without WA_DeleteOnClose it should remain)
        try:
            if preview_window.isVisible(): 
                preview_window.close()
                preview_window.deleteLater()
        except RuntimeError:
            pass # Window already deleted

        self.status_label.setText("Ready to merge.")

    def _inject_new_image(self, path: str):
        """Adds a newly created image to the galleries and selection."""
        # 1. Update Data Models
        if hasattr(self, 'found_files') and isinstance(self.found_files, list):
            self.found_files.append(path)
        
        self.selected_files.append(path)
        
        # 2. Prepare Widget
        pixmap = QPixmap(path)
        if pixmap.isNull():
            return 

        # 3. Add to Top Gallery (Found)
        count = self.found_gallery_layout.count()
        width = self.found_gallery_scroll.viewport().width()
        item_w = self.thumbnail_size + 20
        cols = max(1, width // item_w) if width > 0 else 4
        
        row = count // cols
        col = count % cols
        
        card_top = self.create_card_widget(path, pixmap, is_selected=True)
        self.found_gallery_layout.addWidget(card_top, row, col, Qt.AlignLeft | Qt.AlignTop)
        
        if hasattr(self, 'path_to_label_map'):
            self.path_to_label_map[path] = card_top

        # 4. Add to Bottom Gallery (Selected)
        self.refresh_selected_panel()
        
        self.on_selection_changed()

    def on_merge_error(self, msg):
        self.cleanup_temp_file() # Clean up temp file on worker error
        self.on_selection_changed()
        self.status_label.setText("Failed.")
        QMessageBox.critical(self, "Error", msg)

    def collect(self, output_path: str) -> Dict[str, Any]:
        return {
            "direction": self.direction.currentText(),
            "input_path": self.selected_files,
            "output_path": output_path,
            "input_formats": [f.strip().lstrip('.') for f in SUPPORTED_IMG_FORMATS if f.strip()],
            "spacing": self.spacing.value(),
            "align_mode": self.align_mode.currentText(),
            "grid_size": (self.grid_rows.value(), self.grid_cols.value())
            if self.direction.currentText() == "grid" else None
        }

    def handle_direction_change(self, direction):
        # Update visibility of settings based on direction
        is_grid = direction == "grid"
        is_complex_stitch = direction in ["panorama", "stitch", "sequential"]
        
        self.grid_group.setVisible(is_grid)
        
        self.lbl_spacing.setVisible(not is_complex_stitch)
        self.spacing.setVisible(not is_complex_stitch)
        self.lbl_align.setVisible(not is_complex_stitch)
        self.align_mode.setVisible(not is_complex_stitch)
    
    def get_default_config(self) -> dict:
        return {
            "direction": "horizontal",
            "spacing": 10,
            "grid_size": [2, 2], 
            "scan_directory": "C:/path/to/images",
            "align_mode": "Default (Top/Center)"
        }

    def set_config(self, config: dict):
        try:
            direction = config.get("direction", "horizontal")
            if self.direction.findText(direction) != -1:
                self.direction.setCurrentText(direction)
            
            self.spacing.setValue(config.get("spacing", 10))

            align_mode = config.get("align_mode", "Default (Top/Center)")
            if self.align_mode.findText(align_mode) != -1:
                self.align_mode.setCurrentText(align_mode)
            
            grid_size = config.get("grid_size", [2, 2])
            if isinstance(grid_size, list) and len(grid_size) == 2:
                self.grid_rows.setValue(grid_size[0])
                self.grid_cols.setValue(grid_size[1])

            scan_dir = config.get("scan_directory")
            if scan_dir:
                self.scan_directory_path.setText(scan_dir)
                if os.path.isdir(scan_dir):
                    self.populate_scan_gallery(scan_dir)
            
            print(f"MergeTab configuration loaded.")
            
        except Exception as e:
            print(f"Error applying MergeTab config: {e}")
            QMessageBox.warning(self, "Config Error", f"Failed to apply some settings: {e}")
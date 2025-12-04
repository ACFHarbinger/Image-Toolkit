import os
import cv2
import shutil
import tempfile

from typing import Dict, Any, Optional
from PySide6.QtGui import QPixmap, QAction, QImage
from PySide6.QtCore import (
    Qt,
    QTimer,
    QThread,
    Slot,
    QPoint,
    QEventLoop,
    QMetaObject,
    Signal,
    Q_ARG,
)
from PySide6.QtWidgets import (
    QMenu,
    QPushButton,
    QFormLayout,
    QApplication,
    QLineEdit,
    QFileDialog,
    QWidget,
    QLabel,
    QComboBox,
    QSpinBox,
    QGroupBox,
    QHBoxLayout,
    QVBoxLayout,
    QMessageBox,
    QGridLayout,
    QScrollArea,
)
from ...classes import AbstractClassTwoGalleries
from ...windows import ImagePreviewWindow
from ...components import ClickableLabel, MarqueeScrollArea
from ...helpers import MergeWorker, ImageScannerWorker
from ...styles.style import apply_shadow_effect, SHARED_BUTTON_STYLE
from backend.src.utils.definitions import SUPPORTED_IMG_FORMATS


class MergeTab(AbstractClassTwoGalleries):
    # --- RETAIN THE SIGNAL BRIDGE FOR SAFETY ---
    preview_ready = Signal(str)
    # ------------------------------------------

    def __init__(self):
        super().__init__()
        self.thumbnail_size = 150

        # --- State ---
        self.scanned_dir: str | None = None
        self.output_dir: str | None = None

        self.last_output_dir: str | None = None

        self.open_preview_windows: list[ImagePreviewWindow] = []

        self.current_scan_thread: QThread | None = None
        self.current_scan_worker: ImageScannerWorker | None = None
        self.current_merge_thread: QThread | None = None
        self.current_merge_worker: MergeWorker | None = None
        self.temp_file_path: Optional[str] = None

        # Keep references to threads that are cancelling so they don't get GC'd prematurely
        self._zombie_threads: list[QThread] = []

        self.pending_save_path: Optional[str] = None
        self._last_merged_pixmap: Optional[QPixmap] = None

        # --- UI Setup ---
        main_layout = QVBoxLayout(self)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; }")

        scroll_content = QWidget()
        content_layout = QVBoxLayout(scroll_content)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # === 1. Merge Targets Group (Inputs) ===
        target_group = QGroupBox("Input Configuration")
        target_layout = QFormLayout(target_group)
        v_input_group = QVBoxLayout()

        scan_dir_layout = QHBoxLayout()
        self.scan_directory_path = QLineEdit()
        self.scan_directory_path.setPlaceholderText(
            "Path to directory containing images for merging..."
        )
        self.scan_directory_path.returnPressed.connect(
            self.handle_scan_directory_return
        )

        btn_browse_scan = QPushButton("Browse Input...")
        btn_browse_scan.clicked.connect(self.browse_and_scan_directory)
        apply_shadow_effect(
            btn_browse_scan, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )

        scan_dir_layout.addWidget(self.scan_directory_path)
        scan_dir_layout.addWidget(btn_browse_scan)

        v_input_group.addLayout(scan_dir_layout)
        target_layout.addRow("Input path:", v_input_group)
        content_layout.addWidget(target_group)

        # === 1.5 Output Configuration ===
        output_group = QGroupBox("Output Configuration")
        output_layout = QFormLayout(output_group)

        out_dir_layout = QHBoxLayout()
        self.output_directory_path = QLineEdit()
        self.output_directory_path.setPlaceholderText(
            "(Optional) Select output folder. If empty, you will be prompted to save after merge."
        )
        self.output_directory_path.textChanged.connect(self._update_output_dir_state)

        btn_browse_out = QPushButton("Browse Output...")
        btn_browse_out.clicked.connect(self.browse_output_directory)
        apply_shadow_effect(
            btn_browse_out, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )

        out_dir_layout.addWidget(self.output_directory_path)
        out_dir_layout.addWidget(btn_browse_out)

        output_layout.addRow("Output Folder:", out_dir_layout)

        self.output_filename_input = QLineEdit()
        self.output_filename_input.setPlaceholderText(
            "merged_image (Extension added automatically)"
        )
        output_layout.addRow("Filename:", self.output_filename_input)

        content_layout.addWidget(output_group)

        # === 2. Merge Settings ===
        config_group = QGroupBox("Merge Settings")
        config_layout = QFormLayout(config_group)

        self.direction = QComboBox()
        self.direction.addItems(
            [
                "horizontal",
                "vertical",
                "grid",
                "panorama",
                "stitch",
                "sequential",
                "gif",
            ]
        )
        self.direction.currentTextChanged.connect(self.handle_direction_change)
        config_layout.addRow("Direction:", self.direction)

        self.lbl_spacing = QLabel("Spacing (px):")
        self.spacing = QSpinBox()
        self.spacing.setRange(0, 1000)
        self.spacing.setValue(10)
        config_layout.addRow(self.lbl_spacing, self.spacing)

        self.lbl_align = QLabel("Alignment/Resize:")
        self.align_mode = QComboBox()
        self.align_mode.addItems(
            [
                "Default (Top/Center)",
                "Align Top/Left",
                "Align Bottom/Right",
                "Center",
                "Scaled (Grow Smallest)",
                "Squish (Shrink Largest)",
            ]
        )
        config_layout.addRow(self.lbl_align, self.align_mode)

        self.lbl_duration = QLabel("Duration (ms/frame):")
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(10, 10000)
        self.duration_spin.setValue(500)
        self.duration_spin.setSingleStep(50)
        config_layout.addRow(self.lbl_duration, self.duration_spin)
        self.lbl_duration.hide()
        self.duration_spin.hide()

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
        self.found_gallery_scroll.selection_changed.connect(
            self.handle_marquee_selection
        )
        content_layout.addWidget(self.found_gallery_scroll, 1)

        if hasattr(self, "found_pagination_widget"):
            content_layout.addWidget(
                self.found_pagination_widget, 0, Qt.AlignmentFlag.AlignCenter
            )

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

        if hasattr(self, "selected_pagination_widget"):
            content_layout.addWidget(
                self.selected_pagination_widget, 0, Qt.AlignmentFlag.AlignCenter
            )

        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)

        # === 4. Action Buttons ===
        action_vbox = QVBoxLayout()

        btns_layout = QHBoxLayout()

        self.run_button = QPushButton("Run Merge")
        self.run_button.setStyleSheet(SHARED_BUTTON_STYLE)
        apply_shadow_effect(self.run_button, "#000000", 8, 0, 3)
        self.run_button.clicked.connect(self.start_merge)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setStyleSheet(
            """
            QPushButton { background-color: #c0392b; color: white; font-weight: bold; padding: 12px; border-radius: 8px; }
            QPushButton:hover { background-color: #e74c3c; }
        """
        )
        apply_shadow_effect(self.cancel_button, "#000000", 8, 0, 3)
        self.cancel_button.clicked.connect(self.cancel_merge)
        self.cancel_button.setVisible(False)

        btns_layout.addWidget(self.run_button)
        btns_layout.addWidget(self.cancel_button)

        action_vbox.addLayout(btns_layout)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet(
            "color: #b9bbbe; font-style: italic; padding: 10px;"
        )
        action_vbox.addWidget(self.status_label)
        main_layout.addLayout(action_vbox)

        self.on_selection_changed()
        self.handle_direction_change(self.direction.currentText())
        self.clear_galleries()

    # --- HELPER: RESET UI STATE ---
    def reset_ui_state(self):
        """Restores buttons to default 'Run' state and clears worker refs."""
        self.cancel_button.setVisible(False)
        self.run_button.setVisible(True)
        self.run_button.setEnabled(True)
        self.current_merge_worker = None
        self.current_merge_thread = None
        self.on_selection_changed()

    # --- CANCEL SLOT (FIXED) ---
    @Slot()
    def cancel_merge(self):
        """Interrupts the merge process safely without crashing thread."""
        self.status_label.setText("Cancelling...")

        thread_to_kill = self.current_merge_thread
        worker_to_kill = self.current_merge_worker

        if thread_to_kill:
            # 1. Disconnect signals to prevent callbacks (UI updates/popups)
            try:
                if worker_to_kill:
                    worker_to_kill.finished.disconnect()
                    worker_to_kill.error.disconnect()
                    worker_to_kill.progress.disconnect()
                # Disconnect all signals from the thread
                thread_to_kill.started.disconnect()
                thread_to_kill.finished.disconnect()
            except Exception:
                pass

            # 2. Tell thread to stop
            thread_to_kill.requestInterruption()
            thread_to_kill.quit()

            # 3. Handle deletion safely
            if thread_to_kill.isRunning():
                print("Merge thread running. Detaching to background cleanup.")
                self._zombie_threads.append(thread_to_kill)

                # Connect cleanup to the finished signal using the safe slot
                thread_to_kill.finished.connect(self._cleanup_zombie_thread)
            else:
                thread_to_kill.deleteLater()

        self.cleanup_temp_file()
        self.status_label.setText("Merge cancelled.")
        self.reset_ui_state()

    @Slot()
    def _cleanup_zombie_thread(self):
        """Removes a finished thread from the zombie list using sender()."""
        thread = self.sender()
        if thread:
            if thread in self._zombie_threads:
                self._zombie_threads.remove(thread)
            thread.deleteLater()

    # --- ABSTRACT IMPL ---
    def create_card_widget(
        self, path: str, pixmap: Optional[QPixmap], is_selected: bool
    ) -> QWidget:
        thumb_size = self.thumbnail_size
        clickable_label = ClickableLabel(path)
        clickable_label.setFixedSize(thumb_size + 10, thumb_size + 10)

        clickable_label.get_pixmap = lambda: img_label.pixmap()
        clickable_label.set_selected_style = lambda s: self._update_label_style(
            img_label, path, s
        )

        layout = QVBoxLayout(clickable_label)
        layout.setContentsMargins(0, 0, 0, 0)

        img_label = QLabel()
        img_label.setAlignment(Qt.AlignCenter)
        img_label.setFixedSize(thumb_size, thumb_size)
        layout.addWidget(img_label)

        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(
                thumb_size, thumb_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            img_label.setPixmap(scaled)
        else:
            img_label.setText("Loading...")
            img_label.setStyleSheet("color: #999; border: 1px dashed #666;")

        self._update_label_style(img_label, path, is_selected)

        clickable_label.path_double_clicked.connect(self.handle_full_image_preview)
        clickable_label.path_right_clicked.connect(self.show_image_context_menu)

        return clickable_label

    def update_card_pixmap(self, widget: QWidget, pixmap: Optional[QPixmap]):
        if not isinstance(widget, ClickableLabel):
            return

        img_label = widget.findChild(QLabel)
        if not img_label:
            return

        if pixmap and not pixmap.isNull():
            thumb_size = self.thumbnail_size
            scaled = pixmap.scaled(
                thumb_size, thumb_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            img_label.setPixmap(scaled)
            img_label.setText("")
        else:
            img_label.clear()
            img_label.setText("Loading...")

        is_selected = widget.path in self.selected_files
        self._update_label_style(img_label, widget.path, is_selected)

    def _update_label_style(self, label: QLabel, path: str, selected: bool):
        is_error = label.text() == "Error"
        is_loading = label.text() == "Loading..."

        if selected:
            if is_error:
                label.setStyleSheet(
                    "border: 3px solid #5865f2; background-color: #4f545c;"
                )
            else:
                label.setStyleSheet(
                    "border: 3px solid #5865f2; background-color: #36393f;"
                )
        else:
            if is_error:
                label.setStyleSheet(
                    "border: 1px solid #e74c3c; background-color: #4f545c;"
                )
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
        self.status_label.setText(
            "" if count < 2 else f"Ready to merge {count} images."
        )

    # --- INPUT LOGIC ---
    @Slot()
    def handle_scan_directory_return(self):
        d = self.scan_directory_path.text().strip()
        if d and os.path.isdir(d):
            self.populate_scan_gallery(d)
        else:
            QMessageBox.warning(
                self, "Invalid Path", "The entered path is not a valid directory."
            )

    @Slot()
    def browse_and_scan_directory(self):
        d = QFileDialog.getExistingDirectory(
            self, "Select Directory to Scan", self.last_browsed_dir
        )
        if d:
            self.scan_directory_path.setText(d)
            self.last_browsed_dir = d
            self.populate_scan_gallery(d)

    # --- OUTPUT LOGIC ---
    @Slot()
    def browse_output_directory(self):
        start_dir = (
            self.last_output_dir if self.last_output_dir else self.last_browsed_dir
        )
        d = QFileDialog.getExistingDirectory(self, "Select Output Directory", start_dir)
        if d:
            self.output_directory_path.setText(d)
            self.output_dir = d
            self.last_output_dir = d

    @Slot(str)
    def _update_output_dir_state(self, path: str):
        self.output_dir = path.strip() if path.strip() else None

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
        thread = QThread(self)  # Parent thread to self

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
            QMessageBox.information(
                self, "No Files", f"No supported images found in {self.scanned_dir}"
            )
            self.clear_galleries()
            return

        self.start_loading_thumbnails(sorted(paths))
        self.status_label.setText(f"Scan complete. Loaded {len(paths)} files.")

    # --- MERGING & PREVIEW ---
    @Slot(str)
    def handle_full_image_preview(self, image_path: str):
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

        window = ImagePreviewWindow(
            image_path=image_path,
            db_tab_ref=None,
            parent=self,
            all_paths=target_list,
            start_index=start_index,
        )
        window.path_changed.connect(self.update_preview_highlight)
        window.setAttribute(Qt.WA_DeleteOnClose)
        window.show()
        self.open_preview_windows.append(window)

    @Slot(str, str)
    def update_preview_highlight(self, old_path: str, new_path: str):
        is_closing = new_path == "WINDOW_CLOSED"
        old_card = self.path_to_label_map.get(old_path)
        if old_card:
            original_style = old_card.property("original_style")
            if original_style:
                old_card.setStyleSheet(original_style)
            else:
                self.update_card_style(old_card, old_path in self.selected_files)
            old_card.setProperty("original_style", None)

        if is_closing:
            sender_win = self.sender()
            if sender_win in self.open_preview_windows:
                self.open_preview_windows.remove(sender_win)
            return

        new_card = self.path_to_label_map.get(new_path)
        if new_card:
            self.update_card_style(new_card, new_path in self.selected_files)
            new_card.setProperty("original_style", new_card.styleSheet())
            new_card.setStyleSheet(
                f"{new_card.styleSheet().strip()}; border: 4px solid #3498db;"
            )

    @Slot(QPoint, str)
    def show_image_context_menu(self, global_pos: QPoint, path: str):
        menu = QMenu(self)
        view_action = QAction("View Full Size Preview", self)
        view_action.triggered.connect(lambda: self.handle_full_image_preview(path))
        menu.addAction(view_action)
        menu.addSeparator()

        copy_action = QAction("Copy Image to Clipboard", self)
        copy_action.triggered.connect(lambda: self._copy_image_path_to_clipboard(path))
        menu.addAction(copy_action)
        menu.addSeparator()

        is_selected = path in self.selected_files
        toggle_text = (
            "Deselect Image (Remove from Merge List)"
            if is_selected
            else "Select Image (Add to Merge List)"
        )
        toggle_action = QAction(toggle_text, self)
        toggle_action.triggered.connect(lambda: self.toggle_selection(path))
        menu.addAction(toggle_action)

        if is_selected:
            menu.addSeparator()
            move_up_action = QAction("⬆️ Move Up in Merge Order", self)
            move_up_action.triggered.connect(lambda: self._move_selected_image_up(path))
            menu.addAction(move_up_action)
            move_down_action = QAction("⬇️ Move Down in Merge Order", self)
            move_down_action.triggered.connect(
                lambda: self._move_selected_image_down(path)
            )
            menu.addAction(move_down_action)

        menu.addSeparator()
        delete_action = QAction("🗑️ Delete Image File (Permanent)", self)
        delete_action.triggered.connect(lambda: self.handle_delete_image(path))
        menu.addAction(delete_action)
        menu.exec(global_pos)

    def _copy_image_path_to_clipboard(self, path: str):
        if os.path.exists(path):
            try:
                img = QImage(path)
                if not img.isNull():
                    QApplication.clipboard().setImage(img)
                    self.status_label.setText(
                        f"Copied image to clipboard: {os.path.basename(path)}"
                    )
                else:
                    QMessageBox.warning(
                        self, "Copy Error", "Failed to load image for copying."
                    )
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Copy failed: {e}")

    def _move_selected_image_up(self, path: str):
        try:
            current_index = self.selected_files.index(path)
            if current_index > 0:
                (
                    self.selected_files[current_index],
                    self.selected_files[current_index - 1],
                ) = (
                    self.selected_files[current_index - 1],
                    self.selected_files[current_index],
                )
                self.refresh_selected_panel()
                self.on_selection_changed()
        except ValueError:
            pass

    def _move_selected_image_down(self, path: str):
        try:
            current_index = self.selected_files.index(path)
            if current_index < len(self.selected_files) - 1:
                (
                    self.selected_files[current_index],
                    self.selected_files[current_index + 1],
                ) = (
                    self.selected_files[current_index + 1],
                    self.selected_files[current_index],
                )
                self.refresh_selected_panel()
                self.on_selection_changed()
        except ValueError:
            pass

    def handle_delete_image(self, path: str):
        if (
            QMessageBox.question(
                self, "Delete", f"Permanently delete {os.path.basename(path)}?"
            )
            == QMessageBox.Yes
        ):
            try:
                os.remove(path)
                if hasattr(self, "found_files") and path in self.found_files:
                    self.found_files.remove(path)
                if hasattr(self, "selected_files") and path in self.selected_files:
                    self.selected_files.remove(path)
                if (
                    hasattr(self, "path_to_label_map")
                    and path in self.path_to_label_map
                ):
                    widget = self.path_to_label_map.pop(path)
                    widget.deleteLater()
                self.on_selection_changed()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    @Slot(str)
    def _cleanup_merge_worker_and_show_dialog(self, result_path: str):
        """
        Slot executed on the main thread ONLY. Cleans up thread references
        and then calls the final dialog method.
        """
        self.reset_ui_state()  # Restore buttons
        self.show_preview_and_confirm(result_path)

    def start_merge(self):
        if len(self.selected_files) < 2:
            QMessageBox.warning(self, "Invalid", "Select at least 2 images.")
            return

        # --- PATH CALCULATION ---
        temp_dir = tempfile.gettempdir()
        ext = ".gif" if self.direction.currentText() == "gif" else ".png"

        temp_filename = next(tempfile._get_candidate_names()) + ext
        target_path = os.path.join(temp_dir, temp_filename)
        self.temp_file_path = target_path

        self.pending_save_path = None
        if self.output_dir and os.path.isdir(self.output_dir):
            filename = self.output_filename_input.text().strip()
            if not filename:
                filename = next(tempfile._get_candidate_names())
            if not filename.lower().endswith(ext):
                filename += ext
            self.pending_save_path = os.path.join(self.output_dir, filename)

        # Worker config
        merge_config = self.collect(self.temp_file_path)

        self.run_button.setVisible(False)
        self.cancel_button.setVisible(True)
        self.status_label.setText("Merging...")

        if cv2.ocl.haveOpenCL():
            cv2.ocl.finish()

        worker = MergeWorker(merge_config)
        # --- CRITICAL FIX: Parent the QThread to self ---
        thread = QThread(self)
        # ------------------------------------------------

        self.current_merge_worker = worker
        self.current_merge_thread = thread
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.progress.connect(
            lambda c, t: self.status_label.setText(f"Merging {c}/{t}")
        )

        # Clear old connections if any
        try:
            worker.finished.disconnect()
        except:
            pass

        worker.finished.connect(thread.quit)
        worker.error.connect(self.on_merge_error)
        worker.error.connect(thread.quit)

        # Cleanup slot invocation
        def invoke_cleanup(path):
            QMetaObject.invokeMethod(
                self,
                "_cleanup_merge_worker_and_show_dialog",
                Qt.QueuedConnection,
                Q_ARG(str, path),
            )

        worker.finished.connect(invoke_cleanup)

        # Ensure worker is deleted when thread finishes
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        thread.start()

    def on_merge_done(self, path):
        self.on_selection_changed()
        self.status_label.setText("Done.")
        QMessageBox.information(self, "Success", f"Saved to {path}")

    def cleanup_temp_file(self):
        if self.temp_file_path and os.path.exists(self.temp_file_path):
            try:
                os.remove(self.temp_file_path)
            except Exception as e:
                print(f"Error cleaning up temp file: {e}")
        self.temp_file_path = None

    @Slot(str)
    def show_preview_and_confirm(self, result_path: str):
        # We assume self.reset_ui_state() was called by the cleanup wrapper

        if not os.path.exists(result_path):
            self.on_merge_error(f"Failed to create merge file at: {result_path}")
            return

        self.status_label.setText("Merge complete.")
        self._last_merged_pixmap = QPixmap(result_path)

        # 1. Show Preview Window
        preview_window = ImagePreviewWindow(
            image_path=result_path,
            db_tab_ref=None,
            parent=self,
            all_paths=[result_path],
            start_index=0,
        )
        preview_window.setWindowTitle("Merged Image Preview")
        preview_window.show()
        preview_window.activateWindow()

        # 2. Confirmation Dialog
        confirm = QMessageBox(self)
        confirm.setWindowTitle("Save Merged Image?")

        if self.pending_save_path:
            confirm.setText(
                f"Merge successful. Save to configured output?\n\n{self.pending_save_path}"
            )
            save_text = "Save"
        else:
            confirm.setText("Merge successful. Choose an action:")
            save_text = "Save As..."

        copy_btn = confirm.addButton(
            "Copy to Clipboard", QMessageBox.ButtonRole.ActionRole
        )
        save_btn = confirm.addButton(save_text, QMessageBox.ButtonRole.AcceptRole)
        save_add_btn = confirm.addButton(
            "Save & Add to Selection", QMessageBox.ButtonRole.AcceptRole
        )
        discard_btn = confirm.addButton(
            "Discard", QMessageBox.ButtonRole.DestructiveRole
        )
        confirm.addButton(QMessageBox.StandardButton.Cancel)

        confirm.exec()
        clicked = confirm.clickedButton()

        saved_final_path = None

        if clicked == copy_btn:
            if self._last_merged_pixmap:
                QApplication.clipboard().setPixmap(self._last_merged_pixmap)
            self.cleanup_temp_file()

        elif clicked == save_btn or clicked == save_add_btn:

            # CASE A: Pre-configured output path
            if self.pending_save_path:
                try:
                    if os.path.exists(self.pending_save_path):
                        overwrite = QMessageBox.question(
                            self,
                            "Overwrite?",
                            f"File already exists:\n{self.pending_save_path}\nOverwrite?",
                            QMessageBox.Yes | QMessageBox.No,
                        )
                        if overwrite != QMessageBox.Yes:
                            self.cleanup_temp_file()
                            return

                    shutil.move(result_path, self.pending_save_path)
                    saved_final_path = self.pending_save_path
                    self.temp_file_path = None
                    self.last_output_dir = os.path.dirname(saved_final_path)
                    QMessageBox.information(
                        self, "Success", f"Saved to {saved_final_path}"
                    )
                except Exception as e:
                    QMessageBox.critical(
                        self, "Save Error", f"Failed to move file: {e}"
                    )
                    self.cleanup_temp_file()

            # CASE B: No config, use File Dialog
            else:
                filter_str = (
                    "GIF (*.gif)"
                    if result_path.lower().endswith(".gif")
                    else "PNG (*.png)"
                )
                start_dir = (
                    self.last_output_dir
                    if self.last_output_dir
                    else self.last_browsed_dir
                )

                out, _ = QFileDialog.getSaveFileName(
                    self, "Save Merged Image", start_dir, filter_str
                )
                if out:
                    try:
                        shutil.move(result_path, out)
                        saved_final_path = out
                        self.temp_file_path = None
                        self.last_output_dir = os.path.dirname(out)
                        QMessageBox.information(self, "Success", f"Saved to {out}")
                    except Exception as e:
                        QMessageBox.critical(self, "Error", f"Move failed: {e}")
                        self.cleanup_temp_file()
                else:
                    self.cleanup_temp_file()

            if saved_final_path and clicked == save_add_btn:
                self._inject_new_image(saved_final_path)

        else:
            self.cleanup_temp_file()

        self._last_merged_pixmap = None
        if self.temp_file_path is None and not os.path.exists(result_path):
            preview_window.close()

        self.status_label.setText("Ready to merge.")

    def _inject_new_image(self, path: str):
        if hasattr(self, "found_files") and isinstance(self.found_files, list):
            self.found_files.append(path)
        self.selected_files.append(path)

        pixmap = QPixmap(path)
        if pixmap.isNull():
            return

        count = self.found_gallery_layout.count()
        width = self.found_gallery_scroll.viewport().width()
        cols = max(1, width // (self.thumbnail_size + 20)) if width > 0 else 4

        row = count // cols
        col = count % cols

        card_top = self.create_card_widget(path, pixmap, is_selected=True)
        self.found_gallery_layout.addWidget(
            card_top, row, col, Qt.AlignLeft | Qt.AlignTop
        )

        if hasattr(self, "path_to_label_map"):
            self.path_to_label_map[path] = card_top

        self.refresh_selected_panel()
        self.on_selection_changed()

    def on_merge_error(self, msg):
        self.cleanup_temp_file()
        self.on_selection_changed()
        self.reset_ui_state()  # Ensure cancel button is gone
        self.status_label.setText("Failed.")
        QMessageBox.critical(self, "Error", msg)

    def handle_direction_change(self, direction):
        is_grid = direction == "grid"
        is_complex = direction in ["panorama", "stitch", "sequential"]
        is_gif = direction == "gif"

        self.grid_group.setVisible(is_grid)
        self.lbl_spacing.setVisible(not (is_complex or is_gif))
        self.spacing.setVisible(not (is_complex or is_gif))
        self.lbl_align.setVisible(not (is_complex or is_gif))
        self.align_mode.setVisible(not (is_complex or is_gif))
        self.lbl_duration.setVisible(is_gif)
        self.duration_spin.setVisible(is_gif)

    def collect(self, output_path: str = "") -> Dict[str, Any]:
        return {
            "direction": self.direction.currentText(),
            "scan_directory": self.scan_directory_path.text().strip(),
            "input_path": self.selected_files,
            "output_path": output_path,
            "input_formats": [
                f.strip().lstrip(".") for f in SUPPORTED_IMG_FORMATS if f.strip()
            ],
            "spacing": self.spacing.value(),
            "align_mode": self.align_mode.currentText(),
            "grid_size": (
                (self.grid_rows.value(), self.grid_cols.value())
                if self.direction.currentText() == "grid"
                else None
            ),
            "duration": self.duration_spin.value(),
        }

    def get_default_config(self) -> dict:
        return {
            "direction": "horizontal",
            "spacing": 10,
            "grid_size": [2, 2],
            "scan_directory": "C:/path/to/images",
            "output_directory": "",
            "output_filename": "",
            "align_mode": "Default (Top/Center)",
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

            out_dir = config.get("output_directory")
            if out_dir:
                self.output_directory_path.setText(out_dir)
                self.output_dir = out_dir

            out_fname = config.get("output_filename")
            if out_fname:
                self.output_filename_input.setText(out_fname)

            print(f"MergeTab configuration loaded.")

        except Exception as e:
            print(f"Error applying MergeTab config: {e}")
            QMessageBox.warning(
                self, "Config Error", f"Failed to apply some settings: {e}"
            )

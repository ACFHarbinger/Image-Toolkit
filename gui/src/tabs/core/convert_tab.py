import os
import platform
import subprocess

from typing import Optional, List
from PySide6.QtWidgets import (
    QLineEdit,
    QPushButton,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    QCheckBox,
    QMessageBox,
    QLabel,
    QGroupBox,
    QScrollArea,
    QGridLayout,
    QProgressBar,
    QComboBox,
    QMenu,
    QSpinBox,
)
from PySide6.QtCore import Qt, Slot, QPoint
from PySide6.QtGui import QPixmap, QAction, QImage
from ...helpers import ConversionWorker
from ...windows import ImagePreviewWindow
from ...classes import AbstractClassTwoGalleries
from ...components import OptionalField, MarqueeScrollArea, ClickableLabel
from ...styles.style import apply_shadow_effect, SHARED_BUTTON_STYLE
from backend.src.utils.definitions import SUPPORTED_IMG_FORMATS, SUPPORTED_VIDEO_FORMATS


class ConvertTab(AbstractClassTwoGalleries):
    def __init__(self, dropdown=True):
        super().__init__()
        self.dropdown = dropdown
        self.worker = None
        self.open_preview_windows: List[ImagePreviewWindow] = []

        # --- UI Setup ---
        main_layout = QVBoxLayout(self)

        # Page Scroll Area
        page_scroll = QScrollArea()
        page_scroll.setWidgetResizable(True)
        page_scroll.setStyleSheet("QScrollArea { border: none; }")

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)

        # --- 1. Convert Targets Group ---
        target_group = QGroupBox("Convert Targets")
        target_layout = QFormLayout(target_group)
        v_input_group = QVBoxLayout()

        # Input path
        input_layout = QHBoxLayout()
        self.input_path = QLineEdit()
        self.input_path.setPlaceholderText(
            "Path to directory containing images for conversion..."
        )
        input_layout.addWidget(self.input_path)

        btn_browse_scan = QPushButton("Browse...")
        btn_browse_scan.clicked.connect(self.browse_directory_and_scan)
        apply_shadow_effect(
            btn_browse_scan, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        input_layout.addWidget(btn_browse_scan)

        v_input_group.addLayout(input_layout)
        target_layout.addRow("Input path:", v_input_group)
        content_layout.addWidget(target_group)

        # --- 2. Convert Settings Group ---
        settings_group = QGroupBox("Convert Settings")
        settings_layout = QFormLayout(settings_group)

        # Output format
        self.output_format_combo = QComboBox()
        self.output_format_combo.addItems(["--- Images ---"])
        formatted_formats = [f for f in SUPPORTED_IMG_FORMATS]
        self.output_format_combo.addItems(formatted_formats)

        self.output_format_combo.addItems(["--- Videos ---"])
        video_formats = [f.lstrip(".") for f in SUPPORTED_VIDEO_FORMATS]
        self.output_format_combo.addItems(video_formats)

        self.output_format_combo.setCurrentText("png")
        self.output_format_combo.currentTextChanged.connect(
            self.on_output_format_changed
        )
        settings_layout.addRow("Output format:", self.output_format_combo)

        # New Video Engine Selection
        self.engine_combo = QComboBox()
        self.engine_combo.addItems(["Auto (Recommended)", "FFmpeg", "MoviePy"])
        self.engine_combo.setToolTip("Select the engine used for video conversion.")
        self.engine_label = QLabel("Video Engine:")  # Keep ref to hide/show
        settings_layout.addRow(self.engine_label, self.engine_combo)

        # Output path and Filename Prefix (UPDATED LAYOUT)
        output_settings_container = QVBoxLayout()

        # Output Directory Path
        h_output_dir = QHBoxLayout()
        self.output_path = QLineEdit()
        self.output_path.setPlaceholderText(
            "Leave blank to save in the input directory"
        )
        btn_output = QPushButton("Browse...")
        btn_output.clicked.connect(self.browse_output)
        apply_shadow_effect(
            btn_output, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        h_output_dir.addWidget(self.output_path)
        h_output_dir.addWidget(btn_output)
        output_settings_container.addLayout(h_output_dir)

        # Output Filename Prefix (NEW)
        h_output_name = QHBoxLayout()
        self.output_filename_prefix = QLineEdit()
        self.output_filename_prefix.setPlaceholderText(
            "e.g. 'processed_' (Files will be named processed_1.png, processed_2.png...)"
        )
        h_output_name.addWidget(QLabel("Filename Prefix:"))
        h_output_name.addWidget(self.output_filename_prefix)
        output_settings_container.addLayout(h_output_name)

        output_path_container = QWidget()
        output_path_container.setLayout(output_settings_container)
        self.output_field = OptionalField(
            "Output Directory & Filename", output_path_container, start_open=False
        )
        settings_layout.addRow(self.output_field)

        # Input formats
        if self.dropdown:
            self.selected_formats = set()
            formats_layout = QVBoxLayout()
            btn_layout = QHBoxLayout()
            self.format_buttons = {}
            for fmt in SUPPORTED_IMG_FORMATS:
                self._add_format_button(fmt, btn_layout)
            formats_layout.addLayout(btn_layout)
            self.formats_layout_ref = (
                formats_layout  # Store ref to clear later if needed
            )
            self.format_btn_layout = btn_layout

            all_btn_layout = QHBoxLayout()
            self.btn_add_all = QPushButton("Add All")
            self.btn_add_all.setStyleSheet("background-color: green; color: white;")
            apply_shadow_effect(
                self.btn_add_all, color_hex="#000000", radius=8, x_offset=0, y_offset=3
            )
            self.btn_add_all.clicked.connect(self.add_all_formats)
            self.btn_remove_all = QPushButton("Remove All")
            self.btn_remove_all.setStyleSheet("background-color: red; color: white;")
            apply_shadow_effect(
                self.btn_remove_all,
                color_hex="#000000",
                radius=8,
                x_offset=0,
                y_offset=3,
            )
            self.btn_remove_all.clicked.connect(self.remove_all_formats)
            all_btn_layout.addWidget(self.btn_add_all)
            all_btn_layout.addWidget(self.btn_remove_all)
            formats_layout.addLayout(all_btn_layout)

            formats_container = QWidget()
            formats_container.setLayout(formats_layout)
            self.formats_field = OptionalField(
                "Input formats to filter", formats_container, start_open=False
            )
            settings_layout.addRow(self.formats_field)
        else:
            self.selected_formats = None
            self.input_formats = QLineEdit()
            self.input_formats.setPlaceholderText("e.g. .jpg .png .gif")
            settings_layout.addRow("Input formats (optional):", self.input_formats)

        self.delete_checkbox = QCheckBox("Delete original files after conversion")
        self.delete_checkbox.setStyleSheet(
            """
            QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #555; border-radius: 3px; background-color: #333; }
            QCheckBox::indicator:checked { background-color: #4CAF50; border: 1px solid #4CAF50; image: url(./src/gui/assets/check.png); }
        """
        )
        self.delete_checkbox.setChecked(False)
        settings_layout.addRow(self.delete_checkbox)

        content_layout.addWidget(settings_group)

        # --- 3. Aspect Ratio Group ---
        ar_group = QGroupBox("Aspect Ratio")
        ar_layout = QFormLayout(ar_group)

        self.enable_ar_checkbox = QCheckBox("Change Aspect Ratio")
        self.enable_ar_checkbox.setToolTip(
            "Enable to resize, crop, or pad images to a specific aspect ratio."
        )
        self.enable_ar_checkbox.toggled.connect(self.toggle_ar_controls)
        ar_layout.addRow(self.enable_ar_checkbox)

        # AR Controls
        ar_controls_layout = QHBoxLayout()

        # Mode Selection
        self.ar_mode_combo = QComboBox()
        self.ar_mode_combo.addItems(["Crop", "Pad", "Stretch"])
        self.ar_mode_combo.setToolTip(
            "Crop: Cuts the image to fit.\n"
            "Pad: Adds background bars (Letterbox).\n"
            "Stretch: Distorts image to fit."
        )
        ar_controls_layout.addWidget(QLabel("Mode:"))
        ar_controls_layout.addWidget(self.ar_mode_combo)

        # Preset Selection
        self.ar_combo = QComboBox()
        self.ar_combo.addItems(["16:9", "4:3", "1:1", "9:16", "3:2", "Custom"])
        self.ar_combo.currentTextChanged.connect(self.on_ar_combo_change)
        ar_controls_layout.addWidget(QLabel("Ratio:"))
        ar_controls_layout.addWidget(self.ar_combo)

        # Custom W/H
        self.ar_w = QSpinBox()
        self.ar_w.setRange(1, 99999)
        self.ar_w.setValue(16)
        self.ar_h = QSpinBox()
        self.ar_h.setRange(1, 99999)
        self.ar_h.setValue(9)

        self.ar_custom_container = QWidget()
        custom_layout = QHBoxLayout(self.ar_custom_container)
        custom_layout.setContentsMargins(0, 0, 0, 0)
        custom_layout.addWidget(QLabel("W:"))
        custom_layout.addWidget(self.ar_w)
        custom_layout.addWidget(QLabel("H:"))
        custom_layout.addWidget(self.ar_h)

        ar_controls_layout.addWidget(self.ar_custom_container)
        ar_controls_layout.addStretch()

        self.ar_controls_widget = QWidget()
        self.ar_controls_widget.setLayout(ar_controls_layout)
        self.ar_controls_widget.setEnabled(False)  # Start disabled
        self.ar_custom_container.setVisible(
            False
        )  # Start hidden (preset 16:9 selected)

        ar_layout.addRow(self.ar_controls_widget)
        content_layout.addWidget(ar_group)

        # --- 4. Galleries ---

        # Conversion Progress Bar
        self.convert_progress_bar = QProgressBar()
        self.convert_progress_bar.setTextVisible(True)
        self.convert_progress_bar.setAlignment(Qt.AlignCenter)
        self.convert_progress_bar.setStyleSheet(
            "QProgressBar { background-color: #36393f; color: white; border: 1px solid #4f545c; border-radius: 4px; padding: 2px; }"
            "QProgressBar::chunk { background-color: #5865f2; border-radius: 4px; }"
        )
        self.convert_progress_bar.setMinimum(0)
        self.convert_progress_bar.setMaximum(100)
        self.convert_progress_bar.setValue(0)
        self.convert_progress_bar.hide()
        content_layout.addWidget(self.convert_progress_bar)

        # Scan Progress Bar (Existing)
        self.scan_progress_bar = QProgressBar()
        self.scan_progress_bar.setTextVisible(False)
        self.scan_progress_bar.hide()
        content_layout.addWidget(self.scan_progress_bar)

        # Found Files (Top)
        self.found_gallery_scroll = MarqueeScrollArea()
        self.found_gallery_scroll.setWidgetResizable(True)
        self.found_gallery_scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }"
        )
        self.found_gallery_scroll.setMinimumHeight(600)

        self.gallery_widget = QWidget()
        self.gallery_widget.setStyleSheet("background-color: #2c2f33;")
        self.found_gallery_layout = QGridLayout(self.gallery_widget)
        self.found_gallery_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.found_gallery_scroll.setWidget(self.gallery_widget)

        # Connect Base logic
        self.found_gallery_scroll.selection_changed.connect(
            self.handle_marquee_selection
        )

        # Add shared search input (Lazy Search) for Found Gallery
        content_layout.addWidget(self.found_search_input)

        content_layout.addWidget(self.found_gallery_scroll, 1)

        # Add Pagination Widget (Found)
        if hasattr(self, "found_pagination_widget"):
            content_layout.addWidget(
                self.found_pagination_widget, 0, Qt.AlignmentFlag.AlignCenter
            )

        # Selected Files (Bottom)
        self.selected_gallery_scroll = MarqueeScrollArea()
        self.selected_gallery_scroll.setWidgetResizable(True)
        self.selected_gallery_scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }"
        )
        self.selected_gallery_scroll.setMinimumHeight(400)

        self.selected_widget = QWidget()
        self.selected_widget.setStyleSheet("background-color: #2c2f33;")
        self.selected_gallery_layout = QGridLayout(self.selected_widget)
        self.selected_gallery_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.selected_gallery_scroll.setWidget(self.selected_widget)
        content_layout.addWidget(self.selected_gallery_scroll, 1)

        # Add Pagination Widget (Selected)
        if hasattr(self, "selected_pagination_widget"):
            content_layout.addWidget(
                self.selected_pagination_widget, 0, Qt.AlignmentFlag.AlignCenter
            )

        content_layout.addStretch(1)

        # --- Buttons ---
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)

        self.btn_convert_all = QPushButton("Convert All in Directory")
        self.btn_convert_all.setStyleSheet(SHARED_BUTTON_STYLE)
        apply_shadow_effect(
            self.btn_convert_all, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        self.btn_convert_all.clicked.connect(
            lambda: self.start_conversion_worker(use_selection=False)
        )
        button_layout.addWidget(self.btn_convert_all)

        self.btn_convert_contents = QPushButton("Convert Selected Files (0)")
        self.btn_convert_contents.setStyleSheet(SHARED_BUTTON_STYLE)
        apply_shadow_effect(
            self.btn_convert_contents,
            color_hex="#000000",
            radius=8,
            x_offset=0,
            y_offset=3,
        )
        self.btn_convert_contents.clicked.connect(
            lambda: self.start_conversion_worker(use_selection=True)
        )
        button_layout.addWidget(self.btn_convert_contents)

        content_layout.addWidget(button_container)

        self.status_label = QLabel("Ready.")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet(
            "color: #666; font-style: italic; padding: 8px;"
        )
        content_layout.addWidget(self.status_label)

        page_scroll.setWidget(content_widget)
        main_layout.addWidget(page_scroll)

        # Initial Clear
        self.clear_galleries()

        # Trigger initial state
        self.on_output_format_changed(self.output_format_combo.currentText())

    def _add_format_button(self, fmt, layout):
        btn = QPushButton(fmt)
        btn.setCheckable(True)
        btn.setStyleSheet("QPushButton:hover { background-color: #3498db; }")
        apply_shadow_effect(btn, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        btn.clicked.connect(lambda checked, f=fmt: self.toggle_format(f, checked))
        layout.addWidget(btn)
        self.format_buttons[fmt] = btn

    @Slot(str)
    def on_output_format_changed(self, text: str):
        text = text.lower()
        vid_formats = [f.lstrip(".") for f in SUPPORTED_VIDEO_FORMATS]
        is_video = text in vid_formats or "videos" in text

        # 1. Toggle Engine Visibility
        self.engine_combo.setVisible(is_video)
        self.engine_label.setVisible(is_video)

        # 2. Update Input Formats Buttons (only if dropdown mode)
        if self.dropdown and hasattr(self, "format_btn_layout"):
            # Clear existing
            for btn in self.format_buttons.values():
                self.format_btn_layout.removeWidget(btn)
                btn.deleteLater()
            self.format_buttons.clear()
            self.selected_formats.clear()

            # Populate new
            target_formats = (
                SUPPORTED_VIDEO_FORMATS if is_video else SUPPORTED_IMG_FORMATS
            )
            # Helper to strip dots if needed, though IMG_FORMATS usually has no dots in definitions?
            # definitions.py: SUPPORTED_IMG_FORMATS = ["webp", ...] (no dots)
            # definitions.py: SUPPORTED_VIDEO_FORMATS = {".mp4", ...} (has dots)

            clean_formats = []
            if is_video:
                clean_formats = sorted([f.lstrip(".") for f in target_formats])
            else:
                clean_formats = target_formats

            for fmt in clean_formats:
                self._add_format_button(fmt, self.format_btn_layout)

    # --- IMPLEMENTING ABSTRACT METHODS ---

    def create_card_widget(
        self, path: str, pixmap: Optional[QPixmap], is_selected: bool
    ) -> QWidget:
        thumb_size = self.thumbnail_size
        card_wrapper = ClickableLabel(path)
        card_wrapper.setFixedSize(thumb_size + 10, thumb_size + 10)

        # Required for Base class to fetch pixmap later if needed
        card_wrapper.get_pixmap = lambda: img_label.pixmap()

        card_layout = QVBoxLayout(card_wrapper)
        card_layout.setContentsMargins(0, 0, 0, 0)

        img_label = QLabel()
        img_label.setAlignment(Qt.AlignCenter)
        img_label.setFixedSize(thumb_size, thumb_size)

        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(
                thumb_size, thumb_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            img_label.setPixmap(scaled)
        else:
            # Show loading state if pixmap is None
            if path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS)):
                img_label.setText("Loading...")
                img_label.setStyleSheet("color: #3498db; border: 2px dashed #3498db;")
            else:
                img_label.setText("Loading...")
                img_label.setStyleSheet("color: #999; border: 1px dashed #666;")

        card_layout.addWidget(img_label)
        card_wrapper.setLayout(card_layout)

        # Assign custom styling method for the Base class to call
        card_wrapper.set_selected_style = lambda selected: self._update_card_style(
            img_label, selected
        )

        # Apply initial style
        self._update_card_style(img_label, is_selected)

        # --- Connect Signals for Double Click and Context Menu ---
        card_wrapper.path_double_clicked.connect(self.handle_full_image_preview)
        card_wrapper.path_right_clicked.connect(self.show_image_context_menu)

        return card_wrapper

    def update_card_pixmap(self, widget: QWidget, pixmap: Optional[QPixmap]):
        """Lazy loading callback. Unloads image if pixmap is None."""
        if not isinstance(widget, ClickableLabel):
            return

        img_label = widget.findChild(QLabel)
        if not img_label:
            return

        if pixmap and not pixmap.isNull():
            # Robust conversion
            if isinstance(pixmap, QImage):
                pixmap = QPixmap.fromImage(pixmap)

            thumb_size = self.thumbnail_size
            scaled = pixmap.scaled(
                thumb_size, thumb_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            img_label.setPixmap(scaled)
            img_label.setText("")  # Clear 'Loading...' text
        else:
            img_label.clear()
            img_label.setText("Loading...")

        is_selected = widget.path in self.selected_files
        self._update_card_style(img_label, is_selected)

    def _update_card_style(self, img_label: QLabel, is_selected: bool):
        if is_selected:
            img_label.setStyleSheet(
                "border: 3px solid #5865f2; background-color: #36393f;"
            )
        else:
            if img_label.pixmap() and not img_label.pixmap().isNull():
                img_label.setStyleSheet(
                    "border: 1px solid #4f545c; background-color: #36393f;"
                )
            else:
                img_label.setStyleSheet("border: 1px dashed #666; color: #999;")

    def on_selection_changed(self):
        count = len(self.selected_files)
        self.btn_convert_contents.setText(f"Convert Selected Files ({count})")
        self.btn_convert_contents.setEnabled(count > 0)

    # --- INTERACTION HANDLERS ---

    @Slot(str)
    def handle_full_image_preview(self, image_path: str):
        if not os.path.exists(image_path):
            return

        if image_path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS)):
            try:
                if platform.system() == "Windows":
                    os.startfile(image_path)
                elif platform.system() == "Linux":
                    subprocess.Popen(
                        ["xdg-open", image_path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                else:
                    subprocess.Popen(
                        ["open", image_path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
            except Exception as e:
                QMessageBox.warning(
                    self, "Video Error", f"Could not launch video player: {e}"
                )
            return

        target_list = (
            self.found_files
            if hasattr(self, "found_files") and self.found_files
            else []
        )

        if image_path not in target_list:
            if hasattr(self, "selected_files") and image_path in self.selected_files:
                target_list = sorted(list(self.selected_files))
            else:
                target_list = [image_path]

        try:
            start_index = target_list.index(image_path)
        except ValueError:
            start_index = 0

        preview = ImagePreviewWindow(
            image_path=image_path,
            db_tab_ref=None,
            parent=self,
            all_paths=target_list,
            start_index=start_index,
        )
        preview.setAttribute(Qt.WA_DeleteOnClose)
        preview.show()
        self.open_preview_windows.append(preview)

    @Slot(QPoint, str)
    def show_image_context_menu(self, global_pos: QPoint, path: str):
        menu = QMenu(self)

        view_action = QAction("View Full Size Preview", self)
        view_action.triggered.connect(lambda: self.handle_full_image_preview(path))
        menu.addAction(view_action)

        menu.addSeparator()

        is_selected = path in self.selected_files
        toggle_text = (
            "Deselect image from conversion"
            if is_selected
            else "Select image to convert"
        )
        toggle_action = QAction(toggle_text, self)
        toggle_action.triggered.connect(lambda: self.toggle_selection(path))
        menu.addAction(toggle_action)

        menu.addSeparator()

        delete_action = QAction("🗑️ Delete Image File (Permanent)", self)
        delete_action.triggered.connect(lambda: self.handle_delete_image(path))
        menu.addAction(delete_action)

        menu.exec(global_pos)

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

    # --- INPUT LOGIC ---

    @Slot()
    def browse_directory_and_scan(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select input directory", self.last_browsed_dir
        )
        if directory:
            self.input_path.setText(directory)
            self.last_browsed_dir = directory
            self.scan_directory_visual()

    @Slot()
    def browse_output(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select output directory", ""
        )
        if directory:
            self.output_path.setText(directory)

    def collect_paths(self) -> list[str]:
        p = self.input_path.text().strip()
        if not p or not os.path.isdir(p):
            return []

        # Determine strict filter list
        if self.dropdown and self.selected_formats:
            input_formats = list(self.selected_formats)
        elif (
            not self.dropdown
            and hasattr(self, "input_formats")
            and self.input_formats.text().strip()
        ):
            input_formats = self.join_list_str(self.input_formats.text().strip())
        else:
            # Fallback: All supported formats (Images + Videos)
            vid_formats = [f.lstrip(".").lower() for f in SUPPORTED_VIDEO_FORMATS]
            img_formats = [f.lower() for f in SUPPORTED_IMG_FORMATS]
            input_formats = vid_formats + img_formats

        paths = []
        for root, _, files in os.walk(p):
            for file in files:
                file_ext = os.path.splitext(file)[1].lstrip(".").lower()
                if not input_formats or file_ext in input_formats:
                    paths.append(os.path.join(root, file))
        return paths

    @Slot()
    def scan_directory_visual(self):
        paths = self.collect_paths()
        if not paths:
            QMessageBox.information(self, "No Files", "No matching files found.")
            self.clear_galleries()
            return

        self.start_loading_thumbnails(sorted(paths))

    # --- FORMAT BUTTONS ---
    @Slot(str, bool)
    def toggle_format(self, fmt, checked):
        btn = self.format_buttons[fmt]
        if checked:
            self.selected_formats.add(fmt)
            btn.setStyleSheet(
                """
                QPushButton:checked { background-color: #3320b5; color: white; }
                QPushButton:hover { background-color: #00838a; }
            """
            )
            apply_shadow_effect(
                btn, color_hex="#000000", radius=8, x_offset=0, y_offset=3
            )
        else:
            self.selected_formats.discard(fmt)
            btn.setStyleSheet("QPushButton:hover { background-color: #3498db; }")
            apply_shadow_effect(
                btn, color_hex="#000000", radius=8, x_offset=0, y_offset=3
            )

    @Slot()
    def add_all_formats(self):
        for fmt, btn in self.format_buttons.items():
            btn.setChecked(True)
            self.toggle_format(fmt, True)

    @Slot()
    def remove_all_formats(self):
        for fmt, btn in self.format_buttons.items():
            btn.setChecked(False)
            self.toggle_format(fmt, False)

    # --- ASPECT RATIO LOGIC ---

    @Slot(bool)
    def toggle_ar_controls(self, checked: bool):
        self.ar_controls_widget.setEnabled(checked)

    @Slot(str)
    def on_ar_combo_change(self, text):
        if text == "Custom":
            self.ar_custom_container.setVisible(True)
        else:
            self.ar_custom_container.setVisible(False)
            try:
                if ":" in text:
                    w, h = map(int, text.split(":"))
                    self.ar_w.setValue(w)
                    self.ar_h.setValue(h)
            except:
                pass

    # --- CONVERSION WORKER ---

    @Slot(bool)
    def start_conversion_worker(self, use_selection: bool = False):
        if self.worker and self.worker.isRunning():
            self.cancel_conversion()
            return

        p = self.input_path.text().strip()
        if not p or not os.path.isdir(p):
            QMessageBox.warning(self, "Invalid", "Please select a valid directory.")
            return

        files_for_conversion = (
            self.selected_files if use_selection else self.collect_paths()
        )

        if not files_for_conversion:
            QMessageBox.warning(self, "No Files", "No files to convert.")
            return

        config = self.collect()
        config["files_to_convert"] = files_for_conversion

        # UI Updates
        self.btn_convert_all.setEnabled(False)
        self.btn_convert_contents.setEnabled(False)

        button_to_cancel = (
            self.btn_convert_contents if use_selection else self.btn_convert_all
        )
        button_to_cancel.setEnabled(True)
        button_to_cancel.setText("Cancel Conversion")
        button_to_cancel.setStyleSheet(
            """
            QPushButton { background-color: #cc3333; color: white; font-weight: bold; }
        """
        )

        self.status_label.setText(f"Converting {len(files_for_conversion)} files...")
        self.convert_progress_bar.show()  # Show the new progress bar

        self.worker = ConversionWorker(config)
        self.worker.finished.connect(self.on_conversion_done)
        self.worker.error.connect(self.on_conversion_error)
        self.worker.progress_update.connect(self.update_progress_bar)
        self.worker.start()

    def cancel_conversion(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait()
            self.on_conversion_done(0, "**Conversion cancelled**")
            self.worker = None

    @Slot(int)  # Accepts an integer for percentage
    def update_progress_bar(self, percentage: int):
        self.convert_progress_bar.setValue(percentage)
        self.status_label.setText(f"Converting... {percentage}% complete")

    @Slot(int, str)
    def on_conversion_done(self, count, msg):
        # Reset UI elements
        self.btn_convert_all.setEnabled(True)
        self.btn_convert_all.setText("Convert All in Directory")
        self.btn_convert_all.setStyleSheet(SHARED_BUTTON_STYLE)

        self.on_selection_changed()
        self.btn_convert_contents.setStyleSheet(SHARED_BUTTON_STYLE)

        self.convert_progress_bar.hide()
        self.convert_progress_bar.setValue(0)  # Reset value
        self.status_label.setText(f"{msg}")
        self.worker = None
        if "cancelled" not in msg.lower():
            QMessageBox.information(self, "Complete", msg)

    @Slot(str)
    def on_conversion_error(self, msg):
        self.on_conversion_done(0, msg)
        QMessageBox.critical(self, "Error", msg)

    def collect(self) -> dict:
        input_formats = (
            list(self.selected_formats)
            if self.dropdown and self.selected_formats
            else (
                self.join_list_str(self.input_formats.text().strip())
                if not self.dropdown and hasattr(self, "input_formats")
                else SUPPORTED_IMG_FORMATS
            )
        )

        # Calculate Aspect Ratio
        ar_val = None
        ar_mode = "crop"  # default
        ar_w = None
        ar_h = None

        if self.enable_ar_checkbox.isChecked():
            try:
                w = self.ar_w.value()
                h = self.ar_h.value()
                if h != 0:
                    ar_val = w / h
                    ar_w = w
                    ar_h = h
                    ar_mode = self.ar_mode_combo.currentText().lower()
            except:
                pass

        return {
            "output_format": self.output_format_combo.currentText().lower(),
            "input_path": self.input_path.text().strip(),
            "output_path": self.output_path.text().strip() or None,
            "output_filename_prefix": self.output_filename_prefix.text().strip(),
            "input_formats": [
                f.strip().lstrip(".").lower() for f in input_formats if f.strip()
            ],
            "delete_original": self.delete_checkbox.isChecked(),
            "aspect_ratio": ar_val,
            "aspect_ratio_w": ar_w,
            "aspect_ratio_h": ar_h,
            "aspect_ratio_mode": ar_mode,
            "video_engine": self.engine_combo.currentText().split(" ")[0].lower(),
        }

    def get_default_config(self) -> dict:
        """Returns the default configuration dictionary for the ConvertTab."""
        formats = SUPPORTED_IMG_FORMATS if self.dropdown else "jpg png"
        return {
            "input_path": "",
            "output_format": "png",
            "output_path": "",
            "output_filename_prefix": "",
            "input_formats": formats,
            "delete_original": False,
            "aspect_ratio": None,
            "aspect_ratio_mode": "crop",
            "video_engine": "auto",
        }

    def set_config(self, config: dict):
        """Applies the configuration dictionary to the ConvertTab UI elements."""
        try:
            # 1. Paths
            input_path = config.get("input_path", "")
            self.input_path.setText(input_path)
            output_path = config.get("output_path", "")
            self.output_path.setText(output_path)

            # Set Filename Prefix (NEW)
            self.output_filename_prefix.setText(
                config.get("output_filename_prefix", "")
            )

            if output_path or config.get("output_filename_prefix"):
                self.output_field.set_open(True)

            # 2. Output Format
            output_fmt = config.get("output_format", "png")
            index = self.output_format_combo.findText(output_fmt.lower())
            if index != -1:
                self.output_format_combo.setCurrentIndex(index)

            # 3. Input Formats
            formats = config.get("input_formats", [])
            if self.dropdown:
                self.remove_all_formats()
                for fmt in formats:
                    if fmt in self.format_buttons:
                        self.format_buttons[fmt].setChecked(True)
                        self.toggle_format(fmt, True)
                if formats and len(formats) < len(SUPPORTED_IMG_FORMATS):
                    self.formats_field.set_open(True)
            elif hasattr(self, "input_formats"):
                self.input_formats.setText(" ".join(formats))
                if formats:
                    self.formats_field.set_open(True)

            # 4. Delete Checkbox
            self.delete_checkbox.setChecked(config.get("delete_original", False))

            # 5. Aspect Ratio
            aspect_ratio = config.get("aspect_ratio")
            ar_mode = config.get("aspect_ratio_mode", "crop")

            if aspect_ratio:
                self.enable_ar_checkbox.setChecked(True)

                # Set Mode
                mode_index = self.ar_mode_combo.findText(ar_mode.capitalize())
                if mode_index != -1:
                    self.ar_mode_combo.setCurrentIndex(mode_index)

                # Set Ratio
                ratios = {
                    "16:9": 16 / 9,
                    "4:3": 4 / 3,
                    "1:1": 1.0,
                    "9:16": 9 / 16,
                    "3:2": 3 / 2,
                }
                matched = False
                for label, val in ratios.items():
                    if abs(aspect_ratio - val) < 0.01:
                        self.ar_combo.setCurrentText(label)
                        matched = True
                        break

                if not matched:
                    self.ar_combo.setCurrentText("Custom")
            else:
                self.enable_ar_checkbox.setChecked(False)

            # 6. Load data
            if os.path.isdir(input_path):
                self.scan_directory_visual()

            print("ConvertTab configuration loaded.")
        except Exception as e:
            print(f"Error applying ConvertTab config: {e}")
            QMessageBox.warning(
                self, "Config Error", f"Failed to apply some settings: {e}"
            )

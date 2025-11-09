# gui/tabs/ImageCrawlTab.py
import os

from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLineEdit, QPushButton, QFileDialog, QLabel,
    QGroupBox, QCheckBox, QComboBox, QMessageBox,
    QFormLayout, QHBoxLayout, QVBoxLayout, QProgressBar, QWidget
)
from .base_tab import BaseTab
from ..helpers import ImageCrawlWorker
from ..components import OptionalField
from ..styles import apply_shadow_effect


class ImageCrawlTab(BaseTab):
    def __init__(self, dropdown=True):
        super().__init__()
        self.dropdown = dropdown
        self.worker = None
        path = Path(os.getcwd())
        parts = path.parts
        self.last_browsed_download_dir = os.path.join(Path(*parts[:parts.index('Image-Toolkit') + 1]), 'data', 'tmp')
        self.last_browsed_screenshot_dir = self.last_browsed_download_dir # Keep this initialized

        main_layout = QVBoxLayout(self)

        # --- Crawler Settings Group ---
        crawl_group = QGroupBox("Web Crawler Settings")
        crawl_group.setStyleSheet("""
            QGroupBox { 
                /* Removed specific dark background color for the group box itself */
                border: 1px solid #4f545c; 
                border-radius: 8px;
                margin-top: 10px;
            }
            QGroupBox::title { 
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 4px 10px;
                color: white; /* Text white for contrast */
                border-radius: 4px;
            }
        """)

        form_layout = QFormLayout()
        form_layout.setContentsMargins(10, 20, 10, 10)
        form_layout.setSpacing(15)

        # Target URL
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com/gallery?page=1")
        form_layout.addRow("Target URL:", self.url_input)
        
        # --- NEW: URL Replacement Fields ---
        self.replace_str_input = QLineEdit()
        self.replace_str_input.setPlaceholderText("e.g., page=1 (optional)")
        form_layout.addRow("String to Replace:", self.replace_str_input)
        
        self.replacements_input = QLineEdit()
        self.replacements_input.setPlaceholderText("e.g., page=2, page=3, page=4 (comma-separated)")
        form_layout.addRow("Replacements:", self.replacements_input)
        # --- END NEW ---

        # Download Directory
        download_dir_layout = QHBoxLayout()
        self.download_dir_path = QLineEdit()
        self.download_dir_path.setText(self.last_browsed_download_dir)
        btn_browse_download = QPushButton("Browse...")
        btn_browse_download.clicked.connect(self.browse_download_directory)
        btn_browse_download.setStyleSheet("""
            QPushButton { background-color: #4f545c; padding: 6px 12px; }
            QPushButton:hover { background-color: #5865f2; }
        """)
        apply_shadow_effect(btn_browse_download, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        download_dir_layout.addWidget(self.download_dir_path)
        download_dir_layout.addWidget(btn_browse_download)
        form_layout.addRow("Download Dir:", download_dir_layout)
        
        # Screenshot Directory
        screenshot_dir_layout = QHBoxLayout()
        self.screenshot_dir_path = QLineEdit()
        self.screenshot_dir_path.setPlaceholderText("Optional: directory for screenshots (None)")
        btn_browse_screenshot = QPushButton("Browse...")
        btn_browse_screenshot.clicked.connect(self.browse_screenshot_directory)
        btn_browse_screenshot.setStyleSheet("""
            QPushButton { background-color: #4f545c; padding: 6px 12px; }
            QPushButton:hover { background-color: #5865f2; }
        """)
        apply_shadow_effect(btn_browse_screenshot, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        screenshot_dir_layout.addWidget(self.screenshot_dir_path)
        screenshot_dir_layout.addWidget(btn_browse_screenshot)
        
        screenshot_container = QWidget()
        screenshot_container.setLayout(screenshot_dir_layout)
        
        self.screenshot_field = OptionalField("Screenshot Dir", screenshot_container, start_open=False)
        form_layout.addRow(self.screenshot_field) 

        # Browser
        self.browser_combo = QComboBox()
        self.browser_combo.addItems(["chrome", "firefox", "edge", "brave"])
        self.browser_combo.setCurrentText("brave")
        form_layout.addRow("Browser:", self.browser_combo)

        # Headless
        self.headless_checkbox = QCheckBox("Run in headless mode")
        self.headless_checkbox.setChecked(True)
        self.headless_checkbox.setStyleSheet("""
            QCheckBox::indicator {
                width: 16px; height: 16px; border: 1px solid #555;
                border-radius: 3px; background-color: #333;
            }
            QCheckBox::indicator:checked {
                background-color: #4CAF50; border: 1px solid #4CAF50;
            }
        """)
        form_layout.addRow("", self.headless_checkbox)
        
        # Image Skip Count
        skip_layout = QHBoxLayout()
        self.skip_first_input = QLineEdit("0")
        self.skip_first_input.setFixedWidth(50)
        self.skip_first_input.setAlignment(Qt.AlignCenter)
        self.skip_last_input = QLineEdit("9")
        self.skip_last_input.setFixedWidth(50)
        self.skip_last_input.setAlignment(Qt.AlignCenter)

        skip_layout.addWidget(QLabel("Skip First:"))
        skip_layout.addWidget(self.skip_first_input)
        skip_layout.addSpacing(20)
        skip_layout.addWidget(QLabel("Skip Last:"))
        skip_layout.addWidget(self.skip_last_input)
        skip_layout.addStretch()
        
        form_layout.addRow("Image Skip Count:", skip_layout)

        crawl_group.setLayout(form_layout)
        main_layout.addWidget(crawl_group)

        # --- Progress & Status ---
        self.status_label = QLabel("Ready.")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #aaa; font-style: italic; padding: 8px;")
        main_layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.hide()
        main_layout.addWidget(self.progress_bar)

        # --- Run/Cancel Button Container ---
        self.button_container = QWidget()
        self.button_layout = QVBoxLayout(self.button_container)
        self.button_layout.setContentsMargins(0, 0, 0, 0)

        # Run Button
        self.run_button = QPushButton("Run Crawler")
        self.run_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #667eea, stop:1 #764ba2);
                color: white; font-weight: bold; font-size: 16px;
                padding: 14px; border-radius: 10px; min-height: 44px;
            }
            QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #764ba2, stop:1 #667eea); }
            QPushButton:disabled { background: #718096; }
        """)
        apply_shadow_effect(self.run_button, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.run_button.clicked.connect(self.start_crawl)
        self.button_layout.addWidget(self.run_button, 0, Qt.AlignBottom)

        # Cancel Button
        self.cancel_button = QPushButton("Cancel Crawl")
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #cc3333; /* Red color for cancellation */
                color: white; font-weight: bold; font-size: 16px;
                padding: 14px; border-radius: 10px; min-height: 44px;
            }
            QPushButton:hover { background-color: #ff4444; }
        """)
        apply_shadow_effect(self.cancel_button, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.cancel_button.clicked.connect(self.cancel_crawl)
        self.cancel_button.hide()
        self.button_layout.addWidget(self.cancel_button, 0, Qt.AlignBottom)

        main_layout.addWidget(self.button_container)

        main_layout.addStretch(1)
        self.setLayout(main_layout)

    def browse_download_directory(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select Download Directory", self.last_browsed_download_dir
        )
        if directory:
            self.last_browsed_download_dir = directory
            self.download_dir_path.setText(directory)

    def browse_screenshot_directory(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select Screenshot Directory", self.last_browsed_screenshot_dir
        )
        if directory:
            self.last_browsed_screenshot_dir = directory
            self.screenshot_dir_path.setText(directory)

    def start_crawl(self):
        url = self.url_input.text().strip()
        download_dir = self.download_dir_path.text().strip()
        screenshot_dir = self.screenshot_dir_path.text().strip()
        skip_first = self.skip_first_input.text().strip()
        skip_last = self.skip_last_input.text().strip()
        
        # --- NEW: Get replacement data ---
        replace_str = self.replace_str_input.text().strip() or None
        replacements_str = self.replacements_input.text().strip()
        replacements_list = [r.strip() for r in replacements_str.split(',')] if replacements_str else None

        if not url:
            QMessageBox.warning(self, "Missing URL", "Please enter a target URL.")
            return
        if not url.startswith(("http://", "https://")):
            QMessageBox.warning(self, "Invalid URL", "URL must start with http:// or https://")
            return
        if not download_dir:
            QMessageBox.warning(self, "Missing Path", "Please select a download directory.")
            return
            
        if replace_str and not replacements_list:
            QMessageBox.warning(self, "Invalid Input", "You provided a 'String to Replace' but no 'Replacements'.")
            return
        if not replace_str and replacements_list:
            QMessageBox.warning(self, "Invalid Input", "You provided 'Replacements' but no 'String to Replace'.")
            return
        if replace_str and url.find(replace_str) == -1:
            QMessageBox.warning(self, "Invalid Input", f"The 'String to Replace' ('{replace_str}') was not found in the Target URL.")
            return

        try:
            skip_first = int(skip_first)
            skip_last = int(skip_last)
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Skip First and Skip Last must be integers.")
            return

        config = {
            "url": url,
            "download_dir": download_dir,
            "screenshot_dir": screenshot_dir if screenshot_dir else None,
            "headless": self.headless_checkbox.isChecked(),
            "browser": self.browser_combo.currentText(),
            "skip_first": skip_first,
            "skip_last": skip_last,
            "replace_str": replace_str, # NEW
            "replacements": replacements_list, # NEW
        }

        # UI: Show working state
        self.run_button.hide() 
        self.cancel_button.show() 
        self.status_label.setText("Initializing browser...")
        self.progress_bar.show()
        self.progress_bar.setRange(0, 0) # Indeterminate progress

        # Start worker
        self.worker = ImageCrawlWorker(config)
        self.worker.status.connect(self.status_label.setText)
        # self.worker.progress.connect(...) # Removed, using indeterminate bar
        self.worker.finished.connect(self.on_crawl_done)
        self.worker.error.connect(self.on_crawl_error)
        self.worker.start()

    def cancel_crawl(self):
        """Attempts to stop the QThread worker."""
        if self.worker and self.worker.isRunning():
            self.worker.terminate() 
            self.on_crawl_done(0, "Crawl **cancelled** by user.")
            QMessageBox.information(self, "Cancelled", "The image crawl has been stopped.")

    def on_crawl_done(self, count, message):
        self.run_button.show() 
        self.cancel_button.hide() 
        self.run_button.setText("Run Crawler")
        self.progress_bar.hide()
        self.status_label.setText(message)
        
        if "cancelled" not in message.lower():
            QMessageBox.information(self, "Success", f"{message}\n\nSaved to:\n{self.download_dir_path.text()}")

    def on_crawl_error(self, msg):
        self.run_button.show() 
        self.cancel_button.hide() 
        self.run_button.setText("Run Crawler")
        self.progress_bar.hide()
        self.status_label.setText("Failed.")
        QMessageBox.critical(self, "Error", msg)

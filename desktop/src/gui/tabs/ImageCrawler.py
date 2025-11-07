# gui/tabs/ImageCrawlTab.py
import os

from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLineEdit, QPushButton, QFileDialog, QLabel,
    QGroupBox, QCheckBox, QComboBox, QMessageBox,
    QFormLayout, QHBoxLayout, QVBoxLayout, QProgressBar, QWidget
)
from .BaseTab import BaseTab
from ..helpers import ImageCrawlWorker
from ..components import OptionalField


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
                background-color: #2c2f33; 
                border: 1px solid #4f545c; 
                border-radius: 8px;
                margin-top: 10px;
            }
            QGroupBox::title { 
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 4px 10px;
                background-color: #5865f2;
                color: white;
                border-radius: 4px;
            }
        """)

        form_layout = QFormLayout()
        form_layout.setContentsMargins(10, 20, 10, 10)
        form_layout.setSpacing(15)

        # Target URL
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com/gallery")
        form_layout.addRow("Target URL:", self.url_input)

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
        download_dir_layout.addWidget(self.download_dir_path)
        download_dir_layout.addWidget(btn_browse_download)
        form_layout.addRow("Download Dir:", download_dir_layout)
        
        # --- MODIFIED: Screenshot Directory as OptionalField ---
        screenshot_dir_layout = QHBoxLayout()
        self.screenshot_dir_path = QLineEdit()
        self.screenshot_dir_path.setPlaceholderText("Optional: directory for screenshots (None)")
        btn_browse_screenshot = QPushButton("Browse...")
        btn_browse_screenshot.clicked.connect(self.browse_screenshot_directory)
        btn_browse_screenshot.setStyleSheet("""
            QPushButton { background-color: #4f545c; padding: 6px 12px; }
            QPushButton:hover { background-color: #5865f2; }
        """)
        screenshot_dir_layout.addWidget(self.screenshot_dir_path)
        screenshot_dir_layout.addWidget(btn_browse_screenshot)
        
        screenshot_container = QWidget()
        screenshot_container.setLayout(screenshot_dir_layout)
        
        # Wrap the container in OptionalField
        self.screenshot_field = OptionalField("Screenshot Dir", screenshot_container, start_open=False)
        form_layout.addRow(self.screenshot_field) # Add the optional field to the form

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
        
        # --- Skip First/Last Images ---
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

        # Run Button (Default State)
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
        self.run_button.clicked.connect(self.start_crawl)
        self.button_layout.addWidget(self.run_button, 0, Qt.AlignBottom)

        # Cancel Button (Hidden by default)
        self.cancel_button = QPushButton("Cancel Crawl")
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #cc3333; /* Red color for cancellation */
                color: white; font-weight: bold; font-size: 16px;
                padding: 14px; border-radius: 10px; min-height: 44px;
            }
            QPushButton:hover { background-color: #ff4444; }
        """)
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

    # --- NEW METHOD: Browse Screenshot Directory ---
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

        if not url:
            QMessageBox.warning(self, "Missing URL", "Please enter a target URL.")
            return
        if not url.startswith(("http://", "https://")):
            QMessageBox.warning(self, "Invalid URL", "URL must start with http:// or https://")
            return
        if not download_dir:
            QMessageBox.warning(self, "Missing Path", "Please select a download directory.")
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
            "screenshot_dir": screenshot_dir if screenshot_dir else None,  # Pass None if empty
            "headless": self.headless_checkbox.isChecked(),
            "browser": self.browser_combo.currentText(),
            "skip_first": skip_first,
            "skip_last": skip_last,
        }

        # UI: Show working state
        self.run_button.hide() # Hide Run button
        self.cancel_button.show() # Show Cancel button
        self.status_label.setText("Initializing browser...")
        self.progress_bar.show()
        self.progress_bar.setRange(0, 0)

        # Start worker
        self.worker = ImageCrawlWorker(config)
        self.worker.status.connect(self.status_label.setText)
        self.worker.progress.connect(self.progress_bar.setMaximum if self.progress_bar.maximum() == 0 else lambda c, t: None)
        self.worker.progress.connect(lambda c, t: self.progress_bar.setValue(c))
        self.worker.finished.connect(self.on_crawl_done)
        self.worker.error.connect(self.on_crawl_error)
        self.worker.start()

    def cancel_crawl(self):
        """Attempts to stop the QThread worker."""
        if self.worker and self.worker.isRunning():
            # Use terminate() if quit() is not sufficient to stop the blocking web crawling operation
            self.worker.terminate() 
            self.on_crawl_done(0, "Crawl **cancelled** by user.")
            QMessageBox.information(self, "Cancelled", "The image crawl has been stopped.")

    def on_crawl_done(self, count, message):
        self.run_button.show() # Show Run button
        self.cancel_button.hide() # Hide Cancel button
        self.run_button.setText("Run Crawler")
        self.progress_bar.hide()
        self.status_label.setText(message)
        
        # Only show the success/info box if it wasn't a cancellation
        if "cancelled" not in message.lower():
            QMessageBox.information(self, "Success", f"{message}\n\nSaved to:\n{self.download_dir_path.text()}")

    def on_crawl_error(self, msg):
        self.run_button.show() # Show Run button
        self.cancel_button.hide() # Hide Cancel button
        self.run_button.setText("Run Crawler")
        self.progress_bar.hide()
        self.status_label.setText("Failed.")
        QMessageBox.critical(self, "Error", msg)

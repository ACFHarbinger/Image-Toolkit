# gui/tabs/ImageCrawlTab.py
import os

from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLineEdit, QPushButton, QFileDialog, QLabel,
    QGroupBox, QCheckBox, QComboBox, QMessageBox,
    QFormLayout, QHBoxLayout, QVBoxLayout, QProgressBar, QWidget,
    QListWidget, QMenu, QListWidgetItem
)
from PySide6.QtGui import QAction
from PySide6.QtCore import QPoint
from .base_tab import BaseTab
from ..helpers import ImageCrawlWorker
from ..components import OptionalField
from ..styles.style import apply_shadow_effect


class ImageCrawlTab(BaseTab):
    def __init__(self, dropdown=True):
        super().__init__()
        self.dropdown = dropdown
        self.worker = None
        path = Path(os.getcwd())
        parts = path.parts
        self.last_browsed_download_dir = os.path.join(Path(*parts[:parts.index('Image-Toolkit') + 1]), 'data', 'tmp')
        self.last_browsed_screenshot_dir = self.last_browsed_download_dir 

        main_layout = QVBoxLayout(self)

        # --- Crawler Settings Group ---
        crawl_group = QGroupBox("Web Crawler Settings")
        crawl_group.setStyleSheet("""
            QGroupBox { 
                border: 1px solid #4f545c; 
                border-radius: 8px;
                margin-top: 10px;
            }
            QGroupBox::title { 
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 4px 10px;
                color: white;
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
        
        # --- URL Replacement Fields ---
        self.replace_str_input = QLineEdit()
        self.replace_str_input.setPlaceholderText("e.g., page=1 (optional)")
        form_layout.addRow("String to Replace:", self.replace_str_input)
        
        self.replacements_input = QLineEdit()
        self.replacements_input.setPlaceholderText("e.g., page=2, page=3, page=4 (comma-separated)")
        form_layout.addRow("Replacements:", self.replacements_input)

        # Download Directory
        download_dir_layout = QHBoxLayout()
        self.download_dir_path = QLineEdit()
        self.download_dir_path.setText(self.last_browsed_download_dir)
        btn_browse_download = QPushButton("Browse...")
        btn_browse_download.clicked.connect(self.browse_download_directory)
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
        
        crawl_group.setLayout(form_layout)
        main_layout.addWidget(crawl_group)
        
        # --- Actions Group ---
        actions_group = QGroupBox("Actions (Executed for each image)")
        actions_group.setStyleSheet(crawl_group.styleSheet())
        actions_layout = QVBoxLayout()
        actions_layout.setSpacing(10)

        # Image Skip Count
        skip_layout = QHBoxLayout()
        self.skip_first_input = QLineEdit("0")
        self.skip_first_input.setFixedWidth(50)
        self.skip_first_input.setAlignment(Qt.AlignCenter)
        self.skip_last_input = QLineEdit("0")
        self.skip_last_input.setFixedWidth(50)
        self.skip_last_input.setAlignment(Qt.AlignCenter)

        skip_layout.addWidget(QLabel("Skip First:"))
        skip_layout.addWidget(self.skip_first_input)
        skip_layout.addSpacing(20)
        skip_layout.addWidget(QLabel("Skip Last:"))
        skip_layout.addWidget(self.skip_last_input)
        skip_layout.addStretch()
        actions_layout.addLayout(skip_layout)

        # Action Builder
        action_builder_layout = QHBoxLayout()
        self.action_combo = QComboBox()
        # --- NEW ACTION LIST (FROM PREVIOUS TURN) ---
        self.action_combo.addItems([
            "Find Parent Link (<a>)",
            "Download Simple Thumbnail (Legacy)",
            "Extract High-Res Preview URL",
            "Open Link in New Tab",
            "Click Element by Text",
            "Wait for Page Load",
            "Switch to Last Tab",
            "Find First <img> on Page",
            "Download Image from Element",
            "Download Current URL as Image",
            "Wait for Gallery (Context Reset)"
        ])
        # --- END NEW ACTION LIST ---
        self.action_param_input = QLineEdit()
        self.action_param_input.setPlaceholderText("Parameter (e.g., text to click)")
        self.add_action_button = QPushButton("Add")
        self.add_action_button.clicked.connect(self.add_action)
        
        action_builder_layout.addWidget(self.action_combo, 2)
        action_builder_layout.addWidget(self.action_param_input, 2)
        action_builder_layout.addWidget(self.add_action_button, 1)
        actions_layout.addLayout(action_builder_layout)
        
        # Action List
        self.action_list_widget = QListWidget()
        self.action_list_widget.setStyleSheet("QListWidget { border: 1px solid #4f545c; border-radius: 4px; }")
        
        # --- Context Menu Setup ---
        self.action_list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.action_list_widget.customContextMenuRequested.connect(self.show_context_menu)
        # --- End Context Menu Setup ---
        
        actions_layout.addWidget(self.action_list_widget)
        
        # List Controls
        list_controls_layout = QHBoxLayout()
        # The 'Remove Selected' button will now primarily call the remove_action method, 
        # which is also linked to the right-click menu.
        self.remove_action_button = QPushButton("Remove Selected")
        self.remove_action_button.clicked.connect(self.remove_action)
        self.clear_actions_button = QPushButton("Clear All")
        self.clear_actions_button.clicked.connect(self.action_list_widget.clear)
        list_controls_layout.addWidget(self.remove_action_button)
        list_controls_layout.addWidget(self.clear_actions_button)
        actions_layout.addLayout(list_controls_layout)

        actions_group.setLayout(actions_layout)
        main_layout.addWidget(actions_group)
        # --- End Actions Group ---

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

    def show_context_menu(self, pos: QPoint):
        """Displays the right-click menu for moving/removing items."""
        # Find the item at the clicked position
        item = self.action_list_widget.itemAt(pos)
        if not item:
            return

        menu = QMenu()
        
        # --- Move Actions ---
        move_up_action = QAction("Move Up ▲", self)
        # We use lambda to pass the item (or just rely on currentRow for simplicity)
        move_up_action.triggered.connect(self.move_action_up)
        menu.addAction(move_up_action)

        move_down_action = QAction("Move Down ▼", self)
        move_down_action.triggered.connect(self.move_action_down)
        menu.addAction(move_down_action)
        
        menu.addSeparator()

        # --- Remove Action ---
        remove_action = QAction("Remove 🗑️", self)
        remove_action.triggered.connect(self.remove_action)
        menu.addAction(remove_action)

        # Show the menu at the cursor position
        menu.exec(self.action_list_widget.mapToGlobal(pos))
        
    def move_action_up(self):
        """Moves the selected item one position up."""
        current_row = self.action_list_widget.currentRow()
        if current_row > 0:
            current_item = self.action_list_widget.takeItem(current_row)
            self.action_list_widget.insertItem(current_row - 1, current_item)
            self.action_list_widget.setCurrentRow(current_row - 1)

    def move_action_down(self):
        """Moves the selected item one position down."""
        current_row = self.action_list_widget.currentRow()
        if current_row < self.action_list_widget.count() - 1 and current_row != -1:
            current_item = self.action_list_widget.takeItem(current_row)
            self.action_list_widget.insertItem(current_row + 1, current_item)
            self.action_list_widget.setCurrentRow(current_row + 1)


    def add_action(self):
        action_text = self.action_combo.currentText()
        param = self.action_param_input.text().strip()
        
        if "Click Element by Text" in action_text and not param:
            QMessageBox.warning(self, "Missing Parameter", "This action requires text in the parameter field.")
            return
            
        display_text = f"{action_text}"
        if param:
            display_text += f" | Param: {param}"
            
        self.action_list_widget.addItem(display_text)
        self.action_param_input.clear()

    def remove_action(self):
        """Removes the selected item."""
        current_row = self.action_list_widget.currentRow()
        if current_row >= 0:
            self.action_list_widget.takeItem(current_row)

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
        
        # --- Get replacement data ---
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
            
        # --- Serialize Action List ---
        actions = []
        for i in range(self.action_list_widget.count()):
            item_text = self.action_list_widget.item(i).text()
            if " | Param: " in item_text:
                action_type, param_str = item_text.split(" | Param: ", 1)
                actions.append({"type": action_type, "param": param_str})
            else:
                actions.append({"type": item_text, "param": None})
        
        # If no actions are specified, default to simple download
        if not actions:
            actions.append({"type": "Extract High-Res Preview URL", "param": None})
            print("No actions specified, defaulting to high-res preview extraction.")

        config = {
            "url": url,
            "download_dir": download_dir,
            "screenshot_dir": screenshot_dir if screenshot_dir else None,
            "headless": self.headless_checkbox.isChecked(),
            "browser": self.browser_combo.currentText(),
            "skip_first": skip_first,
            "skip_last": skip_last,
            "replace_str": replace_str,
            "replacements": replacements_list,
            "actions": actions, 
        }

        # UI: Show working state
        self.run_button.hide() 
        self.cancel_button.show() 
        self.status_label.setText("Initializing browser...")
        self.progress_bar.show()
        self.progress_bar.setRange(0, 0)

        # Start worker
        self.worker = ImageCrawlWorker(config)
        self.worker.status.connect(self.status_label.setText)
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

    def get_default_config(self) -> dict:
        """Returns the default configuration values for this tab."""
        return {
            "url": "https://example.com/gallery?page=1",
            "download_dir": "C:/path/to/downloads",
            "screenshot_dir": None,
            "headless": True,
            "browser": "chrome",
            "skip_first": 0,
            "skip_last": 0,
            "replace_str": "page=1",
            "replacements": ["page=2", "page=3"],
            "actions": [
                {"type": "Find Parent Link (<a>)", "param": None},
                {"type": "Extract High-Res Preview URL", "param": None},
                {"type": "Download Image from Element", "param": None}
            ]
        }

    def set_config(self, config: dict):
        """Applies a loaded configuration to the tab's UI."""
        try:
            self.url_input.setText(config.get("url", ""))
            self.download_dir_path.setText(config.get("download_dir", ""))
            self.screenshot_dir_path.setText(config.get("screenshot_dir", ""))
            self.headless_checkbox.setChecked(config.get("headless", True))
            
            browser = config.get("browser", "chrome")
            if self.browser_combo.findText(browser) != -1:
                self.browser_combo.setCurrentText(browser)
                
            self.skip_first_input.setText(str(config.get("skip_first", 0)))
            self.skip_last_input.setText(str(config.get("skip_last", 0)))
            self.replace_str_input.setText(config.get("replace_str", ""))
            self.replacements_input.setText(", ".join(config.get("replacements", [])))
            
            self.action_list_widget.clear()
            actions = config.get("actions", [])
            for action in actions:
                display_text = action.get("type", "Unknown Action")
                param = action.get("param")
                if param:
                    display_text += f" | Param: {param}"
                self.action_list_widget.addItem(display_text)
            
            print(f"ImageCrawlTab configuration loaded.")
            
        except Exception as e:
            print(f"Error applying ImageCrawlTab config: {e}")
            QMessageBox.warning(self, "Config Error", f"Failed to apply some settings: {e}")

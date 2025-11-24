from PySide6.QtGui import QAction
from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import (
    QLineEdit, QPushButton, QLabel, QGroupBox,
    QComboBox, QMessageBox, QFormLayout, QHBoxLayout,
    QVBoxLayout, QListWidget, QMenu, QProgressBar, QWidget
)
from ..windows import LogWindow
from ..helpers import WebRequestsWorker


class WebRequestsTab(QWidget):
    def __init__(self, dropdown=True):
        super().__init__()
        self.dropdown = dropdown
        self.worker = None

        # --- Log Window Initialization ---
        self.log_window = LogWindow(tab_name="Web Requests")
        self.log_window.hide()
        # --- End Log Window Initialization ---

        main_layout = QVBoxLayout(self)

        # --- Group Box Styling ---
        group_box_style = """
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
        """

        # --- Request Configuration Group ---
        request_config_group = QGroupBox("Request Configuration")
        request_config_group.setStyleSheet(group_box_style)
        
        form_layout = QFormLayout()
        form_layout.setContentsMargins(10, 20, 10, 10)
        form_layout.setSpacing(15)

        # Target URL
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://api.example.com/data")
        form_layout.addRow("Base URL:", self.url_input)

        request_config_group.setLayout(form_layout)
        main_layout.addWidget(request_config_group)

        # --- Request Builder Group ---
        request_builder_group = QGroupBox("1. Request List (Runs in order)")
        request_builder_group.setStyleSheet(group_box_style)
        request_builder_layout = QVBoxLayout()
        request_builder_layout.setSpacing(10)

        # Request Builder
        req_builder_layout = QHBoxLayout()
        self.request_type_combo = QComboBox()
        self.request_type_combo.addItems(["GET", "POST"])
        
        self.request_param_input = QLineEdit()
        self.request_param_input.setPlaceholderText("POST Data (key:val, k2:v2) or URL Suffix")
        
        self.add_request_button = QPushButton("Add Request")
        self.add_request_button.clicked.connect(self.add_request)
        
        req_builder_layout.addWidget(self.request_type_combo, 1)
        req_builder_layout.addWidget(self.request_param_input, 2)
        req_builder_layout.addWidget(self.add_request_button, 1)
        request_builder_layout.addLayout(req_builder_layout)
        
        # Request List
        self.request_list_widget = QListWidget()
        self.request_list_widget.setMinimumHeight(150)
        self.request_list_widget.setStyleSheet("QListWidget { border: 1px solid #4f545c; border-radius: 4px; }")
        self.request_list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.request_list_widget.customContextMenuRequested.connect(lambda pos: self.show_context_menu(pos, self.request_list_widget))
        request_builder_layout.addWidget(self.request_list_widget)

        request_builder_group.setLayout(request_builder_layout)
        main_layout.addWidget(request_builder_group)

        # --- Action Builder Group ---
        action_builder_group = QGroupBox("2. Response Actions (Runs for each request)")
        action_builder_group.setStyleSheet(group_box_style)
        action_builder_layout = QVBoxLayout()
        action_builder_layout.setSpacing(10)

        # Action Builder
        act_builder_layout = QHBoxLayout()
        self.action_combo = QComboBox()
        self.action_combo.addItems([
            "Print Response URL",
            "Print Response Status Code",
            "Print Response Headers",
            "Print Response Content (Text)",
            "Save Response Content (Binary)"
        ])
        self.action_param_input = QLineEdit()
        self.action_param_input.setPlaceholderText("Parameter (e.g., file path for Save)")
        self.add_action_button = QPushButton("Add Action")
        self.add_action_button.clicked.connect(self.add_action)
        
        act_builder_layout.addWidget(self.action_combo, 1)
        act_builder_layout.addWidget(self.action_param_input, 2)
        act_builder_layout.addWidget(self.add_action_button, 1)
        action_builder_layout.addLayout(act_builder_layout)
        
        # Action List
        self.action_list_widget = QListWidget()
        self.action_list_widget.setMinimumHeight(150)
        self.action_list_widget.setStyleSheet("QListWidget { border: 1px solid #4f545c; border-radius: 4px; }")
        self.action_list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.action_list_widget.customContextMenuRequested.connect(lambda pos: self.show_context_menu(pos, self.action_list_widget))
        action_builder_layout.addWidget(self.action_list_widget)

        action_builder_group.setLayout(action_builder_layout)
        main_layout.addWidget(action_builder_group)

        # --- Progress & Status ---
        self.status_label = QLabel("Ready.")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #aaa; font-style: italic; padding: 8px;")
        main_layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0) # Indeterminate
        self.progress_bar.setTextVisible(False)
        self.progress_bar.hide()
        main_layout.addWidget(self.progress_bar)

        # --- Run/Cancel Button Container ---
        self.button_container = QWidget()
        self.button_layout = QVBoxLayout(self.button_container)
        self.button_layout.setContentsMargins(0, 0, 0, 0)

        self.run_button = QPushButton("Run Requests")
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
        self.run_button.clicked.connect(self.start_requests)
        self.button_layout.addWidget(self.run_button, 0, Qt.AlignBottom)

        self.cancel_button = QPushButton("Cancel Requests")
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #cc3333; color: white; font-weight: bold;
                font-size: 16px; padding: 14px; border-radius: 10px; min-height: 44px;
            }
            QPushButton:hover { background-color: #ff4444; }
        """)
        self.cancel_button.clicked.connect(self.cancel_requests)
        self.cancel_button.hide()
        self.button_layout.addWidget(self.cancel_button, 0, Qt.AlignBottom)

        main_layout.addWidget(self.button_container)
        main_layout.addStretch(1)
        self.setLayout(main_layout)

    def show_context_menu(self, pos: QPoint, list_widget: QListWidget):
        """Displays a generic context menu for a QListWidget."""
        item = list_widget.itemAt(pos)
        if not item:
            return

        menu = QMenu()
        
        remove_action = QAction("Remove 🗑️", self)
        remove_action.triggered.connect(lambda: self.remove_item(list_widget))
        menu.addAction(remove_action)
        
        clear_action = QAction("Clear All", self)
        clear_action.triggered.connect(list_widget.clear)
        menu.addAction(clear_action)

        menu.exec(list_widget.mapToGlobal(pos))

    def remove_item(self, list_widget: QListWidget):
        """Removes the selected item from the specified list widget."""
        current_row = list_widget.currentRow()
        if current_row >= 0:
            list_widget.takeItem(current_row)

    def add_request(self):
        req_type = self.request_type_combo.currentText()
        param = self.request_param_input.text().strip()
        
        display_text = f"[{req_type}]"
        if param:
            if req_type == "POST":
                display_text += f" | Data: {param}"
            else: # GET
                display_text += f" | Suffix: {param}"
        
        self.request_list_widget.addItem(display_text)
        self.request_param_input.clear()

    def add_action(self):
        action_text = self.action_combo.currentText()
        param = self.action_param_input.text().strip()
        
        if "Save" in action_text and not param:
            QMessageBox.warning(self, "Missing Parameter", "Save actions require a file path or directory as a parameter.")
            return

        display_text = action_text
        if param:
            display_text += f" | Param: {param}"
            
        self.action_list_widget.addItem(display_text)
        self.action_param_input.clear()

    def start_requests(self):
        url = self.url_input.text().strip()

        if not url:
            QMessageBox.warning(self, "Missing URL", "Please enter a base URL.")
            return
        if not url.startswith(("http://", "https://")):
            QMessageBox.warning(self, "Invalid URL", "URL must start with http:// or https://")
            return
        
        if self.request_list_widget.count() == 0:
            QMessageBox.warning(self, "No Requests", "Please add at least one request to run.")
            return
            
        if self.action_list_widget.count() == 0:
            QMessageBox.warning(self, "No Actions", "Please add at least one action to perform on the response.")
            return

        # --- Serialize Request List ---
        requests = []
        for i in range(self.request_list_widget.count()):
            item_text = self.request_list_widget.item(i).text()
            req_type = "GET"
            param = None
            
            if "[POST]" in item_text:
                req_type = "POST"
                if " | Data: " in item_text:
                    param = item_text.split(" | Data: ", 1)[1]
            elif "[GET]" in item_text:
                if " | Suffix: " in item_text:
                    param = item_text.split(" | Suffix: ", 1)[1]
            
            requests.append({"type": req_type, "param": param})

        # --- Serialize Action List ---
        actions = []
        for i in range(self.action_list_widget.count()):
            item_text = self.action_list_widget.item(i).text()
            param = None
            
            if " | Param: " in item_text:
                action_type, param = item_text.split(" | Param: ", 1)
            else:
                action_type = item_text
            
            actions.append({"type": action_type, "param": param})
        
        config = {
            "base_url": url,
            "requests": requests,
            "actions": actions
        }

        # UI: Show working state
        self.run_button.hide()
        self.cancel_button.show()
        self.status_label.setText("Starting requests...")
        self.progress_bar.show()
        
        # --- LOGGING: Clear and show log window ---
        self.log_window.clear_log()
        self.log_window.show()

        # Start worker
        try:
            self.worker = WebRequestsWorker(config)
            
            # --- Connect worker signals to log window and status ---
            self.worker.status.connect(self.log_window.append_log)
            self.worker.status.connect(self.status_label.setText) # Show last status
            self.worker.error.connect(self.log_window.append_log)
            self.worker.finished.connect(self.on_requests_done)
            
            self.worker.start()
        except ImportError:
             QMessageBox.critical(self, "Error", "Failed to import WebRequestsWorker. Check console.")
             self.on_requests_done("ImportError: Worker not found.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start worker: {e}")
            self.on_requests_done(f"Failed to start worker: {e}")


    def cancel_requests(self):
        """Attempts to stop the QThread worker."""
        if self.worker and self.worker.isRunning():
            try:
                self.worker.stop() # Call the custom stop method on the worker
                self.log_window.append_log("Request sequence **cancelled** by user.")
                self.on_requests_done("Cancelled by user.")
                QMessageBox.information(self, "Cancelled", "The request sequence has been stopped.")
            except Exception as e:
                self.log_window.append_log(f"Error during cancel: {e}")
        else:
            self.on_requests_done("Worker was not running.")

    def on_requests_done(self, message):
        self.run_button.show()
        self.cancel_button.hide()
        self.progress_bar.hide()
        self.status_label.setText(message)
        
        if "cancelled" not in message.lower() and "Error" not in message:
            QMessageBox.information(self, "Success", "All requests finished!")

    # --- Config Management (Empty stubs, can be filled later) ---

    def get_default_config(self) -> dict:
        """Returns the default configuration values for this tab."""
        return {
            "base_url": "https://httpbin.org/",
            "requests": [
                {"type": "GET", "param": "get"},
                {"type": "POST", "param": "post_key:post_value"}
            ],
            "actions": [
                {"type": "Print Response Status Code", "param": None},
                {"type": "Print Response Content (Text)", "param": None}
            ]
        }

    def set_config(self, config: dict):
        """Applies a loaded configuration to the tab's UI."""
        try:
            self.url_input.setText(config.get("base_url", ""))
            
            # Load Requests
            self.request_list_widget.clear()
            requests = config.get("requests", [])
            for req in requests:
                req_type = req.get("type", "GET")
                param = req.get("param")
                display_text = f"[{req_type}]"
                if param:
                    display_text += f" | {'Data' if req_type == 'POST' else 'Suffix'}: {param}"
                self.request_list_widget.addItem(display_text)

            # Load Actions
            self.action_list_widget.clear()
            actions = config.get("actions", [])
            for action in actions:
                display_text = action.get("type", "Unknown Action")
                param = action.get("param")
                if param is not None:
                    display_text += f" | Param: {param}"
                self.action_list_widget.addItem(display_text)
            
            print(f"WebRequestsTab configuration loaded.")
            
        except Exception as e:
            print(f"Error applying WebRequestsTab config: {e}")
            QMessageBox.warning(self, "Config Error", f"Failed to apply some settings: {e}")

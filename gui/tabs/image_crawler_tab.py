from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import (
    QLineEdit, QPushButton, QFileDialog, QLabel,
    QGroupBox, QCheckBox, QComboBox, QMessageBox,
    QFormLayout, QHBoxLayout, QVBoxLayout, QWidget,
    QListWidget, QMenu, QProgressBar, QInputDialog,
    QStackedWidget
)
from PySide6.QtGui import QAction
from ..windows import LogWindow
from ..helpers import ImageCrawlWorker
from ..components import OptionalField
from ..styles.style import apply_shadow_effect
from ..utils.app_definitions import SCREENSHOTS_DIR
from backend.src.utils.definitions import LOCAL_SOURCE_PATH


class ImageCrawlTab(QWidget):
    def __init__(self, dropdown=True):
        super().__init__()
        self.dropdown = dropdown
        self.worker = None
        
        # --- Log Window Initialization ---
        self.log_window = LogWindow(tab_name="Web Crawler")
        self.log_window.hide()
        
        self.last_browsed_download_dir = LOCAL_SOURCE_PATH
        self.last_browsed_screenshot_dir = SCREENSHOTS_DIR

        main_layout = QVBoxLayout(self)

        # --- 1. Crawler Type Selection ---
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("<b>Crawler Type:</b>"))
        
        self.crawler_type_combo = QComboBox()
        self.crawler_type_combo.addItems([
            "General Web Crawler", 
            "Image Board Crawler (Danbooru API)",
            "Image Board Crawler (Gelbooru API)",
            "Image Board Crawler (Sankaku Complex API)"
        ])
        self.crawler_type_combo.currentIndexChanged.connect(self.on_crawler_type_changed)
        type_layout.addWidget(self.crawler_type_combo, 1)
        
        main_layout.addLayout(type_layout)

        # --- 2. Stacked Widget for Specific Settings ---
        self.settings_stack = QStackedWidget()
        
        # PAGE 1: General Crawler Settings
        self.page_general = QWidget()
        self.setup_general_page()
        self.settings_stack.addWidget(self.page_general)
        
        # PAGE 2: Image Board Settings
        self.page_board = QWidget()
        self.setup_board_page()
        self.settings_stack.addWidget(self.page_board)
        
        main_layout.addWidget(self.settings_stack)

        # --- 3. Shared Download Settings ---
        download_group = QGroupBox("Output Configuration")
        download_group.setStyleSheet(self._get_group_style())
        download_layout = QFormLayout(download_group)
        download_layout.setContentsMargins(10, 20, 10, 10)

        download_dir_layout = QHBoxLayout()
        self.download_dir_path = QLineEdit()
        self.download_dir_path.setText(self.last_browsed_download_dir)
        btn_browse_download = QPushButton("Browse...")
        btn_browse_download.clicked.connect(self.browse_download_directory)
        apply_shadow_effect(btn_browse_download, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        download_dir_layout.addWidget(self.download_dir_path)
        download_dir_layout.addWidget(btn_browse_download)
        download_layout.addRow("Download Dir:", download_dir_layout)
        
        # Screenshot (General only mostly, but kept shared for simplicity)
        screenshot_dir_layout = QHBoxLayout()
        self.screenshot_dir_path = QLineEdit()
        self.screenshot_dir_path.setPlaceholderText("Optional: directory for screenshots")
        btn_browse_screenshot = QPushButton("Browse...")
        btn_browse_screenshot.clicked.connect(self.browse_screenshot_directory)
        apply_shadow_effect(btn_browse_screenshot, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        screenshot_dir_layout.addWidget(self.screenshot_dir_path)
        screenshot_dir_layout.addWidget(btn_browse_screenshot)
        
        screenshot_container = QWidget()
        screenshot_container.setLayout(screenshot_dir_layout)
        self.screenshot_field = OptionalField("Screenshot Dir", screenshot_container, start_open=False)
        download_layout.addRow(self.screenshot_field)
        
        main_layout.addWidget(download_group)

        # --- 4. Run Controls ---
        # Progress & Status
        self.status_label = QLabel("Ready.")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #aaa; font-style: italic; padding: 8px;")
        main_layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.hide()
        main_layout.addWidget(self.progress_bar)

        # Run/Cancel Button Container
        self.button_container = QWidget()
        self.button_layout = QVBoxLayout(self.button_container)
        self.button_layout.setContentsMargins(0, 0, 0, 0)

        self.run_button = QPushButton("Run Crawler")
        self.run_button.setStyleSheet(self._get_run_btn_style())
        apply_shadow_effect(self.run_button, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.run_button.clicked.connect(self.start_crawl)
        self.button_layout.addWidget(self.run_button, 0, Qt.AlignBottom)

        self.cancel_button = QPushButton("Cancel Crawl")
        self.cancel_button.setStyleSheet(self._get_cancel_btn_style())
        apply_shadow_effect(self.cancel_button, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.cancel_button.clicked.connect(self.cancel_crawl)
        self.cancel_button.hide()
        self.button_layout.addWidget(self.cancel_button, 0, Qt.AlignBottom)

        main_layout.addWidget(self.button_container)
        main_layout.addStretch(1)
        
        # Initial State
        self.on_crawler_type_changed(self.crawler_type_combo.currentIndex()) 

    # --- UI Setup Helpers ---

    def _get_group_style(self):
        return """
            QGroupBox { border: 1px solid #4f545c; border-radius: 8px; margin-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 4px 10px; color: white; border-radius: 4px; }
        """
    def _get_run_btn_style(self):
        return """
            QPushButton { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #667eea, stop:1 #764ba2); color: white; font-weight: bold; padding: 14px; border-radius: 10px; }
            QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #764ba2, stop:1 #667eea); }
        """
    def _get_cancel_btn_style(self):
        return """
            QPushButton { background-color: #cc3333; color: white; font-weight: bold; padding: 14px; border-radius: 10px; }
            QPushButton:hover { background-color: #ff4444; }
        """

    def setup_general_page(self):
        layout = QVBoxLayout(self.page_general)
        layout.setContentsMargins(0, 0, 0, 0)

        # Login Group
        login_group = QGroupBox("General Login Configuration")
        login_group.setStyleSheet(self._get_group_style())
        login_form = QFormLayout()
        login_form.setContentsMargins(10, 20, 10, 10)
        
        self.gen_login_url = QLineEdit()
        self.gen_login_url.setPlaceholderText("https://example.com/login")
        login_form.addRow("Login URL:", self.gen_login_url)
        self.gen_username = QLineEdit()
        self.gen_username.setPlaceholderText("Username/Email")
        login_form.addRow("Username:", self.gen_username)
        self.gen_password = QLineEdit()
        self.gen_password.setEchoMode(QLineEdit.EchoMode.Password)
        login_form.addRow("Password:", self.gen_password)
        login_group.setLayout(login_form)
        layout.addWidget(login_group)

        # General Settings Group
        crawl_group = QGroupBox("Web Scraper Settings")
        crawl_group.setStyleSheet(self._get_group_style())
        form = QFormLayout()
        form.setContentsMargins(10, 20, 10, 10)
        
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com/gallery?page=1")
        form.addRow("Target URL:", self.url_input)
        
        self.replace_str_input = QLineEdit()
        self.replace_str_input.setPlaceholderText("e.g., page=1")
        form.addRow("String to Replace:", self.replace_str_input)
        
        self.replacements_input = QLineEdit()
        self.replacements_input.setPlaceholderText("e.g., page=2, page=3")
        form.addRow("Replacements:", self.replacements_input)
        
        self.browser_combo = QComboBox()
        self.browser_combo.addItems(["chrome", "firefox", "edge", "brave"])
        self.browser_combo.setCurrentText("brave")
        form.addRow("Browser:", self.browser_combo)
        
        self.headless_checkbox = QCheckBox("Run in headless mode")
        self.headless_checkbox.setChecked(True)
        form.addRow("", self.headless_checkbox)
        
        crawl_group.setLayout(form)
        layout.addWidget(crawl_group)

        # Actions Group
        actions_group = QGroupBox("Actions")
        actions_group.setStyleSheet(self._get_group_style())
        act_layout = QVBoxLayout()
        
        # Skip settings
        skip_layout = QHBoxLayout()
        self.skip_first_input = QLineEdit("0")
        self.skip_first_input.setFixedWidth(50)
        self.skip_last_input = QLineEdit("0")
        self.skip_last_input.setFixedWidth(50)
        skip_layout.addWidget(QLabel("Skip First:"))
        skip_layout.addWidget(self.skip_first_input)
        skip_layout.addSpacing(20)
        skip_layout.addWidget(QLabel("Skip Last:"))
        skip_layout.addWidget(self.skip_last_input)
        skip_layout.addStretch()
        act_layout.addLayout(skip_layout)

        # Action Builder
        ab_layout = QHBoxLayout()
        self.action_combo = QComboBox()
        self.action_combo.addItems([
            "Find Parent Link (<a>)", "Download Simple Thumbnail (Legacy)", 
            "Extract High-Res Preview URL", "Open Link in New Tab", "Click Element by Text",
            "Wait for Page Load", "Wait X Seconds", "Switch to Last Tab",
            "Find Element by CSS Selector", "Find <img> Number X on Page",
            "Download Image from Element", "Download Current URL as Image",
            "Wait for Gallery (Context Reset)", "Scrape Text (Saves to JSON)",
            "Scan Page for Text and Skip if Found", "Close Current Tab", "Refresh Current Element"
        ])
        self.action_param = QLineEdit()
        self.action_param.setPlaceholderText("Parameter")
        self.add_act_btn = QPushButton("Add")
        self.add_act_btn.clicked.connect(self.add_action)
        ab_layout.addWidget(self.action_combo, 2)
        ab_layout.addWidget(self.action_param, 2)
        ab_layout.addWidget(self.add_act_btn, 1)
        act_layout.addLayout(ab_layout)

        self.action_list_widget = QListWidget()
        self.action_list_widget.setMinimumHeight(150)
        self.action_list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.action_list_widget.customContextMenuRequested.connect(self.show_context_menu)
        act_layout.addWidget(self.action_list_widget)
        
        # List controls
        lc_layout = QHBoxLayout()
        self.rem_act_btn = QPushButton("Remove Selected")
        self.rem_act_btn.clicked.connect(self.remove_action)
        self.clr_act_btn = QPushButton("Clear All")
        self.clr_act_btn.clicked.connect(self.action_list_widget.clear)
        lc_layout.addWidget(self.rem_act_btn)
        lc_layout.addWidget(self.clr_act_btn)
        act_layout.addLayout(lc_layout)

        actions_group.setLayout(act_layout)
        layout.addWidget(actions_group)

    def setup_board_page(self):
        layout = QVBoxLayout(self.page_board)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Board API Settings
        api_group = QGroupBox("API Configuration")
        api_group.setStyleSheet(self._get_group_style())
        form = QFormLayout()
        form.setContentsMargins(10, 20, 10, 10)
        
        self.board_url = QLineEdit("https://danbooru.donmai.us")
        self.board_url.setPlaceholderText("Board URL")
        form.addRow("Board URL:", self.board_url)
        
        # --- Resource Selection ---
        self.board_resource = QLineEdit("posts")
        self.board_resource.setPlaceholderText("Resource (e.g. posts, tags, comments)")
        form.addRow("Resource:", self.board_resource)
        
        self.board_tags = QLineEdit()
        self.board_tags.setPlaceholderText("e.g. 1girl scenic original")
        form.addRow("Tags:", self.board_tags)
        
        self.board_limit = QLineEdit("20")
        self.board_limit.setPlaceholderText("Images per page")
        form.addRow("Limit (per page):", self.board_limit)
        
        self.board_max_pages = QLineEdit("5")
        self.board_max_pages.setPlaceholderText("Number of pages to crawl")
        form.addRow("Max Pages:", self.board_max_pages)
        
        # --- Extra Parameters ---
        self.board_extra_params = QLineEdit()
        self.board_extra_params.setPlaceholderText("e.g. deleted=show&order=count")
        form.addRow("Extra Query Params:", self.board_extra_params)
        
        api_group.setLayout(form)
        layout.addWidget(api_group)
        
        # API Doc Link Label (to be placed dynamically)
        self.api_doc_link = QLabel("")
        self.api_doc_link.setOpenExternalLinks(True)
        self.api_doc_link.setStyleSheet("padding: 5px; font-size: 10px; color: #aaa;")
        layout.addWidget(self.api_doc_link) # Add here initially

        # Auth Group
        auth_group = QGroupBox("Authentication (Optional)")
        auth_group.setStyleSheet(self._get_group_style())
        a_form = QFormLayout()
        a_form.setContentsMargins(10, 20, 10, 10)
        
        self.board_username_label = QLabel("Username:")
        self.board_username = QLineEdit()
        a_form.addRow(self.board_username_label, self.board_username)
        
        self.board_apikey_label = QLabel("API Key:")
        self.board_apikey = QLineEdit()
        self.board_apikey.setEchoMode(QLineEdit.EchoMode.Password)
        a_form.addRow(self.board_apikey_label, self.board_apikey)
        
        auth_group.setLayout(a_form)
        layout.addWidget(auth_group)
        
        layout.addStretch(1)

    # --- Event Handlers ---

    def update_board_auth_labels(self, index: int):
        """Dynamically updates labels/placeholders based on selected board type."""
        # Ensure elements exist before trying to update them
        if not hasattr(self, 'board_username_label'):
             return

        if index == 1: # Danbooru
            self.board_username_label.setText("Username:")
            self.board_username.setPlaceholderText("Danbooru Username")
            self.board_apikey_label.setText("API Key:")
            self.board_url.setText("https://danbooru.donmai.us")
            self.board_resource.setText("posts")
            self.board_limit.setText("20")
            link = '<a href="https://danbooru.donmai.us/wiki_pages/help:api">Danbooru API Documentation</a>'
            self.api_doc_link.setText(link)
            
        elif index == 2: # Gelbooru
            self.board_username_label.setText("User ID:")
            self.board_username.setPlaceholderText("Gelbooru User ID")
            self.board_apikey_label.setText("API Key:")
            self.board_url.setText("https://gelbooru.com")
            self.board_resource.setText("post") 
            self.board_limit.setText("100")
            link = '<a href="https://gelbooru.com/index.php?page=wiki&s=view&id=18780">Gelbooru API Documentation</a>'
            self.api_doc_link.setText(link)
        
        elif index == 3: # Sankaku Complex
            self.board_username_label.setText("Username/Email:")
            self.board_username.setPlaceholderText("Sankaku Username or Email")
            self.board_apikey_label.setText("Password:")
            self.board_url.setText("https://capi-v2.sankakucomplex.com")
            self.board_resource.setText("posts") 
            self.board_limit.setText("40")
            link = '<a href="https://sankaku.app/">Sankaku Complex API Info</a>'
            self.api_doc_link.setText(link)
        
    def on_crawler_type_changed(self, index):
        # Map combo box index to stack index
        # Combo: 0=General, 1=Danbooru, 2=Gelbooru, 3=Sankaku
        # Stack: 0=General Page, 1=Board Page (Shared)
        
        # If index is 0, show page 0. If index is >= 1, show page 1.
        stack_index = 0 if index == 0 else 1
        self.settings_stack.setCurrentIndex(stack_index)
        
        if index >= 1:
            self.update_board_auth_labels(index)
        
    def show_context_menu(self, pos: QPoint):
        item = self.action_list_widget.itemAt(pos)
        if not item: return
        menu = QMenu()
        
        edit_action = QAction("Edit Parameter ✏️", self)
        edit_action.triggered.connect(self.edit_action_parameter)
        if " | Param: " in item.text(): menu.addAction(edit_action)
        
        remove_action = QAction("Remove 🗑️", self)
        remove_action.triggered.connect(self.remove_action)
        menu.addAction(remove_action)
        menu.exec(self.action_list_widget.mapToGlobal(pos))

    def edit_action_parameter(self):
        current_item = self.action_list_widget.currentItem()
        if not current_item or " | Param: " not in current_item.text():
            return
            
        full_text = current_item.text()
        action_type, param_str = full_text.split(" | Param: ", 1)
        
        is_number_mode = ("Find <img> Number X on Page" in action_type or 
                          "Wait X Seconds" in action_type)
        
        title = f"Edit Parameter for: {action_type}"
        prompt = "Enter new parameter value:"
        
        if is_number_mode:
            try:
                initial_value = int(float(param_str)) 
            except ValueError:
                initial_value = 1 

            if "Wait X Seconds" in action_type:
                 new_param, ok = QInputDialog.getDouble(self, title, prompt, float(initial_value), 0.1, 300.0, 1)
            else: 
                 new_param, ok = QInputDialog.getInt(self, title, prompt, initial_value, 1, 99999, 1)
            
            if ok: new_param = str(new_param)
            else: return 
                 
        else:
            new_param, ok = QInputDialog.getText(self, title, prompt, QLineEdit.EchoMode.Normal, param_str)

        if ok and new_param is not None:
            new_param_str = str(new_param).strip()
            if new_param_str:
                current_item.setText(f"{action_type} | Param: {new_param_str}")
                QMessageBox.information(self, "Success", f"Parameter updated for '{action_type}'.")
            else:
                QMessageBox.warning(self, "Edit Failed", "Parameter value cannot be empty.")

    def add_action(self):
        action_text = self.action_combo.currentText()
        param = self.action_param.text().strip()
        if param: action_text += f" | Param: {param}"
        self.action_list_widget.addItem(action_text)
        self.action_param.clear()

    def remove_action(self):
        row = self.action_list_widget.currentRow()
        if row >= 0: self.action_list_widget.takeItem(row)

    def browse_download_directory(self):
        d = QFileDialog.getExistingDirectory(self, "Download Dir", self.last_browsed_download_dir)
        if d:
            self.last_browsed_download_dir = d
            self.download_dir_path.setText(d)

    def browse_screenshot_directory(self):
        d = QFileDialog.getExistingDirectory(self, "Screenshot Dir", self.last_browsed_screenshot_dir)
        if d:
            self.last_browsed_screenshot_dir = d
            self.screenshot_dir_path.setText(d)

    def start_crawl(self):
        download_dir = self.download_dir_path.text().strip()
        if not download_dir:
            QMessageBox.warning(self, "Error", "Please select a download directory.")
            return

        crawler_type_idx = self.crawler_type_combo.currentIndex()
        config = {"download_dir": download_dir}

        if crawler_type_idx == 0:
            config["type"] = "general"
            config["url"] = self.url_input.text().strip()
            config["browser"] = self.browser_combo.currentText()
            config["headless"] = self.headless_checkbox.isChecked()
            config["screenshot_dir"] = self.screenshot_dir_path.text().strip() or None
            
            rep_str = self.replace_str_input.text().strip()
            reps = self.replacements_input.text().strip()
            config["replace_str"] = rep_str or None
            config["replacements"] = [r.strip() for r in reps.split(',')] if reps else None
            
            actions = []
            for i in range(self.action_list_widget.count()):
                txt = self.action_list_widget.item(i).text()
                atype = txt.split(" | Param: ")[0]
                param = txt.split(" | Param: ")[1] if " | Param: " in txt else None
                
                if param and ("Seconds" in atype):
                    try: param = float(param)
                    except: pass
                elif param and ("Number X" in atype):
                    try: param = int(param)
                    except: pass

                actions.append({"type": atype, "param": param})
            
            if not actions: actions.append({"type": "Extract High-Res Preview URL", "param": None})
            config["actions"] = actions
            
            config["login_config"] = {
                "url": self.gen_login_url.text().strip() or None,
                "username": self.gen_username.text().strip() or None,
                "password": self.gen_password.text().strip() or None
            }
            
            try:
                config["skip_first"] = int(self.skip_first_input.text())
                config["skip_last"] = int(self.skip_last_input.text())
            except: 
                config["skip_first"] = 0
                config["skip_last"] = 0

        elif crawler_type_idx >= 1:
            if crawler_type_idx == 2:
                board_type = "gelbooru"
            elif crawler_type_idx == 3:
                board_type = "sankaku"
            else:
                board_type = "danbooru"
            
            config["type"] = "board"
            config["board_type"] = board_type 
            config["url"] = self.board_url.text().strip()
            config["tags"] = self.board_tags.text().strip()
            
            config["resource"] = self.board_resource.text().strip() or "posts"
            
            extra_params_str = self.board_extra_params.text().strip()
            config["extra_params"] = {}
            if extra_params_str:
                try:
                    pairs = extra_params_str.split('&')
                    for p in pairs:
                        if '=' in p:
                            k, v = p.split('=', 1)
                            config["extra_params"][k.strip()] = v.strip()
                except:
                    print("Error parsing extra params")
            
            try:
                config["limit"] = int(self.board_limit.text().strip())
                config["max_pages"] = int(self.board_max_pages.text().strip())
            except ValueError:
                QMessageBox.warning(self, "Error", "Limit and Max Pages must be integers.")
                return
                
            config["login_config"] = {
                "username": self.board_username.text().strip() or None, 
                "password": self.board_apikey.text().strip() or None
            }
            
            if not config["url"].startswith("http"):
                config["url"] = "https://" + config["url"]
            
            config["screenshot_dir"] = None 
            config["skip_first"] = 0 
            config["skip_last"] = 0

        # Start UI state
        self.run_button.hide()
        self.cancel_button.show()
        self.status_label.setText("Initializing...")
        self.progress_bar.show()
        self.progress_bar.setRange(0, 0)
        self.log_window.clear_log()
        self.log_window.show()

        # Worker
        self.worker = ImageCrawlWorker(config)
        self.worker.status.connect(self.log_window.append_log)
        self.worker.error.connect(self.log_window.append_log)
        self.worker.finished.connect(self.on_crawl_done)
        self.worker.start()

    def cancel_crawl(self):
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.on_crawl_done(0, "Cancelled by user.")

    def on_crawl_done(self, count, message):
        self.run_button.show()
        self.cancel_button.hide()
        self.progress_bar.hide()
        self.status_label.setText(message)
        if "Cancelled" not in message:
            QMessageBox.information(self, "Done", f"{message}\nSaved to: {self.download_dir_path.text()}")
"""Widget construction for ``ImageCrawlTab`` (``_build_ui`` and the two pages).

Extracted from ``image_crawler_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from PySide6.QtCore import QProcess, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ....components import OptionalField
from ....styles import apply_shadow_effect, set_button_role


class _UIBuilderMixin:
    """Builds the crawler-type stack, output/selection groups, and run controls."""

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)

        # --- 1. Crawler Type Selection ---
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("<b>Crawler Type:</b>"))

        self.crawler_type_combo = QComboBox()
        self.crawler_type_combo.addItems(
            [
                "General Web Crawler",
                "Image Board Crawler (Danbooru API)",
                "Image Board Crawler (Gelbooru API)",
                "Image Board Crawler (Sankaku Complex API)",
            ]
        )
        self.crawler_type_combo.currentIndexChanged.connect(
            self.on_crawler_type_changed
        )
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
        download_layout = QFormLayout(download_group)
        download_layout.setContentsMargins(10, 20, 10, 10)

        download_dir_layout = QHBoxLayout()
        self.download_dir_path = QLineEdit()
        self.download_dir_path.setText(self.last_browsed_download_dir)
        btn_browse_download = QPushButton("Browse...")
        btn_browse_download.clicked.connect(self.browse_download_directory)
        apply_shadow_effect(
            btn_browse_download, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        download_dir_layout.addWidget(self.download_dir_path)
        download_dir_layout.addWidget(btn_browse_download)
        download_layout.addRow("Download Dir:", download_dir_layout)

        # Screenshot (General only mostly, but kept shared for simplicity)
        screenshot_dir_layout = QHBoxLayout()
        self.screenshot_dir_path = QLineEdit()
        self.screenshot_dir_path.setPlaceholderText(
            "Optional: directory for screenshots"
        )
        btn_browse_screenshot = QPushButton("Browse...")
        btn_browse_screenshot.clicked.connect(self.browse_screenshot_directory)
        apply_shadow_effect(
            btn_browse_screenshot, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        screenshot_dir_layout.addWidget(self.screenshot_dir_path)
        screenshot_dir_layout.addWidget(btn_browse_screenshot)

        screenshot_container = QWidget()
        screenshot_container.setLayout(screenshot_dir_layout)
        self.screenshot_field = OptionalField(
            "Screenshot Dir", screenshot_container, start_open=False
        )
        download_layout.addRow(self.screenshot_field)

        main_layout.addWidget(download_group)

        # --- 3b. Selection and Deduplication Mode ---
        selection_group = QGroupBox("Deduplication and Selection Mode")
        selection_layout = QFormLayout(selection_group)
        selection_layout.setContentsMargins(10, 20, 10, 10)

        self.selection_mode_combo = QComboBox()
        self.selection_mode_combo.addItems(
            [
                "Download All (Default)",
                "Manual Selection",
                "Automated Selection",
            ]
        )
        selection_layout.addRow("Selection Mode:", self.selection_mode_combo)
        main_layout.addWidget(selection_group)

        # --- 4. Run Controls ---
        # Progress and Status
        self.status_label = QLabel("Ready.")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(
            "color: #aaa; font-style: italic; padding: 8px;"
        )
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
        set_button_role(self.run_button, "success")
        apply_shadow_effect(
            self.run_button, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        self.run_button.clicked.connect(self.start_crawl)

        # --- WebDriver Management ---
        self.webdriver_process = QProcess(self)
        self.webdriver_process.readyReadStandardOutput.connect(self.on_webdriver_stdout)
        self.webdriver_process.readyReadStandardError.connect(self.on_webdriver_stderr)
        self.webdriver_process.finished.connect(self.on_webdriver_finished)

        self.webdriver_button = QPushButton("🌐 Start WebDriver Service")
        set_button_role(self.webdriver_button, "success")
        apply_shadow_effect(
            self.webdriver_button, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        self.webdriver_button.clicked.connect(self.toggle_webdriver)
        self.button_layout.addWidget(
            self.webdriver_button, 0, Qt.AlignmentFlag.AlignBottom
        )

        self.button_layout.addWidget(self.run_button, 0, Qt.AlignmentFlag.AlignBottom)

        self.cancel_button = QPushButton("Cancel Crawl")
        set_button_role(self.cancel_button, "danger")
        apply_shadow_effect(
            self.cancel_button, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        self.cancel_button.clicked.connect(self.cancel_crawl)
        self.cancel_button.hide()
        self.button_layout.addWidget(
            self.cancel_button, 0, Qt.AlignmentFlag.AlignBottom
        )

        main_layout.addWidget(self.button_container)
        main_layout.addStretch(1)

        # Initial State
        self.on_crawler_type_changed(self.crawler_type_combo.currentIndex())

    def setup_general_page(self):
        layout = QVBoxLayout(self.page_general)
        layout.setContentsMargins(0, 0, 0, 0)

        # Login Group
        login_group = QGroupBox("General Login Configuration")
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
        self.action_combo.addItems(
            [
                "Find Parent Link (<a>)",
                "Download Simple Thumbnail (Legacy)",
                "Extract High-Res Preview URL",
                "Open Link in New Tab",
                "Click Element by Text",
                "Wait for Page Load",
                "Wait X Seconds",
                "Switch to Last Tab",
                "Find Element by CSS Selector",
                "Find <img> Number X on Page",
                "Download Image from Element",
                "Download Current URL as Image",
                "Wait for Gallery (Context Reset)",
                "Scrape Text (Saves to JSON)",
                "Scan Page for Text and Skip if Found",
                "Close Current Tab",
                "Refresh Current Element",
            ]
        )
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
        self.action_list_widget.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.action_list_widget.customContextMenuRequested.connect(
            self.show_context_menu
        )
        act_layout.addWidget(self.action_list_widget)

        # List controls
        lc_layout = QHBoxLayout()
        self.rem_act_btn = QPushButton("Remove Selected")
        set_button_role(self.rem_act_btn, "danger")
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
        layout.addWidget(self.api_doc_link)  # Add here initially

        # Auth Group
        auth_group = QGroupBox("Authentication (Optional)")
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


__all__ = ["_UIBuilderMixin"]

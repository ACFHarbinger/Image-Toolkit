import os
import json
import shutil

from pathlib import Path
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QLineEdit,
    QRadioButton,
    QHBoxLayout,
    QLabel,
    QWidget,
    QSizePolicy,
    QScrollArea,
    QPushButton,
    QMessageBox,
    QComboBox,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QGroupBox,
    QFormLayout,
    QApplication,
    QTabWidget,
    QListWidget,
    QListWidgetItem,
    QFileDialog,
    QInputDialog,
    QDialog,
    QDialogButtonBox,
    QColorDialog,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QKeySequenceEdit,
)
from backend.src.constants import (
    IMAGE_TOOLKIT_DIR,
    DAEMON_CONFIG_PATH,
    THUMBNAIL_CACHE_DIR,
    ROOT_DIR,
    API_DIR,
)


class SettingsWindow(QWidget):
    """
    A standalone widget for the application settings, displayed as a modal window.
    """

    def __init__(self, parent=None):
        # Store a reference to the main window to call theme switching
        self.main_window_ref = parent

        super().__init__(None, Qt.Window)

        self.setWindowTitle("Application Settings")
        self.setMinimumSize(800, 600)  # Increased height slightly

        # Reference to the Vault Manager from MainWindow
        self.vault_manager = (
            self.main_window_ref.vault_manager if self.main_window_ref else None
        )

        # Load initial credentials and settings
        self.current_account_name = "N/A"
        self.initial_theme = "dark"  # Default theme
        self.active_tab_configs = {}
        self.system_profiles = {}  # Store loaded profiles
        self.preferences = {}

        if self.vault_manager:
            try:
                creds = self.vault_manager.load_account_credentials()
                self.current_account_name = creds.get("account_name", "N/A")
                self.initial_theme = creds.get("theme", "dark")
                self.active_tab_configs = creds.get("active_tab_configs", {})
                self.system_profiles = creds.get("system_preference_profiles", {})
                self.preferences = creds.get("preferences", {})
            except Exception:
                pass

        # Unpack preference values with defaults
        _p = self.preferences
        self.pref_thumbnail_size = _p.get("thumbnail_size", 180)
        self.pref_page_size = _p.get("page_size", 100)
        self.pref_confirm_deletions = _p.get("confirm_deletions", True)
        self.pref_send_to_trash = _p.get("send_to_trash", True)
        self.pref_found_cache = _p.get("found_cache_maxsize", 300)
        self.pref_selected_cache = _p.get("selected_cache_maxsize", 200)
        self.pref_initial_cache = _p.get("initial_cache_maxsize", 300)
        self.pref_restore_last_dir = _p.get("restore_last_dir", True)
        self.pref_recent_dirs_count = _p.get("recent_dirs_count", 10)
        self.pref_startup_category = _p.get("startup_category", "System Tools")
        self.pref_slideshow_min = _p.get("slideshow_interval_min", 5)
        self.pref_slideshow_sec = _p.get("slideshow_interval_sec", 0)
        self.pref_slideshow_order = _p.get("slideshow_order", "Sequential")
        self.pref_log_level = _p.get("log_level", "INFO")
        self.pref_file_logging = _p.get("file_logging_enabled", False)
        self.pref_extractor_seek_ms = _p.get("extractor_seek_ms", 100)
        self.pref_recent_extractions_count = _p.get("recent_extractions_count", 10)
        self.pref_session_recovery = _p.get("session_recovery_level", "None")
        self.pref_accent_dark = _p.get("accent_color_dark", "#00bcd4")
        self.pref_accent_light = _p.get("accent_color_light", "#007AFF")
        self.pref_font_scale = _p.get("font_scale", 100)
        self.pref_ui_density = _p.get("ui_density", "Comfortable")

        # --- Configuration Defaults State ---
        self.tab_defaults_config = self._load_tab_defaults_from_vault()
        self.current_loaded_config_name = None

        main_layout = QVBoxLayout(self)

        # Determine initial styles based on loaded vault theme
        is_light_theme = self.initial_theme == "light"

        # Theme colors for the header
        header_widget_bg = "#ffffff" if is_light_theme else "#2d2d30"
        header_label_color = "#1e1e1e" if is_light_theme else "white"
        accent_color = "#007AFF" if is_light_theme else "#00bcd4"

        # --- Header Bar ---
        header_widget = QWidget()
        header_widget.setObjectName("header_widget")
        header_widget.setStyleSheet(
            f"background-color: {header_widget_bg}; padding: 10px; border-bottom: 2px solid {accent_color};"
        )
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(10, 5, 10, 5)

        title_label = QLabel("Application Settings")
        title_label.setStyleSheet(
            f"color: {header_label_color}; font-size: 14pt; font-weight: bold;"
        )
        header_layout.addWidget(title_label)
        header_layout.addStretch(1)

        main_layout.addWidget(header_widget)
        # --- End Header Bar ---

        # --- Login Information Section ---
        login_groupbox = QGroupBox("Login/Account Information (Master Password Reset)")
        login_groupbox.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        login_layout = QFormLayout(login_groupbox)
        login_layout.setContentsMargins(10, 10, 10, 10)

        self.account_input = QLineEdit()
        self.account_input.setReadOnly(True)
        self.account_input.setText(self.current_account_name)

        self.new_password_input = QLineEdit()
        self.new_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_password_input.setPlaceholderText("Enter NEW Master Password to reset")

        login_layout.addRow(QLabel("Account Name:"), self.account_input)
        login_layout.addRow(QLabel("New Master Password:"), self.new_password_input)

        # --- Cryptography Vault Sync/Load Section ---
        vault_sync_groupbox = QGroupBox("Cryptography Vault Sync and Load")
        vault_sync_groupbox.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        vault_sync_layout = QVBoxLayout(vault_sync_groupbox)
        vault_sync_layout.setContentsMargins(10, 10, 10, 10)

        vault_sync_desc = QLabel(
            "Synchronize active cryptography files between your home directory (~/.image-toolkit/cryptography) "
            "and the repository templates (assets/cryptography)."
        )
        vault_sync_desc.setStyleSheet("color: #aaa; font-size: 11px;")
        vault_sync_desc.setWordWrap(True)
        vault_sync_layout.addWidget(vault_sync_desc)

        btn_layout = QHBoxLayout()
        self.btn_sync_vault = QPushButton("Sync Vault 📤")
        self.btn_sync_vault.setToolTip(
            "Copy active keystore, vault, and pepper files from ~/.image-toolkit/cryptography to the repository template directory."
        )
        self.btn_sync_vault.setStyleSheet(
            "background-color: #7b1fa2; color: white; font-weight: bold;"
        )
        self.btn_sync_vault.clicked.connect(self._sync_vault_to_assets)

        self.btn_load_vault = QPushButton("Load Vault 📥")
        self.btn_load_vault.setToolTip(
            "Overwrite active files in ~/.image-toolkit/cryptography with template files from the repository directory."
        )
        self.btn_load_vault.setStyleSheet(
            "background-color: #2c3e50; color: white; font-weight: bold;"
        )
        self.btn_load_vault.clicked.connect(self._load_vault_from_assets)

        btn_layout.addWidget(self.btn_sync_vault)
        btn_layout.addWidget(self.btn_load_vault)
        vault_sync_layout.addLayout(btn_layout)

        # --- Preferences Section ---
        prefs_groupbox = QGroupBox("Preferences")
        prefs_groupbox.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        prefs_layout = QVBoxLayout(prefs_groupbox)
        prefs_layout.setContentsMargins(10, 10, 10, 10)
        prefs_layout.addWidget(QLabel("<b>App Theme:</b>"))

        self.dark_theme_radio = QRadioButton("Dark Theme")
        self.light_theme_radio = QRadioButton("Light Theme")

        # Set the radio button based on the loaded initial theme
        if self.initial_theme == "light":
            self.light_theme_radio.setChecked(True)
        else:
            self.dark_theme_radio.setChecked(True)

        prefs_layout.addWidget(self.dark_theme_radio)
        prefs_layout.addWidget(self.light_theme_radio)

        # --- Active Default Configuration Selection ---
        prefs_layout.addSpacing(15)
        prefs_layout.addWidget(QLabel("<b>Startup Tab Configurations:</b>"))

        # Get categorized tab structure
        categorized_tabs = self._get_all_tab_names_categorized()
        self.startup_config_combos = {}

        # Use a top-level VBox for all categories
        all_categories_layout = QVBoxLayout()
        all_categories_layout.setSpacing(10)

        for category_name, display_names in categorized_tabs.items():
            if not display_names:
                continue

            # Add category label
            category_label = QLabel(f"--- {category_name} ---")
            category_label.setStyleSheet("font-weight: bold; margin-top: 5px;")
            all_categories_layout.addWidget(category_label)

            # Create a FormLayout for tabs within this category
            category_form_layout = QFormLayout()
            category_form_layout.setContentsMargins(10, 0, 0, 0)

            for display_name in display_names:
                combo = QComboBox()
                combo.addItem("None (Default)")

                # Get the class name for vault lookup
                tab_instance = self._get_tab_instance_by_display_name(display_name)
                tab_class_name = (
                    type(tab_instance).__name__ if tab_instance else display_name
                )

                # Populate with available saved configs for this tab class
                configs_for_tab = self.tab_defaults_config.get(tab_class_name, {})
                config_names = sorted(configs_for_tab.keys())
                combo.addItems(config_names)

                # Select the currently active config if it exists
                active_config = self.active_tab_configs.get(tab_class_name)
                if active_config and active_config in configs_for_tab:
                    combo.setCurrentText(active_config)

                # Store by class name so MainWindow can apply them correctly
                self.startup_config_combos[tab_class_name] = combo
                category_form_layout.addRow(f"{display_name}:", combo)

            all_categories_layout.addLayout(category_form_layout)

        prefs_layout.addLayout(all_categories_layout)

        # ---------------------------------------------------------------------
        # --- System Preference Profiles Section ---
        # ---------------------------------------------------------------------
        profiles_groupbox = QGroupBox("System Preference Profiles")
        profiles_groupbox.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        profiles_layout = QVBoxLayout(profiles_groupbox)

        # Row 1: Select Profile to Load, Update, or Delete
        profile_select_layout = QHBoxLayout()
        self.profile_combo = QComboBox()
        self.profile_combo.setPlaceholderText("Select Profile...")
        self._refresh_profile_combo()

        self.btn_load_profile = QPushButton("Load Profile")
        self.btn_load_profile.setToolTip(
            "Apply the selected profile's settings to the fields above"
        )
        self.btn_load_profile.clicked.connect(self._load_selected_profile)

        self.btn_use_profile = QPushButton("Use Profile")
        self.btn_use_profile.setToolTip(
            "Load the selected profile's settings and apply them to the app immediately"
        )
        self.btn_use_profile.setStyleSheet("background-color: #27ae60; color: white;")
        self.btn_use_profile.clicked.connect(self._use_selected_profile)

        self.btn_update_profile = QPushButton("Update Profile")
        self.btn_update_profile.setToolTip(
            "Update the selected profile with the current settings from the UI fields"
        )
        self.btn_update_profile.setStyleSheet(
            "background-color: #2980b9; color: white;"
        )
        self.btn_update_profile.clicked.connect(self._update_selected_profile)

        self.btn_delete_profile = QPushButton("Delete Profile")
        self.btn_delete_profile.setStyleSheet(
            "background-color: #e74c3c; color: white;"
        )
        self.btn_delete_profile.clicked.connect(self._delete_selected_profile)

        profile_select_layout.addWidget(QLabel("Profile:"))
        profile_select_layout.addWidget(self.profile_combo, 1)
        profile_select_layout.addWidget(self.btn_load_profile)
        profile_select_layout.addWidget(self.btn_use_profile)
        profile_select_layout.addWidget(self.btn_update_profile)
        profile_select_layout.addWidget(self.btn_delete_profile)

        profiles_layout.addLayout(profile_select_layout)

        # Row 2: Create New Profile
        profile_create_layout = QHBoxLayout()
        self.profile_name_input = QLineEdit()
        self.profile_name_input.setPlaceholderText(
            "New Profile Name (e.g., Work Laptop)"
        )

        self.btn_save_profile = QPushButton("Save Current Settings as Profile")
        self.btn_save_profile.setToolTip(
            "Save the current state of Theme and Tab Configs above as a new profile"
        )
        self.btn_save_profile.setStyleSheet("background-color: #2ecc71; color: white;")
        self.btn_save_profile.clicked.connect(self._save_current_as_profile)

        profile_create_layout.addWidget(QLabel("Name:"))
        profile_create_layout.addWidget(self.profile_name_input, 1)
        profile_create_layout.addWidget(self.btn_save_profile)

        profiles_layout.addLayout(profile_create_layout)

        # ---------------------------------------------------------------------
        # --- Tab Default Configuration Section ---
        # ---------------------------------------------------------------------
        defaults_groupbox = QGroupBox("Tab Default Configuration Management")
        defaults_groupbox.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        defaults_layout = QVBoxLayout(defaults_groupbox)

        # 1. Tab Selection
        tab_select_layout = QFormLayout()

        self.tab_group_combo = QComboBox()
        self.tab_group_combo.setPlaceholderText("Select a Tab Group...")
        categorized_tabs = self._get_all_tab_names_categorized()
        self.tab_group_combo.addItems([""] + sorted(categorized_tabs.keys()))
        self.tab_group_combo.currentTextChanged.connect(self._on_tab_group_changed)
        tab_select_layout.addRow("Select Tab Group:", self.tab_group_combo)

        self.tab_select_combo = QComboBox()
        self.tab_select_combo.setPlaceholderText("Select a Tab...")
        self.tab_select_combo.addItems([""])
        self.tab_select_combo.currentTextChanged.connect(self._refresh_config_dropdown)
        tab_select_layout.addRow("Select Tab Class:", self.tab_select_combo)
        defaults_layout.addLayout(tab_select_layout)

        # 2. Load Existing Configuration
        load_config_layout = QFormLayout()
        self.config_select_combo = QComboBox()
        self.config_select_combo.setPlaceholderText("Load/Edit Existing Config...")
        self.config_select_combo.currentTextChanged.connect(
            self._load_selected_tab_config
        )
        load_config_layout.addRow("Load/Edit Config:", self.config_select_combo)

        # Load/Delete/SET Buttons (Horizontal and full width)
        full_width_buttons_layout = QHBoxLayout()
        full_width_buttons_layout.setContentsMargins(
            0, 5, 0, 5
        )  # Optional spacing adjustment
        full_width_buttons_layout.setSpacing(10)  # Add spacing between the two buttons

        # NEW: Set Selected Config Button
        self.btn_set_config = QPushButton("Set Selected Config")
        self.btn_set_config.clicked.connect(self._set_selected_tab_config)
        # Set policy to expand horizontally
        self.btn_set_config.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        full_width_buttons_layout.addWidget(self.btn_set_config)

        # Existing Delete Button
        self.btn_delete_config = QPushButton("Delete Selected Config")
        self.btn_delete_config.setStyleSheet("background-color: #e74c3c; color: white;")
        self.btn_delete_config.clicked.connect(self._delete_selected_tab_config)
        # Set policy to expand horizontally
        self.btn_delete_config.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        full_width_buttons_layout.addWidget(self.btn_delete_config)

        # Add the config selection layout first
        defaults_layout.addLayout(load_config_layout)
        # Then add the new full-width, side-by-side buttons layout
        defaults_layout.addLayout(full_width_buttons_layout)

        # 3. Create/Edit Configuration
        create_config_group = QGroupBox("Create/Edit Configuration")
        create_config_layout = QFormLayout(create_config_group)

        self.config_name_input = QLineEdit()
        self.config_name_input.setPlaceholderText(
            "Enter a unique name (e.g., HighResConfig)"
        )
        create_config_layout.addRow("Config Name:", self.config_name_input)

        self.default_config_editor = QTextEdit()
        self.default_config_editor.setPlaceholderText(
            "Select a Tab Class to see its default configuration..."
        )
        self.default_config_editor.setMinimumHeight(200)
        create_config_layout.addRow("Configuration (JSON):", self.default_config_editor)

        # Buttons to save/create config
        save_buttons_layout = QHBoxLayout()

        self.btn_create_default = QPushButton("Save Named Configuration")
        self.btn_create_default.setToolTip(
            "Save the JSON currently in the editor as a new configuration"
        )
        self.btn_create_default.clicked.connect(self._save_current_tab_config)

        self.btn_save_current = QPushButton("Save Current Configuration")
        self.btn_save_current.setToolTip(
            "Capture current values from the active tab and save them"
        )
        self.btn_save_current.setStyleSheet(
            "background-color: #007AFF; color: white; font-weight: bold;"
        )
        self.btn_save_current.clicked.connect(self._capture_and_save_current_config)

        save_buttons_layout.addWidget(self.btn_create_default)
        save_buttons_layout.addWidget(self.btn_save_current)

        create_config_layout.addRow(save_buttons_layout)

        defaults_layout.addWidget(create_config_group)

        # ---------------------------------------------------------------------
        # --- Appearance Section ---
        # ---------------------------------------------------------------------
        appearance_groupbox = QGroupBox("Appearance")
        appearance_groupbox.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        appearance_layout = QFormLayout(appearance_groupbox)
        appearance_layout.setContentsMargins(10, 10, 10, 10)

        # Dark accent colour swatch + picker
        dark_accent_row = QHBoxLayout()
        self.dark_accent_swatch = QPushButton()
        self.dark_accent_swatch.setFixedSize(32, 22)
        self.dark_accent_swatch.setToolTip("Click to pick a custom accent colour for the dark theme")
        self._update_swatch(self.dark_accent_swatch, self.pref_accent_dark)
        self.dark_accent_swatch.clicked.connect(lambda: self._pick_accent_color("dark"))
        dark_accent_reset = QPushButton("Reset")
        dark_accent_reset.setFixedWidth(55)
        dark_accent_reset.clicked.connect(lambda: self._reset_accent("dark"))
        dark_accent_row.addWidget(self.dark_accent_swatch)
        dark_accent_row.addWidget(dark_accent_reset)
        dark_accent_row.addStretch()
        appearance_layout.addRow("Dark Theme Accent Colour:", dark_accent_row)

        # Light accent colour swatch + picker
        light_accent_row = QHBoxLayout()
        self.light_accent_swatch = QPushButton()
        self.light_accent_swatch.setFixedSize(32, 22)
        self.light_accent_swatch.setToolTip("Click to pick a custom accent colour for the light theme")
        self._update_swatch(self.light_accent_swatch, self.pref_accent_light)
        self.light_accent_swatch.clicked.connect(lambda: self._pick_accent_color("light"))
        light_accent_reset = QPushButton("Reset")
        light_accent_reset.setFixedWidth(55)
        light_accent_reset.clicked.connect(lambda: self._reset_accent("light"))
        light_accent_row.addWidget(self.light_accent_swatch)
        light_accent_row.addWidget(light_accent_reset)
        light_accent_row.addStretch()
        appearance_layout.addRow("Light Theme Accent Colour:", light_accent_row)

        # Font scale
        self.font_scale_spinbox = QSpinBox()
        self.font_scale_spinbox.setRange(80, 150)
        self.font_scale_spinbox.setSingleStep(10)
        self.font_scale_spinbox.setSuffix(" %")
        self.font_scale_spinbox.setValue(self.pref_font_scale)
        self.font_scale_spinbox.setToolTip(
            "Scale all UI text relative to the base 10pt size (applied on next theme reload)"
        )
        appearance_layout.addRow("Font Scale:", self.font_scale_spinbox)

        # UI density
        self.ui_density_combo = QComboBox()
        self.ui_density_combo.addItems(["Compact", "Comfortable", "Spacious"])
        self.ui_density_combo.setCurrentText(self.pref_ui_density)
        self.ui_density_combo.setToolTip(
            "Controls button padding and widget spacing throughout the app"
        )
        appearance_layout.addRow("UI Density:", self.ui_density_combo)

        # Preview button — applies current accent + density live without saving
        preview_row = QHBoxLayout()
        btn_preview_appearance = QPushButton("Preview")
        btn_preview_appearance.setFixedWidth(90)
        btn_preview_appearance.setToolTip("Apply the current accent/density settings live (does not save)")
        btn_preview_appearance.clicked.connect(self._preview_appearance)
        preview_row.addWidget(btn_preview_appearance)
        preview_row.addStretch()
        appearance_layout.addRow("", preview_row)

        # ---------------------------------------------------------------------
        # --- Gallery and Display Section ---
        # ---------------------------------------------------------------------
        gallery_groupbox = QGroupBox("Gallery and Display")
        gallery_groupbox.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        gallery_layout = QFormLayout(gallery_groupbox)
        gallery_layout.setContentsMargins(10, 10, 10, 10)

        self.thumbnail_size_spinbox = QSpinBox()
        self.thumbnail_size_spinbox.setRange(48, 512)
        self.thumbnail_size_spinbox.setSingleStep(16)
        self.thumbnail_size_spinbox.setValue(self.pref_thumbnail_size)
        self.thumbnail_size_spinbox.setToolTip(
            "Default thumbnail pixel size used across all gallery tabs (restart required)"
        )
        gallery_layout.addRow(
            "Default Thumbnail Size (px):", self.thumbnail_size_spinbox
        )

        self.page_size_combo = QComboBox()
        self.page_size_combo.addItems(["50", "100", "150", "200", "300"])
        self.page_size_combo.setCurrentText(str(self.pref_page_size))
        self.page_size_combo.setToolTip(
            "Default number of images loaded per gallery page (restart required)"
        )
        gallery_layout.addRow("Default Gallery Page Size:", self.page_size_combo)

        self.confirm_deletions_check = QCheckBox(
            "Require confirmation before deleting files"
        )
        self.confirm_deletions_check.setChecked(self.pref_confirm_deletions)
        gallery_layout.addRow(self.confirm_deletions_check)

        self.send_to_trash_check = QCheckBox(
            "Send deleted files to system trash instead of permanent removal"
        )
        self.send_to_trash_check.setChecked(self.pref_send_to_trash)
        gallery_layout.addRow(self.send_to_trash_check)

        # ---------------------------------------------------------------------
        # --- Media Player and Extractor Section ---
        # ---------------------------------------------------------------------
        media_groupbox = QGroupBox("Media Player and Extractor")
        media_groupbox.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        media_layout = QFormLayout(media_groupbox)
        media_layout.setContentsMargins(10, 10, 10, 10)

        self.extractor_seek_spinbox = QSpinBox()
        self.extractor_seek_spinbox.setRange(10, 5000)
        self.extractor_seek_spinbox.setSingleStep(10)
        self.extractor_seek_spinbox.setSuffix(" ms")
        self.extractor_seek_spinbox.setValue(self.pref_extractor_seek_ms)
        self.extractor_seek_spinbox.setToolTip(
            "Time interval to seek when using the mouse wheel or arrow keys in the Extractor tab"
        )
        media_layout.addRow("Extractor Seek Interval:", self.extractor_seek_spinbox)

        self.recent_extractions_spinbox = QSpinBox()
        self.recent_extractions_spinbox.setRange(1, 100)
        self.recent_extractions_spinbox.setValue(self.pref_recent_extractions_count)
        self.recent_extractions_spinbox.setToolTip(
            "Number of most recent extraction configurations/parameters to save"
        )
        media_layout.addRow(
            "Recent Extractions Limit:", self.recent_extractions_spinbox
        )

        # ---------------------------------------------------------------------
        # --- Startup and Session Section ---
        # ---------------------------------------------------------------------
        session_groupbox = QGroupBox("Startup and Session")
        session_groupbox.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        session_layout = QFormLayout(session_groupbox)
        session_layout.setContentsMargins(10, 10, 10, 10)

        category_names = list(self._get_tab_mapping().keys()) or [
            "System Tools",
            "Database Management",
            "Web Integration",
            "Deep Learning",
            "Image Edit",
        ]
        self.startup_category_combo = QComboBox()
        self.startup_category_combo.addItems(category_names)
        if self.pref_startup_category in category_names:
            self.startup_category_combo.setCurrentText(self.pref_startup_category)
        self.startup_category_combo.setToolTip(
            "Which tab group to show when the app launches"
        )
        session_layout.addRow("Default Startup Category:", self.startup_category_combo)

        self.restore_last_dir_check = QCheckBox(
            "Restore last browsed directory on startup"
        )
        self.restore_last_dir_check.setChecked(self.pref_restore_last_dir)
        session_layout.addRow(self.restore_last_dir_check)

        self.recent_dirs_spinbox = QSpinBox()
        self.recent_dirs_spinbox.setRange(3, 20)
        self.recent_dirs_spinbox.setValue(self.pref_recent_dirs_count)
        self.recent_dirs_spinbox.setToolTip(
            "How many recently browsed directories to remember per tab"
        )
        session_layout.addRow(
            "Recent Directories to Remember:", self.recent_dirs_spinbox
        )

        self.session_recovery_combo = QComboBox()
        self.session_recovery_combo.addItems(["None", "Current Tab", "All Tabs"])
        self.session_recovery_combo.setCurrentText(self.pref_session_recovery)
        self.session_recovery_combo.setToolTip(
            "Select the level of information to save during app shutdown to recover on next login."
        )
        session_layout.addRow("Session Recovery Level:", self.session_recovery_combo)

        # ---------------------------------------------------------------------
        # --- Performance and Cache Section ---
        # ---------------------------------------------------------------------
        perf_groupbox = QGroupBox("Performance and Cache")
        perf_groupbox.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        perf_layout = QFormLayout(perf_groupbox)
        perf_layout.setContentsMargins(10, 10, 10, 10)

        perf_layout.addRow(
            QLabel(
                "<i>LRU cache sizes control how many thumbnails stay in memory. "
                "Higher values use more RAM. Changes apply after restart.</i>"
            )
        )

        self.found_cache_spinbox = QSpinBox()
        self.found_cache_spinbox.setRange(50, 2000)
        self.found_cache_spinbox.setSingleStep(50)
        self.found_cache_spinbox.setValue(self.pref_found_cache)
        self.found_cache_spinbox.setToolTip(
            "Max thumbnails held in the 'found' gallery LRU cache"
        )
        perf_layout.addRow("Found Gallery LRU Cache Size:", self.found_cache_spinbox)

        self.selected_cache_spinbox = QSpinBox()
        self.selected_cache_spinbox.setRange(50, 1000)
        self.selected_cache_spinbox.setSingleStep(50)
        self.selected_cache_spinbox.setValue(self.pref_selected_cache)
        self.selected_cache_spinbox.setToolTip(
            "Max thumbnails held in the 'selected' gallery LRU cache"
        )
        perf_layout.addRow(
            "Selected Gallery LRU Cache Size:", self.selected_cache_spinbox
        )

        self.initial_cache_spinbox = QSpinBox()
        self.initial_cache_spinbox.setRange(50, 2000)
        self.initial_cache_spinbox.setSingleStep(50)
        self.initial_cache_spinbox.setValue(self.pref_initial_cache)
        self.initial_cache_spinbox.setToolTip(
            "Max thumbnails held in the wallpaper/single-gallery LRU cache"
        )
        perf_layout.addRow(
            "Wallpaper Gallery LRU Cache Size:", self.initial_cache_spinbox
        )

        # ---------------------------------------------------------------------
        # --- Slideshow Defaults Section ---
        # ---------------------------------------------------------------------
        slideshow_groupbox = QGroupBox("Slideshow Defaults")
        slideshow_groupbox.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        slideshow_def_layout = QFormLayout(slideshow_groupbox)
        slideshow_def_layout.setContentsMargins(10, 10, 10, 10)

        interval_widget = QWidget()
        interval_layout = QHBoxLayout(interval_widget)
        interval_layout.setContentsMargins(0, 0, 0, 0)
        self.slideshow_default_min_spinbox = QSpinBox()
        self.slideshow_default_min_spinbox.setRange(0, 60)
        self.slideshow_default_min_spinbox.setValue(self.pref_slideshow_min)
        self.slideshow_default_min_spinbox.setFixedWidth(60)
        self.slideshow_default_sec_spinbox = QSpinBox()
        self.slideshow_default_sec_spinbox.setRange(0, 59)
        self.slideshow_default_sec_spinbox.setValue(self.pref_slideshow_sec)
        self.slideshow_default_sec_spinbox.setFixedWidth(60)
        interval_layout.addWidget(self.slideshow_default_min_spinbox)
        interval_layout.addWidget(QLabel("min"))
        interval_layout.addWidget(self.slideshow_default_sec_spinbox)
        interval_layout.addWidget(QLabel("sec"))
        interval_layout.addStretch(1)
        slideshow_def_layout.addRow("Default Interval:", interval_widget)

        self.slideshow_default_order_combo = QComboBox()
        self.slideshow_default_order_combo.addItems(
            ["Sequential", "Reverse Sequential", "Random"]
        )
        self.slideshow_default_order_combo.setCurrentText(self.pref_slideshow_order)
        slideshow_def_layout.addRow(
            "Default Playback Order:", self.slideshow_default_order_combo
        )

        # ---------------------------------------------------------------------
        # --- Logging Section ---
        # ---------------------------------------------------------------------
        logging_groupbox = QGroupBox("Logging")
        logging_groupbox.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        logging_layout = QFormLayout(logging_groupbox)
        logging_layout.setContentsMargins(10, 10, 10, 10)

        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.log_level_combo.setCurrentText(self.pref_log_level)
        self.log_level_combo.setToolTip(
            "Minimum severity level to write to the log (DEBUG = most verbose)"
        )
        logging_layout.addRow("Log Level:", self.log_level_combo)

        self.file_logging_check = QCheckBox(
            "Save logs to ~/.image-toolkit/logs/ (rotating, 5 × 1 MB)"
        )
        self.file_logging_check.setChecked(self.pref_file_logging)
        logging_layout.addRow(self.file_logging_check)

        log_dir_label = QLabel(
            f"<small>Log directory: {IMAGE_TOOLKIT_DIR / 'logs'}</small>"
        )
        log_dir_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        logging_layout.addRow(log_dir_label)

        log_buttons_layout = QHBoxLayout()
        self.btn_view_logs = QPushButton("View App Logs")
        self.btn_view_logs.setToolTip(
            "Open the active application log file in the default system viewer."
        )
        self.btn_view_logs.clicked.connect(self._view_app_logs)

        self.btn_view_daemon_logs = QPushButton("View Daemon Logs")
        self.btn_view_daemon_logs.setToolTip(
            "Open the slideshow daemon log file in the default system viewer."
        )
        self.btn_view_daemon_logs.clicked.connect(self._view_daemon_logs)

        log_buttons_layout.addWidget(self.btn_view_logs)
        log_buttons_layout.addWidget(self.btn_view_daemon_logs)
        logging_layout.addRow(log_buttons_layout)

        # ---------------------------------------------------------------------
        # --- Reset State Section ---
        # ---------------------------------------------------------------------
        reset_groupbox = QGroupBox("Reset State")
        reset_groupbox.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        reset_state_layout = QVBoxLayout(reset_groupbox)
        reset_state_layout.setContentsMargins(10, 10, 10, 10)
        reset_state_layout.setSpacing(8)

        reset_state_layout.addWidget(
            QLabel("<b>Warning:</b> these actions are immediate and cannot be undone.")
        )

        # Row 1: thumbnail cache
        cache_row = QHBoxLayout()
        cache_info = QLabel(
            f"<small>Disk thumbnail cache: <code>{THUMBNAIL_CACHE_DIR}</code></small>"
        )
        cache_info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.btn_clear_cache = QPushButton("Clear Thumbnail Cache")
        self.btn_clear_cache.setToolTip(
            "Delete all cached thumbnail files from disk. "
            "They will be regenerated on next gallery load."
        )
        self.btn_clear_cache.setStyleSheet(
            "background-color: #e67e22; color: white; font-weight: bold;"
        )
        self.btn_clear_cache.clicked.connect(self._clear_thumbnail_cache)
        cache_row.addWidget(cache_info, 1)
        cache_row.addWidget(self.btn_clear_cache)
        reset_state_layout.addLayout(cache_row)

        # Row 2: slideshow daemon reset
        daemon_row = QHBoxLayout()
        daemon_info = QLabel(
            "<small>Stops the daemon, removes its PID file, "
            "and deletes the slideshow config JSON file.</small>"
        )
        daemon_info.setWordWrap(True)
        self.btn_reset_daemon = QPushButton("Reset Slideshow Daemon")
        self.btn_reset_daemon.setToolTip(
            "Delete the daemon PID file and remove the slideshow config JSON file."
        )
        self.btn_reset_daemon.setStyleSheet(
            "background-color: #e67e22; color: white; font-weight: bold;"
        )
        self.btn_reset_daemon.clicked.connect(self._reset_slideshow_daemon)
        daemon_row.addWidget(daemon_info, 1)
        daemon_row.addWidget(self.btn_reset_daemon)
        reset_state_layout.addLayout(daemon_row)

        # Row 2.5: reset extraction history
        history_row = QHBoxLayout()
        history_info = QLabel(
            "<small>Delete the central extraction history JSON file containing parameters and file associations.</small>"
        )
        history_info.setWordWrap(True)
        self.btn_reset_history = QPushButton("Reset Extraction History")
        self.btn_reset_history.setToolTip(
            "Deletes the .extraction_history.json file on disk and resets the dropdown selection list."
        )
        self.btn_reset_history.setStyleSheet(
            "background-color: #e67e22; color: white; font-weight: bold;"
        )
        self.btn_reset_history.clicked.connect(self._reset_extraction_history)
        history_row.addWidget(history_info, 1)
        history_row.addWidget(self.btn_reset_history)
        reset_state_layout.addLayout(history_row)

        # Row 3: clear logs
        logs_row = QHBoxLayout()
        logs_info = QLabel(
            f"<small>Application and daemon logs directory: <code>{IMAGE_TOOLKIT_DIR / 'logs'}</code></small>"
        )
        logs_info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.btn_clear_logs = QPushButton("Clear All Logs")
        self.btn_clear_logs.setToolTip(
            "Delete all application and daemon log files from disk."
        )
        self.btn_clear_logs.setStyleSheet(
            "background-color: #e67e22; color: white; font-weight: bold;"
        )
        self.btn_clear_logs.clicked.connect(self._clear_application_logs)
        logs_row.addWidget(logs_info, 1)
        logs_row.addWidget(self.btn_clear_logs)
        reset_state_layout.addLayout(logs_row)

        # Row 4: tab configs + system profiles
        tab_cfg_row = QHBoxLayout()
        tab_cfg_info = QLabel(
            "<small>Removes all saved tab configurations, active tab config "
            "assignments, and system preference profiles from the vault.</small>"
        )
        tab_cfg_info.setWordWrap(True)
        self.btn_clear_tab_configs = QPushButton("Clear Tab Configs and Profiles")
        self.btn_clear_tab_configs.setToolTip(
            "Wipe tab_configurations, active_tab_configs, and "
            "system_preference_profiles from the vault."
        )
        self.btn_clear_tab_configs.setStyleSheet(
            "background-color: #c0392b; color: white; font-weight: bold;"
        )
        self.btn_clear_tab_configs.clicked.connect(self._clear_tab_configs)
        tab_cfg_row.addWidget(tab_cfg_info, 1)
        tab_cfg_row.addWidget(self.btn_clear_tab_configs)
        reset_state_layout.addLayout(tab_cfg_row)

        # --- Credentials Management Section ---
        credentials_groupbox = QGroupBox("Manage Loaded Credentials")
        credentials_groupbox.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        credentials_layout = QVBoxLayout(credentials_groupbox)
        credentials_layout.setContentsMargins(10, 10, 10, 10)

        credentials_desc = QLabel(
            "Manage API credentials loaded in your secure session vault. "
            "You can export unencrypted versions of these files to the backup directory, "
            "import new JSON credential files, or delete existing credentials."
        )
        credentials_desc.setStyleSheet("color: #aaa; font-size: 11px;")
        credentials_desc.setWordWrap(True)
        credentials_layout.addWidget(credentials_desc)

        self.credentials_list = QListWidget()
        self.credentials_list.setMinimumHeight(120)
        self.credentials_list.setMaximumHeight(200)
        self.credentials_list.itemDoubleClicked.connect(self._edit_credential)
        credentials_layout.addWidget(self.credentials_list)

        creds_btn_layout = QHBoxLayout()
        self.btn_export_creds = QPushButton("Export to Backup 📤")
        self.btn_export_creds.setToolTip("Export unencrypted versions of loaded credentials to the backup directory.")
        self.btn_export_creds.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold;")
        self.btn_export_creds.clicked.connect(self._export_credentials_to_backup)

        self.btn_import_cred = QPushButton("Import Credential 📥")
        self.btn_import_cred.setToolTip("Select a new JSON credential file to encrypt and load into the vault.")
        self.btn_import_cred.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold;")
        self.btn_import_cred.clicked.connect(self._import_credential)

        self.btn_edit_cred = QPushButton("Edit Credential ✏️")
        self.btn_edit_cred.setToolTip("View and edit the JSON values of the selected credential.")
        self.btn_edit_cred.setStyleSheet("background-color: #f39c12; color: white; font-weight: bold;")
        self.btn_edit_cred.clicked.connect(self._edit_credential)

        self.btn_delete_cred = QPushButton("Delete Credential ❌")
        self.btn_delete_cred.setToolTip("Delete the selected credential from the vault and disk.")
        self.btn_delete_cred.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold;")
        self.btn_delete_cred.clicked.connect(self._delete_credential)

        creds_btn_layout.addWidget(self.btn_export_creds)
        creds_btn_layout.addWidget(self.btn_import_cred)
        creds_btn_layout.addWidget(self.btn_edit_cred)
        creds_btn_layout.addWidget(self.btn_delete_cred)
        credentials_layout.addLayout(creds_btn_layout)

        # --- Create QTabWidget and Add Tabs ---
        self.tab_widget = QTabWidget()

        # Modern Premium Theme Styles for QTabWidget
        if is_light_theme:
            self.tab_widget.setStyleSheet(
                "QTabWidget::pane { border: 1px solid #dcdcdc; background: white; }"
                "QTabBar::tab { background: #f0f0f0; color: #333; padding: 10px 15px; border: 1px solid #dcdcdc; border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px; }"
                "QTabBar::tab:selected { background: white; border-bottom: 2px solid #007AFF; font-weight: bold; }"
                "QTabBar::tab:hover { background: #e5e5e5; }"
            )
        else:
            self.tab_widget.setStyleSheet(
                "QTabWidget::pane { border: 1px solid #3e3e42; background: #1e1e1e; }"
                "QTabBar::tab { background: #2d2d30; color: #aaa; padding: 10px 15px; border: 1px solid #3e3e42; border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px; }"
                "QTabBar::tab:selected { background: #1e1e1e; color: white; border-bottom: 2px solid #00bcd4; font-weight: bold; }"
                "QTabBar::tab:hover { background: #3e3e42; color: white; }"
            )

        def create_tab_scroll_area():
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet(
                "QScrollArea { border: none; background: transparent; }"
            )
            container = QWidget()
            layout = QVBoxLayout(container)
            layout.setContentsMargins(15, 15, 15, 15)
            layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            layout.setSpacing(15)
            scroll.setWidget(container)
            return scroll, layout

        # Tab 1: Account and Cryptography
        scroll_account, layout_account = create_tab_scroll_area()
        layout_account.addWidget(login_groupbox)
        layout_account.addWidget(vault_sync_groupbox)
        layout_account.addWidget(credentials_groupbox)
        layout_account.addStretch(1)
        self.tab_widget.addTab(scroll_account, "🔐 Account and Vault")

        # Tab 2: Startup and Profiles
        scroll_startup, layout_startup = create_tab_scroll_area()
        layout_startup.addWidget(prefs_groupbox)
        layout_startup.addWidget(session_groupbox)
        layout_startup.addWidget(profiles_groupbox)
        layout_startup.addStretch(1)
        self.tab_widget.addTab(scroll_startup, "🚀 Startup and Profiles")

        # Tab 3: Tab Configurations
        scroll_configs, layout_configs = create_tab_scroll_area()
        layout_configs.addWidget(defaults_groupbox)
        layout_configs.addStretch(1)
        self.tab_widget.addTab(scroll_configs, "🛠️ Tab Configs")

        # Tab 4: Display and Media
        scroll_display_media, layout_display_media = create_tab_scroll_area()
        layout_display_media.addWidget(appearance_groupbox)
        layout_display_media.addWidget(gallery_groupbox)
        layout_display_media.addWidget(media_groupbox)
        layout_display_media.addWidget(slideshow_groupbox)
        layout_display_media.addStretch(1)
        self.tab_widget.addTab(scroll_display_media, "🖼️ Display and Media")

        # Tab 5: System and Logging
        scroll_system, layout_system = create_tab_scroll_area()
        layout_system.addWidget(perf_groupbox)
        layout_system.addWidget(logging_groupbox)
        layout_system.addWidget(reset_groupbox)
        layout_system.addStretch(1)
        self.tab_widget.addTab(scroll_system, "⚙️ System and Logging")

        # Tab 6: Keyboard Shortcuts (GUI/UX §2.29)
        scroll_kb, layout_kb = create_tab_scroll_area()
        layout_kb.addWidget(self._build_shortcuts_groupbox())
        layout_kb.addStretch(1)
        self.tab_widget.addTab(scroll_kb, "⌨️ Shortcuts")

        main_layout.addWidget(self.tab_widget)

        # --- Action Buttons at the bottom (Full Width) ---
        actions_widget = QWidget()
        actions_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        actions_layout = QHBoxLayout(actions_widget)
        actions_layout.setContentsMargins(20, 10, 20, 20)
        actions_layout.setSpacing(10)

        # 1. Reset Button
        self.reset_button = QPushButton("Reset to default")
        self.reset_button.setObjectName("reset_button")
        self.reset_button.clicked.connect(self.reset_settings)
        self.reset_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # 1.5. Reload Button (New) 🆕
        self.reload_button = QPushButton("Reload settings")
        self.reload_button.setObjectName("reload_button")
        self.reload_button.setStyleSheet(
            "background-color: #34495e; color: white; font-weight: bold;"
        )
        self.reload_button.clicked.connect(self.reload_settings)
        self.reload_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # 2. Refresh Button (New) 🆕
        self.refresh_button = QPushButton("Refresh Application (Relaunch) 🔄")
        self.refresh_button.setObjectName("refresh_button")
        self.refresh_button.setStyleSheet(
            "background-color: #f1c40f; color: black; font-weight: bold;"
        )
        self.refresh_button.clicked.connect(self._refresh_application)
        self.refresh_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # 3. Update Button
        self.update_button = QPushButton("Update settings")
        self.update_button.setObjectName("update_button")
        self.update_button.clicked.connect(self.confirm_update_settings)
        self.update_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.update_button.setDefault(True)

        actions_layout.addWidget(self.reset_button)
        actions_layout.addWidget(self.reload_button)
        actions_layout.addWidget(self.refresh_button)  # Added refresh button
        actions_layout.addWidget(self.update_button)

        main_layout.addWidget(actions_widget)

        # Populate credentials list
        self._refresh_credentials_list()

    # ---------------------------------------------------------------------
    # --- Profile Management Methods ---
    # ---------------------------------------------------------------------

    def _refresh_profile_combo(self):
        """Updates the profile selection dropdown."""
        self.profile_combo.clear()
        if self.system_profiles:
            self.profile_combo.addItems(sorted(self.system_profiles.keys()))

    def _get_current_ui_preferences(self):
        """Helper to gather current theme and tab config selections."""
        theme = "light" if self.light_theme_radio.isChecked() else "dark"

        current_tab_configs = {}
        for tab_name, combo in self.startup_config_combos.items():
            selected = combo.currentText()
            if selected != "None (Default)":
                current_tab_configs[tab_name] = selected

        return {"theme": theme, "active_tab_configs": current_tab_configs}

    def _save_current_as_profile(self):
        """Saves current UI preferences as a new profile."""
        name = self.profile_name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "Please enter a profile name.")
            return

        profile_data = self._get_current_ui_preferences()

        try:
            # 1. Update in-memory
            self.system_profiles[name] = profile_data

            # 2. Update vault
            creds = self.vault_manager.load_account_credentials()
            creds["system_preference_profiles"] = self.system_profiles
            if self._save_vault_data(creds):
                QMessageBox.information(self, "Success", f"Profile '{name}' saved.")
                self.profile_name_input.clear()
                self._refresh_profile_combo()
                self.profile_combo.setCurrentText(name)
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save profile: {e}")

    def _update_selected_profile(self):
        """Updates the selected profile with the current theme and tab config selections from the UI."""
        name = self.profile_combo.currentText()
        if not name:
            QMessageBox.warning(self, "Error", "No profile selected to update.")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Update",
            f"Are you sure you want to update the profile '{name}' with the current settings?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        profile_data = self._get_current_ui_preferences()

        try:
            # 1. Update in-memory
            self.system_profiles[name] = profile_data

            # 2. Update vault
            creds = self.vault_manager.load_account_credentials()
            creds["system_preference_profiles"] = self.system_profiles
            if self._save_vault_data(creds):
                QMessageBox.information(
                    self, "Success", f"Profile '{name}' updated successfully."
                )
        except Exception as e:
            QMessageBox.critical(self, "Update Error", f"Failed to update profile: {e}")

    def reload_settings(self):
        """Reloads settings from the vault and re-populates the form fields, allowing newly created tab configurations to appear."""
        if self.vault_manager:
            try:
                creds = self.vault_manager.load_account_credentials()
                self.current_account_name = creds.get("account_name", "N/A")
                self.initial_theme = creds.get("theme", "dark")
                self.active_tab_configs = creds.get("active_tab_configs", {})
                self.system_profiles = creds.get("system_preference_profiles", {})
                self.preferences = creds.get("preferences", {})
            except Exception as e:
                QMessageBox.critical(
                    self, "Error", f"Failed to load credentials from vault:\n{e}"
                )
                return

        # Unpack preference values with defaults
        _p = self.preferences
        self.pref_thumbnail_size = _p.get("thumbnail_size", 180)
        self.pref_page_size = _p.get("page_size", 100)
        self.pref_confirm_deletions = _p.get("confirm_deletions", True)
        self.pref_send_to_trash = _p.get("send_to_trash", True)
        self.pref_found_cache = _p.get("found_cache_maxsize", 300)
        self.pref_selected_cache = _p.get("selected_cache_maxsize", 200)
        self.pref_initial_cache = _p.get("initial_cache_maxsize", 300)
        self.pref_restore_last_dir = _p.get("restore_last_dir", True)
        self.pref_recent_dirs_count = _p.get("recent_dirs_count", 10)
        self.pref_startup_category = _p.get("startup_category", "System Tools")
        self.pref_slideshow_min = _p.get("slideshow_interval_min", 5)
        self.pref_slideshow_sec = _p.get("slideshow_interval_sec", 0)
        self.pref_slideshow_order = _p.get("slideshow_order", "Sequential")
        self.pref_log_level = _p.get("log_level", "INFO")
        self.pref_file_logging = _p.get("file_logging_enabled", False)
        self.pref_extractor_seek_ms = _p.get("extractor_seek_ms", 100)
        self.pref_recent_extractions_count = _p.get("recent_extractions_count", 10)
        self.pref_session_recovery = _p.get("session_recovery_level", "None")
        self.pref_accent_dark = _p.get("accent_color_dark", "#00bcd4")
        self.pref_accent_light = _p.get("accent_color_light", "#007AFF")
        self.pref_font_scale = _p.get("font_scale", 100)
        self.pref_ui_density = _p.get("ui_density", "Comfortable")

        # Reload tab defaults from vault
        self.tab_defaults_config = self._load_tab_defaults_from_vault()

        # Update UI components
        self.new_password_input.clear()
        self.account_input.setText(self.current_account_name)

        if self.initial_theme == "light":
            self.light_theme_radio.setChecked(True)
            self.dark_theme_radio.setChecked(False)
        else:
            self.dark_theme_radio.setChecked(True)
            self.light_theme_radio.setChecked(False)

        # Repopulate startup config combos so that they include newly created tab configurations!
        for tab_class_name, combo in self.startup_config_combos.items():
            current_sel = self.active_tab_configs.get(tab_class_name, "None (Default)")
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("None (Default)")

            configs_for_tab = self.tab_defaults_config.get(tab_class_name, {})
            config_names = sorted(configs_for_tab.keys())
            combo.addItems(config_names)

            # Select active config if it exists
            if current_sel and current_sel in configs_for_tab:
                combo.setCurrentText(current_sel)
            else:
                combo.setCurrentIndex(0)
            combo.blockSignals(False)

        # Repopulate Gallery and Display
        self.thumbnail_size_spinbox.setValue(self.pref_thumbnail_size)
        self.page_size_combo.setCurrentText(str(self.pref_page_size))
        self.confirm_deletions_check.setChecked(self.pref_confirm_deletions)
        self.send_to_trash_check.setChecked(self.pref_send_to_trash)

        # Repopulate Startup and Session
        items = [
            self.startup_category_combo.itemText(i)
            for i in range(self.startup_category_combo.count())
        ]
        if self.pref_startup_category in items:
            self.startup_category_combo.setCurrentText(self.pref_startup_category)
        self.restore_last_dir_check.setChecked(self.pref_restore_last_dir)
        self.recent_dirs_spinbox.setValue(self.pref_recent_dirs_count)
        self.session_recovery_combo.setCurrentText(self.pref_session_recovery)

        # Repopulate Performance and Cache
        self.found_cache_spinbox.setValue(self.pref_found_cache)
        self.selected_cache_spinbox.setValue(self.pref_selected_cache)
        self.initial_cache_spinbox.setValue(self.pref_initial_cache)

        # Repopulate Slideshow Defaults
        self.slideshow_default_min_spinbox.setValue(self.pref_slideshow_min)
        self.slideshow_default_sec_spinbox.setValue(self.pref_slideshow_sec)
        self.slideshow_default_order_combo.setCurrentText(self.pref_slideshow_order)

        # Repopulate Logging
        self.log_level_combo.setCurrentText(self.pref_log_level)
        self.file_logging_check.setChecked(self.pref_file_logging)

        # Repopulate Extractor
        self.extractor_seek_spinbox.setValue(self.pref_extractor_seek_ms)
        self.recent_extractions_spinbox.setValue(self.pref_recent_extractions_count)

        # Repopulate Appearance
        self._update_swatch(self.dark_accent_swatch, self.pref_accent_dark)
        self._update_swatch(self.light_accent_swatch, self.pref_accent_light)
        self.font_scale_spinbox.setValue(self.pref_font_scale)
        self.ui_density_combo.setCurrentText(self.pref_ui_density)

        # Repopulate Profiles dropdown
        self._refresh_profile_combo()

        # Reset Tab Defaults dropdown
        self.tab_group_combo.setCurrentIndex(0)
        self.tab_select_combo.clear()
        self.tab_select_combo.addItems([""])
        self.config_select_combo.clear()
        self.config_name_input.clear()
        self.default_config_editor.clear()

        # Refresh credentials list on reload
        self._refresh_credentials_list()

        QMessageBox.information(
            self, "Settings Reloaded", "Settings reloaded from the vault successfully."
        )

    def _load_selected_profile(self):
        """Loads the selected profile into the UI elements."""
        name = self.profile_combo.currentText()
        if not name or name not in self.system_profiles:
            return

        profile_data = self.system_profiles[name]

        # Apply Theme
        theme = profile_data.get("theme", "dark")
        if theme == "light":
            self.light_theme_radio.setChecked(True)
        else:
            self.dark_theme_radio.setChecked(True)

        # Apply Tab Configs
        saved_configs = profile_data.get("active_tab_configs", {})
        for tab_name, combo in self.startup_config_combos.items():
            if tab_name in saved_configs:
                # Check if the config actually exists in the options
                index = combo.findText(saved_configs[tab_name])
                if index >= 0:
                    combo.setCurrentIndex(index)
                else:
                    combo.setCurrentIndex(0)  # Default
            else:
                combo.setCurrentIndex(0)  # Default

        QMessageBox.information(
            self,
            "Profile Loaded",
            f"Settings from '{name}' loaded into the form. Click 'Update settings' to apply them to the app.",
        )

    def _use_selected_profile(self):
        """Loads the selected profile into the UI and applies it immediately."""
        name = self.profile_combo.currentText()
        if not name or name not in self.system_profiles:
            return

        # Load it into UI fields (but skip the QMessageBox)
        profile_data = self.system_profiles[name]

        theme = profile_data.get("theme", "dark")
        if theme == "light":
            self.light_theme_radio.setChecked(True)
        else:
            self.dark_theme_radio.setChecked(True)

        saved_configs = profile_data.get("active_tab_configs", {})
        for tab_name, combo in self.startup_config_combos.items():
            if tab_name in saved_configs:
                index = combo.findText(saved_configs[tab_name])
                if index >= 0:
                    combo.setCurrentIndex(index)
                else:
                    combo.setCurrentIndex(0)
            else:
                combo.setCurrentIndex(0)

        # Apply immediately by triggering the update logic
        self._update_settings_logic()

    def _delete_selected_profile(self):
        """Deletes the selected profile."""
        name = self.profile_combo.currentText()
        if not name:
            return

        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete profile '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                del self.system_profiles[name]

                # Update vault
                creds = self.vault_manager.load_account_credentials()
                creds["system_preference_profiles"] = self.system_profiles
                if self._save_vault_data(creds):
                    QMessageBox.information(
                        self, "Success", f"Profile '{name}' deleted."
                    )
                    self._refresh_profile_combo()
            except Exception as e:
                QMessageBox.critical(
                    self, "Delete Error", f"Failed to delete profile: {e}"
                )

    # ---------------------------------------------------------------------
    # --- Configuration Management Methods ---
    # ---------------------------------------------------------------------

    def _get_tab_mapping(self):
        """
        Retrieves the tab structure from the main window reference, if available.
        This defines the category -> tab_name -> tab_instance mapping.
        """
        if not self.main_window_ref or not hasattr(self.main_window_ref, "all_tabs"):
            return {}
        return self.main_window_ref.all_tabs

    def _get_all_tab_names_uncategorized(self):
        """
        Helper to flatten the MainWindow's tab structure into a sorted list of unique
        tab class names.
        """
        tab_map = {}
        for category, sub_tabs in self._get_tab_mapping().items():
            for tab_instance in sub_tabs.values():
                class_name = type(tab_instance).__name__
                if class_name not in tab_map:
                    tab_map[class_name] = True
        return sorted(tab_map.keys())

    def _get_all_tab_names_categorized(self):
        """
        Helper to return a dictionary of {Category Name: [Tab Display Names]}
        """
        categorized_tabs = {}
        for category, sub_tabs in self._get_tab_mapping().items():
            # Use the display labels (keys) instead of class names
            categorized_tabs[category] = sorted(list(sub_tabs.keys()))

        return categorized_tabs

    def _get_tab_instance_by_display_name(self, display_name: str):
        """Finds the active instance of a tab by its display name from all_tabs mapping."""
        if not display_name:
            return None

        for category, sub_tabs in self._get_tab_mapping().items():
            if display_name in sub_tabs:
                return sub_tabs[display_name]
        return None

    def _on_tab_group_changed(self, group_name: str):
        try:
            self.tab_select_combo.currentTextChanged.disconnect(
                self._refresh_config_dropdown
            )
        except RuntimeError:
            pass

        self.tab_select_combo.clear()

        if not group_name:
            self.tab_select_combo.addItems([""])
        else:
            categorized_tabs = self._get_all_tab_names_categorized()
            tabs_in_group = categorized_tabs.get(group_name, [])
            self.tab_select_combo.addItems([""] + tabs_in_group)

        self.tab_select_combo.currentTextChanged.connect(self._refresh_config_dropdown)
        self._refresh_config_dropdown(self.tab_select_combo.currentText())

    def _load_tab_defaults_from_vault(self):
        """Loads all named tab configurations from the secure vault."""
        if not self.vault_manager:
            return {}
        try:
            full_data = self.vault_manager.load_account_credentials()
            return full_data.get("tab_configurations", {})
        except Exception as e:
            print(f"Warning: Failed to load tab defaults from vault: {e}")
            return {}

    def _save_vault_data(self, data: dict):
        """Helper function to save the full user data dictionary back to the vault."""
        if not self.vault_manager:
            QMessageBox.critical(
                self, "Save Error", "Vault manager is not available to save settings."
            )
            return False

        try:
            self.vault_manager.save_data(json.dumps(data))
            return True
        except Exception as e:
            QMessageBox.critical(
                self, "Save Error", f"Failed to save data to vault:\n{e}"
            )
            return False

    def _save_tab_defaults_to_vault(self):
        """Saves the entire current tab configuration state back to the secure vault."""
        if not self.vault_manager:
            QMessageBox.critical(
                self, "Save Error", "Vault manager is not available to save settings."
            )
            return False

        try:
            user_data = self.vault_manager.load_account_credentials()
            user_data["tab_configurations"] = self.tab_defaults_config
            return self._save_vault_data(user_data)
        except Exception as e:
            QMessageBox.critical(
                self, "Save Error", f"Failed to prepare data for saving:\n{e}"
            )
            return False

    def _populate_default_config(self, tab_display_name: str):
        """Populates the text editor with the default config from the selected tab display name."""
        self.config_name_input.clear()  # Clear config name
        tab_instance = self._get_tab_instance_by_display_name(tab_display_name)

        if tab_instance and hasattr(tab_instance, "get_default_config"):
            try:
                default_config = tab_instance.get_default_config()
                default_json = json.dumps(default_config, indent=4)
                self.default_config_editor.setText(default_json)
                self.default_config_editor.setPlaceholderText(
                    "Edit the default config below or create a new named config..."
                )
            except Exception as e:
                self.default_config_editor.clear()
                self.default_config_editor.setPlaceholderText(
                    f"Error loading default config: {e}"
                )
        else:
            self.default_config_editor.clear()
            self.default_config_editor.setPlaceholderText(
                "This tab does not have a 'get_default_config' method."
            )

    def _refresh_config_dropdown(self, tab_display_name: str):
        """
        Populates the config dropdown based on the selected tab display name AND
        populates the editor with the default config for that tab.
        """

        try:
            self.config_select_combo.currentTextChanged.disconnect(
                self._load_selected_tab_config
            )
        except RuntimeError:
            pass

        self.config_select_combo.clear()
        self.current_loaded_config_name = None

        if not tab_display_name:
            self.config_select_combo.setPlaceholderText("Select a Tab first.")
            self.config_name_input.clear()
            self.default_config_editor.clear()
            self.default_config_editor.setPlaceholderText(
                "Select a Tab to see its default configuration..."
            )
        else:
            # Get class name for config lookup
            instance = self._get_tab_instance_by_display_name(tab_display_name)
            tab_class_name = type(instance).__name__ if instance else ""

            # Populate the editor with the default config FIRST
            self._populate_default_config(tab_display_name)

            # Now, populate the dropdown with saved configs for this tab class
            configs = self.tab_defaults_config.get(tab_class_name, {})
            config_names = sorted(configs.keys())

            self.config_select_combo.addItems([""] + config_names)
            self.config_select_combo.setPlaceholderText("Load/Edit Existing Config...")

        # Reconnect the signal
        self.config_select_combo.currentTextChanged.connect(
            self._load_selected_tab_config
        )

    def _load_selected_tab_config(self, config_name: str):
        """
        Loads a selected configuration's JSON into the editor.
        If config_name is empty, it re-loads the default config.
        """
        tab_display_name = self.tab_select_combo.currentText()

        if not tab_display_name:
            self.config_name_input.clear()
            self.default_config_editor.clear()
            self.current_loaded_config_name = None
            return

        instance = self._get_tab_instance_by_display_name(tab_display_name)
        tab_class_name = type(instance).__name__ if instance else ""

        if not config_name:
            # User selected the blank placeholder, so load the default config
            self._populate_default_config(tab_display_name)
            self.current_loaded_config_name = None
            return

        # User selected a specific, saved config
        configs = self.tab_defaults_config.get(tab_class_name, {})
        config = configs.get(config_name, {})

        try:
            json_str = json.dumps(config, indent=4)
            self.default_config_editor.setText(json_str)
            self.config_name_input.setText(config_name)
            self.current_loaded_config_name = config_name
        except Exception as e:
            QMessageBox.critical(
                self, "Load Error", f"Failed to load config '{config_name}': {e}"
            )
            # On error, fall back to default
            self._populate_default_config(tab_display_name)
            self.current_loaded_config_name = None

    def _save_current_tab_config(self):
        """Parses the editor content and saves it as a new or updated named configuration."""
        tab_display_name = self.tab_select_combo.currentText()
        config_name = self.config_name_input.text().strip()
        json_text = self.default_config_editor.toPlainText().strip()

        if not tab_display_name or not config_name:
            QMessageBox.warning(
                self,
                "Input Error",
                "Please select a Tab and provide a Config Name.",
            )
            return

        instance = self._get_tab_instance_by_display_name(tab_display_name)
        tab_class_name = type(instance).__name__ if instance else ""

        if not json_text:
            QMessageBox.warning(
                self, "Input Error", "Configuration JSON cannot be empty."
            )
            return

        try:
            new_config = json.loads(json_text)
            if not isinstance(new_config, dict):
                raise ValueError("Configuration must be a valid JSON object.")

            if tab_class_name not in self.tab_defaults_config:
                self.tab_defaults_config[tab_class_name] = {}

            self.tab_defaults_config[tab_class_name][config_name] = new_config

            if self._save_tab_defaults_to_vault():
                QMessageBox.information(
                    self,
                    "Success",
                    f"Configuration '{config_name}' saved for {tab_display_name}.",
                )

                self._refresh_config_dropdown(tab_display_name)
                self.config_select_combo.setCurrentText(config_name)

        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "JSON Error", f"Invalid JSON format:\n{e}")
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"An unexpected error occurred during save: {e}"
            )

    def _capture_and_save_current_config(self):
        """
        Captures the current values from the active tab instance,
        populates the JSON editor, and triggers the save workflow.
        """
        tab_display_name = self.tab_select_combo.currentText()
        if not tab_display_name:
            QMessageBox.warning(self, "Error", "Please select a Tab first.")
            return

        tab_instance = self._get_tab_instance_by_display_name(tab_display_name)
        if not tab_instance:
            QMessageBox.warning(
                self, "Error", "Could not find active tab instance to capture from."
            )
            return

        if not hasattr(tab_instance, "collect"):
            QMessageBox.warning(
                self,
                "Error",
                f"The tab '{tab_display_name}' does not support capturing current configuration (missing 'collect' method).",
            )
            return

        try:
            # Capture data from the live tab
            config_data = tab_instance.collect()

            # Populate editor
            json_str = json.dumps(config_data, indent=4)
            self.default_config_editor.setText(json_str)

            # If the user has already entered a name, we can try to save immediately.
            # If not, _save_current_tab_config will show the validation warning.
            self._save_current_tab_config()

        except Exception as e:
            QMessageBox.critical(
                self, "Capture Error", f"Failed to capture configuration: {e}"
            )

    def _delete_selected_tab_config(self):
        """Deletes the currently selected configuration from the in-memory state and the vault."""
        tab_display_name = self.tab_select_combo.currentText()
        config_name = self.config_select_combo.currentText()

        if not tab_display_name or not config_name:
            QMessageBox.warning(
                self,
                "Delete Error",
                "Please select a tab and a configuration to delete.",
            )
            return

        instance = self._get_tab_instance_by_display_name(tab_display_name)
        tab_class_name = type(instance).__name__ if instance else ""

        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to PERMANENTLY delete the configuration '{config_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                if (
                    tab_class_name in self.tab_defaults_config
                    and config_name in self.tab_defaults_config[tab_class_name]
                ):
                    del self.tab_defaults_config[tab_class_name][config_name]

                    if not self.tab_defaults_config[tab_class_name]:
                        del self.tab_defaults_config[tab_class_name]

                    if self._save_tab_defaults_to_vault():
                        QMessageBox.information(
                            self, "Success", f"Configuration '{config_name}' deleted."
                        )
                        self.config_name_input.clear()
                        self.default_config_editor.clear()
                        self._refresh_config_dropdown(tab_display_name)

            except Exception as e:
                QMessageBox.critical(
                    self, "Delete Error", f"Failed to delete configuration: {e}"
                )

    def _set_selected_tab_config(self):
        """
        Applies the configuration currently loaded in the editor to the active
        instance of the selected tab in the MainWindow.
        """
        tab_display_name = self.tab_select_combo.currentText()
        config_name = self.config_name_input.text().strip()
        json_text = self.default_config_editor.toPlainText().strip()

        if not tab_display_name or not (config_name or json_text):
            QMessageBox.warning(
                self,
                "Set Error",
                "Please select a tab and ensure config JSON is loaded.",
            )
            return

        try:
            config_data = json.loads(json_text)

            target_tab_instance = self._get_tab_instance_by_display_name(
                tab_display_name
            )

            if not target_tab_instance:
                QMessageBox.critical(
                    self,
                    "Set Error",
                    f"Could not find active instance of tab: {tab_display_name}.",
                )
                return

            tab_class_name = type(target_tab_instance).__name__

            if hasattr(target_tab_instance, "set_config") and callable(
                target_tab_instance.set_config
            ):
                target_tab_instance.set_config(config_data)

                config_display_name = (
                    f"'{config_name}'" if config_name else "'(Default)'"
                )
                QMessageBox.information(
                    self,
                    "Success",
                    f"Configuration {config_display_name} applied to {tab_display_name}.",
                )
            else:
                QMessageBox.critical(
                    self,
                    "Set Error",
                    f"Target tab '{tab_display_name}' ({tab_class_name}) does not have a 'set_config' method.",
                )

        except json.JSONDecodeError as e:
            QMessageBox.critical(
                self,
                "JSON Error",
                f"Invalid JSON in editor. Cannot apply configuration:\n{e}",
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"An unexpected error occurred during configuration application: {e}",
            )

    # ---------------------------------------------------------------------
    # --- Relaunch / Other Settings Methods ---
    # ---------------------------------------------------------------------

    def _refresh_application(self):
        """Prompts for confirmation and triggers a full application relaunch."""
        reply = QMessageBox.question(
            self,
            "Confirm Relaunch",
            "Are you sure you want to refresh the application? This will close all windows and relaunch.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            if self.main_window_ref and hasattr(
                self.main_window_ref, "restart_application"
            ):
                # Assuming restart_application handles closing the current instance and starting a new one
                self.main_window_ref.restart_application()
            else:
                # Fallback solution: close current app and advise user to restart
                QMessageBox.critical(
                    self,
                    "Relaunch Error",
                    "Cannot automatically restart. Closing the application now. Please relaunch the main script manually.",
                )
                QApplication.quit()

    def confirm_update_settings(self):
        """Shows a confirmation dialog before calling update_settings_logic."""

        reply = QMessageBox.question(
            self,
            "Confirm Update",
            "Are you sure you want to update the app's settings?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self._update_settings_logic()

    def _update_settings_logic(self):
        """Saves settings (theme preference, and potentially new password) and closes the window."""
        new_password = self.new_password_input.text().strip()
        selected_theme = "dark" if self.dark_theme_radio.isChecked() else "light"

        if not self.vault_manager:
            QMessageBox.critical(
                self, "Update Failed", "Vault manager is not available."
            )
            return

        # --- Handle Password Change (Master Reset) ---
        if new_password:
            try:
                self.vault_manager.update_account_password(
                    self.current_account_name, new_password
                )

                if self.main_window_ref:
                    self.main_window_ref.update_header()

                QMessageBox.information(
                    self,
                    "Success",
                    "Master password successfully updated! All data was preserved.",
                )

            except Exception as e:
                QMessageBox.critical(
                    self, "Update Failed", f"Failed to update master password:\n{e}"
                )
                return

        # --- Handle Theme Change and Preferences ---
        try:
            user_data = self.vault_manager.load_account_credentials()
            user_data["theme"] = selected_theme

            new_active_configs = {}
            for tab_name, combo in self.startup_config_combos.items():
                selected = combo.currentText()
                if selected != "None (Default)":
                    new_active_configs[tab_name] = selected

            user_data["active_tab_configs"] = new_active_configs
            user_data["system_preference_profiles"] = self.system_profiles

            # Persist new preference settings
            user_data["preferences"] = {
                "thumbnail_size": self.thumbnail_size_spinbox.value(),
                "page_size": int(self.page_size_combo.currentText()),
                "confirm_deletions": self.confirm_deletions_check.isChecked(),
                "send_to_trash": self.send_to_trash_check.isChecked(),
                "found_cache_maxsize": self.found_cache_spinbox.value(),
                "selected_cache_maxsize": self.selected_cache_spinbox.value(),
                "initial_cache_maxsize": self.initial_cache_spinbox.value(),
                "restore_last_dir": self.restore_last_dir_check.isChecked(),
                "recent_dirs_count": self.recent_dirs_spinbox.value(),
                "startup_category": self.startup_category_combo.currentText(),
                "slideshow_interval_min": self.slideshow_default_min_spinbox.value(),
                "slideshow_interval_sec": self.slideshow_default_sec_spinbox.value(),
                "slideshow_order": self.slideshow_default_order_combo.currentText(),
                "log_level": self.log_level_combo.currentText(),
                "file_logging_enabled": self.file_logging_check.isChecked(),
                "extractor_seek_ms": self.extractor_seek_spinbox.value(),
                "recent_extractions_count": self.recent_extractions_spinbox.value(),
                "session_recovery_level": self.session_recovery_combo.currentText(),
                "accent_color_dark": self.pref_accent_dark,
                "accent_color_light": self.pref_accent_light,
                "font_scale": self.font_scale_spinbox.value(),
                "ui_density": self.ui_density_combo.currentText(),
            }

            if self._save_vault_data(user_data):
                if self.main_window_ref:
                    self.main_window_ref.cached_creds = user_data
                    if selected_theme:
                        self.main_window_ref.set_application_theme(selected_theme)
                    if hasattr(self.main_window_ref, "_apply_startup_preferences"):
                        self.main_window_ref._apply_startup_preferences()
                    if hasattr(self.main_window_ref, "_apply_active_tab_configs"):
                        self.main_window_ref._apply_active_tab_configs()
                    QMessageBox.information(
                        self, "Success", "Settings updated and saved successfully."
                    )

        except Exception as e:
            QMessageBox.critical(
                self, "Update Failed", f"Failed to save preferences to vault:\n{e}"
            )
            return

        self.close()

    def reset_settings(self):
        """Resets settings fields to hardcoded defaults."""
        self.new_password_input.clear()

        self.dark_theme_radio.setChecked(True)
        self.light_theme_radio.setChecked(False)

        # Reset startup config combo boxes
        for combo in self.startup_config_combos.values():
            combo.setCurrentIndex(0)  # None (Default)

        # Reset Gallery and Display
        self.thumbnail_size_spinbox.setValue(180)
        self.page_size_combo.setCurrentText("100")
        self.confirm_deletions_check.setChecked(True)
        self.send_to_trash_check.setChecked(True)

        # Reset Startup and Session
        items = [
            self.startup_category_combo.itemText(i)
            for i in range(self.startup_category_combo.count())
        ]
        if "System Tools" in items:
            self.startup_category_combo.setCurrentText("System Tools")
        self.restore_last_dir_check.setChecked(True)
        self.recent_dirs_spinbox.setValue(10)
        self.session_recovery_combo.setCurrentText("None")

        # Reset Performance and Cache
        self.found_cache_spinbox.setValue(300)
        self.selected_cache_spinbox.setValue(200)
        self.initial_cache_spinbox.setValue(300)

        # Reset Slideshow Defaults
        self.slideshow_default_min_spinbox.setValue(5)
        self.slideshow_default_sec_spinbox.setValue(0)
        self.slideshow_default_order_combo.setCurrentText("Sequential")

        # Reset Logging
        self.log_level_combo.setCurrentText("INFO")
        self.file_logging_check.setChecked(False)

        # Reset Extractor
        self.extractor_seek_spinbox.setValue(100)
        self.recent_extractions_spinbox.setValue(10)

        # Reset Appearance
        self.pref_accent_dark = "#00bcd4"
        self.pref_accent_light = "#007AFF"
        self._update_swatch(self.dark_accent_swatch, "#00bcd4")
        self._update_swatch(self.light_accent_swatch, "#007AFF")
        self.font_scale_spinbox.setValue(100)
        self.ui_density_combo.setCurrentText("Comfortable")

    # ------------------------------------------------------------------
    # --- Keyboard Shortcuts Helpers (GUI/UX §2.29) -------------------
    # ------------------------------------------------------------------

    def _build_shortcuts_groupbox(self) -> QGroupBox:
        """Build the shortcuts table + action buttons groupbox."""
        from ..utils.shortcut_manager import get_registry, SHORTCUT_REGISTRY

        grp = QGroupBox("Keyboard Shortcuts")
        grp.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        vbox = QVBoxLayout(grp)
        vbox.setContentsMargins(10, 10, 10, 10)

        # Info label
        info = QLabel(
            "Rebind any action by clicking its key cell. Changes take effect on next app launch "
            "(preview window shortcuts apply when a new preview is opened)."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #aaa; font-size: 10px;")
        vbox.addWidget(info)

        # Also show the user_theme.qss hint here as a bonus
        user_qss_path = str(Path.home() / ".image-toolkit" / "user_theme.qss")
        qss_hint = QLabel(
            f"<b>Custom QSS override (§2.31):</b> create <code>{user_qss_path}</code> "
            "to append your own QSS rules on top of the active theme."
        )
        qss_hint.setWordWrap(True)
        qss_hint.setStyleSheet("color: #aaa; font-size: 10px; margin-bottom: 6px;")
        vbox.addWidget(qss_hint)

        # Build table
        reg = get_registry()
        entries = reg.get_all()

        self._shortcut_table = QTableWidget(len(entries), 3)
        self._shortcut_table.setHorizontalHeaderLabels(["Scope", "Action", "Binding"])
        self._shortcut_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._shortcut_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._shortcut_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._shortcut_table.verticalHeader().setVisible(False)
        self._shortcut_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._shortcut_table.setSelectionMode(QTableWidget.NoSelection)
        self._shortcut_table.setAlternatingRowColors(True)

        self._shortcut_editors: dict[str, QKeySequenceEdit] = {}

        for row, entry in enumerate(entries):
            scope_item = QTableWidgetItem(entry["scope"])
            scope_item.setFlags(Qt.ItemIsEnabled)
            desc_item = QTableWidgetItem(entry["description"])
            desc_item.setFlags(Qt.ItemIsEnabled)
            self._shortcut_table.setItem(row, 0, scope_item)
            self._shortcut_table.setItem(row, 1, desc_item)

            editor = QKeySequenceEdit(QKeySequence(entry["current"]))
            editor.setToolTip(f"Default: {entry['default']}")
            self._shortcut_editors[entry["id"]] = editor
            self._shortcut_table.setCellWidget(row, 2, editor)

        vbox.addWidget(self._shortcut_table)

        # Buttons row
        btn_row = QHBoxLayout()
        btn_save_kb = QPushButton("Save Shortcuts")
        btn_save_kb.setToolTip("Write shortcut overrides to ~/.image-toolkit/keybindings.json")
        btn_save_kb.clicked.connect(self._save_shortcuts)
        btn_reset_kb = QPushButton("Reset All to Defaults")
        btn_reset_kb.setToolTip("Clear all overrides and delete keybindings.json")
        btn_reset_kb.clicked.connect(self._reset_shortcuts)
        btn_row.addWidget(btn_save_kb)
        btn_row.addWidget(btn_reset_kb)
        btn_row.addStretch()
        vbox.addLayout(btn_row)
        return grp

    def _save_shortcuts(self) -> None:
        from ..utils.shortcut_manager import get_registry, SHORTCUT_REGISTRY
        reg = get_registry()
        defaults = {e["id"]: e["default"] for e in SHORTCUT_REGISTRY}
        overrides: dict[str, str] = {}
        conflicts: list[str] = []

        for action_id, editor in self._shortcut_editors.items():
            seq = editor.keySequence()
            key_str = seq.toString() if not seq.isEmpty() else ""
            if key_str and key_str != defaults.get(action_id, ""):
                # Conflict detection: same binding as another action
                for other_id, other_editor in self._shortcut_editors.items():
                    if other_id == action_id:
                        continue
                    if other_editor.keySequence().toString() == key_str:
                        conflicts.append(f"{action_id} ↔ {other_id} (both: {key_str})")
            if key_str:
                overrides[action_id] = key_str

        if conflicts:
            msg = "Conflicting shortcuts detected:\n" + "\n".join(conflicts)
            msg += "\n\nSave anyway?"
            reply = QMessageBox.question(self, "Shortcut Conflict", msg,
                                         QMessageBox.Yes | QMessageBox.No)
            if reply != QMessageBox.Yes:
                return

        reg.save(overrides)
        QMessageBox.information(
            self, "Saved",
            "Shortcuts saved. Changes take effect on next app launch."
        )

    def _reset_shortcuts(self) -> None:
        from ..utils.shortcut_manager import get_registry, SHORTCUT_REGISTRY
        reply = QMessageBox.question(
            self, "Reset Shortcuts",
            "Reset all shortcuts to defaults and delete keybindings.json?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        get_registry().reset()
        defaults = {e["id"]: e["default"] for e in SHORTCUT_REGISTRY}
        for action_id, editor in self._shortcut_editors.items():
            editor.setKeySequence(QKeySequence(defaults.get(action_id, "")))
        QMessageBox.information(self, "Reset", "All shortcuts reset to defaults.")

    # ------------------------------------------------------------------
    # --- Appearance Helpers -------------------------------------------
    # ------------------------------------------------------------------

    def _update_swatch(self, button, hex_color):
        """Paint a colour swatch onto a QPushButton."""
        c = QColor(hex_color)
        if not c.isValid():
            c = QColor("#888888")
        button.setStyleSheet(
            f"QPushButton {{ background-color: {c.name()}; border: 1px solid #888; border-radius: 3px; }}"
        )
        button.setText("")

    def _pick_accent_color(self, theme):
        """Open QColorDialog and update the swatch + stored preference."""
        current = self.pref_accent_dark if theme == "dark" else self.pref_accent_light
        initial = QColor(current)
        color = QColorDialog.getColor(
            initial,
            self,
            f"Choose {theme.capitalize()} Theme Accent Colour",
            QColorDialog.ColorDialogOption.DontUseNativeDialog,
        )
        if color.isValid():
            hex_val = color.name()
            if theme == "dark":
                self.pref_accent_dark = hex_val
                self._update_swatch(self.dark_accent_swatch, hex_val)
            else:
                self.pref_accent_light = hex_val
                self._update_swatch(self.light_accent_swatch, hex_val)

    def _reset_accent(self, theme):
        """Reset accent colour to the built-in default."""
        default = "#00bcd4" if theme == "dark" else "#007AFF"
        if theme == "dark":
            self.pref_accent_dark = default
            self._update_swatch(self.dark_accent_swatch, default)
        else:
            self.pref_accent_light = default
            self._update_swatch(self.light_accent_swatch, default)

    def _preview_appearance(self):
        """Apply current accent/density/font settings live without saving."""
        if not self.main_window_ref:
            return
        if not hasattr(self.main_window_ref, "cached_creds") or not self.main_window_ref.cached_creds:
            return
        prefs = dict(self.main_window_ref.cached_creds.get("preferences", {}))
        prefs["accent_color_dark"] = self.pref_accent_dark
        prefs["accent_color_light"] = self.pref_accent_light
        prefs["font_scale"] = self.font_scale_spinbox.value()
        prefs["ui_density"] = self.ui_density_combo.currentText()
        self.main_window_ref.cached_creds["preferences"] = prefs
        theme = self.main_window_ref.current_theme
        self.main_window_ref.set_application_theme(theme)

    # ------------------------------------------------------------------
    # --- Reset State Methods ------------------------------------------
    # ------------------------------------------------------------------

    def _clear_thumbnail_cache(self):
        """Deletes all cached thumbnail files from the disk cache directory."""
        reply = QMessageBox.question(
            self,
            "Confirm Clear",
            f"Delete all thumbnail cache files in:\n{THUMBNAIL_CACHE_DIR}\n\n"
            "Thumbnails will be regenerated on the next gallery load.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            if THUMBNAIL_CACHE_DIR.exists():
                shutil.rmtree(str(THUMBNAIL_CACHE_DIR))
                THUMBNAIL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
                deleted_msg = "Thumbnail cache cleared successfully."
            else:
                deleted_msg = (
                    "Thumbnail cache directory did not exist — nothing to clear."
                )
            QMessageBox.information(self, "Cache Cleared", deleted_msg)
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to clear thumbnail cache:\n{e}"
            )

    def _reset_slideshow_daemon(self):
        """Stops the daemon, deletes its PID file, and deletes the config JSON file."""
        reply = QMessageBox.question(
            self,
            "Confirm Reset",
            "This will:\n"
            f"  • Delete the PID file ({IMAGE_TOOLKIT_DIR / '.slideshow.pid'})\n"
            f"  • Delete the slideshow config file ({DAEMON_CONFIG_PATH})\n\n"
            "The daemon will stop if it is currently running. Log files will NOT be deleted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        messages = []
        errors = []

        pid_path = IMAGE_TOOLKIT_DIR / ".slideshow.pid"
        try:
            if pid_path.exists():
                pid_path.unlink()
                messages.append("Deleted PID file.")
            else:
                messages.append("PID file not found (already clean).")
        except Exception as e:
            errors.append(f"Could not delete PID file: {e}")

        try:
            if DAEMON_CONFIG_PATH.exists():
                DAEMON_CONFIG_PATH.unlink()
                messages.append("Deleted slideshow config file.")
            else:
                messages.append("Slideshow config file not found (already clean).")
        except Exception as e:
            errors.append(f"Could not delete slideshow config file: {e}")

        summary = "\n".join(messages)
        if errors:
            QMessageBox.warning(
                self,
                "Partial Reset",
                f"Completed with issues:\n{summary}\n\nErrors:\n" + "\n".join(errors),
            )
        else:
            QMessageBox.information(self, "Daemon Reset", summary)

    def _reset_extraction_history(self):
        """Deletes the .extraction_history.json file and clears the UI dropdown."""
        history_file = IMAGE_TOOLKIT_DIR / ".extraction_history.json"
        reply = QMessageBox.question(
            self,
            "Confirm Reset",
            f"Are you sure you want to delete the extraction history file?\n\n{history_file}\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            if history_file.exists():
                history_file.unlink()
                QMessageBox.information(
                    self, "Success", "Extraction history file deleted successfully."
                )
            else:
                QMessageBox.information(
                    self,
                    "Information",
                    "Extraction history file not found (already clean).",
                )

            # Immediately notify tabs to reload / clear history
            if self.main_window_ref:
                for cat_tabs in self.main_window_ref.all_tabs.values():
                    for tab in cat_tabs.values():
                        if hasattr(tab, "_load_extraction_history") and callable(
                            tab._load_extraction_history
                        ):
                            tab._load_extraction_history()
                        if hasattr(tab, "_update_recent_extractions_ui") and callable(
                            tab._update_recent_extractions_ui
                        ):
                            tab._update_recent_extractions_ui()
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to reset extraction history:\n{e}"
            )

    def _view_app_logs(self):
        """Opens the application log file in the default system viewer."""
        log_path = IMAGE_TOOLKIT_DIR / "logs" / "image_toolkit.log"
        if not log_path.exists():
            QMessageBox.information(
                self, "No Logs", "No application log file found yet."
            )
            return

        try:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_path)))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open log file:\n{e}")

    def _view_daemon_logs(self):
        """Opens the daemon log file in the default system viewer."""
        log_path = IMAGE_TOOLKIT_DIR / "logs" / "slideshow_daemon.log"
        if not log_path.exists():
            QMessageBox.information(self, "No Logs", "No daemon log file found yet.")
            return

        try:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_path)))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open daemon log file:\n{e}")

    def _clear_application_logs(self):
        """Deletes all log files from the global logs directory."""
        log_dir = IMAGE_TOOLKIT_DIR / "logs"
        reply = QMessageBox.question(
            self,
            "Confirm Clear Logs",
            f"Delete all application and daemon log files in:\n{log_dir}?\n\n"
            "This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            if log_dir.exists():
                # Delete all contents but keep the directory
                for item in log_dir.iterdir():
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(str(item))
                deleted_msg = "All logs cleared successfully."
            else:
                deleted_msg = "Log directory did not exist — nothing to clear."
            QMessageBox.information(self, "Logs Cleared", deleted_msg)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to clear logs:\n{e}")

    def _clear_tab_configs(self):
        """Wipes all tab configurations, active assignments, and system profiles from the vault."""
        reply = QMessageBox.question(
            self,
            "Confirm Clear",
            "This will permanently remove:\n"
            "  • All saved tab configurations\n"
            "  • All active tab config assignments\n"
            "  • All system preference profiles\n\n"
            "This cannot be undone. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        if not self.vault_manager:
            QMessageBox.critical(self, "Error", "Vault manager is not available.")
            return

        try:
            user_data = self.vault_manager.load_account_credentials()
            user_data["tab_configurations"] = {}
            user_data["active_tab_configs"] = {}
            user_data["system_preference_profiles"] = {}
            user_data["session_recovery_data"] = {}

            # Clear the encrypted session recovery file if it exists
            try:
                username = getattr(self.vault_manager, "account_name", None)
                if username:
                    for recovery_dir in (
                        "/home/pkhunter/.image-toolkit/recovery",
                        os.path.expanduser("~/.image-toolkit/recovery"),
                    ):
                        enc_file_path = os.path.join(
                            recovery_dir, f"recovery_{username}.enc"
                        )
                        if os.path.exists(enc_file_path):
                            os.remove(enc_file_path)
            except Exception as e:
                print(f"Warning: Failed to delete recovery file: {e}")

            if self._save_vault_data(user_data):
                # Reset in-memory state
                self.tab_defaults_config = {}
                self.active_tab_configs = {}
                self.system_profiles = {}

                # Reset UI combo boxes
                for combo in self.startup_config_combos.values():
                    combo.clear()
                    combo.addItem("None (Default)")
                self._refresh_profile_combo()

                QMessageBox.information(
                    self,
                    "Cleared",
                    "All tab configurations and system profiles have been removed.",
                )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to clear tab configs:\n{e}")

    def _sync_vault_to_assets(self):
        """
        Sync active files from ~/.image-toolkit/cryptography to the assets/cryptography template directory.
        """
        from backend.src.constants import TEMPLATE_CRYPTO_DIR, CRYPTO_DIR

        active_dir = Path(CRYPTO_DIR)
        template_dir = Path(TEMPLATE_CRYPTO_DIR)

        if not active_dir.exists():
            QMessageBox.warning(
                self, "Sync Error", "Active cryptography directory does not exist."
            )
            return

        template_dir.mkdir(parents=True, exist_ok=True)

        # List of files to sync
        files_to_sync = []
        for item in active_dir.iterdir():
            if item.is_file():
                files_to_sync.append(item.name)

        if not files_to_sync:
            QMessageBox.information(
                self,
                "Sync Vault",
                "No cryptographic files found in active directory to sync.",
            )
            return

        try:
            for fname in files_to_sync:
                src = active_dir / fname
                dst = template_dir / fname
                shutil.copy2(src, dst)
                print(f"[SettingsWindow] Synced {src} -> {dst}")

            QMessageBox.information(
                self,
                "Sync Vault Success",
                f"Successfully synced {len(files_to_sync)} cryptographic file(s) to template directory:\n{template_dir}",
            )
        except Exception as e:
            QMessageBox.critical(self, "Sync Error", f"Failed to sync vault files: {e}")

    def _load_vault_from_assets(self):
        """
        Load (overwrite) active files in ~/.image-toolkit/cryptography with ones from the assets/cryptography template directory.
        """
        from backend.src.constants import TEMPLATE_CRYPTO_DIR, CRYPTO_DIR

        active_dir = Path(CRYPTO_DIR)
        template_dir = Path(TEMPLATE_CRYPTO_DIR)

        if not template_dir.exists():
            QMessageBox.warning(
                self,
                "Load Error",
                "Repository template cryptography directory does not exist.",
            )
            return

        # Confirm overwrite
        reply = QMessageBox.question(
            self,
            "Confirm Load Vault",
            "This will OVERWRITE your active cryptography files in ~/.image-toolkit/cryptography with the template files. "
            "Are you sure you want to proceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        active_dir.mkdir(parents=True, exist_ok=True)

        # List of files to load
        files_to_load = []
        for item in template_dir.iterdir():
            if item.is_file():
                files_to_load.append(item.name)

        if not files_to_load:
            QMessageBox.information(
                self,
                "Load Vault",
                "No template files found in assets directory to load.",
            )
            return

        try:
            for fname in files_to_load:
                src = template_dir / fname
                dst = active_dir / fname
                shutil.copy2(src, dst)
                print(f"[SettingsWindow] Loaded {src} -> {dst}")

            QMessageBox.information(
                self,
                "Load Vault Success",
                f"Successfully loaded {len(files_to_load)} cryptographic file(s) to active directory:\n{active_dir}\nPlease restart the application to apply.",
            )
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to load vault files: {e}")

    # ---------------------------------------------------------------------
    # --- Credential Management Methods ---
    # ---------------------------------------------------------------------

    def _refresh_credentials_list(self):
        """Clears and repopulates the list widget from self.vault_manager.api_credentials."""
        self.credentials_list.clear()
        if self.vault_manager and hasattr(self.vault_manager, "api_credentials"):
            for key in sorted(self.vault_manager.api_credentials.keys()):
                self.credentials_list.addItem(key)

    def _export_credentials_to_backup(self):
        """Exports unencrypted versions of loaded credentials to the backup directory."""
        if not self.vault_manager:
            QMessageBox.warning(self, "Export Failed", "Vault manager is not available.")
            return

        if not hasattr(self.vault_manager, "api_credentials") or not self.vault_manager.api_credentials:
            QMessageBox.information(
                self, "Export Credentials", "No credentials loaded in current vault session."
            )
            return

        backup_dir = ROOT_DIR / "backup"
        try:
            backup_dir.mkdir(parents=True, exist_ok=True)
            exported_files = []

            # 1. Export all loaded api_credentials from vault memory
            for key, val in self.vault_manager.api_credentials.items():
                dest_file = backup_dir / f"{key}.json"
                with open(dest_file, "w", encoding="utf-8") as f:
                    json.dump(val, f, indent=4)
                exported_files.append(dest_file.name)

            # 2. Also copy token.json if present in API_DIR
            token_src = Path(API_DIR) / "token.json"
            if token_src.exists():
                token_dst = backup_dir / "token.json"
                shutil.copy2(token_src, token_dst)
                if "token.json" not in exported_files:
                    exported_files.append("token.json")

            summary_msg = "Successfully exported the following credentials to backup directory:\n\n"
            summary_msg += "\n".join(f"  • {name}" for name in sorted(exported_files))
            summary_msg += f"\n\nPath: {backup_dir}"
            
            QMessageBox.information(self, "Export Success", summary_msg)
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Failed to export credentials: {e}")

    def _import_credential(self):
        """Selects a new JSON credential file to encrypt and load into the vault."""
        if not self.vault_manager or not self.vault_manager.secret_key:
            QMessageBox.warning(self, "Import Failed", "Vault manager or security key is not available.")
            return

        # 1. Browse for JSON file
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import JSON Credential File", str(Path.home()), "JSON (*.json)"
        )
        if not file_path:
            return

        # 2. Read and validate JSON content
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                json_content = f.read()
            # Validate JSON
            api_data = json.loads(json_content)
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to read or parse JSON file: {e}")
            return

        # 3. Prompt user for alias/name
        default_alias = Path(file_path).stem
        alias, ok = QInputDialog.getText(
            self,
            "Credential Alias",
            "Enter a name/alias for this credential:",
            QLineEdit.EchoMode.Normal,
            default_alias,
        )
        if not ok or not alias.strip():
            return
        alias = alias.strip()

        # 4. Encrypt and save to API_DIR
        try:
            api_dir_path = Path(API_DIR)
            api_dir_path.mkdir(parents=True, exist_ok=True)
            enc_file_path = str(api_dir_path / f"{alias}.json.enc")
            raw_json_path = str(api_dir_path / f"{alias}.json")

            # Encrypt
            SecureJsonVault = self.vault_manager.SecureJsonVault
            secret_key = self.vault_manager.secret_key
            temp_file_vault = SecureJsonVault(secret_key, enc_file_path)
            temp_file_vault.saveData(json_content)

            # Copy raw json (matching app startup behavior where it auto-encrypts JSONs)
            with open(raw_json_path, "w", encoding="utf-8") as f:
                f.write(json_content)

            # 5. Load in-memory
            self.vault_manager.api_credentials[alias] = api_data
            self._refresh_credentials_list()

            QMessageBox.information(
                self, "Success", f"Credential '{alias}' imported and encrypted successfully."
            )
        except Exception as e:
            QMessageBox.critical(self, "Import Failed", f"Failed to encrypt and save credential: {e}")

    def _edit_credential(self):
        """Opens a dialog to view, edit, and save the selected credential's JSON."""
        selected_items = self.credentials_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Edit Error", "Please select a credential from the list first.")
            return

        alias = selected_items[0].text()
        if not self.vault_manager or alias not in self.vault_manager.api_credentials:
            QMessageBox.warning(self, "Edit Error", f"Credential '{alias}' not found in memory.")
            return

        # Get current data
        current_data = self.vault_manager.api_credentials[alias]
        try:
            current_json_str = json.dumps(current_data, indent=4)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to serialize credential data: {e}")
            return

        # Create Dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Edit Credential - {alias}")
        dialog.setMinimumSize(500, 400)
        
        layout = QVBoxLayout(dialog)
        
        info_label = QLabel(f"Editing JSON values for: <b>{alias}</b>")
        layout.addWidget(info_label)
        
        editor = QTextEdit()
        editor.setPlainText(current_json_str)
        editor.setStyleSheet("font-family: monospace;")
        layout.addWidget(editor)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(button_box)
        
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_json_str = editor.toPlainText().strip()
            if not new_json_str:
                QMessageBox.warning(self, "Validation Error", "Credential JSON cannot be empty.")
                return
            
            try:
                new_data = json.loads(new_json_str)
            except json.JSONDecodeError as e:
                QMessageBox.critical(self, "JSON Error", f"Invalid JSON format. Changes not saved.\n{e}")
                return
                
            # Now save it back
            try:
                api_dir_path = Path(API_DIR)
                api_dir_path.mkdir(parents=True, exist_ok=True)
                enc_file_path = str(api_dir_path / f"{alias}.json.enc")
                raw_json_path = str(api_dir_path / f"{alias}.json")

                # Encrypt and save
                SecureJsonVault = self.vault_manager.SecureJsonVault
                secret_key = self.vault_manager.secret_key
                temp_file_vault = SecureJsonVault(secret_key, enc_file_path)
                temp_file_vault.saveData(new_json_str)

                # Write raw json matching import behavior
                with open(raw_json_path, "w", encoding="utf-8") as f:
                    f.write(new_json_str)

                # Update in memory
                self.vault_manager.api_credentials[alias] = new_data
                
                QMessageBox.information(self, "Success", f"Credential '{alias}' updated and saved successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Failed to save credential '{alias}': {e}")

    def _delete_credential(self):
        """Delete the selected credential from the vault and disk."""
        selected_items = self.credentials_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Delete Error", "Please select a credential from the list first.")
            return

        alias = selected_items[0].text()

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete the credential '{alias}'?\n"
            "This will delete its encrypted (.json.enc) and unencrypted (.json) source files from the API directory.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            # 1. Delete files on disk
            enc_file_path = Path(API_DIR) / f"{alias}.json.enc"
            raw_json_path = Path(API_DIR) / f"{alias}.json"

            if enc_file_path.exists():
                enc_file_path.unlink()
            if raw_json_path.exists():
                raw_json_path.unlink()

            # 2. Remove from session memory
            if alias in self.vault_manager.api_credentials:
                del self.vault_manager.api_credentials[alias]

            # 3. Refresh list
            self._refresh_credentials_list()

            QMessageBox.information(self, "Success", f"Credential '{alias}' deleted successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Delete Failed", f"Failed to delete credential: {e}")

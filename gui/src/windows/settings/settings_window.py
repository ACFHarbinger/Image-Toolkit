"""Application settings window -- composed from section/behavior mixins.

Split from the former monolithic ``settings_window.py`` (Architecture epic,
issue #122). Each mixin owns one or more UI sections plus the methods that
back them; this module only wires them together and orders section
construction into the seven-tab layout.
"""

from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ._appearance import _AppearanceMixin
from ._credentials import _CredentialsMixin
from ._misc_sections import _MiscSectionsMixin
from ._profile_management import _ProfileManagementMixin
from ._relaunch_settings import _RelaunchSettingsMixin
from ._reset_state import _ResetStateMixin
from ._shortcuts import _ShortcutsMixin
from ._tab_config_editing import _TabConfigEditingMixin
from ._tab_config_management import _TabConfigMixin
from ._theme_studio_mixin import _ThemeStudioMixin
from .app_settings import AppSettings


class SettingsWindow(
    _ProfileManagementMixin,
    _TabConfigMixin,
    _TabConfigEditingMixin,
    _RelaunchSettingsMixin,
    _ShortcutsMixin,
    _AppearanceMixin,
    _ThemeStudioMixin,
    _ResetStateMixin,
    _CredentialsMixin,
    _MiscSectionsMixin,
    QWidget,
):
    """
    A standalone widget for the application settings, displayed as a modal window.
    """

    def __init__(self, parent=None):
        # Store a reference to the main window to call theme switching
        self.main_window_ref = parent

        super().__init__(None, Qt.WindowType.Window)

        self.setWindowTitle("Application Settings")
        self.setMinimumSize(800, 600)  # Increased height slightly

        # Reference to the Vault Manager from MainWindow
        self.vault_manager = self.main_window_ref.vault_manager if self.main_window_ref else None

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
                if getattr(self.vault_manager, "is_guest", False) is True:
                    self.current_account_name = f"{self.current_account_name} (Guest)"
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
        self.pref_restore_last_tab = _p.get("restore_last_tab", False)
        self.pref_minimize_to_tray = bool(
            _p.get("minimize_to_tray", False)
            or _p.get("close_to_tray", False)
            or AppSettings.minimize_to_tray()
        )
        self.pref_default_open_dir = _p.get("default_open_dir", "")
        self.pref_recent_dirs_count = _p.get("recent_dirs_count", 10)
        self.pref_startup_category = _p.get("startup_category", "System Tools")
        self.pref_startup_tab = _p.get("startup_tab", "")
        self.pref_experimental_runtime_shell = _p.get("experimental_runtime_shell", False) is True

        self.pref_slideshow_min = _p.get("slideshow_interval_min", 5)
        self.pref_slideshow_sec = _p.get("slideshow_interval_sec", 0)
        self.pref_slideshow_order = _p.get("slideshow_order", "Sequential")
        self.pref_log_level = _p.get("log_level", "INFO")
        self.pref_file_logging = _p.get("file_logging_enabled", False)
        self.pref_extractor_seek_ms = _p.get("extractor_seek_ms", 100)
        self.pref_recent_extractions_count = _p.get("recent_extractions_count", 10)
        self.pref_enable_extraction_queue = _p.get("enable_extraction_queue", False)
        self.pref_parallel_extraction_processors = _p.get(
            "parallel_extraction_processors", min(4, os.cpu_count() or 1)
        )
        self.pref_extractor_time_format = _p.get("extractor_time_format", "m:s:ms")
        self.pref_extractor_encoder_threads = _p.get("extractor_encoder_threads", 0)
        self.pref_extractor_gif_max_colors = _p.get("extractor_gif_max_colors", 256)
        self.pref_extractor_fps_clamp = _p.get("extractor_fps_clamp", 0)
        self.pref_session_recovery = _p.get("session_recovery_level", "None")
        self.pref_accent_dark = _p.get("accent_color_dark", "#00bcd4")
        self.pref_accent_light = _p.get("accent_color_light", "#007AFF")
        self.pref_font_scale = _p.get("font_scale", 100)
        self.pref_ui_density = _p.get("ui_density", "Comfortable")
        self.pref_app_zoom = _p.get("app_zoom", 0)
        self.pref_background_config = _p.get("background_config", {})
        self.pref_corner_radius = _p.get("corner_radius", 4)
        self.pref_shadow_elevation = _p.get("shadow_elevation", "None")
        self.pref_color_overrides = _p.get("color_overrides", {})
        self.pref_recursive_scan = _p.get("recursive_scan", True)
        self.pref_mal_fetch_method = AppSettings.mal_fetch_method()
        seen_dirs = set()
        self.pref_favourite_directories = [
            x
            for x in (_p.get("favourite_directories", []) + AppSettings.favourite_directories())
            if not (x in seen_dirs or seen_dirs.add(x))
        ]


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
        title_label.setStyleSheet(f"color: {header_label_color}; font-size: 14pt; font-weight: bold;")
        header_layout.addWidget(title_label)
        header_layout.addStretch(1)

        main_layout.addWidget(header_widget)
        # --- End Header Bar ---

        # --- Build all sections ---
        login_groupbox, vault_sync_groupbox = self._build_login_vault_section()
        credentials_groupbox = self._build_credentials_section()
        prefs_groupbox = self._build_prefs_section()
        session_groupbox = self._build_session_section()
        fav_dir_groupbox = self._build_favourites_section()
        profiles_groupbox = self._build_profiles_section()
        defaults_groupbox = self._build_tab_defaults_section()
        appearance_groupbox = self._build_appearance_section()
        gallery_groupbox = self._build_gallery_section()
        media_groupbox = self._build_media_section()
        slideshow_groupbox = self._build_slideshow_section()
        perf_groupbox = self._build_perf_section()
        mal_groupbox = self._build_mal_section()
        logging_groupbox = self._build_logging_section()
        reset_groupbox = self._build_reset_state_section()
        bulk_groupbox = self._build_bulk_update_tab()

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
            scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
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
        layout_startup.addWidget(fav_dir_groupbox)
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
        layout_system.addWidget(mal_groupbox)
        layout_system.addWidget(logging_groupbox)
        layout_system.addWidget(reset_groupbox)
        layout_system.addStretch(1)
        self.tab_widget.addTab(scroll_system, "⚙️ System and Logging")

        # Tab 6: Keyboard Shortcuts (GUI/UX §2.29). Deliberately NOT built via
        # create_tab_scroll_area(): that helper's AlignTop layout + trailing
        # addStretch(1) shrinks its content to its size hint, which made the
        # shortcuts editor look short regardless of available tab space. The
        # shortcuts groupbox has its own internal scroll areas (the scope
        # list and each scope's action page), so it doesn't need an outer
        # QScrollArea wrapper either -- just let it fill the tab.
        shortcuts_tab = QWidget()
        shortcuts_tab_layout = QVBoxLayout(shortcuts_tab)
        shortcuts_tab_layout.setContentsMargins(15, 15, 15, 15)
        shortcuts_tab_layout.addWidget(self._build_shortcuts_groupbox())
        self.tab_widget.addTab(shortcuts_tab, "⌨️ Shortcuts")

        # Tab 7: Appearance and Themes (Theme Studio #438 + QSS editor #441)
        theme_studio_tab = self._build_theme_studio_tab()
        self.tab_widget.addTab(theme_studio_tab, "🎨 Appearance and Themes")

        # Tab 8: Bulk Pattern Update
        scroll_bulk, layout_bulk = create_tab_scroll_area()
        layout_bulk.addWidget(bulk_groupbox)
        layout_bulk.addStretch(1)
        self.tab_widget.addTab(scroll_bulk, "🔄 Bulk Update")

        main_layout.addWidget(self.tab_widget)

        # --- Action Buttons at the bottom (Full Width) ---
        actions_widget = QWidget()
        actions_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        actions_layout = QHBoxLayout(actions_widget)
        actions_layout.setContentsMargins(20, 10, 20, 20)
        actions_layout.setSpacing(10)

        # 1. Reset Button
        self.reset_button = QPushButton("Reset to default")
        self.reset_button.setObjectName("reset_button")
        self.reset_button.clicked.connect(self.reset_settings)
        self.reset_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        # 1.5. Reload Button (New) 🆕
        self.reload_button = QPushButton("Reload settings")
        self.reload_button.setObjectName("reload_button")
        self.reload_button.setStyleSheet("background-color: #34495e; color: white; font-weight: bold;")
        self.reload_button.clicked.connect(self.reload_settings)
        self.reload_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        # 2. Refresh Button (New) 🆕
        self.refresh_button = QPushButton("Refresh Application (Relaunch) 🔄")
        self.refresh_button.setObjectName("refresh_button")
        self.refresh_button.setStyleSheet("background-color: #f1c40f; color: black; font-weight: bold;")
        self.refresh_button.clicked.connect(self._refresh_application)
        self.refresh_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        # 3. Update Button
        self.update_button = QPushButton("Update settings")
        self.update_button.setObjectName("update_button")
        self.update_button.clicked.connect(self.confirm_update_settings)
        self.update_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.update_button.setDefault(True)

        actions_layout.addWidget(self.reset_button)
        actions_layout.addWidget(self.reload_button)
        actions_layout.addWidget(self.refresh_button)  # Added refresh button
        actions_layout.addWidget(self.update_button)

        main_layout.addWidget(actions_widget)

        # Populate credentials list
        self._refresh_credentials_list()
        self._settings_baseline = self._settings_snapshot()

    def _settings_snapshot(self) -> tuple:
        """Return the editable settings state without treating buttons as edits."""
        values = []
        editable_types = (
            QLineEdit, QTextEdit, QPlainTextEdit, QCheckBox, QRadioButton,
            QComboBox, QSpinBox, QSlider, QListWidget,
        )
        for widget in self.findChildren(QWidget):
            if not isinstance(widget, editable_types):
                continue
            if isinstance(widget, (QCheckBox, QRadioButton)):
                value = widget.isChecked()
            elif isinstance(widget, QComboBox):
                value = (widget.currentIndex(), widget.currentText())
            elif isinstance(widget, (QSpinBox, QSlider)):
                value = widget.value()
            elif isinstance(widget, QListWidget):
                value = tuple(widget.item(index).text() for index in range(widget.count()))
            else:
                value = widget.toPlainText() if isinstance(widget, (QTextEdit, QPlainTextEdit)) else widget.text()
            values.append((type(widget).__name__, widget.objectName(), value))
        return tuple(values)

    def _has_unsaved_settings(self) -> bool:
        return self._settings_snapshot() != self._settings_baseline

    def _mark_settings_saved(self) -> None:
        self._settings_baseline = self._settings_snapshot()

    def _confirm_unsaved_settings_exit(self) -> str:
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Unsaved Settings")
        dialog.setText("You have unsaved settings. Do you want to save them before exiting?")
        cancel = dialog.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        discard = dialog.addButton("Exit Without Saving", QMessageBox.ButtonRole.DestructiveRole)
        save = dialog.addButton("Exit", QMessageBox.ButtonRole.AcceptRole)
        cancel.setStyleSheet("background-color: #4b5563; color: white; font-weight: bold;")
        discard.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold;")
        save.setStyleSheet("background-color: #16803c; color: white; font-weight: bold;")
        dialog.setDefaultButton(cancel)
        dialog.exec()
        if dialog.clickedButton() is save:
            return "save"
        if dialog.clickedButton() is discard:
            return "discard"
        return "cancel"

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._has_unsaved_settings():
            event.accept()
            return

        choice = self._confirm_unsaved_settings_exit()
        if choice == "discard":
            event.accept()
        elif choice == "save":
            event.ignore()
            self._update_settings_logic()
        else:
            event.ignore()


__all__ = ["SettingsWindow"]

"""System Preference Profiles section + Profile Management methods.

Extracted from ``settings_window.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import base64
import contextlib

from PySide6.QtCore import QByteArray
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from .app_settings import AppSettings


class _ProfileManagementMixin:
    """Builds the System Preference Profiles groupbox and owns profile CRUD logic."""

    def _build_profiles_section(self) -> QGroupBox:
        profiles_groupbox = QGroupBox("System Preference Profiles")
        profiles_groupbox.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        profiles_layout = QVBoxLayout(profiles_groupbox)

        # Row 1: Select Profile to Load, Update, or Delete
        profile_select_layout = QHBoxLayout()
        self.profile_combo = QComboBox()
        self.profile_combo.setPlaceholderText("Select Profile...")
        self._refresh_profile_combo()

        self.btn_load_profile = QPushButton("Load Profile")
        self.btn_load_profile.setToolTip("Apply the selected profile's settings to the fields above")
        self.btn_load_profile.clicked.connect(self._load_selected_profile)

        self.btn_use_profile = QPushButton("Use Profile")
        self.btn_use_profile.setToolTip("Load the selected profile's settings and apply them to the app immediately")
        self.btn_use_profile.setStyleSheet("background-color: #27ae60; color: white;")
        self.btn_use_profile.clicked.connect(self._use_selected_profile)

        self.btn_update_profile = QPushButton("Update Profile")
        self.btn_update_profile.setToolTip("Update the selected profile with the current settings from the UI fields")
        self.btn_update_profile.setStyleSheet("background-color: #2980b9; color: white;")
        self.btn_update_profile.clicked.connect(self._update_selected_profile)

        self.btn_delete_profile = QPushButton("Delete Profile")
        self.btn_delete_profile.setStyleSheet("background-color: #e74c3c; color: white;")
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
        self.profile_name_input.setPlaceholderText("New Profile Name (e.g., Work Laptop)")

        self.btn_save_profile = QPushButton("Save Current Settings as Profile")
        self.btn_save_profile.setToolTip("Save the current state of Theme and Tab Configs above as a new profile")
        self.btn_save_profile.setStyleSheet("background-color: #2ecc71; color: white;")
        self.btn_save_profile.clicked.connect(self._save_current_as_profile)

        profile_create_layout.addWidget(QLabel("Name:"))
        profile_create_layout.addWidget(self.profile_name_input, 1)
        profile_create_layout.addWidget(self.btn_save_profile)

        profiles_layout.addLayout(profile_create_layout)

        return profiles_groupbox

    # ---------------------------------------------------------------------
    # --- Profile Management Methods ---
    # ---------------------------------------------------------------------

    def _refresh_profile_combo(self):
        """Updates the profile selection dropdown."""
        self.profile_combo.clear()
        if self.system_profiles:
            self.profile_combo.addItems(sorted(self.system_profiles.keys()))

    def _get_current_ui_preferences(self):
        """Helper to gather current theme, tab config, appearance, and layout selections."""
        theme = "light" if self.light_theme_radio.isChecked() else "dark"

        current_tab_configs = {}
        for tab_name, combo in self.startup_config_combos.items():
            selected = combo.currentText()
            if selected != "None (Default)":
                current_tab_configs[tab_name] = selected

        profile_data: dict = {
            "theme": theme,
            "active_tab_configs": current_tab_configs,
            "accent_color_dark": self.pref_accent_dark,
            "accent_color_light": self.pref_accent_light,
            "font_scale": self.font_scale_spinbox.value(),
            "ui_density": self.ui_density_combo.currentText(),
            "app_zoom": self.pref_app_zoom,
        }

        # §4.12 — bundle current window geometry and splitter states
        if self.main_window_ref:
            try:
                geom_bytes = self.main_window_ref.saveGeometry()
                profile_data["layout_geometry"] = base64.b64encode(bytes(geom_bytes)).decode("ascii")
            except Exception:
                pass

        splitters_dict: dict = {}
        for key in AppSettings.all_keys():
            if key.startswith("splitters/"):
                raw = AppSettings.get(key)
                if raw:
                    with contextlib.suppress(Exception):
                        splitters_dict[key] = base64.b64encode(bytes(raw)).decode("ascii")
        if splitters_dict:
            profile_data["layout_splitters"] = splitters_dict

        return profile_data

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
            creds = self.vault_manager.load_account_credentials()  # pyrefly: ignore [missing-attribute]
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
            creds = self.vault_manager.load_account_credentials()  # pyrefly: ignore [missing-attribute]
            creds["system_preference_profiles"] = self.system_profiles
            if self._save_vault_data(creds):
                QMessageBox.information(self, "Success", f"Profile '{name}' updated successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Update Error", f"Failed to update profile: {e}")

    def reload_settings(self, show_msg=True):
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
                QMessageBox.critical(self, "Error", f"Failed to load credentials from vault:\n{e}")
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
        self.pref_enable_extraction_queue = _p.get("enable_extraction_queue", False)
        self.pref_extractor_time_format = _p.get("extractor_time_format", "m:s:ms")
        self.pref_session_recovery = _p.get("session_recovery_level", "None")
        self.pref_accent_dark = _p.get("accent_color_dark", "#00bcd4")
        self.pref_accent_light = _p.get("accent_color_light", "#007AFF")
        self.pref_font_scale = _p.get("font_scale", 100)
        self.pref_ui_density = _p.get("ui_density", "Comfortable")
        self.pref_recursive_scan = _p.get("recursive_scan", True)
        self.pref_app_zoom = _p.get("app_zoom", 0)
        self.pref_mal_fetch_method = AppSettings.mal_fetch_method()
        seen_dirs = set()
        self.pref_favourite_directories = [
            x
            for x in (_p.get("favourite_directories", []) + AppSettings.favourite_directories())
            if not (x in seen_dirs or seen_dirs.add(x))
        ]

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
        self.recursive_scan_check.setChecked(self.pref_recursive_scan)

        # Repopulate Startup and Session
        items = [self.startup_category_combo.itemText(i) for i in range(self.startup_category_combo.count())]
        if self.pref_startup_category in items:
            self.startup_category_combo.setCurrentText(self.pref_startup_category)
        self.restore_last_dir_check.setChecked(self.pref_restore_last_dir)
        self.recent_dirs_count_spinbox.setValue(self.pref_recent_dirs_count)
        self.session_recovery_combo.setCurrentText(self.pref_session_recovery)

        # Repopulate Performance and Cache
        self.found_cache_spinbox.setValue(self.pref_found_cache)
        self.selected_cache_spinbox.setValue(self.pref_selected_cache)
        self.initial_cache_spinbox.setValue(self.pref_initial_cache)

        # Repopulate MyAnimeList Auto-Fill
        _mal_index = self.mal_fetch_method_combo.findData(self.pref_mal_fetch_method)
        self.mal_fetch_method_combo.setCurrentIndex(max(_mal_index, 0))

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
        self.enable_queue_check.setChecked(self.pref_enable_extraction_queue)
        self.extractor_time_format_combo.setCurrentText(self.pref_extractor_time_format)

        # Repopulate Appearance
        if hasattr(self, "dark_accent_swatch") and hasattr(self, "_update_swatch"):
            self._update_swatch(self.dark_accent_swatch, self.pref_accent_dark)
        if hasattr(self, "light_accent_swatch") and hasattr(self, "_update_swatch"):
            self._update_swatch(self.light_accent_swatch, self.pref_accent_light)
        self.font_scale_spinbox.setValue(self.pref_font_scale)
        self.ui_density_combo.setCurrentText(self.pref_ui_density)
        self._zoom_label.setText(self._zoom_label_text())

        # Repopulate Favourite Directories list
        self.fav_list_widget.clear()
        self.fav_list_widget.addItems(self.pref_favourite_directories)

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

        if show_msg:
            QMessageBox.information(self, "Settings Reloaded", "Settings reloaded from the vault successfully.")

    def _apply_appearance_from_profile(self, profile_data: dict) -> None:
        """§4.13 — Push appearance keys from a profile dict into the UI widgets."""
        accent_dark = profile_data.get("accent_color_dark")
        accent_light = profile_data.get("accent_color_light")
        font_scale = profile_data.get("font_scale")
        ui_density = profile_data.get("ui_density")
        if accent_dark:
            self.pref_accent_dark = accent_dark
            if hasattr(self, "dark_accent_swatch") and hasattr(self, "_update_swatch"):
                self._update_swatch(self.dark_accent_swatch, accent_dark)
        if accent_light:
            self.pref_accent_light = accent_light
            if hasattr(self, "light_accent_swatch") and hasattr(self, "_update_swatch"):
                self._update_swatch(self.light_accent_swatch, accent_light)
        if font_scale is not None:
            self.font_scale_spinbox.setValue(int(font_scale))
        if ui_density:
            self.ui_density_combo.setCurrentText(ui_density)

    def _apply_layout_from_profile(self, profile_data: dict) -> None:
        """§4.12 — Restore window geometry and splitter states from a profile.

        Geometry is applied immediately to the main window.  Splitter states are
        written to QSettings so each splitter picks them up on its next init (or
        the next time ``persist_splitter`` is called for that key).
        """
        geom_b64 = profile_data.get("layout_geometry")
        if geom_b64 and self.main_window_ref:
            try:
                geom_bytes = QByteArray(base64.b64decode(geom_b64))
                self.main_window_ref.restoreGeometry(geom_bytes)
            except Exception:
                pass

        for key, val_b64 in profile_data.get("layout_splitters", {}).items():
            try:
                state_bytes = QByteArray(base64.b64decode(val_b64))
                AppSettings.set(key, state_bytes)
            except Exception:
                pass

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
                index = combo.findText(saved_configs[tab_name])
                if index >= 0:
                    combo.setCurrentIndex(index)
                else:
                    combo.setCurrentIndex(0)
            else:
                combo.setCurrentIndex(0)

        # §4.13 Apply Appearance
        self._apply_appearance_from_profile(profile_data)
        # §4.12 Apply Layout
        self._apply_layout_from_profile(profile_data)

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

        # §4.13 Apply Appearance before saving so _update_settings_logic picks them up
        self._apply_appearance_from_profile(profile_data)
        # §4.12 Apply Layout immediately
        self._apply_layout_from_profile(profile_data)

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
                creds = self.vault_manager.load_account_credentials()  # pyrefly: ignore [missing-attribute]
                creds["system_preference_profiles"] = self.system_profiles
                if self._save_vault_data(creds):
                    QMessageBox.information(self, "Success", f"Profile '{name}' deleted.")
                    self._refresh_profile_combo()
            except Exception as e:
                QMessageBox.critical(self, "Delete Error", f"Failed to delete profile: {e}")


__all__ = ["_ProfileManagementMixin"]

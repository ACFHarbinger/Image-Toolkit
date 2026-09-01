"""Startup/Session and Performance/Cache sections + Relaunch/Other Settings methods.

Extracted from ``settings_window.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import os
import shutil

from backend.src.constants import IMAGE_TOOLKIT_DIR, LOCAL_SOURCE_PATH
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
)

from .app_settings import AppSettings


class _RelaunchSettingsMixin:
    """Builds the Startup/Session and Performance/Cache sections; owns relaunch/save/reset logic."""

    def _build_session_section(self) -> QGroupBox:
        session_groupbox = QGroupBox("Startup and Session")
        session_groupbox.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        session_layout = QFormLayout(session_groupbox)
        session_layout.setContentsMargins(10, 10, 10, 10)

        category_names = list(self._get_tab_mapping().keys()) or [
            "System Tools",
            "Library Database",
            "Web Integration",
            "Deep Learning",
            "Image Stitching",
            "Manga",
            "Image Editor",
        ]
        self.startup_category_combo = QComboBox()
        self.startup_category_combo.addItems(category_names)
        if self.pref_startup_category in category_names:
            self.startup_category_combo.setCurrentText(self.pref_startup_category)
        self.startup_category_combo.setToolTip("Which tab group to show when the app launches")
        session_layout.addRow("Default Startup Category:", self.startup_category_combo)

        # Default Startup Tab -- cascades from the category combo above, listing
        # only the tabs that belong to whichever category is currently selected.
        self.startup_tab_combo = QComboBox()
        self._categorized_tabs_for_startup = self._get_all_tab_names_categorized()
        self.startup_tab_combo.setToolTip(
            "Which tab within the default category to select when the app launches "
            "(only used when 'Restore last opened tab on startup' below is unchecked)."
        )
        self._refresh_startup_tab_combo(self.startup_category_combo.currentText())
        if self.pref_startup_tab:
            self.startup_tab_combo.setCurrentText(self.pref_startup_tab)
        self.startup_category_combo.currentTextChanged.connect(self._refresh_startup_tab_combo)
        session_layout.addRow("Default Startup Tab:", self.startup_tab_combo)

        restore_last_dir_row = QHBoxLayout()
        self.restore_last_dir_check = QCheckBox("Restore last browsed directory on startup")
        self.restore_last_dir_check.setChecked(self.pref_restore_last_dir)
        self.restore_last_tab_check = QCheckBox("Restore last opened tab on startup")
        self.restore_last_tab_check.setChecked(self.pref_restore_last_tab)
        self.restore_last_tab_check.setToolTip(
            "If checked, the app reopens whichever category/tab was active when it was last "
            "closed. If unchecked, it always opens the Default Startup Category/Tab above."
        )
        restore_last_dir_row.addWidget(self.restore_last_dir_check)
        restore_last_dir_row.addWidget(self.restore_last_tab_check)
        restore_last_dir_row.addStretch(1)
        session_layout.addRow(restore_last_dir_row)

        self.minimize_to_tray_check = QCheckBox("Close to background tray icon (keep app running in background)")
        self.minimize_to_tray_check.setChecked(self.pref_minimize_to_tray)
        self.minimize_to_tray_check.setToolTip(
            "When enabled, closing the window keeps the application running in the background with "
            "a system tray icon for quick re-opening."
        )
        session_layout.addRow(self.minimize_to_tray_check)


        self.recent_dirs_count_spinbox = QSpinBox()
        self.recent_dirs_count_spinbox.setRange(1, 50)
        self.recent_dirs_count_spinbox.setValue(self.pref_recent_dirs_count)
        self.recent_dirs_count_spinbox.setToolTip(
            "Number of most recently browsed directories to remember per gallery tab"
        )
        session_layout.addRow("Recent Directories Limit:", self.recent_dirs_count_spinbox)

        self.session_recovery_combo = QComboBox()
        self.session_recovery_combo.addItems(["None", "Current Tab", "Current Category", "All Tabs"])
        self.session_recovery_combo.setCurrentText(self.pref_session_recovery)
        self.session_recovery_combo.setToolTip(
            "Select the level of information to save during app shutdown to recover on next login.\n"
            "Current Category restores every tab within the category that was active on close, "
            "not just the single active tab."
        )
        session_layout.addRow("Session Recovery Level:", self.session_recovery_combo)

        # Default browse directory
        default_dir_row = QHBoxLayout()
        self.default_dir_input = QLineEdit()
        self.default_dir_input.setText(self.pref_default_open_dir)
        self.default_dir_input.setPlaceholderText("Select/paste default directory path...")
        self.btn_browse_default_dir = QPushButton("Browse")
        self.btn_browse_default_dir.setFixedWidth(80)
        self.btn_browse_default_dir.clicked.connect(self._browse_default_open_dir)
        default_dir_row.addWidget(self.default_dir_input, 1)
        default_dir_row.addWidget(self.btn_browse_default_dir)
        session_layout.addRow("Default Browse Directory:", default_dir_row)

        return session_groupbox

    def _refresh_startup_tab_combo(self, category_name: str) -> None:
        """Repopulate startup_tab_combo with the tabs belonging to *category_name*."""
        self.startup_tab_combo.blockSignals(True)
        self.startup_tab_combo.clear()
        tab_names = self._categorized_tabs_for_startup.get(category_name, [])
        self.startup_tab_combo.addItems(tab_names)
        self.startup_tab_combo.blockSignals(False)

    def _build_perf_section(self) -> QGroupBox:
        perf_groupbox = QGroupBox("Performance and Cache")
        perf_groupbox.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
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
        self.found_cache_spinbox.setToolTip("Max thumbnails held in the 'found' gallery LRU cache")
        perf_layout.addRow("Found Gallery LRU Cache Size:", self.found_cache_spinbox)

        self.selected_cache_spinbox = QSpinBox()
        self.selected_cache_spinbox.setRange(50, 1000)
        self.selected_cache_spinbox.setSingleStep(50)
        self.selected_cache_spinbox.setValue(self.pref_selected_cache)
        self.selected_cache_spinbox.setToolTip("Max thumbnails held in the 'selected' gallery LRU cache")
        perf_layout.addRow("Selected Gallery LRU Cache Size:", self.selected_cache_spinbox)

        self.initial_cache_spinbox = QSpinBox()
        self.initial_cache_spinbox.setRange(50, 2000)
        self.initial_cache_spinbox.setSingleStep(50)
        self.initial_cache_spinbox.setValue(self.pref_initial_cache)
        self.initial_cache_spinbox.setToolTip("Max thumbnails held in the wallpaper/single-gallery LRU cache")
        perf_layout.addRow("Wallpaper Gallery LRU Cache Size:", self.initial_cache_spinbox)

        self.clear_storyboard_cache_btn = QPushButton("Clear Storyboard Cache")
        self.clear_storyboard_cache_btn.setToolTip("Deletes the storyboard cache directory and all its contents.")
        self.clear_storyboard_cache_btn.clicked.connect(self._clear_storyboard_cache)
        perf_layout.addRow("", self.clear_storyboard_cache_btn)

        return perf_groupbox

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
            if self.main_window_ref and hasattr(self.main_window_ref, "restart_application"):
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
            QMessageBox.critical(self, "Update Failed", "Vault manager is not available.")
            return

        # --- Handle Password Change (Master Reset) ---
        if new_password:
            try:
                self.vault_manager.update_account_password(self.current_account_name, new_password)

                if self.main_window_ref:
                    self.main_window_ref.update_header()

                QMessageBox.information(
                    self,
                    "Success",
                    "Master password successfully updated! All data was preserved.",
                )

            except Exception as e:
                QMessageBox.critical(self, "Update Failed", f"Failed to update master password:\n{e}")
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
                "recursive_scan": self.recursive_scan_check.isChecked(),
                "found_cache_maxsize": self.found_cache_spinbox.value(),
                "selected_cache_maxsize": self.selected_cache_spinbox.value(),
                "initial_cache_maxsize": self.initial_cache_spinbox.value(),
                "restore_last_dir": self.restore_last_dir_check.isChecked(),
                "restore_last_tab": self.restore_last_tab_check.isChecked(),
                "minimize_to_tray": self.minimize_to_tray_check.isChecked(),
                "default_open_dir": self.default_dir_input.text().strip().replace("Downloads/data", "Downloads/Data"),
                "recent_dirs_count": self.recent_dirs_count_spinbox.value(),
                "startup_category": self.startup_category_combo.currentText(),
                "startup_tab": self.startup_tab_combo.currentText(),
                "slideshow_interval_min": self.slideshow_default_min_spinbox.value(),
                "slideshow_interval_sec": self.slideshow_default_sec_spinbox.value(),
                "slideshow_order": self.slideshow_default_order_combo.currentText(),
                "log_level": self.log_level_combo.currentText(),
                "file_logging_enabled": self.file_logging_check.isChecked(),
                "extractor_seek_ms": self.extractor_seek_spinbox.value(),
                "recent_extractions_count": self.recent_extractions_spinbox.value(),
                "enable_extraction_queue": self.enable_queue_check.isChecked(),
                "parallel_extraction_processors": self.parallel_extraction_processors_spinbox.value(),
                "extractor_time_format": self.extractor_time_format_combo.currentText(),
                "extractor_encoder_threads": self.extractor_encoder_threads_spinbox.value() if hasattr(self, "extractor_encoder_threads_spinbox") else 0,
                "extractor_gif_max_colors": self.extractor_gif_max_colors_spinbox.value() if hasattr(self, "extractor_gif_max_colors_spinbox") else 256,
                "extractor_fps_clamp": self.extractor_fps_clamp_spinbox.value() if hasattr(self, "extractor_fps_clamp_spinbox") else 0,
                "session_recovery_level": self.session_recovery_combo.currentText(),
                "accent_color_dark": self.pref_accent_dark,
                "accent_color_light": self.pref_accent_light,
                "color_overrides": self._get_color_overrides_dict() if hasattr(self, "_get_color_overrides_dict") else {},
                "background_config": self._get_background_config_dict() if hasattr(self, "_get_background_config_dict") else {},
                "corner_radius": self.corner_radius_combo.currentData() if hasattr(self, "corner_radius_combo") else 4,
                "font_scale": self.font_scale_spinbox.value(),
                "ui_density": self.ui_density_combo.currentText(),
                "app_zoom": self.pref_app_zoom,
                "favourite_directories": [
                    self.fav_list_widget.item(i).text() for i in range(self.fav_list_widget.count())
                ],
            }


            if self._save_vault_data(user_data):
                # Also save to QSettings (only if not in Guest mode)
                if getattr(self.vault_manager, "is_guest", False) is not True:
                    AppSettings.set_recursive_scan(self.recursive_scan_check.isChecked())
                    AppSettings.set_minimize_to_tray(self.minimize_to_tray_check.isChecked())
                    AppSettings.set_favourite_directories(user_data["preferences"]["favourite_directories"])  # pyrefly: ignore [bad-argument-type]
                    AppSettings.set_mal_fetch_method(self.mal_fetch_method_combo.currentData())
                if self.main_window_ref:
                    old_active_configs = (
                        dict(self.main_window_ref.cached_creds.get("active_tab_configs", {}))
                        if getattr(self.main_window_ref, "cached_creds", None)
                        else {}
                    )
                    self.main_window_ref.cached_creds = user_data
                    if hasattr(self.main_window_ref, "set_minimize_to_tray"):
                        self.main_window_ref.set_minimize_to_tray(self.minimize_to_tray_check.isChecked())
                    if selected_theme:
                        self.main_window_ref.set_application_theme(selected_theme)
                    if hasattr(self.main_window_ref, "_apply_startup_preferences"):
                        self.main_window_ref._apply_startup_preferences()
                    if hasattr(self.main_window_ref, "_apply_active_tab_configs"):
                        self.main_window_ref._apply_active_tab_configs(previous_configs=old_active_configs)
                    QMessageBox.information(self, "Success", "Settings updated and saved successfully.")


        except Exception as e:
            QMessageBox.critical(self, "Update Failed", f"Failed to save preferences to vault:\n{e}")
            return

        self._mark_settings_saved()
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
        self.recursive_scan_check.setChecked(True)

        # Reset Startup and Session
        items = [self.startup_category_combo.itemText(i) for i in range(self.startup_category_combo.count())]
        if "System Tools" in items:
            self.startup_category_combo.setCurrentText("System Tools")
        self._refresh_startup_tab_combo(self.startup_category_combo.currentText())
        self.restore_last_dir_check.setChecked(True)
        self.restore_last_tab_check.setChecked(False)
        self.minimize_to_tray_check.setChecked(False)

        self.recent_dirs_count_spinbox.setValue(10)
        self.session_recovery_combo.setCurrentText("None")

        # Reset Performance and Cache
        self.found_cache_spinbox.setValue(300)
        self.selected_cache_spinbox.setValue(200)
        self.initial_cache_spinbox.setValue(300)

        # Reset MyAnimeList Auto-Fill
        _default_mal_index = self.mal_fetch_method_combo.findData("jikan")
        self.mal_fetch_method_combo.setCurrentIndex(max(_default_mal_index, 0))

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
        self.enable_queue_check.setChecked(False)
        self.parallel_extraction_processors_spinbox.setValue(
            min(4, self.parallel_extraction_processors_spinbox.maximum())
        )
        self.extractor_time_format_combo.setCurrentText("m:s:ms")
        if hasattr(self, "extractor_encoder_threads_spinbox"):
            self.extractor_encoder_threads_spinbox.setValue(0)
        if hasattr(self, "extractor_gif_max_colors_spinbox"):
            self.extractor_gif_max_colors_spinbox.setValue(256)
        if hasattr(self, "extractor_fps_clamp_spinbox"):
            self.extractor_fps_clamp_spinbox.setValue(0)

        # Reset Appearance and Theme Studio
        self.pref_accent_dark = "#00bcd4"
        self.pref_accent_light = "#007AFF"
        if hasattr(self, "_reset_palette_to_base_defaults"):
            self._reset_palette_to_base_defaults()
        if hasattr(self, "bg_path_input"):
            self.bg_path_input.clear()
        if hasattr(self, "bg_fit_combo"):
            self.bg_fit_combo.setCurrentText("Cover")
        if hasattr(self, "bg_opacity_slider"):
            self.bg_opacity_slider.setValue(50)
        if hasattr(self, "bg_blur_spin"):
            self.bg_blur_spin.setValue(0)
        if hasattr(self, "glassmorphism_check"):
            self.glassmorphism_check.setChecked(False)
        if hasattr(self, "corner_radius_combo"):
            self.corner_radius_combo.setCurrentIndex(1)  # Subtle (4px)
        self.font_scale_spinbox.setValue(100)
        self.ui_density_combo.setCurrentText("Comfortable")
        self.pref_app_zoom = 0
        self._zoom_label.setText(self._zoom_label_text())
        self.fav_list_widget.clear()
        self.default_dir_input.clear()


    def _browse_default_open_dir(self):
        current_dir = self.default_dir_input.text().strip()
        if not current_dir or not os.path.exists(current_dir):
            current_dir = LOCAL_SOURCE_PATH
        d = QFileDialog.getExistingDirectory(self, "Select Default Browse Directory", current_dir)
        if d:
            self.default_dir_input.setText(d)

    def _clear_storyboard_cache(self):
        storyboard_dir = IMAGE_TOOLKIT_DIR / "storyboard-cache"
        if not storyboard_dir.exists():
            QMessageBox.information(self, "Storyboard Cache", "Storyboard cache is already empty or does not exist.")
            return

        reply = QMessageBox.question(
            self,
            "Clear Storyboard Cache",
            "Are you sure you want to delete the storyboard cache directory and all its contents?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                shutil.rmtree(storyboard_dir)
                QMessageBox.information(self, "Storyboard Cache", "Storyboard cache cleared successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to clear storyboard cache:\n{e}")


__all__ = ["_RelaunchSettingsMixin"]

"""Preferences (startup tab config) and Tab Default Configuration sections + methods.

Extracted from ``settings_window.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import contextlib
import json

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
)


class _TabConfigMixin:
    """Builds the Preferences and Tab Default Configuration sections and their handlers."""

    def _build_prefs_section(self) -> QGroupBox:
        prefs_groupbox = QGroupBox("Preferences")
        prefs_groupbox.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        prefs_layout = QVBoxLayout(prefs_groupbox)
        prefs_layout.setContentsMargins(10, 10, 10, 10)
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
                tab_class_name = type(tab_instance).__name__ if tab_instance else display_name

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

        return prefs_groupbox

    def _build_tab_defaults_section(self) -> QGroupBox:
        defaults_groupbox = QGroupBox("Tab Default Configuration Management")
        defaults_groupbox.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
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
        self.config_select_combo.currentTextChanged.connect(self._load_selected_tab_config)
        load_config_layout.addRow("Load/Edit Config:", self.config_select_combo)

        # Load/Delete/SET Buttons (Horizontal and full width)
        full_width_buttons_layout = QHBoxLayout()
        full_width_buttons_layout.setContentsMargins(0, 5, 0, 5)  # Optional spacing adjustment
        full_width_buttons_layout.setSpacing(10)  # Add spacing between the two buttons

        # NEW: Set Selected Config Button
        self.btn_set_config = QPushButton("Set Selected Config")
        self.btn_set_config.clicked.connect(self._set_selected_tab_config)
        # Set policy to expand horizontally
        self.btn_set_config.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        full_width_buttons_layout.addWidget(self.btn_set_config)

        # Existing Delete Button
        self.btn_delete_config = QPushButton("Delete Selected Config")
        self.btn_delete_config.setStyleSheet("background-color: #e74c3c; color: white;")
        self.btn_delete_config.clicked.connect(self._delete_selected_tab_config)
        # Set policy to expand horizontally
        self.btn_delete_config.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        full_width_buttons_layout.addWidget(self.btn_delete_config)

        # Add the config selection layout first
        defaults_layout.addLayout(load_config_layout)
        # Then add the new full-width, side-by-side buttons layout
        defaults_layout.addLayout(full_width_buttons_layout)

        # Export/Import config as JSON file
        transfer_buttons_layout = QHBoxLayout()
        transfer_buttons_layout.setContentsMargins(0, 0, 0, 5)
        transfer_buttons_layout.setSpacing(10)

        self.btn_export_config = QPushButton("Export Config to JSON 📤")
        self.btn_export_config.setToolTip("Save the currently selected/edited configuration to a .json file")
        self.btn_export_config.setStyleSheet("background-color: #7b1fa2; color: white; font-weight: bold;")
        self.btn_export_config.clicked.connect(self._export_selected_tab_config)
        self.btn_export_config.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        transfer_buttons_layout.addWidget(self.btn_export_config)

        self.btn_import_config = QPushButton("Import Config from JSON 📥")
        self.btn_import_config.setToolTip("Load a configuration from a .json file and save it for its tab")
        self.btn_import_config.setStyleSheet("background-color: #2c3e50; color: white; font-weight: bold;")
        self.btn_import_config.clicked.connect(self._import_tab_config_from_json)
        self.btn_import_config.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        transfer_buttons_layout.addWidget(self.btn_import_config)

        defaults_layout.addLayout(transfer_buttons_layout)

        # 3. Create/Edit Configuration
        create_config_group = QGroupBox("Create/Edit Configuration")
        create_config_layout = QFormLayout(create_config_group)

        self.config_name_input = QLineEdit()
        self.config_name_input.setPlaceholderText("Enter a unique name (e.g., HighResConfig)")
        create_config_layout.addRow("Config Name:", self.config_name_input)

        self.default_config_editor = QTextEdit()
        self.default_config_editor.setPlaceholderText("Select a Tab Class to see its default configuration...")
        self.default_config_editor.setMinimumHeight(200)
        create_config_layout.addRow("Configuration (JSON):", self.default_config_editor)

        # Buttons to save/create config
        save_buttons_layout = QHBoxLayout()

        self.btn_create_default = QPushButton("Save Named Configuration")
        self.btn_create_default.setToolTip("Save the JSON currently in the editor as a new configuration")
        self.btn_create_default.clicked.connect(self._save_current_tab_config)

        self.btn_save_current = QPushButton("Save Current Configuration")
        self.btn_save_current.setToolTip("Capture current values from the active tab and save them")
        self.btn_save_current.setStyleSheet("background-color: #007AFF; color: white; font-weight: bold;")
        self.btn_save_current.clicked.connect(self._capture_and_save_current_config)

        save_buttons_layout.addWidget(self.btn_create_default)
        save_buttons_layout.addWidget(self.btn_save_current)

        create_config_layout.addRow(save_buttons_layout)

        defaults_layout.addWidget(create_config_group)

        return defaults_groupbox

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
        for _category, sub_tabs in self._get_tab_mapping().items():
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

        for _category, sub_tabs in self._get_tab_mapping().items():
            if display_name in sub_tabs:
                return sub_tabs[display_name]
        return None

    def _on_tab_group_changed(self, group_name: str):
        with contextlib.suppress(RuntimeError):
            self.tab_select_combo.currentTextChanged.disconnect(self._refresh_config_dropdown)

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
            QMessageBox.critical(self, "Save Error", "Vault manager is not available to save settings.")
            return False

        try:
            self.vault_manager.save_data(json.dumps(data))
            return True
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save data to vault:\n{e}")
            return False

    def _save_tab_defaults_to_vault(self):
        """Saves the entire current tab configuration state back to the secure vault."""
        if not self.vault_manager:
            QMessageBox.critical(self, "Save Error", "Vault manager is not available to save settings.")
            return False

        try:
            user_data = self.vault_manager.load_account_credentials()
            user_data["tab_configurations"] = self.tab_defaults_config
            return self._save_vault_data(user_data)
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to prepare data for saving:\n{e}")
            return False



__all__ = ["_TabConfigMixin"]

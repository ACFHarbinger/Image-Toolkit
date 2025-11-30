import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLineEdit, QRadioButton, QHBoxLayout,
    QLabel, QWidget, QSizePolicy, QScrollArea,
    QPushButton, QMessageBox, QComboBox, QTextEdit,
    QVBoxLayout, QGroupBox, QFormLayout, QApplication,
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
        self.setMinimumSize(800, 500)
        
        # Reference to the Vault Manager from MainWindow
        self.vault_manager = self.main_window_ref.vault_manager if self.main_window_ref else None

        # Load initial credentials and settings
        self.current_account_name = "N/A"
        self.initial_theme = "dark" # Default theme
        if self.vault_manager:
            try:
                creds = self.vault_manager.load_account_credentials()
                self.current_account_name = creds.get('account_name', 'N/A')
                self.initial_theme = creds.get('theme', 'dark')
            except Exception:
                pass
        
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
        header_widget.setStyleSheet(f"background-color: {header_widget_bg}; padding: 10px; border-bottom: 2px solid {accent_color};")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(10, 5, 10, 5)
        
        title_label = QLabel("Application Settings")
        title_label.setStyleSheet(f"color: {header_label_color}; font-size: 14pt; font-weight: bold;")
        header_layout.addWidget(title_label)
        header_layout.addStretch(1) 
        
        main_layout.addWidget(header_widget)
        # --- End Header Bar ---

        # Create a scrollable container for the content
        content_scroll = QScrollArea()
        content_scroll.setWidgetResizable(True)
        content_container = QWidget()
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)


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
        
        content_layout.addWidget(login_groupbox)
        
        # --- Preferences Section ---
        prefs_groupbox = QGroupBox("Preferences")
        prefs_groupbox.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        prefs_layout = QVBoxLayout(prefs_groupbox)
        prefs_layout.setContentsMargins(10, 10, 10, 10)
        
        self.dark_theme_radio = QRadioButton("Dark Theme")
        self.light_theme_radio = QRadioButton("Light Theme")
        
        # Set the radio button based on the loaded initial theme
        if self.initial_theme == "light":
            self.light_theme_radio.setChecked(True)
        else:
            self.dark_theme_radio.setChecked(True)
        
        prefs_layout.addWidget(self.dark_theme_radio)
        prefs_layout.addWidget(self.light_theme_radio)
        
        content_layout.addWidget(prefs_groupbox)

        
        # ---------------------------------------------------------------------
        # --- Tab Default Configuration Section ---
        # ---------------------------------------------------------------------
        defaults_groupbox = QGroupBox("Tab Default Configuration Management")
        defaults_groupbox.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        defaults_layout = QVBoxLayout(defaults_groupbox)
        
        # 1. Tab Selection
        tab_select_layout = QFormLayout()
        self.tab_select_combo = QComboBox()
        self.tab_select_combo.setPlaceholderText("Select a Tab...")
        tab_names = self._get_all_tab_names()
        self.tab_select_combo.addItems([""] + tab_names)
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
        full_width_buttons_layout.setContentsMargins(0, 5, 0, 5) # Optional spacing adjustment
        full_width_buttons_layout.setSpacing(10) # Add spacing between the two buttons

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
        self.config_name_input.setPlaceholderText("Enter a unique name (e.g., HighResConfig)")
        create_config_layout.addRow("Config Name:", self.config_name_input)
        
        self.default_config_editor = QTextEdit()
        self.default_config_editor.setPlaceholderText("Select a Tab Class to see its default configuration...")
        self.default_config_editor.setMinimumHeight(200)
        create_config_layout.addRow("Configuration (JSON):", self.default_config_editor)

        # Button to save/create the current JSON config
        self.btn_create_default = QPushButton("Save Named Configuration")
        self.btn_create_default.clicked.connect(self._save_current_tab_config)
        create_config_layout.addRow(self.btn_create_default)
        
        defaults_layout.addWidget(create_config_group)
        content_layout.addWidget(defaults_groupbox)
        
        
        content_layout.addStretch(1)
        
        content_scroll.setWidget(content_container)
        main_layout.addWidget(content_scroll) 

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
        
        # 2. Refresh Button (New) 🆕
        self.refresh_button = QPushButton("Refresh Application (Relaunch) 🔄")
        self.refresh_button.setObjectName("refresh_button")
        self.refresh_button.setStyleSheet("background-color: #f1c40f; color: black; font-weight: bold;")
        self.refresh_button.clicked.connect(self._refresh_application)
        self.refresh_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        # 3. Update Button
        self.update_button = QPushButton("Update settings")
        self.update_button.setObjectName("update_button")
        self.update_button.clicked.connect(self.confirm_update_settings)
        self.update_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.update_button.setDefault(True)

        actions_layout.addWidget(self.reset_button)
        actions_layout.addWidget(self.refresh_button) # Added refresh button
        actions_layout.addWidget(self.update_button)
        
        main_layout.addWidget(actions_widget)

    # ---------------------------------------------------------------------
    # --- Configuration Management Methods ---
    # ---------------------------------------------------------------------

    def _get_all_tab_names(self):
        """
        Helper to flatten the MainWindow's tab structure into a list of unique 
        tab class names.
        """
        
        tab_map = {}
        if not self.main_window_ref or not hasattr(self.main_window_ref, 'all_tabs'):
            return []
            
        for command_category, sub_tabs in self.main_window_ref.all_tabs.items():
            for tab_instance in sub_tabs.values(): 
                class_name = type(tab_instance).__name__
                if class_name not in tab_map:
                    tab_map[class_name] = True
                    
        return sorted(tab_map.keys())

    def _get_tab_instance(self, tab_class_name: str):
        """Finds the active instance of a tab by its class name."""
        if not self.main_window_ref or not hasattr(self.main_window_ref, 'all_tabs') or not tab_class_name:
            return None
            
        for category, sub_tabs in self.main_window_ref.all_tabs.items():
            for tab_instance in sub_tabs.values():
                if type(tab_instance).__name__ == tab_class_name:
                    return tab_instance
        return None

    def _load_tab_defaults_from_vault(self):
        """Loads all named tab configurations from the secure vault."""
        if not self.vault_manager:
            return {}
        try:
            full_data = self.vault_manager.load_account_credentials()
            return full_data.get('tab_configurations', {})
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
            user_data['tab_configurations'] = self.tab_defaults_config
            return self._save_vault_data(user_data)
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to prepare data for saving:\n{e}")
            return False

    def _populate_default_config(self, tab_class_name: str):
        """Populates the text editor with the default config from the selected tab class."""
        self.config_name_input.clear() # Clear config name
        tab_instance = self._get_tab_instance(tab_class_name)
        
        if tab_instance and hasattr(tab_instance, 'get_default_config'):
            try:
                default_config = tab_instance.get_default_config()
                default_json = json.dumps(default_config, indent=4)
                self.default_config_editor.setText(default_json)
                self.default_config_editor.setPlaceholderText("Edit the default config below or create a new named config...")
            except Exception as e:
                self.default_config_editor.clear()
                self.default_config_editor.setPlaceholderText(f"Error loading default config: {e}")
        else:
            self.default_config_editor.clear()
            self.default_config_editor.setPlaceholderText("This tab does not have a 'get_default_config' method.")

    def _refresh_config_dropdown(self, tab_class_name: str):
        """
        Populates the config dropdown based on the selected tab class AND
        populates the editor with the default config for that tab.
        """
        
        try:
            self.config_select_combo.currentTextChanged.disconnect(self._load_selected_tab_config)
        except RuntimeError:
            pass
            
        self.config_select_combo.clear()
        self.current_loaded_config_name = None

        if not tab_class_name:
            self.config_select_combo.setPlaceholderText("Select a Tab Class first.")
            self.config_name_input.clear()
            self.default_config_editor.clear()
            self.default_config_editor.setPlaceholderText("Select a Tab Class to see its default configuration...")
        else:
            # Populate the editor with the default config FIRST
            self._populate_default_config(tab_class_name)

            # Now, populate the dropdown with saved configs
            configs = self.tab_defaults_config.get(tab_class_name, {})
            config_names = sorted(configs.keys())
            
            self.config_select_combo.addItems([""] + config_names)
            self.config_select_combo.setPlaceholderText("Load/Edit Existing Config...")

        # Reconnect the signal
        self.config_select_combo.currentTextChanged.connect(self._load_selected_tab_config)


    def _load_selected_tab_config(self, config_name: str):
        """
        Loads a selected configuration's JSON into the editor.
        If config_name is empty, it re-loads the default config.
        """
        tab_class_name = self.tab_select_combo.currentText()
        
        if not tab_class_name:
            self.config_name_input.clear()
            self.default_config_editor.clear()
            self.current_loaded_config_name = None
            return

        if not config_name:
            # User selected the blank placeholder, so load the default config
            self._populate_default_config(tab_class_name)
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
            QMessageBox.critical(self, "Load Error", f"Failed to load config '{config_name}': {e}")
            # On error, fall back to default
            self._populate_default_config(tab_class_name)
            self.current_loaded_config_name = None


    def _save_current_tab_config(self):
        """Parses the editor content and saves it as a new or updated named configuration."""
        tab_class_name = self.tab_select_combo.currentText()
        config_name = self.config_name_input.text().strip()
        json_text = self.default_config_editor.toPlainText().strip()
        
        if not tab_class_name or not config_name:
            QMessageBox.warning(self, "Input Error", "Please select a Tab Class and provide a Config Name.")
            return

        if not json_text:
            QMessageBox.warning(self, "Input Error", "Configuration JSON cannot be empty.")
            return

        try:
            new_config = json.loads(json_text)
            if not isinstance(new_config, dict):
                raise ValueError("Configuration must be a valid JSON object.")

            if tab_class_name not in self.tab_defaults_config:
                self.tab_defaults_config[tab_class_name] = {}
            
            self.tab_defaults_config[tab_class_name][config_name] = new_config
            
            if self._save_tab_defaults_to_vault():
                QMessageBox.information(self, "Success", f"Configuration '{config_name}' saved for {tab_class_name}.")
                
                self._refresh_config_dropdown(tab_class_name)
                self.config_select_combo.setCurrentText(config_name)
            
        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "JSON Error", f"Invalid JSON format:\n{e}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An unexpected error occurred during save: {e}")


    def _delete_selected_tab_config(self):
        """Deletes the currently selected configuration from the in-memory state and the vault."""
        tab_class_name = self.tab_select_combo.currentText()
        config_name = self.config_select_combo.currentText()
        
        if not tab_class_name or not config_name:
            QMessageBox.warning(self, "Delete Error", "Please select a tab class and a configuration to delete.")
            return

        reply = QMessageBox.question(self, 'Confirm Deletion', 
            f"Are you sure you want to PERMANENTLY delete the configuration '{config_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
            QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            try:
                if tab_class_name in self.tab_defaults_config and config_name in self.tab_defaults_config[tab_class_name]:
                    del self.tab_defaults_config[tab_class_name][config_name]
                    
                    if not self.tab_defaults_config[tab_class_name]:
                        del self.tab_defaults_config[tab_class_name]
                        
                    if self._save_tab_defaults_to_vault():
                        QMessageBox.information(self, "Success", f"Configuration '{config_name}' deleted.")
                        self.config_name_input.clear()
                        self.default_config_editor.clear()
                        self._refresh_config_dropdown(tab_class_name)
                    
            except Exception as e:
                QMessageBox.critical(self, "Delete Error", f"Failed to delete configuration: {e}")

    def _set_selected_tab_config(self):
        """
        Applies the configuration currently loaded in the editor to the active 
        instance of the selected tab in the MainWindow.
        """
        tab_class_name = self.tab_select_combo.currentText()
        config_name = self.config_name_input.text().strip()
        json_text = self.default_config_editor.toPlainText().strip()
        
        if not tab_class_name or not (config_name or json_text):
            QMessageBox.warning(self, "Set Error", "Please select a tab and ensure config JSON is loaded.")
            return
            
        try:
            config_data = json.loads(json_text)
            
            target_tab_instance = self._get_tab_instance(tab_class_name)

            if not target_tab_instance:
                QMessageBox.critical(self, "Set Error", f"Could not find active instance of tab: {tab_class_name}.")
                return

            if hasattr(target_tab_instance, 'set_config') and callable(target_tab_instance.set_config):
                target_tab_instance.set_config(config_data)
                
                config_display_name = f"'{config_name}'" if config_name else "'(Default)'"
                QMessageBox.information(self, "Success", f"Configuration {config_display_name} applied to {tab_class_name}.")
            else:
                QMessageBox.critical(self, "Set Error", f"Target tab '{tab_class_name}' does not have a 'set_config' method.")

        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "JSON Error", f"Invalid JSON in editor. Cannot apply configuration:\n{e}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An unexpected error occurred during configuration application: {e}")

    # ---------------------------------------------------------------------
    # --- Relaunch / Other Settings Methods ---
    # ---------------------------------------------------------------------

    def _refresh_application(self):
        """Prompts for confirmation and triggers a full application relaunch."""
        reply = QMessageBox.question(self, 'Confirm Relaunch', 
            "Are you sure you want to refresh the application? This will close all windows and relaunch.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
            QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            if self.main_window_ref and hasattr(self.main_window_ref, 'restart_application'):
                # Assuming restart_application handles closing the current instance and starting a new one
                self.main_window_ref.restart_application()
            else:
                # Fallback solution: close current app and advise user to restart
                QMessageBox.critical(self, "Relaunch Error", "Cannot automatically restart. Closing the application now. Please relaunch the main script manually.")
                QApplication.quit()


    def confirm_update_settings(self):
        """Shows a confirmation dialog before calling update_settings_logic."""
        
        reply = QMessageBox.question(self, 'Confirm Update', 
            "Are you sure you want to update the app's settings?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
            QMessageBox.StandardButton.No)

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
                self.vault_manager.update_account_password(
                    self.current_account_name, 
                    new_password
                )
                
                if self.main_window_ref:
                    self.main_window_ref.update_header()
                    
                QMessageBox.information(self, "Success", "Master password successfully updated! All data was preserved.")
                
            except Exception as e:
                QMessageBox.critical(self, "Update Failed", f"Failed to update master password:\n{e}")
                return
        
        # --- Handle Theme Change and save all preferences to the vault ---
        try:
            user_data = self.vault_manager.load_account_credentials()
            user_data['theme'] = selected_theme
            
            if self._save_vault_data(user_data):
                if self.main_window_ref and selected_theme:
                    self.main_window_ref.set_application_theme(selected_theme)
                    QMessageBox.information(self, "Success", "Settings updated and saved successfully.")
            
        except Exception as e:
            QMessageBox.critical(self, "Update Failed", f"Failed to save preferences to vault:\n{e}")
            return
            
        self.close()

    def reset_settings(self):
        """Resets settings fields to hardcoded defaults (placeholder)."""
        self.new_password_input.clear()
        
        self.dark_theme_radio.setChecked(True)
        self.light_theme_radio.setChecked(False)

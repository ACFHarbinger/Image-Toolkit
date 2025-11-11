from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel, QWidget, QSizePolicy,
    QVBoxLayout, QGroupBox, QFormLayout,
    QLineEdit, QRadioButton, QHBoxLayout,
    QPushButton, QMessageBox
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
        
        # Reference to the Vault Manager from MainWindow
        self.vault_manager = self.main_window_ref.vault_manager if self.main_window_ref else None

        # Load initial credentials
        self.current_account_name = "N/A"
        if self.vault_manager:
            try:
                # Assuming load_account_credentials handles the initial decryption check
                creds = self.vault_manager.load_account_credentials()
                self.current_account_name = creds.get('account_name', 'N/A')
            except Exception:
                # Vault not initialized/loaded in some context, ignore for settings display
                pass


        main_layout = QVBoxLayout(self)

        # Determine initial styles based on MainWindow's current theme
        is_light_theme = self.main_window_ref and self.main_window_ref.current_theme == "light"
        
        # Theme colors for the header (must match main_window.py logic)
        header_widget_bg = "#ffffff" if is_light_theme else "#2d2d30"
        header_label_color = "#1e1e1e" if is_light_theme else "white"
        accent_color = "#007AFF" if is_light_theme else "#00bcd4"
        
        # --- MODIFICATION: Add Header Bar to mimic MainWindow ---
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

        # Create a container for the content to provide padding
        content_container = QWidget()
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)


        # --- Login Information Section ---
        login_groupbox = QGroupBox("Account Information")
        login_groupbox.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        login_layout = QFormLayout(login_groupbox)
        login_layout.setContentsMargins(10, 10, 10, 10)
        
        self.account_input = QLineEdit()
        self.account_input.setReadOnly(True) # Account name cannot be changed
        self.account_input.setText(self.current_account_name)
        
        # Only New Password field is required for the reset
        self.new_password_input = QLineEdit()
        self.new_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_password_input.setPlaceholderText("Enter NEW Password to reset")
        
        login_layout.addRow(QLabel("Account Name:"), self.account_input)
        login_layout.addRow(QLabel("New Password:"), self.new_password_input)
        
        content_layout.addWidget(login_groupbox)
        
        # --- Preferences Section ---
        prefs_groupbox = QGroupBox("Preferences")
        prefs_groupbox.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        prefs_layout = QVBoxLayout(prefs_groupbox)
        prefs_layout.setContentsMargins(10, 10, 10, 10)
        
        self.dark_theme_radio = QRadioButton("Dark Theme")
        self.light_theme_radio = QRadioButton("Light Theme")
        
        # Set the correct radio button based on current main window theme
        if self.main_window_ref and self.main_window_ref.current_theme == "light":
            self.light_theme_radio.setChecked(True)
        else:
            self.dark_theme_radio.setChecked(True) # Default is Dark
        
        prefs_layout.addWidget(self.dark_theme_radio)
        prefs_layout.addWidget(self.light_theme_radio)
        
        content_layout.addWidget(prefs_groupbox)
        
        content_layout.addStretch(1)
        main_layout.addWidget(content_container)

        
        # --- Action Buttons at the bottom ---
        actions_widget = QWidget()
        actions_layout = QHBoxLayout(actions_widget)
        actions_layout.setContentsMargins(20, 10, 20, 20)
        actions_layout.setSpacing(10)
        
        self.reset_button = QPushButton("Reset to default")
        self.reset_button.setObjectName("reset_button")
        self.reset_button.clicked.connect(self.reset_settings)
        
        self.update_button = QPushButton("Update settings")
        self.update_button.setObjectName("update_button")
        self.update_button.clicked.connect(self.confirm_update_settings) # Connect to confirmation method

        actions_layout.addWidget(self.reset_button)
        actions_layout.addStretch(1) 
        actions_layout.addWidget(self.update_button)
        
        main_layout.addWidget(actions_widget)


    def confirm_update_settings(self):
        """Shows a confirmation dialog before calling update_settings_logic."""
        
        # Use QMessageBox.question for confirmation
        reply = QMessageBox.question(self, 'Confirm Update', 
            "Are you sure you want to update the app's settings?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
            QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            self._update_settings_logic()

    def _update_settings_logic(self):
        """Saves settings (theme preference, and potentially new password) and closes the window."""
        new_password = self.new_password_input.text().strip()
        
        # --- Handle Password Change ---
        if new_password:
            if not self.vault_manager:
                QMessageBox.critical(self, "Update Failed", "Vault manager is not available.")
                return

            try:
                # Call the data-preserving update method
                self.vault_manager.update_account_password(
                    self.current_account_name, 
                    new_password
                )
                
                # Update the MainWindow's account name display if necessary
                if self.main_window_ref:
                    self.main_window_ref.update_header()
                    
                QMessageBox.information(self, "Success", "Master password successfully updated! All data was preserved.")
                
            except Exception as e:
                QMessageBox.critical(self, "Update Failed", f"Failed to update master password: {e}")
                return
        
        # --- Handle Theme Change ---
        selected_theme = "dark" if self.dark_theme_radio.isChecked() else "light"

        # Apply the new theme if it changed
        if self.main_window_ref and selected_theme:
            self.main_window_ref.set_application_theme(selected_theme)
            
        self.close()

    def reset_settings(self):
        """Resets settings fields to hardcoded defaults (placeholder)."""
        # Account field is read-only, only clear password inputs
        self.new_password_input.clear()
        
        # Default theme is Dark
        self.dark_theme_radio.setChecked(True)
        self.light_theme_radio.setChecked(False)

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel, QWidget, QSizePolicy,
    QVBoxLayout, QGroupBox, QFormLayout,
    QLineEdit, QRadioButton, QHBoxLayout,
    QPushButton
)


class SettingsWindow(QWidget):
    """
    A standalone widget for the application settings, displayed as a modal window.
    """
    def __init__(self, parent=None):
        # CRITICAL FIX: Removed 'parent' from super() call but kept Qt.Window
        super().__init__(None, Qt.Window) 
        
        # Store a reference to the main window to call theme switching
        self.main_window_ref = parent 
        
        self.setWindowTitle("Application Settings") 

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
        login_groupbox = QGroupBox("Login information")
        login_groupbox.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        login_layout = QFormLayout(login_groupbox)
        login_layout.setContentsMargins(10, 10, 10, 10)
        
        self.account_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        
        login_layout.addRow(QLabel("Account:"), self.account_input)
        login_layout.addRow(QLabel("Password:"), self.password_input)
        
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
        self.update_button.clicked.connect(self.update_settings)

        actions_layout.addWidget(self.reset_button)
        actions_layout.addStretch(1) 
        actions_layout.addWidget(self.update_button)
        
        main_layout.addWidget(actions_widget)


    def update_settings(self):
        """Saves settings (account info, theme preference) and closes the window."""
        account = self.account_input.text()
        password = self.password_input.text()
        
        selected_theme = None
        if self.dark_theme_radio.isChecked():
            selected_theme = "dark"
        elif self.light_theme_radio.isChecked():
            selected_theme = "light"

        print(f"--- Settings Updated ---")
        print(f"Account: {account}")
        print(f"Password: {'*' * len(password)}")
        print(f"Theme: {selected_theme}")
        print(f"------------------------")

        # Apply the new theme if it changed
        if self.main_window_ref and selected_theme:
            self.main_window_ref.set_application_theme(selected_theme)
            
        self.close()

    def reset_settings(self):
        """Resets settings fields to hardcoded defaults (placeholder)."""
        self.account_input.clear()
        self.password_input.clear()
        
        # Default theme is Dark
        self.dark_theme_radio.setChecked(True)
        self.light_theme_radio.setChecked(False)
        
        print("Settings fields reset to default.")

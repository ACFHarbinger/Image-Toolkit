from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel, QWidget, QSizePolicy,
    QVBoxLayout, QGroupBox, QFormLayout,
    QLineEdit, QRadioButton, QHBoxLayout,
    QPushButton # Added QPushButton
)


class SettingsWindow(QWidget):
    """
    A standalone widget for the application settings, displayed as a modal window.
    """
    def __init__(self, parent=None):
        # CRITICAL FIX: Removed 'parent' from super() call but kept Qt.Window
        super().__init__(None, Qt.Window) 
        
        # FIX: Re-added setWindowTitle for OS window management
        self.setWindowTitle("Application Settings") 

        main_layout = QVBoxLayout(self)

        # --- MODIFICATION: Add Header Bar to mimic MainWindow ---
        header_widget = QWidget()
        header_widget.setObjectName("header_widget")
        header_widget.setStyleSheet("background-color: #4f545c; padding: 10px; border-bottom: 2px solid #5865f2;")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(10, 5, 10, 5)
        
        title_label = QLabel("Application Settings")
        title_label.setStyleSheet("color: white; font-size: 14pt; font-weight: bold;")
        header_layout.addWidget(title_label)
        header_layout.addStretch(1) 
        
        main_layout.addWidget(header_widget)
        # --- End Header Bar ---

        # Create a container for the content to provide padding
        content_container = QWidget()
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)


        # --- Login Information Section (Existing Content) ---
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
        
        # --- Preferences Section (Existing Content) ---
        prefs_groupbox = QGroupBox("Preferences")
        prefs_groupbox.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        prefs_layout = QVBoxLayout(prefs_groupbox)
        prefs_layout.setContentsMargins(10, 10, 10, 10)
        
        self.dark_theme_radio = QRadioButton("Dark Theme")
        self.light_theme_radio = QRadioButton("Light Theme")
        
        self.dark_theme_radio.setChecked(True) # Default
        
        prefs_layout.addWidget(self.dark_theme_radio)
        prefs_layout.addWidget(self.light_theme_radio)
        
        content_layout.addWidget(prefs_groupbox)
        
        # Add a stretch to push content up
        content_layout.addStretch(1)

        # Add the content container to the main layout
        main_layout.addWidget(content_container)

        
        # --- NEW MODIFICATION: Action Buttons at the bottom ---
        actions_widget = QWidget()
        actions_layout = QHBoxLayout(actions_widget)
        actions_layout.setContentsMargins(20, 10, 20, 20)
        actions_layout.setSpacing(10)
        
        # 1. Reset Button
        self.reset_button = QPushButton("Reset to default")
        self.reset_button.setObjectName("reset_button")
        self.reset_button.clicked.connect(self.reset_settings)
        
        # 2. Update Button
        self.update_button = QPushButton("Update settings")
        self.update_button.setObjectName("update_button")
        self.update_button.clicked.connect(self.update_settings)

        # Add buttons to the layout (Reset on the left, Update on the right)
        actions_layout.addWidget(self.reset_button)
        actions_layout.addStretch(1) # Push the update button to the right
        actions_layout.addWidget(self.update_button)
        
        main_layout.addWidget(actions_widget)
        # --- End NEW MODIFICATION ---


    def update_settings(self):
        """Button for saving settings."""
        account = self.account_input.text()
        is_dark = self.dark_theme_radio.isChecked()
        self.close() # Close the window after saving

    def reset_settings(self):
        """Button for resetting settings to defaults."""
        self.account_input.clear()
        self.dark_theme_radio.setChecked(True)
        self.light_theme_radio.setChecked(False)

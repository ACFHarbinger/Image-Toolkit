import os

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QImageReader
from PySide6.QtWidgets import (
    QLabel, QWidget, QTabWidget, 
    QSizePolicy, QPushButton, QStyle, QComboBox, # <-- QComboBox is now imported
    QVBoxLayout, QHBoxLayout, QApplication,
)
from . import SettingsWindow
from ..tabs import (
    WallpaperTab,
    MergeTab, DatabaseTab,
    ConvertTab, DeleteTab, 
    ScanMetadataTab, SearchTab, 
    ImageCrawlTab, DriveSyncTab,
)
from ..utils.styles import DARK_QSS, LIGHT_QSS
from ..utils.app_definitions import NEW_LIMIT_MB
try:
    from app.src.core.java_vault_manager import JavaVaultManager
except:
    from src.core.java_vault_manager import JavaVaultManager


class MainWindow(QWidget):
    def __init__(self, vault_manager: JavaVaultManager, dropdown=True, app_icon=None):
        super().__init__()
        
        # Store the authenticated vault manager instance
        self.vault_manager = vault_manager
        
        self.setWindowTitle("Image Database & Edit Toolkit")
        self.setMinimumSize(950, 950)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        QImageReader.setAllocationLimit(NEW_LIMIT_MB)
        
        # Initialize theme tracker
        self.current_theme = "dark"

        vbox = QVBoxLayout()
        
        self.settings_window = None 

        # --- Application Header ---
        header_widget = QWidget()
        header_widget.setObjectName("header_widget")
        header_widget.setStyleSheet(f"background-color: #2d2d30; padding: 10px; border-bottom: 2px solid #00bcd4;")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(10, 5, 10, 5)
        
        # Display the logged-in account name in the header
        try:
            account_name = self.vault_manager.load_account_credentials().get('account_name', 'Authenticated User')
        except Exception:
            account_name = 'Authenticated User'
            
        title_label = QLabel(f"Image Database and Toolkit - {account_name}")
        title_label.setStyleSheet(f"color: white; font-size: 18pt; font-weight: bold;")
        header_layout.addWidget(title_label)
        header_layout.addStretch(1) 
        
        # --- Settings button ---
        self.settings_button = QPushButton()
        if app_icon and os.path.exists(app_icon):
            settings_icon = QIcon(app_icon)
            self.settings_button.setIcon(settings_icon)
        else:
            settings_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ToolBarHorizontalExtensionButton)
            self.settings_button.setIcon(settings_icon)
            
        self.settings_button.setIconSize(QSize(24, 24))
        self.settings_button.setFixedSize(QSize(36, 36))
        self.settings_button.setObjectName("settings_button")
        self.settings_button.setToolTip("Open Settings")
        
        # Set the button as the default button, making it clickable with the Enter key
        self.settings_button.setDefault(True) 
        
        self.settings_button.setStyleSheet(f"""
            QPushButton#settings_button {{
                background-color: transparent;
                border: none;
                padding: 5px;
                border-radius: 18px; 
            }}
        """)
        header_layout.addWidget(self.settings_button)
        
        vbox.addWidget(header_widget)
        
        # ------------------------------------------------------------------
        # --- NEW: Command Selection (QComboBox) ---
        # ------------------------------------------------------------------
        command_layout = QHBoxLayout()
        command_label = QLabel("Select Category:")
        command_label.setStyleSheet("font-weight: 600;")
        command_layout.addWidget(command_label)
        
        self.command_combo = QComboBox()
        # Define the high-level categories based on the user's request
        self.command_combo.addItems(['System Tools', 'Database Management', 'Web Integration'])
        self.command_combo.currentTextChanged.connect(self.on_command_changed)
        self.command_combo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        command_layout.addWidget(self.command_combo)
        command_layout.addStretch()
        vbox.addLayout(command_layout)
        
        # ------------------------------------------------------------------
        # --- Tab Initialization and Mapping ---
        # ------------------------------------------------------------------
        # Instantiate all sub-command tabs once
        self.database_tab = DatabaseTab(dropdown=dropdown)
        self.search_tab = SearchTab(self.database_tab, dropdown=dropdown)
        self.scan_metadata_tab = ScanMetadataTab(self.database_tab, dropdown=dropdown)
        self.convert_tab = ConvertTab(dropdown=dropdown)
        self.merge_tab = MergeTab(dropdown=dropdown)
        self.delete_tab = DeleteTab(dropdown=dropdown)
        self.crawler_tab = ImageCrawlTab(dropdown=dropdown)
        self.drive_sync_tab = DriveSyncTab(dropdown=dropdown)
        self.wallpaper_tab = WallpaperTab(self.database_tab, dropdown=dropdown)

        # Set references *after* all tabs are created
        self.database_tab.scan_tab_ref = self.scan_metadata_tab 
        self.database_tab.search_tab_ref = self.search_tab

        # Define the hierarchical map based on the user's request
        self.all_tabs = {
            'System Tools': {
                "Convert Format": self.convert_tab,
                "Merge Images": self.merge_tab,
                "Delete Images": self.delete_tab,
                "Display Wallpaper": self.wallpaper_tab,
            }, 
            'Database Management': {
                "Database Configuration": self.database_tab,
                "Search Images": self.search_tab,
                "Scan Metadata": self.scan_metadata_tab,
            }, 
            'Web Integration': {
                "Web Crawler": self.crawler_tab,
                "Cloud Synchronization": self.drive_sync_tab,
            }
        }
        # --- End Tab Initialization ---

        # Tabs container (This will now hold the currently selected command's sub-tabs)
        self.tabs = QTabWidget()
        vbox.addWidget(self.tabs)
        
        # Set initial content based on the first item in the QComboBox
        self.on_command_changed(self.command_combo.currentText())

        self.settings_button.clicked.connect(self.open_settings_window)
        
        self.setLayout(vbox)
        
        # --- CRITICAL FIX: Apply theme after all widgets are initialized ---
        self.set_application_theme(self.current_theme)


    def on_command_changed(self, new_command: str):
        """
        Dynamically changes the tabs displayed in the QTabWidget based on 
        the selection in the QComboBox.
        """
        # Clear existing tabs
        self.tabs.clear()
        
        # Get the map of tabs for the selected command category
        tab_map = self.all_tabs.get(new_command, {})
        
        # Add the tabs to the QTabWidget
        for tab_name, tab_widget in tab_map.items():
            self.tabs.addTab(tab_widget, tab_name)

    # --- Theme Switching Logic ---
    def set_application_theme(self, theme_name):
        """Applies the selected theme (QSS) to the entire application."""
        # Theme specific colors
        if theme_name == "dark":
            qss = DARK_QSS
            self.current_theme = "dark"
            # Settings button styles
            hover_bg = "#5f646c"
            pressed_bg = "#00bcd4"
            accent_color = "#00bcd4"
            # Header label styles (Dark theme header is always dark BG)
            header_label_color = "white"
            header_widget_bg = "#2d2d30"
        elif theme_name == "light":
            qss = LIGHT_QSS
            self.current_theme = "light"
            # Settings button styles
            hover_bg = "#cccccc" 
            pressed_bg = "#007AFF"
            accent_color = "#007AFF"
            # Header label styles (User request: Black text on White background)
            header_label_color = "#1e1e1e" # Black text
            header_widget_bg = "#ffffff" # White background
        else:
            return 
            
        QApplication.instance().setStyleSheet(qss)
        
        # --- Header Widget (The bar itself) ---
        header_widget = self.findChild(QWidget, "header_widget")
        if header_widget:
            # Apply background and blue dash border
            header_widget.setStyleSheet(f"background-color: {header_widget_bg}; padding: 10px; border-bottom: 2px solid {accent_color};")
            
            # --- Header Label (The 'Image Database and Toolkit' text) ---
            title_label = header_widget.findChild(QLabel)
            if title_label:
                # Update the label to reflect the current account name
                try:
                    account_name = self.vault_manager.load_account_credentials().get('account_name', 'Authenticated User')
                except Exception:
                    account_name = 'Authenticated User'
                    
                title_label.setText(f"Image Database and Toolkit - {account_name}")
                title_label.setStyleSheet(f"color: {header_label_color}; font-size: 18pt; font-weight: bold;")

        # Re-apply the settings button style
        self.settings_button.setStyleSheet(f"""
            QPushButton#settings_button {{
                background-color: transparent;
                border: none;
                padding: 5px;
                border-radius: 18px; 
            }}
            QPushButton#settings_button:hover {{
                background-color: {hover_bg}; 
            }}
            QPushButton#settings_button:pressed {{
                background-color: {pressed_bg}; 
            }}
        """)


    def open_settings_window(self):
        """
        Instantiates and shows the SettingsWindow as a separate window.
        """
        if not self.settings_window:
            self.settings_window = SettingsWindow(self) 
            self.settings_window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose) 
            self.settings_window.destroyed.connect(lambda: self._reset_settings_window_ref())
            
        self.settings_window.show()
        self.settings_window.activateWindow()

    def _reset_settings_window_ref(self):
        """Resets the settings window reference when it is closed."""
        self.settings_window = None

    def on_tab_changed(self, index):
        pass

    def showEvent(self, event):
        super().showEvent(event)
        self._shown = True

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            # Ensure JVM shutdown on app exit
            if self.vault_manager:
                self.vault_manager.shutdown()
            QApplication.quit()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        """Ensure JVM shutdown on main window close."""
        if self.vault_manager:
            self.vault_manager.shutdown()
        super().closeEvent(event)

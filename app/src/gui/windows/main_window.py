import os

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QImageReader
from PySide6.QtWidgets import (
    QLabel, QWidget, QTabWidget, 
    QSizePolicy, QPushButton, QStyle,
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
from ..styles import DARK_QSS, LIGHT_QSS 
from ..app_definitions import NEW_LIMIT_MB
try:
    from app.src.core.java_vault_manager import JavaVaultManager
except:
    from src.core.java_vault_manager import JavaVaultManager


class MainWindow(QWidget):
    # CRITICAL: Now requires an authenticated JavaVaultManager instance
    def __init__(self, vault_manager: JavaVaultManager, dropdown=True, app_icon=None):
        super().__init__()
        
        # Store the authenticated vault manager instance
        self.vault_manager = vault_manager
        
        self.setWindowTitle("Image Database & Edit Toolkit")
        self.setMinimumSize(1000, 900)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        QImageReader.setAllocationLimit(NEW_LIMIT_MB)
        
        # Initialize theme tracker
        self.current_theme = "dark"

        vbox = QVBoxLayout()
        
        self.settings_window = None 

        # --- Application Header (Mimics React App Header) ---
        header_widget = QWidget()
        header_widget.setObjectName("header_widget")
        # NOTE: Initial style is set for Dark Theme default
        header_widget.setStyleSheet(f"background-color: #2d2d30; padding: 10px; border-bottom: 2px solid #00bcd4;")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(10, 5, 10, 5)
        
        # Display the logged-in account name in the header
        try:
            # We assume the account data is in the vault. 
            # We don't reload it here, but typically you'd cache the username.
            account_name = self.vault_manager.load_account_credentials().get('account_name', 'Authenticated User')
        except Exception:
            account_name = 'Authenticated User'
            
        title_label = QLabel(f"Image Database and Toolkit - {account_name}")
        title_label.setStyleSheet(f"color: white; font-size: 18pt; font-weight: bold;")
        header_layout.addWidget(title_label)
        header_layout.addStretch(1) 
        
        # --- Settings (app icon) button (self.settings_button is created here) ---
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
        
        # NOTE: Initial style will be overwritten by set_application_theme()
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
        
        # Tabs for subcommands
        self.tabs = QTabWidget()
        
        # --- Create tabs in order ---
        self.database_tab = DatabaseTab(dropdown=dropdown)
        self.search_tab = SearchTab(self.database_tab, dropdown=dropdown)
        self.scan_metadata_tab = ScanMetadataTab(self.database_tab, dropdown=dropdown)
        self.convert_tab = ConvertTab(dropdown=dropdown)
        self.merge_tab = MergeTab(dropdown=dropdown)
        self.delete_tab = DeleteTab(dropdown=dropdown)
        self.crawler_tab = ImageCrawlTab(dropdown=dropdown)
        self.drive_sync_tab = DriveSyncTab(dropdown=dropdown)
        self.wallpaper_tab = WallpaperTab(self.database_tab, dropdown=dropdown)
        
        # --- Set references *after* all tabs are created ---
        self.database_tab.scan_tab_ref = self.scan_metadata_tab 
        self.database_tab.search_tab_ref = self.search_tab

        self.tabs.addTab(self.convert_tab, "Convert")
        self.tabs.addTab(self.merge_tab, "Merge")
        self.tabs.addTab(self.delete_tab, "Delete")
        self.tabs.addTab(self.search_tab, "Search")
        self.tabs.addTab(self.database_tab, "Database")
        self.tabs.addTab(self.scan_metadata_tab, "Scan Metadata")
        self.tabs.addTab(self.crawler_tab, "Web Crawler")
        self.tabs.addTab(self.drive_sync_tab, "Drive Sync")
        self.tabs.addTab(self.wallpaper_tab, "Wallpaper")
        
        self.tabs.currentChanged.connect(self.on_tab_changed)
        
        self.settings_button.clicked.connect(self.open_settings_window)
        
        vbox.addWidget(self.tabs)

        self.setLayout(vbox)
        
        # --- CRITICAL FIX: Apply theme after all widgets are initialized ---
        self.set_application_theme(self.current_theme)

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
                    
                title_label.setText(f"Image Database and Toolkit - Logged in as: {account_name}")
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

import os

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QImageReader
from PySide6.QtWidgets import (
    QSizePolicy, QPushButton, QStyle, QComboBox,
    QLabel, QWidget, QTabWidget, QScrollArea,
    QVBoxLayout, QHBoxLayout, QApplication,
)
from .windows import SettingsWindow
from .tabs import (
    WallpaperTab,
    MergeTab, DatabaseTab,
    ConvertTab, DeleteTab, 
    ScanMetadataTab, SearchTab, 
    ImageCrawlTab, DriveSyncTab,
)
from .styles.style import DARK_QSS, LIGHT_QSS
from .utils.app_definitions import NEW_LIMIT_MB
from backend.src.core.java_vault_manager import JavaVaultManager


class MainWindow(QWidget):
    def __init__(self, vault_manager: JavaVaultManager, dropdown=True, app_icon=None):
        super().__init__()
        
        # Store the authenticated vault manager instance
        self.vault_manager = vault_manager
        
        self.setWindowTitle("Image Database & Edit Toolkit")
        self.setMinimumWidth(800)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        QImageReader.setAllocationLimit(NEW_LIMIT_MB)
        
        # --- LOAD THEME AND ACCOUNT INFO FROM VAULT (LOAD 1 OF 1) ---
        account_name = 'Authenticated User'
        initial_theme = "dark"
        
        # Cache the credentials for reuse throughout initialization
        self.cached_creds = {}

        if self.vault_manager:
            try:
                # *** FIRST AND ONLY INITIAL LOAD OF VAULT DATA ***
                self.cached_creds = self.vault_manager.load_account_credentials()
                account_name = self.cached_creds.get('account_name', 'Authenticated User')
                initial_theme = self.cached_creds.get('theme', 'dark')
            except Exception as e:
                print(f"Warning: Failed to load account credentials or theme: {e}")
                
        # Initialize theme tracker with the loaded value
        self.current_theme = initial_theme

        vbox = QVBoxLayout()
        
        # settings_window is tracked here
        self.settings_window = None 

        # --- Application Header ---
        header_widget = QWidget()
        header_widget.setObjectName("header_widget")
        # Note: Initial style is set here but will be immediately overwritten by set_application_theme
        header_widget.setStyleSheet(f"background-color: #2d2d30; padding: 10px; border-bottom: 2px solid #00bcd4;")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(10, 5, 10, 5)
        
        # Display the loaded account name in the header
        self.title_label = QLabel(f"Image Database and Toolkit - {account_name}")
        self.title_label.setStyleSheet(f"color: white; font-size: 18pt; font-weight: bold;")
        header_layout.addWidget(self.title_label)
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
        # Use the theme loaded from the vault
        self.set_application_theme(self.current_theme)


    def on_command_changed(self, new_command: str):
        """
        Dynamically changes the tabs displayed in the QTabWidget based on 
        the selection in the QComboBox, wrapping each tab in a QScrollArea.
        """
        # Clear existing tabs
        self.tabs.clear()
        
        # Get the map of tabs for the selected command category
        tab_map = self.all_tabs.get(new_command, {})
        
        # Add the tabs to the QTabWidget
        for tab_name, tab_widget in tab_map.items():
            
            # --- START NEW SCROLLABLE WRAPPER ---
            # 1. Create a QScrollArea instance
            scroll_wrapper = QScrollArea()
            # 2. Ensure the scroll area resizes to its content size hint
            scroll_wrapper.setWidgetResizable(True)
            # 3. Remove the scroll area border for a cleaner look
            scroll_wrapper.setFrameShape(QScrollArea.Shape.NoFrame)
            
            # 4. Set the actual tab widget (e.g., DatabaseTab) as the scroll area's widget
            # Note: We set the tab widget itself as the content to be scrolled.
            scroll_wrapper.setWidget(tab_widget)
            
            # 5. Add the scroll area to the QTabWidget instead of the tab widget itself
            self.tabs.addTab(scroll_wrapper, tab_name)
            # --- END NEW SCROLLABLE WRAPPER ---
            
    def update_header(self):
        """Updates the header text and style after a settings change (like password reset)."""
        # Reload account name by forcing a reload of credentials
        try:
            # Reload credentials to get the latest account name/theme/etc.
            self.cached_creds = self.vault_manager.load_account_credentials()
            account_name = self.cached_creds.get('account_name', 'Authenticated User')
        except Exception:
            account_name = 'Authenticated User'
            
        # Update the label text
        self.title_label.setText(f"Image Database and Toolkit - {account_name}")
        
        # Re-apply theme to ensure styles are correct after text update
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
            title_label = self.title_label # Use the stored reference
            if title_label:
                # Retrieve account name from the cached credentials, avoiding a second vault load
                account_name = self.cached_creds.get('account_name', 'Authenticated User')
                    
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
        """
        Ensure JVM shutdown and close all child windows on main window close.
        """
        
        # 1. Close the Settings window if open
        if self.settings_window:
            self.settings_window.close()
            # Note: self.settings_window is cleared by its destroyed signal connection
        
        # 2. Close all Slideshow Queue windows
        # Note: self.wallpaper_tab.open_queue_windows is the list we need to close
        for win in list(self.wallpaper_tab.open_queue_windows):
            if win.isVisible():
                win.close()
        
        # 3. Close all Image Preview windows
        # Note: self.wallpaper_tab.open_image_preview_windows is the list we need to close
        for win in list(self.wallpaper_tab.open_image_preview_windows):
            if win.isVisible():
                win.close()
                
        # 4. Ensure JVM shutdown
        if self.vault_manager:
            self.vault_manager.shutdown()
            
        super().closeEvent(event)

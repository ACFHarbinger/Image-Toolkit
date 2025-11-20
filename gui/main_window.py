import os
import sys

from PySide6.QtCore import Qt, QSize, QObject
from PySide6.QtGui import QIcon, QImageReader
from PySide6.QtWidgets import (
    QSizePolicy, QPushButton, QStyle, QComboBox,
    QLabel, QWidget, QTabWidget, QScrollArea,
    QVBoxLayout, QHBoxLayout, QApplication,
    QMessageBox
)
from .windows import SettingsWindow
from .tabs import (
    MergeTab, DatabaseTab,
    ConvertTab, DeleteTab, 
    ScanMetadataTab, SearchTab, 
    ImageCrawlTab, DriveSyncTab,
    WallpaperTab, WebRequestsTab,
)
from .tabs.deep_learning import (
    R3GANEvaluateTab, R3GANGenerateTab,
    R3GANTrainTab, MetaCLIPInferenceTab,
    SD3ControlNetTab, SD3TextToImageTab,
)
from .styles.style import DARK_QSS, LIGHT_QSS
from .utils.app_definitions import NEW_LIMIT_MB
from backend.src.core.java_vault_manager import JavaVaultManager


class MainWindow(QWidget):
    def __init__(self, vault_manager: JavaVaultManager, dropdown=True, app_icon=None):
        super().__init__()
        
        # Store the authenticated vault manager instance
        self.vault_manager = vault_manager
        
        self.setWindowTitle("Image Database and Edit Toolkit")
        self.setMinimumWidth(800)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        QImageReader.setAllocationLimit(NEW_LIMIT_MB)
        
        # --- LOAD THEME AND ACCOUNT INFO FROM VAULT (LOAD 1 OF 1) ---
        account_name = 'Authenticated User'
        initial_theme = "dark"
        
        self.cached_creds = {}

        if self.vault_manager:
            try:
                self.cached_creds = self.vault_manager.load_account_credentials()
                account_name = self.cached_creds.get('account_name', 'Authenticated User')
                initial_theme = self.cached_creds.get('theme', 'dark')
            except Exception as e:
                print(f"Warning: Failed to load account credentials or theme: {e}")
                
        self.current_theme = initial_theme

        vbox = QVBoxLayout()
        self.settings_window = None 

        # --- Application Header ---
        header_widget = QWidget()
        header_widget.setObjectName("header_widget")
        header_widget.setStyleSheet(f"background-color: #2d2d30; padding: 10px; border-bottom: 2px solid #00bcd4;")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(10, 5, 10, 5)
        
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
        
        # --- Command Selection ---
        command_layout = QHBoxLayout()
        command_label = QLabel("Select Category:")
        command_label.setStyleSheet("font-weight: 600;")
        command_layout.addWidget(command_label)
        
        self.command_combo = QComboBox()
        self.command_combo.addItems(['System Tools', 'Database Management', 'Web Integration', 'Deep Learning'])
        self.command_combo.currentTextChanged.connect(self.on_command_changed)
        self.command_combo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        command_layout.addWidget(self.command_combo)
        command_layout.addStretch()
        vbox.addLayout(command_layout)
        
        # --- Tab Initialization ---
        self.database_tab = DatabaseTab(dropdown=dropdown)
        self.search_tab = SearchTab(self.database_tab, dropdown=dropdown)
        self.scan_metadata_tab = ScanMetadataTab(self.database_tab, dropdown=dropdown)
        self.convert_tab = ConvertTab(dropdown=dropdown)
        self.merge_tab = MergeTab(dropdown=dropdown)
        self.delete_tab = DeleteTab(dropdown=dropdown)
        self.crawler_tab = ImageCrawlTab(dropdown=dropdown)
        self.drive_sync_tab = DriveSyncTab(dropdown=dropdown)
        self.wallpaper_tab = WallpaperTab(self.database_tab, dropdown=dropdown)
        self.web_requests_tab = WebRequestsTab(dropdown=dropdown)

        # Deep Learning Tabs
        self.r3gan_gen_tab = R3GANGenerateTab()
        self.r3gan_train_tab = R3GANTrainTab()
        self.r3gan_eval_tab = R3GANEvaluateTab()
        self.metaclip_infer_tab = MetaCLIPInferenceTab()
        self.sd3_t2i_tab = SD3TextToImageTab()
        self.sd3_controlnet_tab = SD3ControlNetTab()

        # --- LINK TABS (Critical for Cross-Tab Communication) ---
        self.database_tab.scan_tab_ref = self.scan_metadata_tab 
        self.database_tab.search_tab_ref = self.search_tab
        self.database_tab.merge_tab_ref = self.merge_tab       # <--- NEW
        self.database_tab.delete_tab_ref = self.delete_tab     # <--- NEW
        self.database_tab.wallpaper_tab_ref = self.wallpaper_tab # <--- NEW

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
                "Web Requests": self.web_requests_tab,
                "Cloud Synchronization": self.drive_sync_tab,
            },
            'Deep Learning': {
                "GAN Train": self.r3gan_train_tab,
                "GAN Evaluate": self.r3gan_eval_tab,
                "GAN Generate": self.r3gan_gen_tab,
                "DGM Text-to-Image": self.sd3_t2i_tab,
                "DGM ControlNet": self.sd3_controlnet_tab,
                "CLIP Inference": self.metaclip_infer_tab,
            },
        }

        self.tabs = QTabWidget()
        vbox.addWidget(self.tabs)
        
        self.on_command_changed(self.command_combo.currentText())

        self.settings_button.clicked.connect(self.open_settings_window)
        
        self.setLayout(vbox)
        self.set_application_theme(self.current_theme)
        self.showMaximized()


    def on_command_changed(self, new_command: str):
        """
        Dynamically changes the tabs. 
        CRITICAL: Rescues widgets from ScrollAreas before clearing to prevent Segfaults.
        """
        # --- FIX START: Rescue widgets from deletion ---
        # QScrollArea takes ownership of its widget. If we clear self.tabs,
        # the QScrollArea is deleted, and it deletes our reusable Tab object (SearchTab, etc).
        # We must take the widget back before clearing.
        count = self.tabs.count()
        for i in range(count):
            scroll_area = self.tabs.widget(i)
            if isinstance(scroll_area, QScrollArea):
                # takeWidget() unparents the widget and passes ownership back to us
                # preventing it from being destroyed.
                scroll_area.takeWidget()
        # --- FIX END ---

        self.tabs.clear()
        
        tab_map = self.all_tabs.get(new_command, {})
        
        for tab_name, tab_widget in tab_map.items():
            scroll_wrapper = QScrollArea()
            scroll_wrapper.setWidgetResizable(True)
            scroll_wrapper.setFrameShape(QScrollArea.Shape.NoFrame)
            scroll_wrapper.setWidget(tab_widget)
            self.tabs.addTab(scroll_wrapper, tab_name)
            
    def update_header(self):
        try:
            self.cached_creds = self.vault_manager.load_account_credentials()
            account_name = self.cached_creds.get('account_name', 'Authenticated User')
        except Exception:
            account_name = 'Authenticated User'
        self.title_label.setText(f"Image Database and Toolkit - {account_name}")
        self.set_application_theme(self.current_theme)

    def restart_application(self):
        self.close()
        QApplication.instance().quit()
        print("Application attempting relaunch...")
        try:
            os.execv(sys.executable, ['python'] + sys.argv)
        except OSError as e:
            QMessageBox.critical(self, "Relaunch Error", f"Failed to execute relaunch command:\n{e}\nPlease restart manually.")
            print(f"FATAL: os.execv failed: {e}")

    def set_application_theme(self, theme_name):
        if theme_name == "dark":
            qss = DARK_QSS
            self.current_theme = "dark"
            hover_bg = "#5f646c"
            pressed_bg = "#00bcd4"
            accent_color = "#00bcd4"
            header_label_color = "white"
            header_widget_bg = "#2d2d30"
        elif theme_name == "light":
            qss = LIGHT_QSS
            self.current_theme = "light"
            hover_bg = "#cccccc" 
            pressed_bg = "#007AFF"
            accent_color = "#007AFF"
            header_label_color = "#1e1e1e"
            header_widget_bg = "#ffffff"
        else:
            return 
            
        QApplication.instance().setStyleSheet(qss)
        
        header_widget = self.findChild(QWidget, "header_widget")
        if header_widget:
            header_widget.setStyleSheet(f"background-color: {header_widget_bg}; padding: 10px; border-bottom: 2px solid {accent_color};")
            title_label = self.title_label
            if title_label:
                account_name = self.cached_creds.get('account_name', 'Authenticated User')
                title_label.setText(f"Image Database and Toolkit - {account_name}")
                title_label.setStyleSheet(f"color: {header_label_color}; font-size: 18pt; font-weight: bold;")

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
        if not self.settings_window:
            self.settings_window = SettingsWindow(self) 
            self.settings_window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose) 
            self.settings_window.destroyed.connect(lambda: self._reset_settings_window_ref())
        self.settings_window.show()
        self.settings_window.activateWindow()

    def _reset_settings_window_ref(self):
        self.settings_window = None

    def showEvent(self, event):
        super().showEvent(event)
        self._shown = True

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            if self.vault_manager:
                self.vault_manager.shutdown()
            QApplication.quit()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        if self.settings_window:
            self.settings_window.close()
        
        def safe_close_windows(window_list):
            for win in list(window_list):
                if win: 
                    try:
                        win.close()
                    except RuntimeError:
                        pass

        if hasattr(self.wallpaper_tab, 'open_queue_windows'):
            safe_close_windows(self.wallpaper_tab.open_queue_windows)
        if hasattr(self.wallpaper_tab, 'open_image_preview_windows'):
            safe_close_windows(self.wallpaper_tab.open_image_preview_windows)
        if hasattr(self.scan_metadata_tab, 'open_preview_windows'):
            safe_close_windows(self.scan_metadata_tab.open_preview_windows)
            
        if self.vault_manager:
            self.vault_manager.shutdown()
            
        super().closeEvent(event)

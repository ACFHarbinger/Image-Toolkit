import os
import sys
import signal
import argparse
import traceback

from pathlib import Path
from PySide6.QtCore import QTimer, Qt, QSize
from PySide6.QtGui import QIcon, QImageReader
from PySide6.QtWidgets import (
    QLabel, QWidget, QTabWidget, 
    QSizePolicy, QPushButton, QStyle,
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
from .styles import GLOBAL_QSS
from .app_definitions import NEW_LIMIT_MB


class MainWindow(QWidget):
    def __init__(self, dropdown=True, app_icon=None):
        super().__init__()
        self.setWindowTitle("Image Database & Edit Toolkit")
        self.setMinimumSize(1080, 900)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        QImageReader.setAllocationLimit(NEW_LIMIT_MB)
        
        # Apply the global style sheet
        QApplication.instance().setStyleSheet(GLOBAL_QSS)

        vbox = QVBoxLayout()
        
        # --- MODIFICATION: Initialize settings window to None ---
        self.settings_window = None 

        # --- Application Header (Mimics React App Header) ---
        header_widget = QWidget()
        header_widget.setObjectName("header_widget")
        header_widget.setStyleSheet("background-color: #4f545c; padding: 10px; border-bottom: 2px solid #5865f2;")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(10, 5, 10, 5)
        
        title_label = QLabel("Image Database and Toolkit")
        title_label.setStyleSheet("color: white; font-size: 18pt; font-weight: bold;")
        header_layout.addWidget(title_label)
        header_layout.addStretch(1) 
        
        # --- Settings (app icon) button ---
        self.settings_button = QPushButton()
        
        # Use the application icon file path
        if app_icon and os.path.exists(app_icon):
            settings_icon = QIcon(app_icon)
            self.settings_button.setIcon(settings_icon)
        else:
            # Fallback to a standard icon if the file path is not found/invalid
            settings_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ToolBarHorizontalExtensionButton)
            self.settings_button.setIcon(settings_icon)
            
        self.settings_button.setIconSize(QSize(24, 24))
        self.settings_button.setFixedSize(QSize(36, 36))
        self.settings_button.setObjectName("settings_button")
        self.settings_button.setToolTip("Open Settings")
        
        # Style the button to be transparent and fit in
        self.settings_button.setStyleSheet("""
            QPushButton#settings_button {
                background-color: transparent;
                border: none;
                padding: 5px;
                border-radius: 18px; /* Make it circular */
            }
            QPushButton#settings_button:hover {
                background-color: #5f646c; /* Slightly lighter shade */
            }
            QPushButton#settings_button:pressed {
                background-color: #5865f2; /* Highlight color */
            }
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
        
        # --- MODIFICATION: SettingsTab instance is REMOVED from here ---

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
        
        # --- MODIFICATION: Settings tab is REMOVED from here ---

        self.tabs.currentChanged.connect(self.on_tab_changed)
        
        # --- MODIFICATION: Connect settings button click to open_settings_window ---
        self.settings_button.clicked.connect(self.open_settings_window)
        
        vbox.addWidget(self.tabs)

        self.setLayout(vbox)

    def open_settings_window(self):
        """
        Instantiates and shows the SettingsWindow as a separate window.
        Uses self.settings_window to track the instance and prevent opening duplicates.
        """
        if not self.settings_window:
            # Pass 'self' as the parent so the settings window is centered over the main window
            self.settings_window = SettingsWindow(self) 
            self.settings_window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose) # Clean up when closed
            # Connect the close signal to reset the reference
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
            QApplication.quit()
        else:
            super().keyPressEvent(event)


def main(args):
    app = QApplication(sys.argv)
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    timer = QTimer()
    timer.start(100) 
    timer.timeout.connect(lambda: None) 

    path = Path(os.getcwd())
    parts = path.parts
    icon_file_path = os.path.join(Path(*parts[:parts.index('Image-Toolkit') + 1]), 
                                    'src', 'images', "image_toolkit_icon.png")
    try:
        try:
            app_icon = QIcon(icon_file_path)
            app.setWindowIcon(app_icon)
        except Exception as e:
            pass 
        
        w = MainWindow(dropdown=~args['dropdown'], app_icon=icon_file_path)
        
        # --- MODIFICATION: Call showMaximized() to open in full size ---
        w.showMaximized()
        
        exit_code = app.exec()
    except KeyboardInterrupt:
        print("\nExiting due to Ctrl+C...")
        exit_code = 2
    except Exception as e:
        exit_code = 1
        traceback.print_exc(file=sys.stdout)
        print("###############" * 10)
        print(e)
    finally:
        sys.exit(exit_code)


if __name__ =="__main__":
    gui_parser = argparse.ArgumentParser(add_help=False)
    gui_parser.add_argument('--no_dropdown', action='store_true', help="Disable dropdown buttons for optional fields")
    main(vars(gui_parser.parse_args()))
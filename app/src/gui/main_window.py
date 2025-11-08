import os
import sys
import signal
import argparse
import traceback

from pathlib import Path
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QIcon, QImageReader
from PySide6.QtWidgets import (
    QLabel, QWidget, QTabWidget, QSizePolicy,
    QVBoxLayout, QHBoxLayout, QApplication,
)
from .tabs import (
    MergeTab, DatabaseTab,
    ConvertTab, DeleteTab, 
    ScanFSETab, SearchTab, 
    ImageCrawlTab, DriveSyncTab
)
from .styles import GLOBAL_QSS
from .app_definitions import NEW_LIMIT_MB


class MainWindow(QWidget):
    def __init__(self, dropdown=True):
        super().__init__()
        self.setWindowTitle("Image Database & Edit Toolkit")
        self.setMinimumSize(1080, 900)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        QImageReader.setAllocationLimit(NEW_LIMIT_MB)
        
        # Apply the global style sheet
        QApplication.instance().setStyleSheet(GLOBAL_QSS)

        vbox = QVBoxLayout()

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
        
        vbox.addWidget(header_widget)
        
        # Tabs for subcommands
        self.tabs = QTabWidget()
        
        # --- MODIFICATION: Create tabs in order ---
        self.database_tab = DatabaseTab(dropdown=dropdown)
        self.search_tab = SearchTab(self.database_tab, dropdown=dropdown)
        self.scan_fse_tab = ScanFSETab(self.database_tab, dropdown=dropdown)
        self.convert_tab = ConvertTab(dropdown=dropdown)
        self.merge_tab = MergeTab(dropdown=dropdown)
        self.delete_tab = DeleteTab(dropdown=dropdown)
        self.crawler_tab = ImageCrawlTab(dropdown=dropdown)
        self.drive_sync_tab = DriveSyncTab(dropdown=dropdown)
        
        # --- MODIFICATION: Set references *after* all tabs are created ---
        self.database_tab.scan_tab_ref = self.scan_fse_tab 
        self.database_tab.search_tab_ref = self.search_tab # This is the missing link

        self.tabs.addTab(self.convert_tab, "Convert")
        self.tabs.addTab(self.merge_tab, "Merge")
        self.tabs.addTab(self.delete_tab, "Delete")
        self.tabs.addTab(self.search_tab, "Search")
        self.tabs.addTab(self.database_tab, "Database")
        self.tabs.addTab(self.scan_fse_tab, "Scan")
        self.tabs.addTab(self.crawler_tab, "Web Crawler")
        self.tabs.addTab(self.drive_sync_tab, "Drive Sync")

        self.tabs.currentChanged.connect(self.on_tab_changed)
        
        vbox.addWidget(self.tabs)

        self.setLayout(vbox)

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
        
        w = MainWindow(dropdown=args['dropdown'])
        
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
    gui_parser.add_argument('--dropdown', type=bool, default=True, help="Use dropdown buttons for optional fields")
    main(vars(gui_parser.parse_args()))
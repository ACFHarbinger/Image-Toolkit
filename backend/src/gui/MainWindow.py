import os
import sys
import signal
import argparse
import traceback

from pathlib import Path
from PySide6.QtGui import QIcon
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QLabel, QWidget, QTabWidget, QSizePolicy,
    QVBoxLayout, QHBoxLayout, QApplication,
)
from .tabs import (
    MergeTab, DatabaseTab,
    ConvertTab, DeleteTab, 
    ScanFSETab, SearchTab, 
    ImageCrawlTab
)


# --- GLOBAL STYLE SHEET (QSS) to mimic React/Tailwind Dark Mode ---
GLOBAL_QSS = """
    /* General Dark Mode Base */
    QWidget, QMainWindow, QDialog {
        background-color: #2c2f33; /* Dark background */
        color: #f2f2f2; /* Light text */
        font-family: Arial, sans-serif;
    }
    
    /* Buttons - Modern, rounded style */
    QPushButton {
        background-color: #5865f2; /* Violet/Indigo base */
        color: white;
        border: none;
        padding: 8px 16px;
        border-radius: 8px; /* Rounded corners */
        font-weight: bold;
        /* REMOVED: transition: background-color 0.2s; */
    }
    QPushButton:hover {
        background-color: #4754c4; /* Slightly darker violet on hover */
    }
    QPushButton:pressed {
        background-color: #3f479a;
    }
    QPushButton:disabled {
        background-color: #4f545c; /* Darker gray for disabled */
        color: #a0a0a0;
    }
    
    /* Tab Widget Styling */
    QTabWidget::pane { /* The border around the tabs */
        border: 1px solid #4f545c;
        background-color: #2c2f33;
        border-radius: 8px;
    }
    QTabBar::tab {
        background: #36393f; /* Slightly lighter tab background */
        color: #b9bbbe;
        padding: 8px 15px;
        border-top-left-radius: 8px;
        border-top-right-radius: 8px;
        margin-right: 2px;
    }
    QTabBar::tab:selected {
        background: #4f545c; /* Highlight selected tab */
        color: white;
        font-weight: bold;
    }
    QTabBar::tab:hover {
        background: #5865f2;
        color: white;
    }

    /* Input Fields */
    QLineEdit, QComboBox, QSpinBox, QTextEdit {
        background-color: #36393f; /* Darker input background */
        color: #f2f2f2;
        border: 1px solid #4f545c;
        padding: 6px;
        border-radius: 4px;
    }
    
    /* Group Boxes */
    QGroupBox {
        border: 1px solid #4f545c;
        margin-top: 20px;
        border-radius: 8px;
        padding-top: 15px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top center; 
        padding: 0 10px;
        background-color: #5865f2; /* Violet title background */
        color: white;
        border-radius: 4px;
    }
    
    /* Labels */
    QLabel {
        color: #f2f2f2;
    }
    
    /* Scroll Area (for image gallery) */
    QScrollArea {
        border: 1px solid #4f545c;
        border-radius: 8px;
    }

    /* --- SCROLL BAR STYLING FOR VISIBILITY --- */
    QScrollBar:vertical, QScrollBar:horizontal {
        border: 1px solid #36393f;
        background: #36393f; /* Dark background color for the trough/track */
        width: 10px; /* Width for vertical scrollbar */
        height: 10px; /* Height for horizontal scrollbar */
        margin: 0px 0px 0px 0px;
    }

    QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
        background: #b9bbbe; /* Light gray color for the handle (visible part) */
        min-height: 20px;
        min-width: 20px;
        border-radius: 4px;
    }
    
    QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {
        background: #f2f2f2; /* Brighter white on hover */
    }
    
    /* Hide the buttons/arrows at the ends of the scrollbar */
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
        border: none;
        background: none;
    }
"""


class MainWindow(QWidget):
    def __init__(self, dropdown=True):
        super().__init__()
        self.setWindowTitle("Image Database & Edit Toolkit")
        self.setMinimumSize(1080, 900)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Apply the global style sheet
        QApplication.instance().setStyleSheet(GLOBAL_QSS)

        vbox = QVBoxLayout()

        # --- Application Header (Mimics React App Header) ---
        header_widget = QWidget()
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
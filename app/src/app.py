import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
from .gui.MainWindow import MainWindow
from .utils.definitions import ICON_FILE


def launch_app():
    app = QApplication(sys.argv)
    try:
        app_icon = QIcon(ICON_FILE)
        app.setWindowIcon(app_icon)
    except Exception:
        pass 
    
    w = MainWindow(dropdown=True)
    w.show()
    app.exec()


if __name__ =="__main__":
    launch_app()
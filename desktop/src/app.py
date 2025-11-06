import os
import sys

from pathlib import Path
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
from ..src.gui.MainWindow import MainWindow


def launch_app():
    app = QApplication(sys.argv)
    path = Path(os.getcwd())
    parts = path.parts
    icon_file_path = os.path.join(Path(*parts[:parts.index('Image-Toolkit') + 1]), 
                                    'src', 'images', "image_toolkit_icon.png")
    try:
        app_icon = QIcon(icon_file_path)
        app.setWindowIcon(app_icon)
    except Exception as e:
        pass 
    
    w = MainWindow(dropdown=True)
    w.show()
    app.exec()


if __name__ =="__main__":
    launch_app()
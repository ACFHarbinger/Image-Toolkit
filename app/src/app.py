import sys
import signal
import traceback

from PySide6.QtGui import QIcon
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from .gui.main_window import MainWindow
from .utils.definitions import ICON_FILE


def log_uncaught_exceptions(ex_type, ex_value, ex_traceback):
    """Handler for uncaught exceptions that prints traceback to console."""
    sys.__excepthook__(ex_type, ex_value, ex_traceback) # Call the default handler first
    print("\n--- Uncaught Python Exception ---")
    traceback.print_exception(ex_type, ex_value, ex_traceback)
    print("-----------------------------------")


def launch_app():
    # This allows the Python interpreter to process signals (like SIGINT).
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    timer = QTimer()
    timer.start(100) # Check every 100 milliseconds
    timer.timeout.connect(lambda: None) # Do nothing, just wake up Python

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
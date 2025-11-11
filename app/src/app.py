import sys
import signal
import traceback
import threading

from PySide6.QtGui import QIcon
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from .utils.definitions import ICON_FILE, CTRL_C_TIMEOUT
from .gui.main_window import MainWindow


def log_uncaught_exceptions(ex_type, ex_value, ex_traceback):
    """Handler for uncaught exceptions that prints traceback to console."""
    sys.__excepthook__(ex_type, ex_value, ex_traceback) # Call the default handler first
    print("\n--- Uncaught Python Exception ---")
    traceback.print_exception(ex_type, ex_value, ex_traceback)
    print("-----------------------------------")


def launch_app(opts):
    app = QApplication(sys.argv)
    try:
        app_icon = QIcon(ICON_FILE)
        app.setWindowIcon(app_icon)
    except Exception:
        print(f"WARNING: Failed to set application icon. Ensure '{ICON_FILE}' exists.") 

    current_window = None
    
    # Create a custom signal handler that works with Qt
    def handle_interrupt(signum, frame):
        """Handle Ctrl+C signal by gracefully closing the application"""
        print("\nCtrl+C received - closing application...")
        if current_window is not None:
            current_window.close()
        app.quit()
        # Force exit if app doesn't quit quickly
        threading.Timer(CTRL_C_TIMEOUT, lambda: sys.exit(1)).start()
    
    # Set up signal handler for Ctrl+C
    signal.signal(signal.SIGINT, handle_interrupt)
    
    def launch_gui(dropdown=True): 
        """Creates and shows a new instance of the MainWindow."""
        nonlocal current_window
        
        # 1. Check if an old instance exists
        if current_window is not None:
            current_window.close() 

        # 2. Create the new window instance, passing the saved tab_index
        current_window = MainWindow(
            dropdown=dropdown, 
            #restart_callback=launch_gui,
            app_icon=ICON_FILE,
        )
        current_window.show()
    
    launch_gui(dropdown=~opts['no_dropdown'])
    
    # Install a custom event filter to catch the interrupt
    old_handler = signal.signal(signal.SIGINT, signal.SIG_DFL)
    try:
        return app.exec()
    finally:
        # Restore original handler
        signal.signal(signal.SIGINT, old_handler)


if __name__ =="__main__":
    launch_app({'no_dropdown': False})
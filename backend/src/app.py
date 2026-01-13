import os
import sys
import signal
import traceback
import threading

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtCore import QUrl
from gui.src.windows import LoginWindow
from gui.src.main_backend import MainBackend
from backend.src.core.file_system_entries import FSETool
from backend.src.utils.definitions import ICON_FILE, CTRL_C_TIMEOUT


def log_uncaught_exceptions(ex_type, ex_value, ex_traceback):
    """Handler for uncaught exceptions that prints traceback to console."""
    sys.__excepthook__(
        ex_type, ex_value, ex_traceback
    )  # Call the default handler first
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

    # We will track the active window (either login or main)
    active_window = None

    # Create a custom signal handler that works with Qt
    def handle_interrupt(signum, frame):
        """Handle Ctrl+C signal by gracefully closing the application"""
        print("\nCtrl+C received - closing application...")
        if active_window is not None:
            active_window.close()
        app.quit()
        # Force exit if app doesn't quit quickly
        threading.Timer(CTRL_C_TIMEOUT, lambda: sys.exit(1)).start()

    # Set up signal handler for Ctrl+C
    signal.signal(signal.SIGINT, handle_interrupt)

    def launch_main_gui(vault_manager):
        """
        Creates and shows the MainWindow after successful authentication.
        Replaces the LoginWindow.
        """
        nonlocal active_window


        # 1. Close the login window if it's still around
        if active_window and isinstance(active_window, LoginWindow):
            # The LoginWindow's closeEvent handles JVM shutdown if needed
            active_window.close()

        # 2. Launch QML Application
        engine = QQmlApplicationEngine()
        
        # Initialize Backend Bridge
        main_backend = MainBackend(vault_manager)
        
        # Set Context Property
        engine.rootContext().setContextProperty("mainBackend", main_backend)
        
        # Load QML
        qml_file = os.path.join(os.path.dirname(__file__), "../../gui/qml/Main.qml")
        engine.load(QUrl.fromLocalFile(qml_file))
        
        if not engine.rootObjects():
            print("Error: QML file failed to load. Exiting.")
            sys.exit(-1)

        # Keep reference to engine to prevent garbage collection
        active_window = engine 

    # Create and show the Login Window
    login_window = LoginWindow()
    # Connect the success signal to the function that launches the main app
    login_window.login_successful.connect(launch_main_gui)
    active_window = login_window
    active_window.show()
    # --- END OF NEW LOGIN FLOW ---

    # Install a custom event filter to catch the interrupt
    old_handler = signal.signal(signal.SIGINT, signal.SIG_DFL)
    try:
        return app.exec()
    finally:
        # Restore original handler
        signal.signal(signal.SIGINT, old_handler)


if __name__ == "__main__":
    # Ensure all exceptions are logged before crashing
    sys.excepthook = log_uncaught_exceptions

    # Simplified opts for direct launch
    launch_app({"no_dropdown": False})

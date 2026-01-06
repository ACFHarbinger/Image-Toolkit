import os
import sys
import signal
import traceback
import threading
from PySide6.QtGui import QIcon
from PySide6.QtCore import QUrl, QTimer
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from gui.src.windows import MainWindow, LoginWindow
from .utils.definitions import ICON_FILE, CTRL_C_TIMEOUT


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

    # --- QML INITIALIZATION ---
    engine = QQmlApplicationEngine()
    
    # Add quest for QML imports
    qml_dir = os.path.join(os.path.dirname(__file__), "..", "..", "gui", "qml")
    engine.addImportPath(os.path.abspath(qml_dir))

    def launch_main_gui(vault_manager):
        """
        Creates and shows the MainWindow after successful authentication.
        """
        nonlocal active_window
        print("DEBUG: launch_main_gui called.")
        
        # 1. Close login window asynchronously to prevent QML crash
        # (The button handler calling this must finish before destruction)
        if active_window and hasattr(active_window, 'root'):
            print("DEBUG: Closing LoginWindow.")
            old_window = active_window
            # Hide immediately to prevent "2 apps" visual
            if hasattr(old_window.root, 'setVisible'):
                old_window.root.setVisible(False)
            QTimer.singleShot(100, old_window.root.close)

        # 2. Create MainWindow (now a logic provider)
        # Parent it to app to ensure it isn't GC'd
        active_window = MainWindow(
            vault_manager=vault_manager,
            dropdown=not opts["no_dropdown"],
            app_icon=ICON_FILE
        )
        active_window.setParent(app) 
        print(f"DEBUG: MainWindow created: {active_window}")
        
        # 3. Expose to QML
        engine.rootContext().setContextProperty("mainBackend", active_window)
        print("DEBUG: mainBackend context property set.")
        
        # 4. Load Main.qml
        qml_main = os.path.join(qml_dir, "Main.qml")
        engine.load(QUrl.fromLocalFile(os.path.abspath(qml_main)))
        
        if not engine.rootObjects():
            print("Error: Could not load Main.qml")
            sys.exit(-1)

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

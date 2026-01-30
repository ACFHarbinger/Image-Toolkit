import sys
import signal
import traceback
import threading

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
from gui.src.windows import MainWindow, LoginWindow
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
        """Handle Ctrl+C and Termination signals by gracefully closing the application"""
        sig_name = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"
        print(f"\n{sig_name} received - closing application...")
        if active_window is not None:
            # This triggers the closeEvent, which handles VaultManager shutdown
            active_window.close()
        app.quit()
        
        # Force exit if app doesn't quit quickly (e.g., stuck thread)
        threading.Timer(CTRL_C_TIMEOUT, lambda: sys.exit(1)).start()

    # Set up signal handlers
    signal.signal(signal.SIGINT, handle_interrupt)
    signal.signal(signal.SIGTERM, handle_interrupt)

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

        # 2. Create the new main window instance
        active_window = MainWindow(
            vault_manager=vault_manager,  # Pass the authenticated manager
            dropdown=~opts["no_dropdown"],
            app_icon=ICON_FILE,
        )
        active_window.show()

    # Create and show the Login Window
    login_window = LoginWindow()
    # Connect the success signal to the function that launches the main app
    login_window.login_successful.connect(launch_main_gui)
    active_window = login_window
    active_window.show()
    # --- END OF NEW LOGIN FLOW ---

    # Start the Qt event loop
    # We rely on the python signal handlers registered above.
    # Note: For signals to process immediately in Python while Qt is running,
    # we relies on Python generic handling. Some setups might require a timer,
    # but basic SIGINT/SIGTERM usually interrupts app.exec().
    return app.exec()


if __name__ == "__main__":
    # Ensure all exceptions are logged before crashing
    sys.excepthook = log_uncaught_exceptions

    # Simplified opts for direct launch
    launch_app({"no_dropdown": False})

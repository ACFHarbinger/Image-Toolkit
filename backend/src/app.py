import sys
import signal
import logging
import logging.handlers
import threading
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
from gui.src.windows.main import MainWindow, LoginWindow
from backend.src.constants import ICON_FILE, CTRL_C_TIMEOUT

# ---------------------------------------------------------------------------
# Logging setup (item 1.13) — rotating file handler + coloured console output
# ---------------------------------------------------------------------------

def _setup_logging(log_level: int = logging.INFO) -> None:
    """Configure the root logger with a rotating file handler and console output."""
    log_dir = Path.home() / ".image-toolkit" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "image_toolkit.log"

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)  # capture everything; handlers filter by level

    # Rotating file: 5 MB per file, keep last 5 files
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    file_handler.setFormatter(file_fmt)
    root.addHandler(file_handler)

    # Console: INFO and above only
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_fmt = logging.Formatter("%(levelname)-8s %(name)s: %(message)s")
    console_handler.setFormatter(console_fmt)
    root.addHandler(console_handler)

    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.getLogger("transformers").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    logging.info("Logging initialised → %s", log_file)


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# QSettings key schema (A.5) — types for known static keys
# Dynamic keys (session/{ClassName}/*, labels/*, splitters/*) are prefixes.
# ---------------------------------------------------------------------------

SETTINGS_SCHEMA: dict[str, type] = {
    "mainwindow/geometry": bytes,
}

SETTINGS_PREFIX_TYPES: dict[str, type] = {
    "session/": str,
    "splitters/": bytes,
    "splitter/": bytes,
}


def _validate_settings() -> None:
    """Log warnings for QSettings keys whose stored type does not match SETTINGS_SCHEMA."""
    try:
        from PySide6.QtCore import QSettings
        s = QSettings("ImageToolkit", "ImageToolkit")
        stored_keys = set(s.allKeys())
        for key, expected_type in SETTINGS_SCHEMA.items():
            if key not in stored_keys:
                continue
            val = s.value(key)
            if val is not None and not isinstance(val, expected_type):
                logger.warning(
                    "QSettings key %r has unexpected type %s (expected %s) — clearing",
                    key, type(val).__name__, expected_type.__name__,
                )
                s.remove(key)
        # Warn about completely unknown keys (not in schema or known prefixes)
        known_prefixes = tuple(SETTINGS_PREFIX_TYPES)
        for key in stored_keys:
            if key in SETTINGS_SCHEMA:
                continue
            if any(key.startswith(p) for p in known_prefixes):
                continue
            logger.debug("QSettings: unrecognised key %r", key)
    except Exception as exc:
        logger.debug("QSettings validation skipped: %s", exc)


def log_uncaught_exceptions(ex_type, ex_value, ex_traceback):
    """Forward uncaught exceptions to the root logger as CRITICAL."""
    logger.critical(
        "Uncaught exception",
        exc_info=(ex_type, ex_value, ex_traceback),
    )
    sys.__excepthook__(ex_type, ex_value, ex_traceback)


def launch_app(opts):
    _setup_logging(log_level=logging.DEBUG if getattr(opts, "verbose", False) else logging.INFO)
    sys.excepthook = log_uncaught_exceptions

    app = QApplication(sys.argv)
    _validate_settings()
    try:
        app_icon = QIcon(ICON_FILE)
        app.setWindowIcon(app_icon)
    except Exception:
        logger.warning("Failed to set application icon. Ensure '%s' exists.", ICON_FILE)

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
        t = threading.Timer(CTRL_C_TIMEOUT, lambda: sys.exit(1))
        t.daemon = True
        t.start()

    # Set up signal handlers
    signal.signal(signal.SIGINT, handle_interrupt)
    signal.signal(signal.SIGTERM, handle_interrupt)

    interpreter_timer = QTimer(app)
    interpreter_timer.start(100)
    interpreter_timer.timeout.connect(lambda: None)

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
            dropdown=not opts.get("no_dropdown", False),
            app_icon=ICON_FILE,
            enable_manager=opts.get("enable_manager", False),
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

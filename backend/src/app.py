import atexit
import contextlib
import json
import logging
import logging.handlers
import os
import signal
import sys
import threading
from pathlib import Path

from gui.src.windows import LoginWindow, MainWindow
from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from backend.src.constants import (
    CTRL_C_TIMEOUT,
    DAEMON_CONFIG_PATH,
    ICON_FILE,
    MONITOR_SLIDESHOW_DAEMON_CONFIG_PATH,
)
from backend.src.constants.app import SETTINGS_PREFIX_TYPES, SETTINGS_SCHEMA
from backend.src.constants.utils import PID_PATH
from backend.src.core import lifecycle_memory, telemetry

# ---------------------------------------------------------------------------
# Logging setup (item 1.13) — rotating file handler + coloured console output
# ---------------------------------------------------------------------------

_LOG_FILE_HANDLER_TAG = "_image_toolkit_rotating_file_handler"


def _make_file_handler() -> logging.handlers.RotatingFileHandler:
    """Build the rotating file handler shared by initial setup and §2.16F reconfiguration."""
    log_dir = Path.home() / ".image-toolkit" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "image_toolkit.log"

    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    ))
    # Tag so _reconfigure_logging can find/remove this exact handler later,
    # rather than matching any RotatingFileHandler that might exist.
    setattr(file_handler, _LOG_FILE_HANDLER_TAG, True)
    return file_handler


def _setup_logging(log_level: int = logging.INFO) -> None:
    """Configure the root logger with a rotating file handler and console output.

    Runs before the vault is unlocked (no access to the log_level /
    file_logging_enabled preferences yet), so this always enables file
    logging and uses `log_level` only for the console handler — matching
    the pre-existing --verbose CLI behavior. `_reconfigure_logging` (§2.16F)
    re-applies the vault's actual preferences once they're available.
    """
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)  # capture everything; handlers filter by level

    root.addHandler(_make_file_handler())

    # Console: INFO and above only (or DEBUG if --verbose)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_fmt = logging.Formatter("%(levelname)-8s %(name)s: %(message)s")
    console_handler.setFormatter(console_fmt)
    root.addHandler(console_handler)

    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.getLogger("transformers").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    logging.info("Logging initialised")


def _reconfigure_logging(log_level_name: str, file_logging_enabled: bool) -> None:
    """§2.16F: apply the vault's log_level / file_logging_enabled preferences.

    Called from MainWindow._apply_startup_preferences(), once the vault is
    unlocked — `_setup_logging()` itself can't do this since it runs before
    login. Previously these two preferences round-tripped through the
    settings window but were never consumed anywhere (GUI/UX §2.9F).
    """
    root = logging.getLogger()
    level = getattr(logging, str(log_level_name).upper(), logging.INFO)

    for handler in root.handlers:
        if isinstance(handler, logging.StreamHandler) and not isinstance(
            handler, logging.handlers.RotatingFileHandler
        ):
            handler.setLevel(level)

    has_file_handler = any(
        getattr(h, _LOG_FILE_HANDLER_TAG, False) for h in root.handlers
    )
    if file_logging_enabled and not has_file_handler:
        root.addHandler(_make_file_handler())
    elif not file_logging_enabled and has_file_handler:
        for handler in list(root.handlers):
            if getattr(handler, _LOG_FILE_HANDLER_TAG, False):
                root.removeHandler(handler)
                handler.close()

    logging.info(
        "Logging reconfigured from preferences: level=%s file_logging=%s",
        logging.getLevelName(level), file_logging_enabled,
    )


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# QSettings key schema (A.5) — types for known static keys
# Dynamic keys (session/{ClassName}/*, labels/*, splitters/*) are prefixes.
# ---------------------------------------------------------------------------


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


def _persistent_slideshow_daemon_pids() -> set[int]:
    """Return the PIDs of active slideshow daemons that must outlive the GUI."""
    protected: set[int] = set()
    sources = (
        (DAEMON_CONFIG_PATH, PID_PATH),
        (MONITOR_SLIDESHOW_DAEMON_CONFIG_PATH, None),
    )
    for config_path, pid_path in sources:
        try:
            with config_path.open(encoding="utf-8") as config_file:
                config = json.load(config_file)
            if not config.get("running"):
                continue
            raw_pid = pid_path.read_text(encoding="utf-8") if pid_path else config.get("pid")
            pid = int(raw_pid)
            if pid > 0:
                protected.add(pid)
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            continue
    return protected


def _is_persistent_daemon_process(process, protected_pids: set[int]) -> bool:
    """Whether ``process`` belongs to an explicitly active slideshow daemon."""
    current = process
    seen: set[int] = set()
    while current is not None:
        try:
            pid = current.pid
        except Exception:
            return False
        if pid in protected_pids:
            return True
        if pid in seen:
            return False
        seen.add(pid)
        try:
            current = current.parent()
        except Exception:
            return False
    return False


def _reap_child_processes() -> None:
    """Reap transient descendants without terminating active slideshow daemons.

    The daemons deliberately call ``start_new_session=True`` and persist their
    PID because they are expected to keep changing wallpapers after a normal
    GUI exit. They are still process descendants, so the generic shutdown
    reaper must exclude their process trees.
    """
    try:
        import psutil

        kids = psutil.Process().children(recursive=True)
    except Exception:
        return
    protected_pids = _persistent_slideshow_daemon_pids()
    reapable = [
        child for child in kids
        if not _is_persistent_daemon_process(child, protected_pids)
    ]
    for c in reapable:
        with contextlib.suppress(Exception):
            c.terminate()
    with contextlib.suppress(Exception):
        _gone, alive = psutil.wait_procs(reapable, timeout=2)
        for c in alive:
            with contextlib.suppress(Exception):
                c.kill()


def _hard_exit(code: int = 1) -> None:
    """Reap children then os._exit — skips atexit / Qt teardown that may hang."""
    _reap_child_processes()
    os._exit(code)


def _install_shutdown_handlers(app, get_active_window) -> None:
    """Idempotent SIGINT/SIGTERM handling with a hard-exit watchdog.

    Fixes the zombie-after-SIGTERM state (OS shutdown, OOM-killer hitting a
    child, `just` teardown): the old handler re-entered on a second signal and
    ran a *second* graceful closeEvent, its watchdog used `sys.exit(1)` from a
    timer thread (which only ends that thread, never the process), and nobody
    reaped the child tree — so icons stayed and the launching terminal was
    left unusable.
    """
    state = {"count": 0}

    atexit.register(_reap_child_processes)
    with contextlib.suppress(Exception):
        app.aboutToQuit.connect(_reap_child_processes)

    def handle_interrupt(signum, _frame):
        state["count"] += 1
        try:
            sig_name = signal.Signals(signum).name
        except Exception:
            sig_name = str(signum)

        if state["count"] >= 2:
            print(f"\n{sig_name} again — forcing exit.", flush=True)
            _hard_exit()
            return

        print(f"\n{sig_name} received - closing application...", flush=True)
        # Arm the hard watchdog BEFORE any teardown, so a wedged closeEvent or
        # stuck worker can't keep the process alive past CTRL_C_TIMEOUT.
        t = threading.Timer(CTRL_C_TIMEOUT, _hard_exit)
        t.daemon = True
        t.start()
        with contextlib.suppress(Exception):
            win = get_active_window()
            if win is not None:
                win.close()
        app.quit()

    signal.signal(signal.SIGINT, handle_interrupt)
    signal.signal(signal.SIGTERM, handle_interrupt)


# Basename (no extension) of desktop/ImageToolkit.desktop — also the value of
# StartupWMClass in that file. Keep the three in sync.
APP_DESKTOP_FILE_NAME = "ImageToolkit"


def set_app_identity(app) -> None:
    """Give the process one stable window-manager identity.

    Without a desktop-file name, Wayland (KWin) derives a fresh ``app_id`` for
    surfaces created after the main window — notably the ``QSystemTrayIcon``
    and its menu, built the first time the app minimises to background — so
    the task manager shows a SECOND Image-Toolkit icon that never groups with
    the first. Setting it here (and matching ``StartupWMClass`` in the
    ``.desktop`` entry) makes every surface share one taskbar entry. Must run
    before any window is shown.
    """
    app.setApplicationName("Image Toolkit")
    app.setApplicationDisplayName("Image Toolkit")
    app.setOrganizationName("Image-Toolkit")
    app.setDesktopFileName(APP_DESKTOP_FILE_NAME)


def launch_app(opts):
    _setup_logging(log_level=logging.DEBUG if getattr(opts, "verbose", False) else logging.INFO)
    sys.excepthook = log_uncaught_exceptions

    app = QApplication(sys.argv)
    set_app_identity(app)
    lifecycle_memory.snapshot("qt_init")  # §12.5 (issue #70)
    _validate_settings()
    try:
        app_icon = QIcon(ICON_FILE)
        app.setWindowIcon(app_icon)
    except Exception:
        logger.warning("Failed to set application icon. Ensure '%s' exists.", ICON_FILE)

    # We will track the active window (either login or main)
    active_window = None
    main_window_launch_pending = False

    _install_shutdown_handlers(app, lambda: active_window)

    interpreter_timer = QTimer(app)
    interpreter_timer.start(100)
    interpreter_timer.timeout.connect(lambda: None)

    # QSocketNotifier/heap-corruption startup race (issue #81). History
    # (full detail in .agent/cache/gallery_crash_deleteorphaned_2026-07-27.md):
    # rounds 6-12 all assumed this was a *timing* race against Qt
    # Multimedia's async PipeWire device probe, and tried an eagerly
    # constructed `QAudioOutput()` here (to get the probe started as early
    # as possible) plus progressively longer settle windows before letting
    # any scanner QThread start. That was disproven by direct instrumentation
    # in round 12: the settle window was *always* already fully elapsed by
    # the time any scan could start (login/vault-unlock alone took longer
    # than the ceiling), and the probe's own completion signal
    # (QMediaDevices.audioOutputsChanged) never fired even once in a full
    # session -- yet the crash still happened. It is not a "hasn't
    # finished probing yet" problem.
    #
    # Round 13 found the actual mechanism for the crash this repro reliably
    # hits: VideoScannerWorker.run() (gui/src/helpers/video/video_scan_worker.py)
    # spawns a concurrent.futures.ThreadPoolExecutor to generate video
    # thumbnails in parallel; each worker thread (a plain Python thread, not
    # a QThread) calls QImage().loadFromData(...) via
    # VideoThumbnailer.generate() to decode the JPEG bytes ffmpeg/
    # ffmpegthumbnailer wrote to stdout. The first time any video thumbnail
    # gets decoded in the process, Qt's JPEG image-format plugin lazily
    # loads -- off the main thread. This is the same "Qt subsystem lazily
    # dlopening a native lib off the main thread while the (then still
    # loaded) JPype JVM was in-process" crash class already fixed 3 times
    # before for other subsystems (native file dialog/GTK, QWebEngineView/
    # Chromium, QMediaPlayer FFmpeg VA-API -- see jvm_native_lib_conflicts
    # in project memory); the JVM itself has since been removed from the
    # product entirely (see base/src/secret/README.md and the C++ crypto module),
    # which closed the whole class. Priming the JPEG plugin here,
    # synchronously, on the main thread, closed that specific SIGSEGV
    # (confirmed live).
    #
    # A live retest after that fix still failed, though differently (an
    # "Invalid socket ... disabling" spam-hang, then a glibc heap-corruption
    # abort) -- both are the *other* documented symptoms of this same
    # `QSocketNotifier` problem class, not a new one. The eagerly
    # constructed `QAudioOutput()` audio-priming object itself is the
    # remaining, consistent common factor across every failure mode seen so
    # far (every one starts with this exact warning, and Qt Multimedia's
    # PipeWire backend -- triggered only by that object, nothing else in
    # this repro touches Qt Multimedia at all -- is the only thing in this
    # app that owns a socket notifier of this kind). Removed entirely for
    # this repro: ExtractorTab's own QAudioOutput/QMediaPlayer are already
    # constructed lazily (only when a video is actually previewed, see
    # extractor_tab.py's `audio_output`/`media_player` properties), so
    # nothing else in a pure Wallpaper-tab-browsing session touches Qt
    # Multimedia at all once this is gone. If ExtractorTab's own lazy video-
    # preview path independently hits this same crash class later, that is
    # a separate, narrower problem to solve on its own terms -- not a
    # reason to keep an unconditional startup cost that has not measurably
    # helped across seven rounds of fixes (see Addendum 13 in
    # .agent/cache/gallery_crash_deleteorphaned_2026-07-27.md).

    from PySide6.QtCore import QBuffer, QByteArray, QIODevice
    from PySide6.QtGui import QImage as _QImagePrime

    _prime_src = _QImagePrime(2, 2, _QImagePrime.Format.Format_RGB32)
    _prime_src.fill(0)
    _prime_bytes = QByteArray()
    _prime_buf = QBuffer(_prime_bytes)
    _prime_buf.open(QIODevice.OpenModeFlag.WriteOnly)
    _prime_encode_ok = _prime_src.save(_prime_buf, "JPG")
    _prime_buf.close()
    _prime_decoded = _QImagePrime()
    _prime_decode_ok = _prime_decoded.loadFromData(_prime_bytes, "JPG")
    print(
        f"[startup-probe-guard] JPEG plugin primed on main thread "
        f"(encode_ok={_prime_encode_ok}, decode_ok={_prime_decode_ok})",
        flush=True,
    )
    telemetry.emit(
        "startup", "jpeg_plugin.primed",
        encode_ok=_prime_encode_ok, decode_ok=_prime_decode_ok,
        tid=threading.get_ident(),
    )

    def launch_main_gui(vault_manager):
        """
        Creates and shows the MainWindow after successful authentication.
        Replaces the LoginWindow.
        """
        nonlocal active_window, main_window_launch_pending
        if main_window_launch_pending:
            logger.warning("Ignoring duplicate login-success signal during startup")
            return
        main_window_launch_pending = True
        print("[startup-probe-guard] login succeeded", flush=True)
        telemetry.emit("startup", "login.succeeded", tid=threading.get_ident())

        # Create the new main window instance (deferred -- see the
        # QSocketNotifier/heap-corruption comment above) and only THEN
        # close the login window. Closing LoginWindow first and
        # constructing MainWindow 400ms later (as an earlier version of
        # this fix did) leaves a window with zero top-level windows open;
        # QApplication's default quitOnLastWindowClosed=True then quits the
        # whole app right there -- silently, with no crash log, matching
        # exactly the "crashes immediately after login" symptom this caused.
        def _build_and_show_main_window():
            nonlocal active_window, main_window_launch_pending
            print("[startup-probe-guard] MainWindow construction starting", flush=True)
            telemetry.emit("startup", "main_window.construction.start", tid=threading.get_ident())
            previous_window = active_window
            try:
                active_window = MainWindow(
                    vault_manager=vault_manager,
                    dropdown=not opts.get("no_dropdown", False),
                    app_icon=ICON_FILE,
                    enable_manager=opts.get("enable_manager", False),
                )
            except Exception as exc:
                main_window_launch_pending = False
                logger.exception("MainWindow construction failed after login")
                if isinstance(previous_window, LoginWindow):
                    previous_window.auth_transition_failed(
                        f"The main window could not start:\n{exc}"
                    )
                return
            active_window.show()
            telemetry.emit("startup", "main_window.shown", tid=threading.get_ident())
            # Captures the cumulative cost of JVM start (VaultManager, inside
            # the login flow that just completed) + first-tab construction —
            # the "after gallery load" phase in §12.5's spec happens later,
            # driven by whatever tab/directory the user opens first, which
            # isn't a fixed lifecycle point app.py can snapshot generically;
            # see bench_app_lifecycle.py for the controlled N-image variant.
            lifecycle_memory.snapshot("main_window_shown")  # §12.5 (issue #70)
            if previous_window and isinstance(previous_window, LoginWindow):
                # The LoginWindow's closeEvent handles teardown if
                # needed. Closed only now that MainWindow is already up, so
                # at least one top-level window is always open.
                previous_window.close()

        QTimer.singleShot(400, _build_and_show_main_window)

    # Create and show the Login Window
    login_window = LoginWindow()
    # Connect the success signal to the function that launches the main app
    login_window.login_successful.connect(launch_main_gui)
    active_window = login_window
    active_window.show()
    lifecycle_memory.snapshot("login_window_shown")  # §12.5 (issue #70)
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

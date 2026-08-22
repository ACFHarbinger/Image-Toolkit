#!/usr/bin/env python3
"""Faithful startup repro for the residual QObject corruption crash.

Runs the real app's startup sequence end-to-end under the SAME process
conditions as `python backend/main.py` -- QT_FFMPEG_DECODING_HW_DEVICE_TYPES
pin, system libpulse/libfontconfig preloads (SONAME-dedup guards), submodule
package registration, Qt media-backend pin, file-dialog patch -- but then
auto-triggers a guest login (the real LoginWindow._do_guest_login() path ->
VaultManager.create_guest_vault() -> JVM start) shortly after the login window
is shown. That reaches MainWindow construction -- the phase where the residual
QObject/event-dispatcher corruption crash fires (Addendum 29) -- without any
GUI interaction.

Designed to be run under the core-capture gdb pipeline (run_with_gdb.sh) so a
real core of the crash lands for the first time:

    RUN_ARGS="dev/repro_guest_startup.py" bash dev/run_with_gdb.sh

Reproduction is stochastic -- run it repeatedly until a crash lands. Do NOT
set IMAGE_TOOLKIT_TELEMETRY for it (a single telemetry-on run dodged the race
entirely -- Addendum 29).
"""
from __future__ import annotations

import contextlib
import ctypes
import os
import sys
import warnings
from pathlib import Path

os.environ.setdefault("QT_FFMPEG_DECODING_HW_DEVICE_TYPES", "cuda")

# Same SONAME-dedup guards as backend/main.py -- must run before any import
# that pulls in `base`/cv2/Qt.
with contextlib.suppress(OSError):
    ctypes.CDLL("/usr/lib/x86_64-linux-gnu/libpulse.so.0")
with contextlib.suppress(OSError):
    ctypes.CDLL("/usr/lib/x86_64-linux-gnu/libfontconfig.so.1")

repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))

from git.scripts._submodule_bootstrap import register_submodule_packages  # noqa: E402

register_submodule_packages(repo_root)

from backend.src.qt_runtime_env import pin_qt_media_backend  # noqa: E402

pin_qt_media_backend()

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

# After MainWindow is shown, additionally hammer the two linked Wallpaper
# panels with rapid back-to-back directory switches. The scan pipeline's own
# comment (_scan_pipeline.py) calls rapid back-to-back switches "the exact
# repro this whole investigation is built around": each switch tears down and
# rebuilds QObjects, and the tight burst of construction/destruction across
# both panels' scanner QThreads is where every observed crash lands -- inside
# PySide6/Shiboken's binding-layer bookkeeping. The startup restore alone is
# gentler; the hammer substantially raises the per-run crash odds.
_DEFAULT_REPRO_DIR = str(Path(__file__).resolve().parent.parent / "docs/tutorials/images")
_REPRO_SCAN_DIR = os.environ.get("IMAGE_TOOLKIT_REPRO_SCAN_DIR", _DEFAULT_REPRO_DIR)
_HAMMER_DIRS = (
    _REPRO_SCAN_DIR,
    os.environ.get("IMAGE_TOOLKIT_REPRO_SECONDARY_DIR", str(Path.home() / "Pictures")),
)

# Patch the guest-login flow BEFORE launch_app() runs so the modal "Logged in
# as guest" dialog never blocks an unattended run, and the login window
# auto-logs-in as an anonymous guest shortly after it is shown.
from gui.src.windows.authentication import LoginWindow as _LoginWindowCls  # noqa: E402

# Inject a crafted session-recovery payload into the guest vault so the real
# MainWindow._restore_session_recovery() path fires the wallpaper scan-dir
# restore -- the exact two-panel populate_scan_image_gallery race documented in
# Addenda 16/20-29 -- even though a fresh guest session normally has no saved
# recovery data. Guest vaults are volatile-memory only (no disk persistence),
# so this only ever affects this repro process.
_RECOVERY_SCAN_DIR = _REPRO_SCAN_DIR

_GUEST_RECOVERY_PAYLOAD = {
    "preferences": {"session_recovery_level": "All Tabs"},
    "session_recovery_data": {
        "active_category": "System Tools",
        "active_tab": "Wallpaper",
        "tab_configs": {
            "WallpaperTab": {
                "scan_directory": _RECOVERY_SCAN_DIR,
            },
        },
    },
}


def _noop_information(*args, **kwargs):
    return QMessageBox.StandardButton.Ok


QMessageBox.information = staticmethod(_noop_information)

_orig_show = _LoginWindowCls.show
_orig_do_guest_login = _LoginWindowCls._do_guest_login


def _inject_recovery(vault_manager):
    try:
        creds = vault_manager.load_account_credentials() or {}
        creds.setdefault("preferences", {}).update(
            _GUEST_RECOVERY_PAYLOAD["preferences"]
        )
        creds["session_recovery_data"] = _GUEST_RECOVERY_PAYLOAD["session_recovery_data"]
        vault_manager.save_data(__import__("json").dumps(creds))
        print(
            f"[repro] injected wallpaper recovery payload "
            f"(scan_directory={_RECOVERY_SCAN_DIR!r}) into guest vault",
            flush=True,
        )
    except Exception as e:  # noqa: BLE001 -- repro helper
        print(f"[repro] WARNING: failed to inject recovery payload: {e}", flush=True)


def _auto_guest_show(self):
    _orig_show(self)
    QTimer.singleShot(1500, lambda: _auto_guest_login(self))


def _auto_guest_login(self):
    print("[repro] auto-guest fired", flush=True)
    try:
        _orig_do_guest_login(self, "", anonymous=True)
        print("[repro] _do_guest_login returned", flush=True)
    except Exception as e:  # noqa: BLE001 -- repro helper
        print(f"[repro] _do_guest_login raised: {e!r}", flush=True)
    if getattr(self, "vault_manager", None) is not None:
        _inject_recovery(self.vault_manager)
        print("[repro] recovery injected", flush=True)
    _schedule_wallpaper_hammer()


def _hammer_wallpaper_race() -> bool:
    """Trigger rapid back-to-back switches on both Wallpaper panels once found."""
    for w in QApplication.topLevelWidgets():
        all_tabs = getattr(w, "all_tabs", None)
        if not all_tabs:
            continue
        wtab = all_tabs.get("System Tools", {}).get("Wallpaper")
        if wtab is None:
            continue
        system_display = getattr(wtab, "system_display", None)
        monitor_display = getattr(wtab, "monitor_display", None)
        if system_display is None or monitor_display is None:
            continue
        print("[repro] MainWindow found; hammering both Wallpaper panels", flush=True)
        for directory in _HAMMER_DIRS:
            for panel in (system_display, monitor_display):
                try:
                    panel.populate_scan_image_gallery(directory, emit_signal=True)
                except Exception as e:  # noqa: BLE001 -- repro helper
                    print(f"[repro] hammer call raised: {e!r}", flush=True)
        return True
    return False


def _schedule_wallpaper_hammer():
    def _retry():
        if _hammer_wallpaper_race():
            print("[repro] wallpaper hammer scheduled", flush=True)
        else:
            QTimer.singleShot(500, _retry)

    QTimer.singleShot(2000, _retry)


_LoginWindowCls.show = _auto_guest_show

from gui.src.windows.settings.file_dialog_patch import apply_patch  # noqa: E402

apply_patch()

warnings.filterwarnings(
    "ignore", message=".*urllib3.*doesn't match a supported version!.*"
)

from backend.src.app import launch_app  # noqa: E402

if __name__ == "__main__":
    sys.exit(launch_app({"no_dropdown": False, "enable_manager": False}))

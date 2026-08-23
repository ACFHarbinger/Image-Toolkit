#!/usr/bin/env python3
"""One-off verification driver: guest login -> land on the Database
(Management) tab -> screenshot -> quit.

Not a repro/crash driver -- just the minimal faithful-startup boilerplate
from dev/repro_guest_startup.py, stripped of the recovery-payload hammer,
retargeted at "Library Database" / "Management" instead of Wallpaper.
Answers the one open loop several agent sessions flagged: does the
Database tab's listings actually load in a real GUI, not just does
base.database.Database(...) construct.
"""
from __future__ import annotations

import contextlib
import ctypes
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_FFMPEG_DECODING_HW_DEVICE_TYPES", "cuda")

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

_GUEST_RECOVERY_PAYLOAD = {
    "preferences": {
        "session_recovery_level": "All Tabs",
        "restore_last_tab": True,
    },
    "session_recovery_data": {
        "active_category": "Library Database",
        "active_tab": "Management",
        "tab_configs": {},
    },
}


def _noop_information(*args, **kwargs):
    return QMessageBox.StandardButton.Ok


QMessageBox.information = staticmethod(_noop_information)
QMessageBox.warning = staticmethod(_noop_information)
QMessageBox.critical = staticmethod(_noop_information)

from gui.src.windows.authentication import LoginWindow as _LoginWindowCls  # noqa: E402

_orig_show = _LoginWindowCls.show
_orig_do_guest_login = _LoginWindowCls._do_guest_login


def _inject_recovery(vault_manager):
    try:
        creds = vault_manager.load_account_credentials() or {}
        creds.setdefault("preferences", {}).update(_GUEST_RECOVERY_PAYLOAD["preferences"])
        creds["session_recovery_data"] = _GUEST_RECOVERY_PAYLOAD["session_recovery_data"]
        vault_manager.save_data(json.dumps(creds))
        print("[verify] injected recovery payload targeting Database tab", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"[verify] WARNING: failed to inject recovery payload: {e}", flush=True)


def _auto_guest_show(self):
    _orig_show(self)
    QTimer.singleShot(1500, lambda: _auto_guest_login(self))


def _auto_guest_login(self):
    print("[verify] auto-guest fired", flush=True)
    try:
        _orig_do_guest_login(self, "", anonymous=True)
        print("[verify] _do_guest_login returned", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"[verify] _do_guest_login raised: {e!r}", flush=True)
    if getattr(self, "vault_manager", None) is not None:
        _inject_recovery(self.vault_manager)
    QTimer.singleShot(3000, _check_database_tab)


def _check_database_tab():
    for w in QApplication.topLevelWidgets():
        all_tabs = getattr(w, "all_tabs", None)
        if not all_tabs:
            continue
        db_tab = all_tabs.get("Library Database", {}).get("Management")
        if db_tab is None:
            continue
        print(f"[verify] MainWindow found, database_tab={db_tab!r}", flush=True)
        print(f"[verify] current category={w.command_combo.currentText()!r} "
              f"current sub-tab={w.tabs.tabText(w.tabs.currentIndex())!r}", flush=True)
        screenshot_path = Path.home() / ".image-toolkit" / "telemetry" / "database_tab_verify.png"
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        pixmap = w.grab()
        pixmap.save(str(screenshot_path))
        print(f"[verify] screenshot saved to {screenshot_path}", flush=True)

        try:
            db_tab.connect_database(silent=False)
            print(f"[verify] connect_database() returned, db={getattr(db_tab, 'db', None)!r}", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"[verify] connect_database() raised: {e!r}", flush=True)

        screenshot_path2 = Path.home() / ".image-toolkit" / "telemetry" / "database_tab_verify_connected.png"
        pixmap2 = w.grab()
        pixmap2.save(str(screenshot_path2))
        print(f"[verify] post-connect screenshot saved to {screenshot_path2}", flush=True)

        QTimer.singleShot(1500, w.close)
        return
    print("[verify] MainWindow not found yet, retrying", flush=True)
    QTimer.singleShot(1000, _check_database_tab)


_LoginWindowCls.show = _auto_guest_show

from gui.src.windows.settings.file_dialog_patch import apply_patch  # noqa: E402

apply_patch()

import warnings  # noqa: E402

warnings.filterwarnings("ignore", message=".*urllib3.*doesn't match a supported version!.*")

from backend.src.app import launch_app  # noqa: E402

if __name__ == "__main__":
    sys.exit(launch_app({"no_dropdown": False, "enable_manager": False}))

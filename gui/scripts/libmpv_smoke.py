#!/usr/bin/env python3
"""Isolated libmpv lifecycle smoke harness for #517.

This deliberately does not import ExtractorTab or embed a player in the
application.  The parent process supervises a short-lived Qt/libmpv worker so
a native abort is reported as a signal instead of taking down a GUI session.
"""

from __future__ import annotations

import argparse
import ctypes
import ctypes.util
import os
import subprocess
import sys


def _library_path() -> str | None:
    return ctypes.util.find_library("mpv")


def _worker(qt_platform: str | None) -> int:
    if qt_platform:
        os.environ["QT_QPA_PLATFORM"] = qt_platform

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QWidget

    library_path = _library_path()
    if library_path is None:
        print("SKIP: libmpv is not installed")
        return 77

    app = QApplication.instance() or QApplication([])
    host = QWidget()
    host.setAttribute(Qt.WidgetAttribute.WA_NativeWindow)
    host.winId()

    libmpv = ctypes.CDLL(library_path)
    libmpv.mpv_create.restype = ctypes.c_void_p
    libmpv.mpv_initialize.argtypes = [ctypes.c_void_p]
    libmpv.mpv_initialize.restype = ctypes.c_int
    libmpv.mpv_terminate_destroy.argtypes = [ctypes.c_void_p]
    handle = libmpv.mpv_create()
    if not handle:
        print("FAIL: mpv_create returned null")
        return 1
    try:
        status = libmpv.mpv_initialize(handle)
        if status < 0:
            print(f"FAIL: mpv_initialize returned {status}")
            return 1
        print(f"PASS: Qt platform={app.platformName()}, libmpv initialized and destroyed")
        return 0
    finally:
        libmpv.mpv_terminate_destroy(handle)


def _supervise(qt_platform: str | None) -> int:
    command = [sys.executable, __file__, "--worker"]
    if qt_platform:
        command.extend(("--qt-platform", qt_platform))
    completed = subprocess.run(command, check=False)
    if completed.returncode < 0:
        print(f"FAIL: libmpv worker terminated by signal {-completed.returncode}")
        return 1
    if completed.returncode == 77:
        print("SKIP: install libmpv before retrying this smoke harness")
        return 0
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--qt-platform",
        help="optional Qt platform plugin, e.g. offscreen for a headless lifecycle-only run",
    )
    args = parser.parse_args()
    return _worker(args.qt_platform) if args.worker else _supervise(args.qt_platform)


if __name__ == "__main__":
    raise SystemExit(main())

"""#461 stress pass: rapid dir-nav, dual linked wallpaper restore, teardown-during-load.

A native SIGSEGV/SIGABRT in this file is a 1.0.0 release blocker. Success is
the process surviving the hammer — not a particular gallery layout.
"""

from __future__ import annotations

import time
import types

import pytest
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication, QFileDialog
from shiboken6 import Shiboken

from gui.src.constants.ui import DIALOG_OPTS
from gui.src.tabs.core.wallpaper_tab.manager import WallpaperTab
from gui.test.image.test_gallery_classes import ConcreteSingleGallery

pytestmark = pytest.mark.gui

_HAMMER_ROUNDS = 12
_IMAGES_PER_DIR = 8


def _write_pngs(directory, n: int, hue_base: int) -> list[str]:
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for i in range(n):
        img = QImage(24, 24, QImage.Format.Format_RGB32)
        img.fill(QColor(hue_base, 40 + i * 8, 180 - i * 4))
        path = directory / f"img_{i:03d}.png"
        assert img.save(str(path), "PNG")
        paths.append(str(path))
    return paths


def _pump(seconds: float) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.01)


def _skip_startup_settle(monkeypatch) -> None:
    import gui.src.tabs.core.wallpaper_tab.common.wallpaper_common_base._scan_pipeline as scan_pipeline

    monkeypatch.setattr(scan_pipeline, "startup_settle_remaining_ms", lambda: 0)


def _make_wallpaper_tab(q_app):
    return WallpaperTab(types.SimpleNamespace(db=None))


def _assert_alive(*widgets) -> None:
    for widget in widgets:
        assert Shiboken.isValid(widget)


class TestGalleryCrashStress:
    def test_dual_linked_rapid_dir_nav(self, q_app, monkeypatch, tmp_path):
        _skip_startup_settle(monkeypatch)
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        _write_pngs(dir_a, _IMAGES_PER_DIR, hue_base=20)
        _write_pngs(dir_b, _IMAGES_PER_DIR, hue_base=120)

        tab = _make_wallpaper_tab(q_app)
        system = tab.system_display
        monitor = tab.monitor_display
        dirs = (str(dir_a), str(dir_b))

        for i in range(_HAMMER_ROUNDS):
            system.populate_scan_image_gallery(dirs[i % 2], emit_signal=True)
            _pump(0.04)

        _pump(0.6)
        _assert_alive(tab, system, monitor)
        tab.close()
        _pump(0.2)

    def test_startup_restore_then_rapid_switch(self, q_app, monkeypatch, tmp_path):
        """Session-recovery restore (250ms timer) plus a second set_config,
        then immediate dir-nav — the Addendum 16 two-restore burst."""
        _skip_startup_settle(monkeypatch)
        dir_a = tmp_path / "restore_a"
        dir_b = tmp_path / "restore_b"
        _write_pngs(dir_a, _IMAGES_PER_DIR, hue_base=30)
        _write_pngs(dir_b, _IMAGES_PER_DIR, hue_base=90)

        tab = _make_wallpaper_tab(q_app)
        tab.set_config({"scan_directory": str(dir_a)})
        tab.set_config({"scan_directory": str(dir_b)})
        _pump(0.5)
        tab.system_display.populate_scan_image_gallery(str(dir_a), emit_signal=True)
        _pump(0.08)
        tab.system_display.populate_scan_image_gallery(str(dir_b), emit_signal=True)
        _pump(0.6)
        _assert_alive(tab, tab.system_display, tab.monitor_display)
        tab.close()
        _pump(0.2)

    def test_teardown_during_wallpaper_load(self, q_app, monkeypatch, tmp_path):
        _skip_startup_settle(monkeypatch)
        dir_a = tmp_path / "live"
        _write_pngs(dir_a, _IMAGES_PER_DIR, hue_base=60)

        for _ in range(6):
            tab = _make_wallpaper_tab(q_app)
            tab.system_display.populate_scan_image_gallery(str(dir_a), emit_signal=True)
            _pump(0.03)
            tab.system_display.cancel_loading()
            tab.monitor_display.cancel_loading()
            tab.close()
            tab.deleteLater()
            _pump(0.15)

    def test_teardown_during_single_gallery_load(self, q_app, tmp_path):
        paths = _write_pngs(tmp_path / "gallery", 16, hue_base=10)
        for _ in range(8):
            gallery = ConcreteSingleGallery()
            gallery.start_loading_gallery(paths)
            _pump(0.02)
            gallery.cancel_loading()
            gallery.clear_gallery_widgets()
            gallery.deleteLater()
            _pump(0.1)

    def test_browse_scan_directory_forces_non_native_dialog(
        self, q_app, monkeypatch, tmp_path
    ):
        captured = {}

        def fake_get(parent, caption, start_dir, options=None):
            captured["options"] = options
            return ""

        monkeypatch.setattr(QFileDialog, "getExistingDirectory", fake_get)
        _skip_startup_settle(monkeypatch)
        tab = _make_wallpaper_tab(q_app)
        tab.system_display.last_browsed_scan_dir = str(tmp_path)
        tab.system_display.browse_scan_directory()
        assert captured["options"] is not None
        assert captured["options"] & DIALOG_OPTS
        tab.close()

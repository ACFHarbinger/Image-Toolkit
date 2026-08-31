"""Regression coverage for Wallpaper's thread-free directory scanner."""

from __future__ import annotations

import time
import types

import pytest
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication, QGridLayout, QScrollArea, QWidget

from gui.src.tabs.core.wallpaper_tab.common.wallpaper_common_base import (
    WallpaperCommonBase,
)
from gui.src.tabs.core.wallpaper_tab.manager import WallpaperTab
from gui.src.windows.settings.app_settings import AppSettings

pytestmark = pytest.mark.gui


class ConcreteWallpaperBase(WallpaperCommonBase):
    def __init__(self):
        super().__init__()
        self.gallery_scroll_area = QScrollArea()
        self.gallery_widget = QWidget()
        self.gallery_layout = QGridLayout(self.gallery_widget)
        self.gallery_scroll_area.setWidget(self.gallery_widget)

    def create_card_widget(self, path, pixmap=None):
        return QWidget()

    def update_card_pixmap(self, widget, pixmap, label_ref=None):
        pass

    def create_gallery_label(self, path, size):
        return QWidget()

    def get_default_config(self):
        return {}

    def set_config(self, config):
        pass


def _pump(seconds: float) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.005)


def _write_png(path, color=40) -> str:
    image = QImage(24, 24, QImage.Format.Format_RGB32)
    image.fill(QColor(color, 80, 120))
    assert image.save(str(path), "PNG")
    return str(path)


def test_directory_scan_creates_no_qthread_scanners(q_app, tmp_path):
    panel = ConcreteWallpaperBase()
    expected = _write_png(tmp_path / "one.png")

    panel.populate_scan_image_gallery(str(tmp_path), emit_signal=False)
    assert panel.img_scanner_thread is None
    assert panel.vid_scanner_thread is None
    _pump(0.4)

    assert panel.master_image_paths == [expected]
    assert panel._directory_scan_state is None
    assert panel._scan_pipeline_busy is False
    panel.close()


def test_latest_browse_closes_and_replaces_previous_iterator(q_app, tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    _write_png(first / "old.png", 20)
    expected = _write_png(second / "new.png", 100)
    panel = ConcreteWallpaperBase()

    panel.populate_scan_image_gallery(str(first), emit_signal=False)
    old_state = panel._directory_scan_state
    panel.populate_scan_image_gallery(str(second), emit_signal=False)

    assert old_state.current_iterator is None
    _pump(0.4)
    assert panel.scanned_dir == str(second)
    assert panel.master_image_paths == [expected]
    panel.close()


def test_recursive_scan_finds_nested_supported_files(q_app, monkeypatch, tmp_path):
    monkeypatch.setattr(AppSettings, "recursive_scan", staticmethod(lambda: True))
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    expected = {
        _write_png(tmp_path / "root.png", 30),
        _write_png(nested / "nested.png", 60),
    }
    (nested / "ignored.txt").write_text("not an image")
    panel = ConcreteWallpaperBase()

    panel.populate_scan_image_gallery(str(tmp_path), emit_signal=False)
    _pump(0.5)

    assert set(panel.master_image_paths) == expected
    panel.close()


def test_linked_panel_mirror_waits_for_complete_thumbnail_generation(
    q_app, tmp_path
):
    expected = _write_png(tmp_path / "wallpaper.png")
    tab = WallpaperTab(types.SimpleNamespace(db=None))
    source = tab.system_display
    observed_idle = []
    assert source.gallery.model.thread_pool.maxThreadCount() == 1
    assert tab.monitor_display.gallery.model.thread_pool.maxThreadCount() == 1
    source.directory_scanned.connect(
        lambda _directory: observed_idle.append(
            not source.gallery.model.has_pending_loads()
        )
    )

    source.populate_scan_image_gallery(str(tmp_path), emit_signal=True)
    _pump(1.0)

    assert observed_idle == [True]
    assert source.gallery.model.cached_image(expected) is not None
    assert tab.monitor_display.master_image_paths == [expected]
    assert source.img_scanner_thread is None
    assert tab.monitor_display.img_scanner_thread is None
    tab.close()


def test_close_cancels_incremental_scan_timer(q_app, tmp_path):
    for index in range(600):
        (tmp_path / f"item_{index:04d}.png").write_bytes(b"invalid")
    panel = ConcreteWallpaperBase()
    panel.populate_scan_image_gallery(str(tmp_path), emit_signal=False)

    panel.close()

    assert panel._directory_scan_state is None
    assert not panel._directory_scan_timer.isActive()

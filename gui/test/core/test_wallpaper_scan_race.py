"""Regression tests for image-directory scanning in WallpaperCommonBase.

The threaded scanner (``ImageScannerWorker`` / ``VideoScannerWorker``, their
cross-thread ``scan_finished`` signals, and the settle-window that used to
gate ``QThread`` starts) was removed entirely — directory traversal now
runs in short GUI-event-loop slices with no worker object or signal (see
``_scan_pipeline.py``'s module docstring). The tests that exercised that
machinery went with it; ``_on_image_scan_finished`` / ``_on_video_scan_finished``
survive only as no-op compat slots for stale queued deliveries.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QGridLayout, QScrollArea, QWidget

from gui.src.tabs.core.wallpaper_tab.common.wallpaper_common_base import (
    WallpaperCommonBase,
)

pytestmark = pytest.mark.gui


class ConcreteWallpaperBase(WallpaperCommonBase):
    def __init__(self):
        super().__init__()
        self.gallery_scroll_area = QScrollArea()
        self.gallery_widget = QWidget()
        self.gallery_layout = QGridLayout()
        self.gallery_widget.setLayout(self.gallery_layout)
        self.gallery_scroll_area.setWidget(self.gallery_widget)

    def create_card_widget(self, path, pixmap=None):
        return QWidget()

    def update_card_pixmap(self, widget, pixmap, label_ref=None):
        pass

    # pyrefly: ignore [bad-override]
    def create_gallery_label(self, path, size):
        return QWidget()

    def get_default_config(self):
        return {}

    def set_config(self, config):
        pass


class TestWallpaperGalleryLoading:
    def test_startup_thumbnail_is_scaled_and_cached(self, q_app, tmp_path):
        path = tmp_path / "large.png"
        image = QImage(800, 400, QImage.Format.Format_RGB32)
        image.fill(Qt.GlobalColor.red)
        assert image.save(str(path))

        panel = ConcreteWallpaperBase()
        panel.thumbnail_size = 96
        thumb = panel._get_or_generate_thumbnail(str(path))

        assert thumb is not None
        assert not thumb.isNull()
        assert thumb.width() <= 96
        assert thumb.height() <= 96
        cached = panel._initial_pixmap_cache.get(str(path))
        assert cached is not None
        assert cached.width() <= 96
        assert cached.height() <= 96

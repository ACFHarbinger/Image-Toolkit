"""Tests for Gallery Presentation Modes and Custom Thumbnail Overlays (§2.40, #508, #542)."""

from __future__ import annotations

import pytest
from gui.src.components.gallery.presentation_mode import (
    GalleryOverlayConfig,
    GalleryPresentationMode,
)
from gui.src.components.virtual_gallery.delegate import VirtualGalleryDelegate
from gui.src.components.virtual_gallery.virtual_gallery_model import VirtualGalleryModel
from gui.src.components.virtual_gallery.virtual_gallery_view import VirtualGalleryView
from PySide6.QtCore import QObject, QRect, QRunnable, Qt, Signal
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtWidgets import QListView, QStyleOptionViewItem

pytestmark = pytest.mark.gui


class _DummySignals(QObject):
    result = Signal(str, QImage)


class DummyLoaderWorker(QRunnable):
    def __init__(self, path: str, size: int):
        super().__init__()
        self.path = path
        self.size = size
        self.load_generation = 0
        self.signals = _DummySignals()

    def run(self):
        pass


class TestGalleryPresentationMode:
    def test_overlay_config_defaults_and_toggles(self):
        cfg = GalleryOverlayConfig()
        assert cfg.show_rating is True
        assert cfg.show_resolution is True
        assert cfg.show_format is True
        assert cfg.show_star_rating is True
        assert cfg.show_tag_count is True

        cfg.show_rating = False
        assert cfg.show_rating is False

    def test_virtual_gallery_model_overlay_metadata(self, q_app):
        model = VirtualGalleryModel(worker_factory=DummyLoaderWorker, fill_mode=False)
        paths = ["/images/art1.png", "/images/art2.jpg"]
        model.set_paths(paths)

        model.set_overlay_metadata(
            "/images/art1.png",
            rating="s",
            resolution=(3840, 2160),
            file_format="PNG",
            star_rating=4.9,
            tag_count=18,
        )

        idx = model.index(0, 0)
        assert model.data(idx, model.RatingRole) == "s"
        assert model.data(idx, model.ResolutionRole) == (3840, 2160)
        assert model.data(idx, model.FormatRole) == "PNG"
        assert model.data(idx, model.StarRatingRole) == 4.9
        assert model.data(idx, model.TagCountRole) == 18

        # Clear overlay metadata
        model.clear_overlay_metadata()
        assert model.data(idx, model.RatingRole) is None
        assert model.data(idx, model.ResolutionRole) is None

    def test_virtual_gallery_delegate_paint_overlays(self, q_app):
        model = VirtualGalleryModel(worker_factory=DummyLoaderWorker, fill_mode=False)
        model.set_paths(["/images/sample.png"])
        model.set_overlay_metadata(
            "/images/sample.png",
            rating="g",
            resolution=(1920, 1080),
            file_format="PNG",
            star_rating=5.0,
            tag_count=12,
        )

        delegate = VirtualGalleryDelegate()
        pix = QPixmap(200, 200)
        pix.fill(Qt.GlobalColor.black)
        painter = QPainter(pix)

        opt = QStyleOptionViewItem()
        opt.rect = QRect(0, 0, 180, 180)
        idx = model.index(0, 0)

        # Paint with overlay config
        delegate.paint(painter, opt, idx)
        painter.end()

        assert not pix.isNull()

    def test_virtual_gallery_view_presentation_modes(self, q_app):
        view = VirtualGalleryView()
        model = VirtualGalleryModel(worker_factory=DummyLoaderWorker, fill_mode=False)
        model.set_paths(["/images/art1.png", "/images/art2.png"])
        view.setModel(model)

        assert view.presentation_mode == GalleryPresentationMode.UNIFORM_GRID
        assert view.viewMode() == QListView.ViewMode.IconMode

        # Switch to Compact List
        view.set_presentation_mode(GalleryPresentationMode.COMPACT_LIST)
        assert view.presentation_mode == GalleryPresentationMode.COMPACT_LIST
        assert view.viewMode() == QListView.ViewMode.ListMode

        # Switch to Masonry
        view.set_presentation_mode(GalleryPresentationMode.MASONRY)
        assert view.presentation_mode == GalleryPresentationMode.MASONRY
        assert view.viewMode() == QListView.ViewMode.IconMode

        # Update overlay config
        custom_cfg = GalleryOverlayConfig(show_rating=False, show_tag_count=False)
        view.set_overlay_config(custom_cfg)
        assert view.itemDelegate().overlay_config.show_rating is False

    def test_empty_space_right_click_offers_presentation_menu(self, q_app, monkeypatch):
        """This is currently the only reachable UI path to
        set_presentation_mode()/set_overlay_config() in the live app --
        item right-clicks stay delegated to path_right_clicked (existing
        convention, unaffected)."""
        view = VirtualGalleryView()
        model = VirtualGalleryModel(worker_factory=DummyLoaderWorker, fill_mode=False)
        model.set_paths([])  # empty model -- every position is "empty space"
        view.setModel(model)
        view.resize(400, 400)

        built_menus = []
        real_build = view._build_presentation_menu

        def _spy_build():
            menu = real_build()
            built_menus.append(menu)
            return menu

        monkeypatch.setattr(view, "_build_presentation_menu", _spy_build)
        monkeypatch.setattr(view, "_show_presentation_menu", lambda pos: view._build_presentation_menu())

        item_clicks = []
        view.path_right_clicked.connect(lambda pos, path: item_clicks.append(path))

        pos = view.viewport().rect().center()
        assert not view.indexAt(pos).isValid()
        view._on_context_menu(pos)

        assert len(built_menus) == 1
        assert item_clicks == []

    def test_presentation_menu_switches_mode_and_toggles_overlay(self, q_app):
        view = VirtualGalleryView()
        model = VirtualGalleryModel(worker_factory=DummyLoaderWorker, fill_mode=False)
        model.set_paths([])
        view.setModel(model)

        menu = view._build_presentation_menu()

        mode_menu = next(a.menu() for a in menu.actions() if a.text() == "Presentation Mode")
        masonry_action = next(a for a in mode_menu.actions() if a.text() == "Masonry")
        masonry_action.trigger()
        assert view.presentation_mode == GalleryPresentationMode.MASONRY

        overlay_menu = next(a.menu() for a in menu.actions() if a.text() == "Thumbnail Overlays")
        rating_action = next(a for a in overlay_menu.actions() if a.text() == "Rating Badge")
        assert rating_action.isChecked() is True
        rating_action.trigger()
        assert view.itemDelegate().overlay_config.show_rating is False

"""Presentation-mode wiring tests for ``AbstractGalleryBase`` (§2.40 / #508).

Exercises the mode/overlay machinery through a real
``AbstractClassSingleGallery`` subclass (factory-backed card creation, the
production path) rather than only VirtualGallery -- the gap #508 re-scoping
called out.
"""

from __future__ import annotations

import pytest
from gui.src.classes.image.abstract_class_single_gallery import (
    AbstractClassSingleGallery,
)
from gui.src.components.gallery.presentation_mode import (
    GalleryOverlayConfig,
    GalleryPresentationMode,
)
from gui.src.windows.settings.app_settings import AppSettings
from PySide6.QtGui import QContextMenuEvent, QPixmap
from PySide6.QtWidgets import QGridLayout, QLabel, QScrollArea, QWidget

pytestmark = pytest.mark.gui


class FactoryGallery(AbstractClassSingleGallery):
    """Real single-gallery subclass using the mixin ``create_card_widget`` so
    card creation goes through the shared factory and the new overlay/geometry
    hooks."""

    def __init__(self):
        super().__init__()
        self.gallery_scroll_area = QScrollArea()
        # Resizable so the content actually fills the viewport offscreen --
        # otherwise childAt() over the card sees nothing (no polish pass).
        self.gallery_scroll_area.setWidgetResizable(True)
        self.gallery_widget = QWidget()
        self.gallery_layout = QGridLayout()
        self.gallery_widget.setLayout(self.gallery_layout)
        self.gallery_scroll_area.setWidget(self.gallery_widget)

    def create_gallery_label(self, path: str, size: int) -> QLabel:
        label = QLabel()
        label.file_path = path
        label.setFixedSize(size + 10, size + 10)
        return label

    def get_default_config(self) -> dict:
        return {}

    def set_config(self, config: dict) -> None:
        pass


def _card_paths(layout: QGridLayout) -> list[tuple[int, int, QWidget]]:
    out = []
    for i in range(layout.count()):
        item = layout.itemAt(i)
        if item.widget() is not None:
            out.append((*layout.getItemPosition(i)[:2], item.widget()))
    return out


@pytest.fixture
def gallery(q_app):
    AppSettings.set_session(FactoryGallery.__name__, "presentation_mode", "")
    AppSettings.set_session(FactoryGallery.__name__, "gallery_overlay_config", {})
    g = FactoryGallery()
    yield g
    g.gallery_scroll_area.deleteLater()


class TestPresentationModeOnGalleryBase:
    def test_default_mode_is_uniform_grid(self, gallery):
        assert gallery.presentation_mode == GalleryPresentationMode.UNIFORM_GRID

    def test_set_presentation_mode_roundtrip(self, gallery):
        gallery.set_presentation_mode(GalleryPresentationMode.MASONRY)
        assert gallery.presentation_mode == GalleryPresentationMode.MASONRY
        gallery.set_presentation_mode(GalleryPresentationMode.COMPACT_LIST)
        assert gallery.presentation_mode == GalleryPresentationMode.COMPACT_LIST
        # Idempotent re-set is a no-op (no geometry churn).
        gallery.set_presentation_mode(GalleryPresentationMode.COMPACT_LIST)

    def test_mode_persists_per_gallery_class(self, gallery, q_app):
        gallery.set_presentation_mode(GalleryPresentationMode.COMPACT_LIST)
        assert (
            AppSettings.session(FactoryGallery.__name__, "presentation_mode", "")
            == GalleryPresentationMode.COMPACT_LIST.value
        )
        fresh = FactoryGallery()
        assert fresh.presentation_mode == GalleryPresentationMode.COMPACT_LIST
        fresh.set_presentation_mode(GalleryPresentationMode.UNIFORM_GRID)
        fresh.gallery_scroll_area.deleteLater()

    def test_common_place_card_uniform_grid_row_major(self, gallery):
        cards = [gallery.create_card_widget(f"/img/{i}.png", None) for i in range(5)]
        for i, card in enumerate(cards):
            gallery.common_place_card(gallery.gallery_layout, card, i, 3)
        placed = _card_paths(gallery.gallery_layout)
        assert [(r, c) for r, c, _ in placed] == [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1)]

    def test_common_place_card_compact_single_column_and_small_thumb(self, gallery):
        gallery.set_presentation_mode(GalleryPresentationMode.COMPACT_LIST)
        card = gallery.create_card_widget("/img/a.png", None)
        label = card.findChild(QLabel)
        assert label.width() == gallery._COMPACT_THUMB
        gallery.common_place_card(gallery.gallery_layout, card, 0, 3)
        row, col, _ = _card_paths(gallery.gallery_layout)[0]
        assert (row, col) == (0, 0)

    def test_switch_back_to_uniform_restores_geometry(self, gallery):
        card = gallery.create_card_widget("/img/a.png", None)
        gallery.path_to_card_widget["/img/a.png"] = card
        label = card.findChild(QLabel)
        orig_w, orig_h = label.width(), label.height()
        gallery.set_presentation_mode(GalleryPresentationMode.COMPACT_LIST)
        assert label.height() == gallery._COMPACT_THUMB
        gallery.set_presentation_mode(GalleryPresentationMode.UNIFORM_GRID)
        assert (label.width(), label.height()) == (orig_w, orig_h)

    def test_mode_change_reflows_existing_cards_without_a_resize(self, gallery):
        cards = [gallery.create_card_widget(f"/img/{i}.png", None) for i in range(4)]
        for i, card in enumerate(cards):
            gallery.path_to_card_widget[f"/img/{i}.png"] = card
            gallery.common_place_card(gallery.gallery_layout, card, i, 2)
        gallery._current_cols = 2

        gallery.set_presentation_mode(GalleryPresentationMode.COMPACT_LIST)

        assert [(row, col) for row, col, _ in _card_paths(gallery.gallery_layout)] == [
            (0, 0),
            (1, 0),
            (2, 0),
            (3, 0),
        ]

    def test_masonry_places_each_card_on_own_row_and_balances_columns(self, gallery):
        gallery.set_presentation_mode(GalleryPresentationMode.MASONRY)
        heights = [100, 10, 100, 10]
        cards = []
        for i, h in enumerate(heights):
            card = gallery.create_card_widget(f"/img/{i}.png", None)
            card.setFixedSize(gallery.thumbnail_size + 10, h)
            cards.append(card)
            gallery.common_place_card(gallery.gallery_layout, card, i, 2)
        placed = _card_paths(gallery.gallery_layout)
        rows = [r for r, _c, _w in placed]
        cols = [c for _r, c, _w in placed]
        # Every card on a distinct row -> per-row height = that card's height.
        assert len(set(rows)) == len(cards)
        # Shortest-column-first packing: 100->0, 10->1, 100->1, 10->0.
        assert cols == [0, 1, 1, 0]
        heights_by_col = {0: heights[0] + heights[3], 1: heights[1] + heights[2]}
        assert abs(heights_by_col[0] - heights_by_col[1]) <= max(heights) - min(heights)

    def test_reflow_masonry_rebalances_with_current_heights(self, gallery):
        gallery.set_presentation_mode(GalleryPresentationMode.MASONRY)
        cards = []
        for i, h in enumerate([50, 50, 50, 200]):
            card = gallery.create_card_widget(f"/img/{i}.png", None)
            card.setFixedSize(gallery.thumbnail_size + 10, h)
            cards.append(card)
            gallery.common_place_card(gallery.gallery_layout, card, i, 2)
        # Squeeze the tall card: reflow must move it to the shorter column.
        cards[3].setFixedSize(gallery.thumbnail_size + 10, 50)
        gallery.common_reflow_layout(gallery.gallery_layout, 2)
        placed = _card_paths(gallery.gallery_layout)
        col_of = {w.property("gallery_path"): c for _r, c, w in placed}
        assert col_of["/img/3.png"] in (0, 1)
        assert len({r for r, _c, _w in placed}) == 4


class TestOverlayBadgesOnGalleryBase:
    def _make_card(self, gallery):
        card = gallery.create_card_widget("/img/art.png", None)
        gallery.path_to_card_widget["/img/art.png"] = card
        return card

    def test_badges_render_from_metadata_per_config(self, gallery):
        card = self._make_card(gallery)
        gallery.set_overlay_metadata(
            "/img/art.png",
            rating="s",
            resolution=(1920, 1080),
            file_format="PNG",
            star_rating=4.5,
            tag_count=12,
        )
        badges = card.findChildren(QLabel, "gallery_card_badge")
        texts = [b.text() for b in badges]
        assert "S" in texts
        assert "1920×1080" in texts
        assert "PNG" in texts
        assert "★ 4.5" in texts
        assert "🏷 12" in texts

    def test_overlay_config_toggles_hide_chips(self, gallery):
        card = self._make_card(gallery)
        gallery.set_overlay_metadata("/img/art.png", rating="g", tag_count=3)
        gallery.set_overlay_config(
            GalleryOverlayConfig(show_rating=False, show_tag_count=False)
        )
        texts = [b.text() for b in card.findChildren(QLabel, "gallery_card_badge")]
        assert "G" not in texts
        assert not any("3" in t for t in texts)

    def test_no_metadata_no_strip(self, gallery):
        card = self._make_card(gallery)
        assert card.findChild(QWidget, "gallery_card_badge_strip") is None
        gallery.set_overlay_metadata("/img/other.png", rating="s")  # not this card's path
        assert card.findChild(QWidget, "gallery_card_badge_strip") is None

    def test_clear_overlay_metadata_removes_strips(self, gallery):
        card = self._make_card(gallery)
        gallery.set_overlay_metadata("/img/art.png", rating="s")
        assert card.findChild(QWidget, "gallery_card_badge_strip") is not None
        gallery.clear_overlay_metadata()
        assert card.findChild(QWidget, "gallery_card_badge_strip") is None


class TestPresentationMenuOnGalleryBase:
    def test_menu_switches_mode_and_toggles_overlay(self, gallery):
        menu = gallery._build_presentation_menu()
        # Hold explicit refs to every wrapper: PySide6 ties QMenu::addMenu()
        # children to wrapper lifetimes, so generator temporaries kill the
        # sibling submenus (empirically verified, 2026-09-13).
        actions = menu.actions()
        mode_menu = next(a.menu() for a in actions if a.text() == "Presentation Mode")
        mode_actions = mode_menu.actions()
        masonry = next(a for a in mode_actions if a.text() == "Masonry")
        masonry.trigger()
        assert gallery.presentation_mode == GalleryPresentationMode.MASONRY

        actions2 = menu.actions()
        overlay_menu = next(a.menu() for a in actions2 if a.text() == "Thumbnail Overlays")
        overlay_actions = overlay_menu.actions()
        rating = next(a for a in overlay_actions if a.text() == "Rating Badge")
        assert rating.isChecked() is True
        rating.trigger()
        assert gallery._overlay_config.show_rating is False

    def test_event_filter_shows_menu_on_empty_space_only(self, gallery, q_app, monkeypatch):
        card = gallery.create_card_widget("/img/a.png", None)
        gallery.path_to_card_widget["/img/a.png"] = card
        gallery.common_place_card(gallery.gallery_layout, card, 0, 3)
        gallery.gallery_scroll_area.resize(800, 600)
        gallery.gallery_scroll_area.show()
        q_app.processEvents()

        viewport = gallery.gallery_scroll_area.viewport()

        # PySide6 built-in method descriptors can't be class-patched, and a
        # real QMenu.exec() would block forever offscreen -- substitute the
        # builder (the menu itself is covered by the menu test above).
        class _FakeMenu:
            def __init__(self):
                self.execed_with = None

            def exec(self, pos):
                self.execed_with = pos

        fakes = []

        def fake_build():
            fake = _FakeMenu()
            fakes.append(fake)
            return fake

        monkeypatch.setattr(gallery, "_build_presentation_menu", fake_build)

        # Cards live at the top-left; the viewport centre is empty space.
        empty_pos = viewport.rect().center()
        event = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, empty_pos)
        assert gallery.eventFilter(viewport, event) is True
        assert len(fakes) == 1 and fakes[0].execed_with is not None

        # Over the card itself the menu must stay out of the way.
        card_center = card.mapTo(viewport, card.rect().center())
        card_event = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, card_center)
        assert gallery.eventFilter(viewport, card_event) is False
        assert len(fakes) == 1

    def test_masonry_pixmap_arrival_resizes_and_schedules_reflow(self, gallery):
        gallery.set_presentation_mode(GalleryPresentationMode.MASONRY)
        card = gallery.create_card_widget("/img/wide.png", None)
        label = card.findChild(QLabel)
        orig_h = label.height()
        wide = QPixmap(label.width() * 2, label.width())  # 2:1 aspect
        gallery.update_card_pixmap(card, wide)
        assert label.height() < orig_h  # clamped toward the wide aspect
        assert gallery._masonry_reflow_timer.isActive()

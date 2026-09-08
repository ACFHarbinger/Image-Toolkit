"""Pure factory/highlight-helper tests — no full tab."""

from __future__ import annotations

import pytest
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QWidget

from gui.src.components.gallery.card_factory import (
    IN_DB_COLOR,
    PREVIEW_COLOR,
    PREVIEW_WIDTH,
    SELECTION_COLOR,
    apply_preview_highlight,
    create_gallery_card,
    highlight_border_spec,
    reset_preview_highlight,
)
from gui.src.components.labels.clickable_label import ClickableLabel

pytestmark = pytest.mark.gui


def _pix(size: int = 32) -> QPixmap:
    pix = QPixmap(size, size)
    pix.fill()
    return pix


def _single_label(path: str, size: int) -> QLabel:
    label = QLabel()
    label.file_path = path
    label.setFixedSize(size, size)
    return label


def _two_label(path: str, size: int) -> QLabel:
    label = ClickableLabel(path)
    label.setFixedSize(size + 10, size + 10)
    return label


def _noop_style(_widget: QWidget, _selected: bool) -> None:
    return None


class TestCreateGalleryCard:
    def test_single_variant_container_and_gallery_path(self, q_app):
        card = create_gallery_card(
            path="/tmp/a.jpg",
            pixmap=None,
            thumb_size=64,
            selected=False,
            variant="single",
            approx_item_width=100,
            create_label=_single_label,
            update_style=_noop_style,
        )
        assert card.property("gallery_path") == "/tmp/a.jpg"
        assert card.width() == 100
        assert card.height() == 100
        inner = card.findChild(QLabel)
        assert inner is not None
        assert inner.text() == "Loading..."
        assert "dashed" in inner.styleSheet()

    def test_single_variant_applies_pixmap_callback(self, q_app):
        seen = []

        def apply_pixmap(container, pixmap, label):
            seen.append((container, pixmap, label))
            label.setPixmap(pixmap)
            label.setText("")

        pix = _pix()
        card = create_gallery_card(
            path="/tmp/b.jpg",
            pixmap=pix,
            thumb_size=64,
            selected=True,
            variant="single",
            approx_item_width=80,
            create_label=_single_label,
            update_style=_noop_style,
            apply_pixmap=apply_pixmap,
        )
        assert len(seen) == 1
        assert seen[0][0] is card
        inner = card.findChild(QLabel)
        assert inner is not None
        assert not inner.pixmap().isNull()

    def test_two_variant_clickable_wrapper_and_gallery_path(self, q_app):
        styled = []

        def update_style(widget, selected):
            styled.append((widget, selected))

        pix = _pix(200)
        card = create_gallery_card(
            path="/tmp/c.png",
            pixmap=pix,
            thumb_size=64,
            selected=True,
            variant="two",
            create_label=_two_label,
            update_style=update_style,
        )
        assert isinstance(card, ClickableLabel)
        assert card.property("gallery_path") == "/tmp/c.png"
        img = card.findChild(QLabel)
        assert img is not None
        assert not img.pixmap().isNull()
        assert styled and styled[0][1] is True

    def test_two_variant_video_loading_style(self, q_app):
        card = create_gallery_card(
            path="/tmp/clip.mp4",
            pixmap=None,
            thumb_size=64,
            selected=False,
            variant="two",
            create_label=_two_label,
            update_style=_noop_style,
            is_video=True,
        )
        img = card.findChild(QLabel)
        assert img is not None
        assert img.text() == "Loading..."
        assert "#3498db" in img.styleSheet()


class TestHighlightHelper:
    def test_border_spec_priority(self):
        assert highlight_border_spec(preview=True, selected=True, in_db=True) == (
            PREVIEW_COLOR,
            PREVIEW_WIDTH,
        )
        assert highlight_border_spec(selected=True, in_db=True) == (
            SELECTION_COLOR,
            3,
        )
        assert highlight_border_spec(in_db=True) == (IN_DB_COLOR, 3)
        assert highlight_border_spec() == (None, 0)

    def test_apply_and_reset_preview_highlight(self, q_app):
        card = QWidget()
        card.setStyleSheet("border: 1px solid #4f545c;")
        calls = []

        def update_style(widget, selected):
            calls.append(selected)
            widget.setStyleSheet("border: 2px solid #5865f2;")

        apply_preview_highlight(
            card, "/tmp/x.jpg", is_selected=True, update_style=update_style
        )
        assert calls == [True]
        assert PREVIEW_COLOR in card.styleSheet()
        assert card.property("original_style") is not None

        reset_preview_highlight(
            card, "/tmp/x.jpg", is_selected=True, update_style=update_style
        )
        assert PREVIEW_COLOR not in card.styleSheet()
        assert card.property("original_style") is None

    def test_helpers_noop_on_missing_card(self, q_app):
        apply_preview_highlight(
            None, "/tmp/x.jpg", is_selected=False, update_style=_noop_style
        )
        reset_preview_highlight(
            None, "/tmp/x.jpg", is_selected=False, update_style=_noop_style
        )

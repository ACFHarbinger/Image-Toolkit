"""Regressions for the Extractor internal-player geometry."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from PySide6.QtCore import QSizeF, Qt
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy

pytestmark = pytest.mark.gui


def _make_video_tab():
    from gui.src.tabs.core.extractor_tab import ExtractorTab

    with (
        patch("gui.src.tabs.core.extractor_tab._media_player.QMediaPlayer"),
        patch("gui.src.tabs.core.extractor_tab._media_player.QAudioOutput"),
    ):
        tab = ExtractorTab()
    video_tab = tab.video_subtab if hasattr(tab, "video_subtab") else tab
    return tab, video_tab


def test_video_view_has_layout_space_in_a_scrollable_tab(q_app):
    _, video_tab = _make_video_tab()
    view = video_tab.video_view

    assert view.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Expanding

    owner = next(
        layout
        for layout in view.parentWidget().findChildren(QHBoxLayout)
        if layout.indexOf(view) >= 0
    )
    assert owner.itemAt(owner.indexOf(view)).alignment() == Qt.AlignmentFlag(0)


def test_fit_uses_video_aspect_instead_of_viewport_aspect(q_app):
    _, video_tab = _make_video_tab()
    item = video_tab.video_item

    with patch.object(type(item), "nativeSize", return_value=QSizeF(890, 480)):
        video_tab.video_view.resize(200, 900)
        video_tab.fit_video_in_view()

    assert item.size().width() == pytest.approx(890)
    assert item.size().height() == pytest.approx(480)


def test_native_size_change_refits_after_stream_probe(q_app):
    _, video_tab = _make_video_tab()
    item = video_tab.video_item

    with patch.object(type(item), "nativeSize", return_value=QSizeF(1920, 1080)):
        item.nativeSizeChanged.emit(QSizeF(1920, 1080))

    assert item.size() == QSizeF(1920, 1080)


def test_resolution_changes_rendered_size_in_real_scroll_layout(q_app):
    owner, tab = _make_video_tab()
    owner.resize(1800, 1000)
    tab.video_container_widget.show()
    owner.show()
    item = tab.video_item
    with patch.object(type(item), "nativeSize", return_value=QSizeF(1920, 1080)):
        for _ in range(5):
            q_app.processEvents()
        tab.fit_video_in_view()
        first_height = tab.video_view.height()
        first_scale = tab.video_view.transform().m11()
        assert first_height >= 600
        tab.combo_resolution.setCurrentIndex(1)
        for _ in range(5):
            q_app.processEvents()
        assert tab.video_view.height() > first_height
        assert tab.video_view.transform().m11() > first_scale
        owner.resize(800, 1000)
        for _ in range(5):
            q_app.processEvents()
        assert tab.video_view.width() <= 800
        assert tab.video_view.height() == pytest.approx(tab.video_view.width() * 9 / 16, abs=1)
    owner.close()

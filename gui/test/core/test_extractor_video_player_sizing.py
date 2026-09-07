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

    assert view.minimumHeight() == 360
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

    with patch.object(video_tab, "fit_video_in_view") as fit:
        item.nativeSizeChanged.emit(QSizeF(1920, 1080))

    fit.assert_called_once()

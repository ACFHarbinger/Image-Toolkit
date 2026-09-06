"""Regression: the Extractor tab's internal video player must not distort
(crop/stretch) the video's aspect ratio.

User-reported (live desktop, real video files): after the sizing fix in
test_extractor_video_player_sizing.py, videos rendered at their full
allotted area but heavily cropped/stretched -- one 890x480 (~1.85:1)
video rendered as a tall, narrow, heavily-distorted strip.

Root cause, found via git archaeology (commit ebd2ff66 confirmed clean by
the user; bisected forward from there): `fit_video_in_view()` called
`video_item.setSize(video_view.viewport().rect().size())` -- sizing the
QGraphicsVideoItem to the VIEWPORT's raw rect. QGraphicsVideoItem
stretches its decoded frame to fill its own size() (it does not preserve
aspect internally), so forcing the item's size to an arbitrary viewport
rect crops/stretches the video to whatever aspect the surrounding layout
happens to produce, regardless of the video's real aspect ratio.

This was always structurally wrong, but invisible before commit
4d33faeb ("fix(gui): resolve remaining Extractor tab overflow at 800px
minimum width", 2026-09-04): that commit replaced
`video_view.setFixedSize(w, h)` (which pinned the viewport to an exact,
resolution-combo-selected size, e.g. 1280x720 for "720p") with
`setMaximumSize(w, h)` only, with no replacement minimum. Before that
change the viewport was always close to a standard 16:9-ish resolution,
which happened to closely match most real videos' native aspect ratio,
masking the bug. After that change the real viewport aspect started
varying with window width/available layout space, exposing the
crop/distortion for any video whose native aspect doesn't happen to
match whatever aspect the viewport landed on.

Fix: size the item to the video's own native aspect ratio
(QGraphicsVideoItem.nativeSize(), once known -- see the nativeSizeChanged
connection in the video_item property) and let
QGraphicsView.fitInView(item, KeepAspectRatio) scale+letterbox it within
whatever viewport space is actually available, instead of forcing the
item's own shape to match that viewport.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from PySide6.QtCore import QSizeF

pytestmark = pytest.mark.gui


def _make_tab():
    from gui.src.tabs.core.extractor_tab import ExtractorTab

    with (
        patch("gui.src.tabs.core.extractor_tab._media_player.QMediaPlayer"),
        patch("gui.src.tabs.core.extractor_tab._media_player.QAudioOutput"),
    ):
        return ExtractorTab()


class TestFitVideoInViewPreservesNativeAspectRatio:
    def test_item_is_sized_to_native_aspect_not_viewport_rect(self, q_app):
        """The core regression: video_item.setSize() must reflect the
        video's own native size, not the viewport's arbitrary rect."""
        tab = _make_tab()
        video_tab = tab.video_subtab if hasattr(tab, "video_subtab") else tab

        # Force a real (constructed) video item and stub its nativeSize()
        # to a distinctly non-viewport aspect ratio (890x480, ~1.85:1 --
        # the real file that exposed this live).
        item = video_tab.video_item
        native = QSizeF(890, 480)
        with patch.object(type(item), "nativeSize", return_value=native):
            # Give the view an arbitrary, very different aspect ratio to
            # prove the item's size doesn't just mirror it.
            video_tab.video_view.resize(200, 900)
            video_tab.fit_video_in_view()

        item_size = item.size()
        assert item_size.width() == pytest.approx(890), (
            f"video_item width {item_size.width()} does not match the "
            "video's native width -- it's mirroring the viewport instead"
        )
        assert item_size.height() == pytest.approx(480), (
            f"video_item height {item_size.height()} does not match the "
            "video's native height -- it's mirroring the viewport instead"
        )

    def test_empty_native_size_does_not_force_a_bogus_item_size(self, q_app):
        """Before Qt Multimedia has probed the stream, nativeSize() is
        (0, 0) -- fit_video_in_view() must not force the item to an empty
        or viewport-derived size in that window; it should just wait for
        nativeSizeChanged and leave the item's existing size alone."""
        tab = _make_tab()
        video_tab = tab.video_subtab if hasattr(tab, "video_subtab") else tab

        item = video_tab.video_item
        item.setSize(QSizeF(123, 456))
        with patch.object(type(item), "nativeSize", return_value=QSizeF(0, 0)):
            video_tab.fit_video_in_view()

        # Size is left untouched -- not clobbered with an empty/viewport size.
        assert item.size().width() == pytest.approx(123)
        assert item.size().height() == pytest.approx(456)

    def test_implausible_native_size_is_not_trusted(self, q_app):
        """A real-world file was found live with corrupted aspect-ratio
        container metadata: ffprobe confirms an 890x480 (~1.85:1) h264
        stream, but Qt Multimedia's own FFmpeg backend reported
        nativeSize() as 35x480 (~0.073:1) for it -- Qt relaying bad
        metadata, not misusing good metadata. fit_video_in_view() must
        not trust an implausible aspect ratio; it should leave the
        item's existing size alone instead of rendering a postage-stamp
        sliver."""
        tab = _make_tab()
        video_tab = tab.video_subtab if hasattr(tab, "video_subtab") else tab

        item = video_tab.video_item
        item.setSize(QSizeF(500, 400))
        with patch.object(type(item), "nativeSize", return_value=QSizeF(35, 480)):
            video_tab.fit_video_in_view()

        assert item.size().width() == pytest.approx(500), (
            f"video_item width {item.size().width()} was overwritten with "
            "an implausible native size instead of being left alone"
        )
        assert item.size().height() == pytest.approx(400)

    def test_native_size_changed_signal_triggers_a_refit(self, q_app):
        """nativeSize() is only known asynchronously, after Qt Multimedia
        actually probes the stream -- the item must be connected to
        re-fit once that arrives, not just at construction time."""
        tab = _make_tab()
        video_tab = tab.video_subtab if hasattr(tab, "video_subtab") else tab

        item = video_tab.video_item
        with patch.object(video_tab, "fit_video_in_view") as mock_fit:
            item.nativeSizeChanged.emit(QSizeF(1920, 1080))
            mock_fit.assert_called_once()

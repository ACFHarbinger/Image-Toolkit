"""Regression: the Extractor tab's internal video player must fill the
available width (up to its 1280x720 cap), not shrink to a postage stamp.

User-reported (live desktop, real video files): the video frame rendered
correctly but at a tiny fixed size regardless of the "Player Size"
selection or window width.

Root cause: `player_inner_layout.addWidget(video_view, 1,
Qt.AlignmentFlag.AlignCenter)` -- a non-zero alignment argument tells Qt's
layout to size the widget to its sizeHint() instead of filling the cell.
QGraphicsView's sizeHint() with an empty/near-empty scene is tiny (~70x70
in isolation, confirmed empirically), so the view -- and the video frame
scaled to fit inside it via fit_video_in_view() -- rendered squeezed into
that tiny box.

Predates this session entirely (present since the original extractor_tab
package split, commit 47b902ad) -- surfaced for the first time in a long
while only because this session's live-desktop testing actually exercised
the internal player.

Fix: video_view is added with no alignment (so its Expanding/Preferred
size policy and setMaximumSize(1280, 720) cap do the sizing), wrapped in
its own QHBoxLayout with side stretches so it still centers once the
window is wider than the cap.

The size-simulation part of this regression (video_view's actual pixel
size in a shown window) is verified separately against an isolated
reproduction of the same widget/layout pattern, not against the full
ExtractorTab -- the offscreen QPA platform used in CI does not fully
propagate geometry through ExtractorTab's several nested
QTabWidget/QStackedWidget/QScrollArea layers ("This plugin does not
support propagateSizeHints()"), which would make a full-tab test flaky
for reasons unrelated to this bug. The structural assertions below (no
non-zero alignment, correct stretch weighting) are what actually
determine the bug on the real widget.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

pytestmark = pytest.mark.gui


def _make_tab():
    from gui.src.tabs.core.extractor_tab import ExtractorTab

    with (
        patch("gui.src.tabs.core.extractor_tab._media_player.QMediaPlayer"),
        patch("gui.src.tabs.core.extractor_tab._media_player.QAudioOutput"),
    ):
        return ExtractorTab()


class TestVideoViewLayoutIsNotPinnedToSizeHint:
    def test_video_view_has_no_non_zero_alignment_in_its_layout(self, q_app):
        """A non-zero alignment on video_view's layout entry is exactly
        what causes Qt to shrink it to sizeHint() instead of filling its
        cell -- this is the actual root cause, verified structurally."""
        tab = _make_tab()
        video_tab = tab.video_subtab if hasattr(tab, "video_subtab") else tab
        video_view = video_tab.video_view

        # video_view lives in its own QHBoxLayout (video_row) nested inside
        # player_inner_layout -- walk up to find the layout that directly
        # owns it.
        parent = video_view.parentWidget()
        assert parent is not None
        found = None
        for layout in parent.findChildren(QHBoxLayout) + [parent.layout()]:
            if layout is not None and layout.indexOf(video_view) != -1:
                found = layout
                break
        assert found is not None, "could not find video_view's owning layout"
        item_alignment = found.itemAt(found.indexOf(video_view)).alignment()
        assert item_alignment == Qt.AlignmentFlag(0), (
            f"video_view has a non-zero alignment ({item_alignment}) "
            "-- this shrinks it to sizeHint() instead of filling the cell"
        )

    def test_video_view_keeps_its_expanding_size_policy_and_cap(self, q_app):
        tab = _make_tab()
        video_tab = tab.video_subtab if hasattr(tab, "video_subtab") else tab
        video_view = video_tab.video_view

        assert video_view.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Expanding
        assert video_view.maximumSize().width() == 1280
        assert video_view.maximumSize().height() == 720
        assert video_view.minimumSize().width() == 0

    def test_video_view_has_a_real_minimum_height(self, q_app):
        """Part 2 of this regression: the width fix alone still left
        video_view's height at a near-zero sizeHint (confirmed live:
        1280x26) because this tab's page lives inside a QScrollArea that
        forces content WIDTH to the viewport but never forces extra
        HEIGHT -- every section only ever gets its own sizeHint height,
        no matter its stretch factor. An explicit minimum height (below
        every entry's cap in available_resolutions) is the real floor."""
        tab = _make_tab()
        video_tab = tab.video_subtab if hasattr(tab, "video_subtab") else tab
        video_view = video_tab.video_view

        min_height = video_view.minimumSize().height()
        assert min_height > 100, (
            f"video_view minimum height is {min_height} -- too close to "
            "the near-zero sizeHint that caused the 1280x26 squeeze"
        )
        for _w, cap_h in video_tab.available_resolutions:
            assert min_height <= cap_h, (
                f"minimum height {min_height} exceeds a resolution cap "
                f"{cap_h} -- change_resolution() would then request an "
                "invalid min > max size"
            )


class TestVideoViewFillsAvailableWidthIsolated:
    """Reproduces the exact widget/layout pattern _media_player.py uses,
    isolated from ExtractorTab's other nested scroll/tab machinery (see
    module docstring for why the full-tab geometry isn't reliable under
    the offscreen QPA platform)."""

    def _build(self, alignment):
        app = QApplication.instance() or QApplication([])
        host = QWidget()
        host.resize(1000, 800)
        layout = QVBoxLayout(host)
        scene = QGraphicsScene()
        view = QGraphicsView(scene)
        view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        view.setMinimumSize(0, 0)
        view.setMaximumSize(1280, 720)

        if alignment:
            layout.addWidget(view, 1, Qt.AlignmentFlag.AlignCenter)
        else:
            row = QHBoxLayout()
            row.addStretch(1)
            row.addWidget(view, 100)
            row.addStretch(1)
            layout.addLayout(row, 1)

        host.show()
        app.processEvents()
        return host, view

    def test_pre_fix_pattern_reproduces_the_tiny_view_bug(self, q_app):
        host, view = self._build(alignment=True)
        try:
            assert view.width() < 150, (
                "sanity check: the old AlignCenter pattern should still "
                f"reproduce a tiny view (got width={view.width()})"
            )
        finally:
            host.close()

    def test_fixed_pattern_fills_available_width(self, q_app):
        host, view = self._build(alignment=False)
        try:
            assert view.width() > 500, (
                f"video_view.width()={view.width()} looks squeezed instead "
                "of filling the layout up to its 1280px cap"
            )
        finally:
            host.close()


class TestVideoViewHeightInsideScrollAreaIsolated:
    """Reproduces the real bug's actual mechanism: a QScrollArea page with
    many sibling sections, where setWidgetResizable(True) forces content
    WIDTH to the viewport (letting Expanding widgets claim extra width)
    but never forces extra HEIGHT -- so a bare stretch factor does nothing
    and video_view gets squeezed to a near-zero sizeHint height."""

    def _build(self, min_height):
        from PySide6.QtWidgets import QLabel, QScrollArea

        app = QApplication.instance() or QApplication([])
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)

        for i in range(15):
            lbl = QLabel(f"section {i}")
            lbl.setMinimumHeight(40)
            layout.addWidget(lbl)

        scene = QGraphicsScene()
        view = QGraphicsView(scene)
        view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        view.setMinimumSize(0, min_height)
        view.setMaximumSize(1280, 720)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(view, 100)
        row.addStretch(1)
        layout.addLayout(row, 1)

        for i in range(10):
            lbl = QLabel(f"more section {i}")
            lbl.setMinimumHeight(30)
            layout.addWidget(lbl)

        scroll.setWidget(content)
        scroll.resize(1000, 800)
        scroll.show()
        app.processEvents()
        return scroll, view

    def test_zero_minimum_height_reproduces_the_squeeze(self, q_app):
        scroll, view = self._build(min_height=0)
        try:
            assert view.height() < 150, (
                "sanity check: with no explicit minimum height, a "
                f"QScrollArea page with many siblings squeezes video_view "
                f"(got height={view.height()})"
            )
        finally:
            scroll.close()

    def test_explicit_minimum_height_fixes_the_squeeze(self, q_app):
        scroll, view = self._build(min_height=360)
        try:
            assert view.height() >= 360, (
                f"video_view.height()={view.height()} is below its "
                "explicit 360px floor"
            )
        finally:
            scroll.close()

from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.gui


class TestExtractorTabDragPreview:
    """The main video surface (QMediaPlayer / QGraphicsVideoItem) is never
    touched while the slider is actively being dragged -- a floating
    storyboard-preview popup is updated instead (see storyboard.py). The
    real player frame is only committed once the drag pauses ("settles")
    or releases. This replaces every previous live-decode-during-drag
    approach (subprocess-per-frame, proxy-backed subprocess, persistent
    in-process decoder) -- all of which either couldn't sustain real-time
    cadence under actual interactive dragging or reintroduced QMediaPlayer
    surface-swap bugs. See moon/roadmaps/new_features.md §4.14.

    Every codec (including AV1/VP9) flows through the exact same
    QMediaPlayer path -- native Qt/FFmpeg playback handles them fine, so
    there is no separate transcoded-proxy path to special-case here
    anymore.
    """

    def _make_tab(self, tmp_path):
        from gui.src.tabs.core.extractor_tab import ExtractorTab

        video_path = tmp_path / "episode.mkv"
        video_path.write_text("dummy")

        with (
            patch("gui.src.tabs.core.extractor_tab.QMediaPlayer"),
            patch("gui.src.tabs.core.extractor_tab.QAudioOutput"),
        ):
            tab = ExtractorTab()
        mock_player = MagicMock()
        mock_player.position.return_value = 0
        mock_player.duration.return_value = 0
        tab._media_player = mock_player
        tab.video_path = str(video_path)
        tab.duration_ms = 120_000
        tab.slider.setRange(0, 120_000)
        return tab, mock_player, video_path

    def test_drag_tick_never_touches_media_player(self, q_app, tmp_path):
        tab, mock_player, _ = self._make_tab(tmp_path)

        tab._slider_scrubbing = True
        tab._update_drag_preview(45_000)
        tab._update_drag_preview(50_000)
        tab._update_drag_preview(55_000)

        mock_player.setPosition.assert_not_called()
        assert tab.slider.value() == 55_000

    def test_drag_tick_restarts_settle_timer_and_updates_popup(self, q_app, tmp_path):
        from gui.src.helpers.video.storyboard import StoryboardMeta

        tab, _, _ = self._make_tab(tmp_path)
        mock_page = MagicMock()
        mock_page.copy.return_value = MagicMock()
        tab._storyboard_pages = [mock_page]
        tab._storyboard_meta = StoryboardMeta(
            interval_ms=2000,
            tile_width=160,
            tile_height=90,
            cols=5,
            tiles_per_page=25,
            count=25,
            duration_ms=120_000,
            pages=["page_0000.jpg"],
        )

        with patch.object(tab, "_ensure_scrub_popup") as mock_ensure:
            mock_popup = MagicMock()
            mock_ensure.return_value = mock_popup

            tab._update_drag_preview(4_500)

            mock_popup.show_at.assert_called_once()
            kwargs = mock_popup.show_at.call_args.kwargs
            _, x, y, w, h = tab._storyboard_meta.tile_location_for(4_500)
            assert kwargs["tile_rect"] == (x, y, w, h)
            assert kwargs["pixmap"] is mock_page

        assert tab._drag_settle_timer.isActive()

    def test_settle_commits_real_seek_while_still_dragging(self, q_app, tmp_path):
        tab, mock_player, _ = self._make_tab(tmp_path)
        tab.slider.setValue(30_000)

        with patch.object(tab.slider, "isSliderDown", return_value=True):
            tab._on_drag_settled()

        mock_player.setPosition.assert_called_once_with(30_000)

    def test_settle_is_a_noop_if_already_released(self, q_app, tmp_path):
        tab, mock_player, _ = self._make_tab(tmp_path)

        with patch.object(tab.slider, "isSliderDown", return_value=False):
            tab._on_drag_settled()

        mock_player.setPosition.assert_not_called()

    def test_release_commits_real_seek_and_hides_popup(self, q_app, tmp_path):
        tab, mock_player, _ = self._make_tab(tmp_path)
        tab.slider.setValue(60_000)

        with patch.object(tab, "_hide_scrub_popup") as mock_hide:
            tab._slider_scrubbing = True
            tab.set_position_on_release()

            mock_hide.assert_called_once()
        mock_player.setPosition.assert_called_once_with(60_000)
        assert tab._slider_scrubbing is False # pyrefly: ignore [unnecessary-comparison]

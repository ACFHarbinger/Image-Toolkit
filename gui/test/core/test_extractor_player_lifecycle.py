"""Regressions for the extractor player's explicit lifecycle state
(ui-arch-43 / R2.d, issue #565).

Covers the ``NotLoaded -> Restored -> PlayerReady -> Playing`` transitions
and the issue #546 fix: entering ``PlayerReady`` must unconditionally
re-fit the view instead of relying on ``QGraphicsVideoItem.nativeSizeChanged``,
which only fires on an actual value change and therefore silently no-ops
when a same-resolution video replaces the previous one.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from gui.src.tabs.core.extractor_tab._player_lifecycle import PlayerLifecycleState

pytestmark = pytest.mark.gui


def _make_tab(tmp_path):
    from gui.src.tabs.core.extractor_tab import ExtractorTab

    video_path = tmp_path / "episode.mp4"
    video_path.write_text("dummy")
    with (
        patch("gui.src.tabs.core.extractor_tab._media_player.QMediaPlayer"),
        patch("gui.src.tabs.core.extractor_tab._media_player.QAudioOutput"),
    ):
        tab = ExtractorTab()
    video_tab = tab.video_subtab if hasattr(tab, "video_subtab") else tab
    video_tab._media_player = MagicMock()
    video_tab._media_player.position.return_value = 0
    video_tab._media_player.duration.return_value = 0
    return tab, video_tab, str(video_path)


def test_starts_not_loaded(q_app, tmp_path):
    _, video_tab, _ = _make_tab(tmp_path)
    assert video_tab._player_lifecycle_state is PlayerLifecycleState.NOT_LOADED


def test_deferred_load_transitions_to_restored(q_app, tmp_path):
    _, video_tab, video = _make_tab(tmp_path)
    video_tab.load_media(video, force=True, defer_player=True)
    assert video_tab._player_lifecycle_state is PlayerLifecycleState.RESTORED


def test_direct_load_transitions_to_player_ready(q_app, tmp_path):
    _, video_tab, video = _make_tab(tmp_path)
    video_tab.load_media(video, force=True)
    assert video_tab._player_lifecycle_state is PlayerLifecycleState.PLAYER_READY


def test_toggle_playback_completes_restored_to_playing(q_app, tmp_path):
    """The full session-recovery chain: RESTORED -> PLAYER_READY -> PLAYING,
    driven entirely by the first user Play press (issue #565's exit
    criterion state set)."""
    _, video_tab, video = _make_tab(tmp_path)
    video_tab.load_media(video, force=True, defer_player=True)
    assert video_tab._player_lifecycle_state is PlayerLifecycleState.RESTORED

    video_tab._media_player.playbackState.return_value = None
    video_tab.toggle_playback()

    assert video_tab._player_lifecycle_state is PlayerLifecycleState.PLAYING


def test_pause_returns_to_player_ready(q_app, tmp_path):
    from PySide6.QtMultimedia import QMediaPlayer

    _, video_tab, video = _make_tab(tmp_path)
    video_tab.load_media(video, force=True)
    video_tab._media_player.playbackState.return_value = QMediaPlayer.PlaybackState.PlayingState
    video_tab.toggle_playback()
    assert video_tab._player_lifecycle_state is PlayerLifecycleState.PLAYER_READY


def test_close_resets_to_not_loaded(q_app, tmp_path):
    tab, video_tab, video = _make_tab(tmp_path)
    video_tab.load_media(video, force=True)
    assert video_tab._player_lifecycle_state is PlayerLifecycleState.PLAYER_READY
    tab.close()
    assert video_tab._player_lifecycle_state is PlayerLifecycleState.NOT_LOADED


def test_transitions_are_logged(q_app, tmp_path, caplog):
    _, video_tab, video = _make_tab(tmp_path)
    with caplog.at_level(logging.INFO, logger="gui.src.tabs.core.extractor_tab._player_lifecycle"):
        video_tab.load_media(video, force=True, defer_player=True)
    assert any("not_loaded -> restored" in r.message for r in caplog.records)


def test_player_ready_entry_unconditionally_refits_even_without_a_native_size_change(q_app, tmp_path):
    """Issue #546's real remaining bug: nativeSizeChanged only fires on an
    actual value change, so swapping to a second, same-resolution video
    after the first was already fitted left a stale transform with no
    signal to re-trigger it. The PLAYER_READY transition itself must call
    fit_video_in_view() every time, not rely on that signal."""
    _, video_tab, video = _make_tab(tmp_path)

    with patch.object(video_tab, "fit_video_in_view") as mock_fit:
        video_tab._set_player_lifecycle_state(PlayerLifecycleState.PLAYER_READY)
        mock_fit.assert_called_once()

    # A second, distinct entry into PLAYER_READY (e.g. a second video with
    # the same resolution, so nativeSizeChanged would never fire) must
    # re-fit again -- it is not a one-shot connected to the signal.
    video_tab._player_lifecycle_state = PlayerLifecycleState.RESTORED
    with patch.object(video_tab, "fit_video_in_view") as mock_fit:
        video_tab._set_player_lifecycle_state(PlayerLifecycleState.PLAYER_READY)
        mock_fit.assert_called_once()


def test_same_state_transition_is_a_no_op(q_app, tmp_path):
    """Re-entering the same state (e.g. toggle_playback() re-running
    load_media() when nothing actually changed) must not re-log or re-fit."""
    _, video_tab, video = _make_tab(tmp_path)
    video_tab.load_media(video, force=True)
    assert video_tab._player_lifecycle_state is PlayerLifecycleState.PLAYER_READY

    with patch.object(video_tab, "fit_video_in_view") as mock_fit:
        video_tab._set_player_lifecycle_state(PlayerLifecycleState.PLAYER_READY)
        mock_fit.assert_not_called()

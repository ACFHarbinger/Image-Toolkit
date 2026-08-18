"""Regression tests for the startup freeze/crash fix (issue #81 family).

Confirmed live root causes (faulthandler captures, "Fatal Python error:
Aborted"):

1. Every gallery used QThreadPool.globalInstance(), so a wallpaper
   startup-restore cancel_loading() -> thread_pool.waitForDone(-1) blocked
   the main thread on OTHER tabs' pooled workers (ExtractorTab's ffmpeg
   thumbnail batch), freezing startup.
2. QMediaPlayer/QAudioOutput were constructed during session recovery
   (speed-combo setCurrentIndex, load_media, eventFilter, tab change), and
   QAudioOutput() construction aborts the process in this environment --
   even in isolation. QMediaPlayer() alone never aborted.

Fix under test:
- gallery_base.py: dedicated per-instance QThreadPool.
- _view_controls.py: update_playback_speed records the rate without
  constructing the player; _current_duration_ms() avoids constructing it in
  the eventFilter; toggle_playback completes a deferred load.
- _video_session_history.py: load_media(defer_player=True) restores UI state
  only; _on_active_video_tab_changed defers while pending.
- _config_methods.py: recovery calls load_media(..., defer_player=True).
- _media_player.py: the player property does NOT construct QAudioOutput
  (on-demand only); construction is guarded by MEDIA_BACKEND_LOAD_LOCK.
- video_thumbnailer.py: media_backend_spawn_guard() serializes ffmpeg
  subprocess spawns against the first player construction.
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.gui


class TestGalleryDedicatedPool:
    """Galleries must not share QThreadPool.globalInstance() (the cross-tab
    waitForDone(-1) freeze)."""

    def _make_gallery(self):
        from gui.src.tabs.core.wallpaper_tab.common.wallpaper_common_base import (
            WallpaperCommonBase,
        )
        from PySide6.QtWidgets import QGridLayout, QScrollArea, QWidget

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

        return ConcreteWallpaperBase()

    def test_gallery_uses_dedicated_pool_not_global(self, q_app):
        from PySide6.QtCore import QThreadPool

        gallery = self._make_gallery()
        assert gallery.thread_pool is not QThreadPool.globalInstance()
        assert gallery.thread_pool.maxThreadCount() >= 2

    def test_two_galleries_do_not_share_a_pool(self, q_app):
        a = self._make_gallery()
        b = self._make_gallery()
        assert a.thread_pool is not b.thread_pool


class TestPlaybackSpeedDeferral:
    """update_playback_speed must not construct the player (it fires during
    session recovery via combo_player_speed.setCurrentIndex)."""

    def _make_tab(self, tmp_path):
        from gui.src.tabs.core.extractor_tab import ExtractorTab

        with (
            patch("gui.src.tabs.core.extractor_tab._media_player.QMediaPlayer"),
            patch("gui.src.tabs.core.extractor_tab._media_player.QAudioOutput"),
        ):
            return ExtractorTab()

    def test_update_playback_speed_records_rate_without_constructing(self, q_app, tmp_path):
        tab = self._make_tab(tmp_path)
        tab.update_playback_speed("2x")
        assert tab._media_player is None
        assert tab._pending_playback_rate == 2.0

    def test_media_player_property_applies_pending_rate(self, q_app, tmp_path):
        import gui.src.helpers.video.video_thumbnailer as vt
        from gui.src.tabs.core.extractor_tab import ExtractorTab

        with (
            patch("gui.src.tabs.core.extractor_tab._media_player.QMediaPlayer"),
            patch("gui.src.tabs.core.extractor_tab._media_player.QAudioOutput"),
        ):
            tab = ExtractorTab()
            tab.update_playback_speed("1.5x")
            assert tab._media_player is None
            try:
                player = tab.media_player
                player.setPlaybackRate.assert_called_once_with(1.5)
            finally:
                # The property marks the shared backend-loaded flag; restore
                # for test isolation so later spawn-guard tests still
                # exercise the locking path.
                vt._media_backend_loaded = False

    def test_media_player_property_does_not_construct_audio_output(self, q_app, tmp_path):
        import gui.src.helpers.video.video_thumbnailer as vt
        from gui.src.tabs.core.extractor_tab import ExtractorTab

        with (
            patch("gui.src.tabs.core.extractor_tab._media_player.QMediaPlayer"),
            patch("gui.src.tabs.core.extractor_tab._media_player.QAudioOutput"),
        ):
            tab = ExtractorTab()
            try:
                tab.media_player
            finally:
                vt._media_backend_loaded = False
            assert tab._audio_output is None

    def test_current_duration_ms_returns_zero_without_constructing(self, q_app, tmp_path):
        tab = self._make_tab(tmp_path)
        assert tab.duration_ms == 0
        assert tab._current_duration_ms() == 0
        assert tab._media_player is None

    def test_load_video_config_defers_media_position(self, q_app, tmp_path):
        """Restoring media_position must not construct QMediaPlayer."""
        tab = self._make_tab(tmp_path)
        video = str(tmp_path / "episode.mp4")
        tab.slider.setMaximum(60_000)
        tab.active_videos_config[video] = {"media_position": 12_345}
        tab._load_video_config(video)
        assert tab._media_player is None
        assert tab._pending_media_position == 12_345
        assert tab.slider.value() == 12_345

    def test_media_player_property_applies_pending_position(self, q_app, tmp_path):
        import gui.src.helpers.video.video_thumbnailer as vt
        from gui.src.tabs.core.extractor_tab import ExtractorTab

        with (
            patch("gui.src.tabs.core.extractor_tab._media_player.QMediaPlayer"),
            patch("gui.src.tabs.core.extractor_tab._media_player.QAudioOutput"),
        ):
            tab = ExtractorTab()
            tab._pending_media_position = 9_000
            try:
                player = tab.media_player
                player.setPosition.assert_called_once_with(9_000)
            finally:
                vt._media_backend_loaded = False


class TestLoadMediaDefer:
    """load_media(defer_player=True) restores UI state without building the
    player; the first player interaction completes the load."""

    def _make_tab(self, tmp_path):
        from gui.src.tabs.core.extractor_tab import ExtractorTab

        video_path = tmp_path / "episode.mp4"
        video_path.write_text("dummy")
        with (
            patch("gui.src.tabs.core.extractor_tab._media_player.QMediaPlayer"),
            patch("gui.src.tabs.core.extractor_tab._media_player.QAudioOutput"),
        ):
            tab = ExtractorTab()
        tab._media_player = MagicMock()
        tab._media_player.position.return_value = 0
        tab._media_player.duration.return_value = 0
        return tab, str(video_path)

    def test_deferred_load_sets_pending_without_constructing(self, q_app, tmp_path):
        tab, video = self._make_tab(tmp_path)
        tab.load_media(video, force=True, defer_player=True)
        assert tab.video_path == video
        assert tab._media_load_pending is True
        # The player was pre-seeded by the test harness; verify the deferred
        # path did not run _apply_player_mode (setSource not called).
        tab._media_player.setSource.assert_not_called()

    def test_toggle_playback_completes_deferred_load(self, q_app, tmp_path):
        tab, video = self._make_tab(tmp_path)
        tab.load_media(video, force=True, defer_player=True)
        assert tab._media_load_pending is True
        tab.toggle_playback()
        # pyrefly: ignore [unnecessary-comparison]
        assert tab._media_load_pending is False
        tab._media_player.setSource.assert_called_once()


class TestMediaBackendSpawnGuard:
    """ffmpeg subprocess spawns serialize against the first player
    construction; once the backend is loaded the lock is skipped."""

    def test_guard_serializes_before_backend_loaded(self):
        import gui.src.helpers.video.video_thumbnailer as vt

        vt._media_backend_loaded = False
        vt.MEDIA_BACKEND_LOAD_LOCK.acquire()
        entered = []

        def run():
            with vt.media_backend_spawn_guard():
                entered.append(True)

        t = threading.Thread(target=run)
        t.start()
        t.join(0.5)
        # Blocked on the held lock: the guard must not have entered yet.
        assert entered == []
        vt.MEDIA_BACKEND_LOAD_LOCK.release()
        t.join(2.0)
        assert entered == [True]

    def test_guard_skips_lock_after_backend_loaded(self):
        import gui.src.helpers.video.video_thumbnailer as vt

        vt._media_backend_loaded = True
        vt.MEDIA_BACKEND_LOAD_LOCK.acquire()
        entered = []

        def run():
            with vt.media_backend_spawn_guard():
                entered.append(True)

        t = threading.Thread(target=run)
        t.start()
        t.join(0.5)
        vt.MEDIA_BACKEND_LOAD_LOCK.release()
        assert entered == [True]

    def test_mark_media_backend_loaded_flips_flag(self):
        import gui.src.helpers.video.video_thumbnailer as vt

        vt._media_backend_loaded = False
        vt.mark_media_backend_loaded()
        # pyrefly: ignore [unnecessary-comparison]
        assert vt._media_backend_loaded is True
        vt._media_backend_loaded = False

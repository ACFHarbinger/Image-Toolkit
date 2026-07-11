import os
from unittest.mock import MagicMock, patch

import pytest
from gui.src.helpers.video.transcoded_playback import (
    NativeScrubPreview,
    TranscodedPlayback,
    _extract_frame_jpeg,
    needs_transcoded_playback,
    proxy_is_complete,
    proxy_path_for,
)

pytestmark = pytest.mark.gui

HEVC_SAMPLE = (
    "/home/pkhunter/Downloads/data/Videos/"
    "Midareuchi - 02 [1080p-HEVC][hstream.moe][v2].mkv"
)


class TestTranscodedPlayback:
    def test_needs_transcoded_playback_for_av1(self):
        with patch(
            "gui.src.helpers.video.transcoded_playback._probe_codec",
            return_value="av1",
        ):
            assert needs_transcoded_playback("/tmp/ep.mkv") is True

    def test_proxy_is_complete_rejects_truncated(self, tmp_path):
        video = tmp_path / "episode.mkv"
        video.write_text("demo")
        proxy = proxy_path_for(str(video))
        proxy.parent.mkdir(parents=True, exist_ok=True)
        proxy.write_bytes(b"x" * 5000)

        durations = {
            os.path.abspath(str(video)): 966_000,
            str(proxy): 60_000,
        }

        def fake_duration(path):
            return durations.get(path, 0)

        with patch(
            "gui.src.helpers.video.transcoded_playback.probe_duration_ms",
            side_effect=fake_duration,
        ):
            assert proxy_is_complete(str(video)) is False

    def test_preview_scrub_does_not_use_player_path_initially(self, q_app, tmp_path):
        video = tmp_path / "episode.mkv"
        video.write_text("demo")

        with (
            patch(
                "gui.src.helpers.video.transcoded_playback.needs_transcoded_playback",
                return_value=True,
            ),
            patch(
                "gui.src.helpers.video.transcoded_playback.proxy_is_complete",
                return_value=False,
            ),
            patch(
                "gui.src.helpers.video.transcoded_playback.probe_duration_ms",
                return_value=120_000,
            ),
            patch.object(TranscodedPlayback, "start"),
        ):
            playback = TranscodedPlayback(str(video))
            assert playback.use_preview_scrub is True
            assert playback.player_media_path is None

    def test_extractor_av1_scrub_avoids_qt_seek_while_previewing(self, q_app, tmp_path):
        from gui.src.tabs.core.extractor_tab import ExtractorTab

        video_path = tmp_path / "episode.mkv"
        video_path.write_text("dummy")

        with (
            patch("gui.src.tabs.core.extractor_tab.QMediaPlayer"),
            patch("gui.src.tabs.core.extractor_tab.QAudioOutput"),
            patch(
                "gui.src.tabs.core.extractor_tab.needs_transcoded_playback",
                return_value=True,
            ),
            patch.object(TranscodedPlayback, "start"),
        ):
            tab = ExtractorTab()
            mock_player = MagicMock()
            mock_player.position.return_value = 0
            mock_player.duration.return_value = 0
            tab._media_player = mock_player
            tab.video_path = str(video_path)
            tab.duration_ms = 120_000
            tab.slider.setRange(0, 120_000)
            tab._transcoded = TranscodedPlayback(str(video_path))
            tab._transcoded._player_path = None

            tab._slider_scrubbing = True
            tab._seek_to(45_000, from_scrub=True)

            mock_player.setPosition.assert_not_called()
            assert tab.slider.value() == 45_000

    def test_extractor_hevc_scrub_avoids_qt_seek_while_previewing(self, q_app, tmp_path):
        from gui.src.tabs.core.extractor_tab import ExtractorTab

        video_path = tmp_path / "episode.mkv"
        video_path.write_text("dummy")

        with (
            patch("gui.src.tabs.core.extractor_tab.QMediaPlayer"),
            patch("gui.src.tabs.core.extractor_tab.QAudioOutput"),
            patch(
                "gui.src.tabs.core.extractor_tab.needs_transcoded_playback",
                return_value=False,
            ),
        ):
            tab = ExtractorTab()
            mock_player = MagicMock()
            mock_player.position.return_value = 0
            mock_player.duration.return_value = 0
            tab._media_player = mock_player
            tab.video_path = str(video_path)
            tab.duration_ms = 120_000
            tab.slider.setRange(0, 120_000)
            tab._transcoded = None
            tab._native_scrub = NativeScrubPreview(str(video_path))

            with patch.object(
                NativeScrubPreview, "request_preview"
            ) as mock_request_preview:
                tab._slider_scrubbing = True
                tab._seek_to(45_000, from_scrub=True)

                mock_player.setPosition.assert_not_called()
                mock_request_preview.assert_called_once_with(45_000)
                assert tab.slider.value() == 45_000

            # QMediaPlayer keeps showing the last real frame underneath the
            # overlay for the native-codec path -- nothing should ever be
            # hidden while waiting for the first extracted frame.
            assert tab.video_item.isVisible() is True

    def test_extractor_hevc_scrub_seeks_qt_on_release(self, q_app, tmp_path):
        from gui.src.tabs.core.extractor_tab import ExtractorTab

        video_path = tmp_path / "episode.mkv"
        video_path.write_text("dummy")

        with (
            patch("gui.src.tabs.core.extractor_tab.QMediaPlayer"),
            patch("gui.src.tabs.core.extractor_tab.QAudioOutput"),
            patch(
                "gui.src.tabs.core.extractor_tab.needs_transcoded_playback",
                return_value=False,
            ),
        ):
            tab = ExtractorTab()
            mock_player = MagicMock()
            mock_player.position.return_value = 0
            mock_player.duration.return_value = 0
            tab._media_player = mock_player
            tab.video_path = str(video_path)
            tab.duration_ms = 120_000
            tab.slider.setRange(0, 120_000)
            tab._transcoded = None
            tab._native_scrub = NativeScrubPreview(str(video_path))

            assert tab._preview_item is not None
            tab._preview_item.setVisible(True)

            tab._slider_scrubbing = False
            tab._seek_to(60_000, from_scrub=False)

            mock_player.setPosition.assert_called_once_with(60_000)
            assert tab._preview_item.isVisible() is False


@pytest.mark.skipif(
    not os.path.exists(HEVC_SAMPLE), reason="HEVC sample file not present on disk"
)
def test_extract_frame_jpeg_on_real_hevc():
    data = _extract_frame_jpeg(HEVC_SAMPLE, 30_000, max_height=480)
    assert data and len(data) > 1000


class TestNativeScrubPreviewCadence:
    """A fast drag delivers slider ticks far more often than a single frame
    extraction can complete. Cancel-and-restart-on-every-tick was tried and
    measured to produce almost no visible updates (every request kills the
    previous one before it can finish) -- the fix is to coalesce ticks that
    arrive while a request is in flight into a single "latest pending"
    position and chase it once the current extraction completes.
    """

    def test_rapid_ticks_coalesce_into_a_single_in_flight_worker(self, tmp_path):
        video_path = tmp_path / "episode.mkv"
        video_path.write_text("dummy")

        nsp = NativeScrubPreview(str(video_path))
        nsp.set_scrubbing(True)

        spawned = []
        with patch(
            "gui.src.helpers.video.transcoded_playback.QThreadPool.globalInstance"
        ) as mock_pool:
            mock_pool.return_value.start.side_effect = spawned.append

            nsp.request_preview(1_000)
            nsp.request_preview(2_000)
            nsp.request_preview(3_000)

            assert len(spawned) == 1
            assert nsp._pending_ms == 3_000

    def test_completion_chases_latest_pending_position(self, tmp_path):
        video_path = tmp_path / "episode.mkv"
        video_path.write_text("dummy")

        nsp = NativeScrubPreview(str(video_path))
        nsp.set_scrubbing(True)

        spawned = []
        emitted = []
        nsp.preview_image.connect(emitted.append)

        with patch(
            "gui.src.helpers.video.transcoded_playback.QThreadPool.globalInstance"
        ) as mock_pool:
            mock_pool.return_value.start.side_effect = spawned.append

            nsp.request_preview(1_000)
            nsp.request_preview(2_000)
            nsp.request_preview(3_000)
            assert len(spawned) == 1

            # The single in-flight worker finishes for its own (now-stale)
            # position; it should immediately re-fire for the latest one.
            nsp._on_frame_ready(nsp._request_id, 1_000, MagicMock())
            assert len(emitted) == 1
            assert len(spawned) == 2
import os
from unittest.mock import MagicMock, patch

import pytest
from gui.src.helpers.video.transcoded_playback import (
    TranscodedPlayback,
    needs_transcoded_playback,
    proxy_is_complete,
    proxy_path_for,
)

pytestmark = pytest.mark.gui


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
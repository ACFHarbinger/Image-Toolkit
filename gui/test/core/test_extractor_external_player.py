"""The "Switch to External Player" button must actually launch an
external player (previously both branches used the same internal
QMediaPlayer, so the button appeared to do nothing -- see #374 follow-up).

On Linux the launcher prefers the user's default handler (xdg-open, e.g.
Haruna) and falls back to a known player binary only when xdg-open is
unavailable. Duplicate launches for the same video are suppressed, and an
explicit toggle to external mode always (re)launches.
"""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.gui


class TestExtractorTabExternalPlayer:
    def _make_tab(self, tmp_path):
        from gui.src.elements.core.extractor_tab import ExtractorTab

        video_path = tmp_path / "episode.mp4"
        video_path.write_text("dummy")

        with (
            patch("gui.src.elements.core.extractor_tab._media_player.QMediaPlayer"),
            patch("gui.src.elements.core.extractor_tab._media_player.QAudioOutput"),
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

    @contextmanager
    def _linux_launch(self, which_result="/usr/bin/xdg-open"):
        """Patch the Linux launch path; yields the mocked subprocess.Popen."""
        with (
            patch(
                "gui.src.elements.core.extractor_tab._view_controls.platform.system",
                return_value="Linux",
            ),
            patch(
                "gui.src.elements.core.extractor_tab._view_controls.shutil.which",
                return_value=which_result,
            ),
            patch(
                "gui.src.elements.core.extractor_tab._view_controls.subprocess.Popen"
            ) as mock_popen,
        ):
            yield mock_popen

    def test_toggle_to_external_launches_default_handler(self, q_app, tmp_path):
        tab, _, video_path = self._make_tab(tmp_path)

        with self._linux_launch() as mock_popen:
            tab.toggle_player_mode()

        assert tab.use_internal_player is False
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        assert args[0] == "/usr/bin/xdg-open"
        assert args[1] == str(video_path)
        assert mock_popen.call_args.kwargs.get("stdout") is not None

    def test_explicit_toggle_relaunches_same_video(self, q_app, tmp_path):
        """An explicit toggle back to external mode relaunches even when the
        same video was already launched once (the user may have closed the
        external player window since)."""
        tab, _, _ = self._make_tab(tmp_path)
        tab._external_player_launched_path = str(tab.video_path)

        with self._linux_launch() as mock_popen:
            tab.toggle_player_mode()

        mock_popen.assert_called_once()

    def test_reapplying_same_video_does_not_relaunch(self, q_app, tmp_path):
        """_apply_player_mode() runs on every video load; re-applying the
        already-launched video must not spawn a duplicate player window."""
        tab, _, video_path = self._make_tab(tmp_path)
        tab.use_internal_player = False
        tab._external_player_launched_path = str(video_path)

        with self._linux_launch() as mock_popen:
            tab._apply_player_mode()

        mock_popen.assert_not_called()

    def test_new_video_in_external_mode_relaunches(self, q_app, tmp_path):
        tab, _, video_path = self._make_tab(tmp_path)
        tab.use_internal_player = False
        tab._external_player_launched_path = "/other/video.mp4"

        with self._linux_launch() as mock_popen:
            tab._apply_player_mode()

        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        assert args[1] == str(video_path)

    def test_falls_back_to_known_player_when_no_xdg(self, q_app, tmp_path):
        tab, _, video_path = self._make_tab(tmp_path)

        def fake_which(name):
            if name == "xdg-open":
                return None
            if name == "haruna":
                return "/usr/bin/haruna"
            return None

        with (
            patch(
                "gui.src.elements.core.extractor_tab._view_controls.platform.system",
                return_value="Linux",
            ),
            patch(
                "gui.src.elements.core.extractor_tab._view_controls.shutil.which",
                side_effect=fake_which,
            ),
            patch(
                "gui.src.elements.core.extractor_tab._view_controls.subprocess.Popen"
            ) as mock_popen,
        ):
            tab.toggle_player_mode()

        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        assert args == ["/usr/bin/haruna", str(video_path)]

    def test_toggle_back_to_internal_does_not_launch(self, q_app, tmp_path):
        tab, _, _ = self._make_tab(tmp_path)
        tab.use_internal_player = False
        tab._external_player_launched_path = None

        with self._linux_launch() as mock_popen:
            tab.toggle_player_mode()  # -> internal mode

        assert tab.use_internal_player is True
        mock_popen.assert_not_called()

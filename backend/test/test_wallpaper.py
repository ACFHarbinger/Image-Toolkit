import pytest

from unittest.mock import MagicMock, patch
from src.core.wallpaper import WallpaperManager


class TestWallpaperManager:
    @pytest.fixture
    def mock_subprocess(self):
        with patch("src.core.wallpaper.subprocess.run") as mock:
            yield mock

    @pytest.fixture
    def mock_monitor(self):
        m = MagicMock()
        m.x = 0
        m.y = 0
        m.width = 1920
        m.height = 1080
        m.is_primary = True
        return m

    # --- Windows Tests ---

    @patch("src.core.wallpaper.platform.system", return_value="Windows")
    @patch("src.core.wallpaper.winreg", create=True)
    @patch("src.core.wallpaper.ctypes", create=True)
    def test_apply_wallpaper_windows_solid_color(
        self, mock_ctypes, mock_winreg, mock_platform, mock_monitor
    ):
        # Mock Registry
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value = mock_key

        WallpaperManager.apply_wallpaper(
            path_map={"0": "#FF0000"},
            monitors=[mock_monitor],
            style_name="SolidColor",
            qdbus="qdbus",
        )

        # Verify Registry Writes
        # We expect writes to Control Panel\Desktop and Control Panel\Colors
        assert mock_winreg.SetValueEx.call_count >= 3

        # Check SystemParametersInfoW call
        mock_ctypes.windll.user32.SystemParametersInfoW.assert_called_once()

    @patch("src.core.wallpaper.platform.system", return_value="Windows")
    @patch("src.core.wallpaper.winreg", create=True)
    @patch("src.core.wallpaper.ctypes", create=True)
    def test_apply_wallpaper_windows_single_image(
        self, mock_ctypes, mock_winreg, mock_platform, mock_monitor
    ):
        # Mock Registry
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value = mock_key

        WallpaperManager.apply_wallpaper(
            path_map={"0": "/path/to/img.jpg"},
            monitors=[mock_monitor],
            style_name="Fill",
            qdbus="qdbus",
        )

        # Verify Registry Writes
        assert winreg_set_value_ex_called_with(mock_winreg, "WallpaperStyle")

        # Verify SPI call with path
        args = mock_ctypes.windll.user32.SystemParametersInfoW.call_args[0]
        assert str(args[2]).endswith("img.jpg")

    # --- Linux Tests ---

    @patch("src.core.wallpaper.platform.system", return_value="Linux")
    def test_apply_wallpaper_linux_kde(
        self, mock_platform, mock_subprocess, mock_monitor
    ):
        # Mock 'which qdbus' -> success
        mock_subprocess.side_effect = None
        mock_subprocess.return_value.returncode = 0

        WallpaperManager.apply_wallpaper(
            path_map={"0": "/path/to/img.jpg"},
            monitors=[mock_monitor],
            style_name="Fill",
            qdbus="/usr/bin/qdbus",
        )

        # Verify qdbus command execution
        last_call = mock_subprocess.call_args_list[-1]
        cmd = last_call[0][0]
        assert "/usr/bin/qdbus" in cmd
        assert "org.kde.plasmashell" in cmd

    @patch("src.core.wallpaper.platform.system", return_value="Linux")
    @patch("src.core.wallpaper.Image")  # Mock PIL for spanned
    def test_apply_wallpaper_linux_gnome_fallback(
        self, mock_pil, mock_platform, mock_subprocess, mock_monitor
    ):
        # Mock 'which qdbus' -> fail -> trigger GNOME fallback
        original_side_effect = mock_subprocess.side_effect

        def side_effect(cmd, **kwargs):
            if isinstance(cmd, list) and "which" in cmd[0]:
                raise FileNotFoundError()
            return MagicMock()

        mock_subprocess.side_effect = side_effect

        WallpaperManager.apply_wallpaper(
            path_map={"0": "/path/to/img.jpg"},
            monitors=[mock_monitor],
            style_name="Fill",
            qdbus="qdbus",
        )

        # Verify gsettings usage (GNOME)
        # Check if we see a call with "gsettings set org.gnome.desktop.background"
        gsettings_calls = [
            c
            for c in mock_subprocess.call_args_list
            if isinstance(c[0][0], list) and "gsettings" in c[0][0][0]
        ]
        assert len(gsettings_calls) > 0


# Helper to check winreg calls simpler
def winreg_set_value_ex_called_with(mock_winreg, result_key):
    for call in mock_winreg.SetValueEx.call_args_list:
        if result_key in call[0]:
            return True
    return False

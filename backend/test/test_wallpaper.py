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

    @patch("src.core.wallpaper.base")
    @patch("src.core.wallpaper.platform.system", return_value="Linux")
    def test_apply_wallpaper_linux_kde(
        self, mock_platform, mock_base, mock_monitor
    ):
        mock_base.evaluate_kde_script.return_value = "0:0:0:0"

        WallpaperManager.apply_wallpaper(
            path_map={"0": "/path/to/img.jpg"},
            monitors=[mock_monitor],
            style_name="Fill",
            qdbus="/usr/bin/qdbus",
        )

        # Verify base.evaluate_kde_script was called with correct arguments
        assert mock_base.evaluate_kde_script.call_count >= 1
        args = mock_base.evaluate_kde_script.call_args_list[-1][0]
        assert args[0] == "/usr/bin/qdbus"
        assert "org.kde.image" in args[1]

    @patch("src.core.wallpaper.base")
    @patch("src.core.wallpaper.platform.system", return_value="Linux")
    @patch("src.core.wallpaper.Image")  # Mock PIL for spanned
    def test_apply_wallpaper_linux_gnome_fallback(
        self, mock_pil, mock_platform, mock_base, mock_monitor
    ):
        # Make base.evaluate_kde_script raise an exception to trigger fallback
        mock_base.evaluate_kde_script.side_effect = RuntimeError("qdbus failed")

        WallpaperManager.apply_wallpaper(
            path_map={"0": "/path/to/img.jpg"},
            monitors=[mock_monitor],
            style_name="Fill",
            qdbus="qdbus",
        )

        # Verify base.set_wallpaper_gnome was called as fallback
        mock_base.set_wallpaper_gnome.assert_called_once()
        args = mock_base.set_wallpaper_gnome.call_args[0]
        assert "/path/to/img.jpg" in args[0]

    @patch("src.core.wallpaper.base")
    @patch("src.core.wallpaper.platform.system", return_value="Linux")
    @patch("src.core.wallpaper.shutil.which", return_value="/usr/bin/plasma-apply-wallpaperimage")
    @patch("src.core.wallpaper.os.path.exists", return_value=True)
    @patch("src.core.wallpaper.subprocess.run")
    def test_apply_wallpaper_linux_kde_dbus_failed_plasma_apply_fallback(
        self, mock_run, mock_exists, mock_which, mock_platform, mock_base, mock_monitor
    ):
        # get_kde_desktops succeeds by returning desktops, but setting fails
        mock_base.evaluate_kde_script.side_effect = ["0:0:0:0", RuntimeError("qdbus failed setting wallpaper")]

        WallpaperManager.apply_wallpaper(
            path_map={"0": "/path/to/img.jpg"},
            monitors=[mock_monitor],
            style_name="Fill",
            qdbus="qdbus",
        )

        # Verify plasma-apply-wallpaperimage was run
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "/usr/bin/plasma-apply-wallpaperimage"
        assert "--fill-mode" in cmd
        assert "preserveAspectCrop" in cmd
        assert "/path/to/img.jpg" in cmd[-1]

    @patch("src.core.wallpaper.base")
    @patch("src.core.wallpaper.platform.system", return_value="Linux")
    @patch("src.core.wallpaper.shutil.which", return_value="/usr/bin/plasma-apply-wallpaperimage")
    @patch("src.core.wallpaper.os.path.exists", return_value=True)
    @patch("src.core.wallpaper.subprocess.run")
    @patch.dict("os.environ", {"XDG_CURRENT_DESKTOP": "KDE"})
    def test_apply_wallpaper_linux_kde_env_plasma_apply_fallback(
        self, mock_run, mock_exists, mock_which, mock_platform, mock_base, mock_monitor
    ):
        # D-Bus fails completely (get_kde_desktops returns [])
        mock_base.evaluate_kde_script.side_effect = RuntimeError("qdbus failed completely")

        WallpaperManager.apply_wallpaper(
            path_map={"0": "/path/to/img.jpg"},
            monitors=[mock_monitor],
            style_name="Fill",
            qdbus="qdbus",
        )

        # Verify plasma-apply-wallpaperimage was run as KDE env fallback
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "/usr/bin/plasma-apply-wallpaperimage"

    @patch("src.core.wallpaper.base")
    @patch("src.core.wallpaper.platform.system", return_value="Linux")
    @patch("src.core.wallpaper.Path.exists", return_value=False)
    def test_apply_wallpaper_linux_kde_missing_video_plugin(
        self, mock_exists, mock_platform, mock_base, mock_monitor
    ):
        # get_kde_desktops succeeds
        mock_base.evaluate_kde_script.return_value = "0:0:0:0"

        with pytest.raises(RuntimeError, match="No supported KDE video wallpaper plugin found"):
            WallpaperManager.apply_wallpaper(
                path_map={"0": "/path/to/video.mp4"},
                monitors=[mock_monitor],
                style_name="SmartVideoWallpaper::Fill",
                qdbus="qdbus",
            )


# Helper to check winreg calls simpler
def winreg_set_value_ex_called_with(mock_winreg, result_key):
    for call in mock_winreg.SetValueEx.call_args_list:
        if result_key in call[0]:
            return True
    return False

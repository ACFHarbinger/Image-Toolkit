from unittest.mock import MagicMock, patch

import pytest
from src.core.wallpaper import WallpaperManager

# §5.17: wallpaper.py was split into a wallpaper/ package by OS (_windows.py,
# _kde.py, _gnome.py, manager.py), each importing only what it needs. Patches
# below target the submodule that actually owns each name at call time
# (e.g. src.core.wallpaper._windows.winreg, not src.core.wallpaper.winreg) --
# mock.patch resolves names via the module's own globals, not via
# WallpaperManager's inherited-method lookup, so patching the pre-split
# top-level path would silently no-op post-split.
#
# `base` (the native extension) is imported separately in three submodules
# (_dbus.py, _gnome.py, manager.py). Tests that only exercise one of those
# call sites patch that submodule's `base` directly; tests whose code path
# crosses more than one (e.g. a KDE D-Bus failure falling through to the
# GNOME base.set_wallpaper_gnome call in manager.py) use the shared
# `mock_base` fixture below, which patches all three to the same Mock so a
# single assertion object sees every call regardless of which submodule made it.


class TestWallpaperManager:
    @pytest.fixture
    def mock_base(self):
        shared = MagicMock()
        with (
            patch("src.core.wallpaper._dbus.base", shared),
            patch("src.core.wallpaper._gnome.base", shared),
            patch("src.core.wallpaper.manager.base", shared),
        ):
            yield shared

    @pytest.fixture
    def mock_subprocess(self):
        with patch("src.core.wallpaper._gnome.subprocess.run") as mock:
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

    @patch("src.core.wallpaper.manager.platform.system", return_value="Windows")
    @patch("src.core.wallpaper._windows.winreg", create=True)
    @patch("src.core.wallpaper._windows.ctypes", create=True)
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

    @patch("src.core.wallpaper.manager.platform.system", return_value="Windows")
    @patch("src.core.wallpaper._windows.winreg", create=True)
    @patch("src.core.wallpaper._windows.ctypes", create=True)
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

    @patch("src.core.wallpaper.manager.platform.system", return_value="Linux")
    def test_apply_wallpaper_linux_kde(self, mock_platform, mock_base, mock_monitor):
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

    @patch("src.core.wallpaper.manager.platform.system", return_value="Linux")
    @patch("src.core.wallpaper._gnome.Image")  # Mock PIL for spanned
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

    @patch("src.core.wallpaper.manager.platform.system", return_value="Linux")
    @patch(
        "src.core.wallpaper._kde.shutil.which",
        return_value="/usr/bin/plasma-apply-wallpaperimage",
    )
    @patch("src.core.wallpaper._kde.os.path.exists", return_value=True)
    @patch("src.core.wallpaper._kde.subprocess.run")
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

    @patch("src.core.wallpaper.manager.platform.system", return_value="Linux")
    @patch(
        "src.core.wallpaper._kde.shutil.which",
        return_value="/usr/bin/plasma-apply-wallpaperimage",
    )
    @patch("src.core.wallpaper._kde.os.path.exists", return_value=True)
    @patch("src.core.wallpaper._kde.subprocess.run")
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

    @patch("src.core.wallpaper.manager.platform.system", return_value="Linux")
    @patch("src.core.wallpaper._kde.Path.exists", return_value=False)
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

    @patch("src.core.wallpaper.manager.platform.system", return_value="Linux")
    @patch(
        "src.core.wallpaper._kde.Path.exists",
        # get_best_video_plugin() finds the reborn plugin dir on disk...
        return_value=True,
    )
    @patch("src.core.wallpaper._kde.subprocess.run")
    def test_apply_wallpaper_linux_kde_video_plugin_switch_silently_fails(
        self, mock_run, mock_exists, mock_platform, mock_base, mock_monitor
    ):
        """Regression test: when the KDE video wallpaper plugin is found on
        disk but the ``d.wallpaperPlugin = "..."`` assignment doesn't
        actually take effect inside Plasma's scripting engine (the JS runs
        without throwing — evaluateScript() over D-Bus always exits 0), the
        old code fell through and unconditionally blanked org.kde.image's
        Color to transparent black, producing a black screen while
        WallpaperWorker still reported Success: True. It must now raise
        instead of silently "succeeding".
        """
        # First call: get_kde_desktops(). Second call: the actual video
        # wallpaper script — its `print("ERROR: ...")` diagnostic is what
        # the (mocked) Plasma shell's evaluateScript would return when the
        # plugin switch didn't take, since currentConfigGroup change never
        # got applied to a *different* plugin.
        mock_base.evaluate_kde_script.side_effect = [
            "0:0:0:0",
            "ERROR: monitor 0 failed to switch to video wallpaper plugin "
            "'luisbocanegra.smart.video.wallpaper.reborn' (still on 'org.kde.image').",
        ]

        with pytest.raises(RuntimeError, match="KDE wallpaper script reported errors"):
            WallpaperManager.apply_wallpaper(
                path_map={"0": "/path/to/video.mp4"},
                monitors=[mock_monitor],
                style_name="SmartVideoWallpaper::Fill",
                qdbus="qdbus",
            )

        # And critically: a video-mode failure must NOT fall back to
        # plasma-apply-wallpaperimage (which can't render video and would
        # just trade one misleading "success" for another).
        mock_run.assert_not_called()

    @patch("src.core.wallpaper.manager.platform.system", return_value="Linux")
    @patch("src.core.wallpaper._kde.Path.exists", return_value=True)
    def test_apply_wallpaper_linux_kde_video_writes_file_uri(
        self, mock_exists, mock_platform, mock_base, mock_monitor
    ):
        """Regression test: VideoUrls/VideoWallpaperBackgroundVideo are
        QUrl-typed config keys and need an actual file:// URI. Writing a
        bare filesystem path there (as the code used to, mirroring
        org.kde.image's "Image" key, which *does* want a raw path) let
        writeConfig()/reloadConfig() succeed with no error while the video
        plugin had nothing resolvable to play — a black screen with
        Success: True, confirmed live via the plugin-switch/write
        diagnostics added in 35c0e0f1 (which showed the switch and write
        both succeeding, ruling out the earlier hypothesis).
        """
        mock_base.evaluate_kde_script.side_effect = [
            "0:0:0:0",
            "OK: monitor 0 switched.",
        ]

        WallpaperManager.apply_wallpaper(
            path_map={"0": "/path/to/video.mp4"},
            monitors=[mock_monitor],
            style_name="SmartVideoWallpaper::Fill",
            qdbus="qdbus",
        )

        script = mock_base.evaluate_kde_script.call_args_list[-1][0][1]
        assert 'writeConfig("VideoUrls", "file:///path/to/video.mp4")' in script
        assert 'writeConfig("VideoUrls", "/path/to/video.mp4")' not in script


# Helper to check winreg calls simpler
def winreg_set_value_ex_called_with(mock_winreg, result_key):
    return any(result_key in call[0] for call in mock_winreg.SetValueEx.call_args_list)

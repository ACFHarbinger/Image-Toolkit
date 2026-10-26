"""Bridge-produced slideshow config uses contract styles and no Qt geometry."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import Mock

import pytest


@pytest.fixture
def daemon(tmp_path, monkeypatch):
    # Loading the legacy daemon configures file logging at import time.
    from middleware.src.constants import utils

    monkeypatch.setattr(utils, "DISPLAY_LOG_PATH", tmp_path / "display.log")
    path = Path(__file__).resolve().parents[2] / "src/utils/display/slideshow_daemon.py"
    spec = importlib.util.spec_from_file_location("slideshow_bridge_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(("desktop", "style", "expected"), [
    ("KDE", "fit", "Scaled, Keep Proportions"),
    ("GNOME", "span", "Spanned"),
    ("KDE", "Centered", "Centered"),
])
def test_daemon_translates_bridge_styles_and_preserves_qt_names(daemon, monkeypatch, desktop, style, expected):
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", desktop)
    monkeypatch.setenv("XDG_SESSION_DESKTOP", "")
    monkeypatch.setattr("middleware.src.services.wallpaper.handlers.platform.system", lambda: "Linux")
    apply = Mock()
    monkeypatch.setattr(daemon.WallpaperManager, "apply_wallpaper", apply)
    daemon._apply_all({"0": {"paths": ["/caller/a.png"], "index": 0}}, "kde", None, style, [])
    assert apply.call_args.args[2] == expected


def test_bridge_config_discovers_monitors_without_saved_geometry(daemon, monkeypatch):
    import screeninfo

    monitors = [screeninfo.Monitor(x=0, y=0, width=1280, height=720)]
    discover = Mock(return_value=monitors)
    monkeypatch.setattr(screeninfo, "get_monitors", discover)
    assert daemon._parse_monitors({"monitor_queues": {"0": ["/caller/a.png"]}}) == monitors
    discover.assert_called_once()


def test_qt_geometry_does_not_trigger_discovery(daemon, monkeypatch):
    import screeninfo

    discover = Mock(side_effect=AssertionError("unexpected discovery"))
    monkeypatch.setattr(screeninfo, "get_monitors", discover)
    monitors = daemon._parse_monitors({"monitor_geometries": {"0": {"width": 640, "height": 480}}})
    assert monitors[0].width == 640
    discover.assert_not_called()

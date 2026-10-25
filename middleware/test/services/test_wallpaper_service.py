"""Unit tests for the Wallpaper domain service (A-01 / #913)."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from unittest.mock import patch

import pytest
from middleware.src.services.base import CommandValidationError
from middleware.src.services.wallpaper import (
    GetMonitorsResult,
    MonitorInfoItem,
    SetWallpaperCommand,
    SetWallpaperResult,
    SlideshowConfigCommand,
    SlideshowToggleCommand,
    WallpaperService,
    WallpaperServiceProtocol,
)
from PIL import Image


def _create_sample_image(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (64, 64), (120, 160, 200))
    img.save(path)
    return str(path)


def test_wallpaper_protocol_conformance() -> None:
    service = WallpaperService()
    assert isinstance(service, WallpaperServiceProtocol)


def test_wallpaper_command_immutability() -> None:
    cmd = SetWallpaperCommand(path_map={"0": "/a.png"}, style="fill")
    with pytest.raises(dataclasses.FrozenInstanceError):
        cmd.style = "fit"  # type: ignore[misc]

    res = SetWallpaperResult(success=True, message="ok")
    with pytest.raises(dataclasses.FrozenInstanceError):
        res.success = False  # type: ignore[misc]


def test_get_monitors_execution() -> None:
    service = WallpaperService()
    result = service.get_monitors()
    assert isinstance(result, GetMonitorsResult)
    assert len(result.monitors) >= 1
    assert isinstance(result.monitors[0], MonitorInfoItem)
    assert result.monitors[0].width > 0
    assert result.monitors[0].height > 0
    assert result.desktop_environment != ""


def test_set_wallpaper_validation_empty_map() -> None:
    service = WallpaperService()
    with pytest.raises(CommandValidationError):
        service.set_wallpaper(SetWallpaperCommand(path_map={}))


def test_set_wallpaper_missing_file(tmp_path: Path) -> None:
    service = WallpaperService()
    missing_path = str(tmp_path / "missing_wallpaper.png")
    result = service.set_wallpaper(SetWallpaperCommand(path_map={"0": missing_path}))
    assert result.success is False
    assert "does not exist" in result.message


def test_set_wallpaper_success_with_mock(tmp_path: Path) -> None:
    img_path = _create_sample_image(tmp_path / "bg.png")
    service = WallpaperService()

    with patch("middleware.src.core.wallpaper.manager.WallpaperManager.apply_wallpaper") as mock_apply:
        result = service.set_wallpaper(
            SetWallpaperCommand(
                path_map={"0": img_path},
                style="fit",
                background_color="#123456",
            )
        )
        assert result.success is True
        assert "0" in result.applied_monitors
        mock_apply.assert_called_once()


def test_slideshow_config_read_and_update(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg_path = tmp_path / "slideshow.json"
    monkeypatch.setattr("middleware.src.services.wallpaper.handlers.DAEMON_CONFIG_PATH", cfg_path)
    monkeypatch.setattr("middleware.src.services.wallpaper.handlers.IMAGE_TOOLKIT_DIR", tmp_path)

    service = WallpaperService()
    initial = service.slideshow_config(SlideshowConfigCommand(update=False))
    assert initial.interval_seconds == 300

    # Validation: invalid interval
    with pytest.raises(CommandValidationError):
        service.slideshow_config(SlideshowConfigCommand(update=True, interval_seconds=0))

    # Update config
    updated = service.slideshow_config(
        SlideshowConfigCommand(
            update=True,
            interval_seconds=120,
            style="span",
            monitor_queues={"0": ["/path/1.png", "/path/2.png"]},
            current_paths={"0": "/path/1.png"},
        )
    )
    assert updated.interval_seconds == 120
    assert updated.style == "span"
    assert updated.monitor_queues["0"] == ["/path/1.png", "/path/2.png"]
    assert cfg_path.exists()

    # Read back fresh
    readback = service.slideshow_config(SlideshowConfigCommand(update=False))
    assert readback.interval_seconds == 120
    assert readback.style == "span"
    assert readback.monitor_queues["0"] == ["/path/1.png", "/path/2.png"]


def test_slideshow_toggle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg_path = tmp_path / "slideshow.json"
    monkeypatch.setattr("middleware.src.services.wallpaper.handlers.DAEMON_CONFIG_PATH", cfg_path)
    monkeypatch.setattr("middleware.src.services.wallpaper.handlers.IMAGE_TOOLKIT_DIR", tmp_path)

    service = WallpaperService()
    start_res = service.slideshow_toggle(SlideshowToggleCommand(running=True))
    assert start_res.running is True
    assert "started" in start_res.message

    stop_res = service.slideshow_toggle(SlideshowToggleCommand(running=False))
    assert stop_res.running is False
    assert "stopped" in stop_res.message

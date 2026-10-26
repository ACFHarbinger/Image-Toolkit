"""Unit tests for the Wallpaper domain service (A-01 / #913)."""

from __future__ import annotations

import dataclasses
import json
import os
import signal
import subprocess
import sys
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
    assert readback.running is False


def test_slideshow_config_reports_a_live_daemon(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from middleware.src.sidecar.handlers.wallpaper import handle_slideshow_config

    cfg_path = tmp_path / "slideshow.json"
    monkeypatch.setattr("middleware.src.services.wallpaper.handlers.DAEMON_CONFIG_PATH", cfg_path)
    monkeypatch.setattr("middleware.src.services.wallpaper.handlers.IMAGE_TOOLKIT_DIR", tmp_path)
    cfg_path.write_text(
        json.dumps(
            {
                "interval_seconds": 30,
                "style": "fill",
                "monitor_queues": {},
                "current_paths": {},
                "running": True,
                "pid": 424242,
            }
        ),
        encoding="utf-8",
    )

    service = WallpaperService()
    dead = service.slideshow_config(SlideshowConfigCommand(update=False))
    assert dead.running is False

    monkeypatch.setattr(
        "middleware.src.services.wallpaper.handlers._pid_alive", lambda pid: pid == 424242
    )
    live = handle_slideshow_config(service, {"update": False})
    assert live["running"] is True

    cfg_path.write_text(
        json.dumps({"running": False, "pid": 424242, "interval_seconds": 30, "style": "fill"}),
        encoding="utf-8",
    )
    stopped = service.slideshow_config(SlideshowConfigCommand(update=False))
    assert stopped.running is False


_FAKE_DAEMON_PID = 515151


class _FakeDaemonProc:
    pid = _FAKE_DAEMON_PID


def _isolate_daemon_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    cfg_path = tmp_path / "slideshow.json"
    monkeypatch.setattr("middleware.src.services.wallpaper.handlers.DAEMON_CONFIG_PATH", cfg_path)
    monkeypatch.setattr("middleware.src.services.wallpaper.handlers.IMAGE_TOOLKIT_DIR", tmp_path)
    return cfg_path


def _patch_daemon_process(
    monkeypatch: pytest.MonkeyPatch,
    *,
    die_on_term: bool,
) -> dict[str, list]:
    """Replace Popen and os.kill so the real slideshow daemon never starts."""
    captured: dict[str, list] = {"commands": [], "signals": []}
    alive = {"value": True}

    def _popen(cmd, **kwargs):
        captured["commands"].append((list(cmd), kwargs))
        return _FakeDaemonProc()

    def _kill(pid: int, sig: int) -> None:
        captured["signals"].append((pid, sig))
        if pid != _FAKE_DAEMON_PID:
            raise ProcessLookupError
        if sig == 0 and not alive["value"]:
            raise ProcessLookupError
        if sig == signal.SIGTERM and die_on_term:
            alive["value"] = False

    monkeypatch.setattr("middleware.src.services.wallpaper.handlers.subprocess.Popen", _popen)
    monkeypatch.setattr("middleware.src.services.wallpaper.handlers.os.kill", _kill)
    return captured


def test_slideshow_toggle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg_path = _isolate_daemon_config(tmp_path, monkeypatch)
    captured = _patch_daemon_process(monkeypatch, die_on_term=True)
    service = WallpaperService()
    service.slideshow_config(
        SlideshowConfigCommand(
            update=True,
            interval_seconds=120,
            style="span",
            monitor_queues={"0": ["/path/1.png"]},
            current_paths={"0": "/path/1.png"},
        )
    )

    start_res = service.slideshow_toggle(SlideshowToggleCommand(running=True))
    assert start_res.running is True
    assert start_res.pid == _FAKE_DAEMON_PID
    assert start_res.pid != os.getpid()
    assert "started" in start_res.message
    assert start_res.error is None

    assert len(captured["commands"]) == 1
    cmd, kwargs = captured["commands"][0]
    script = Path(cmd[-1])
    assert cmd[0] == sys.executable
    assert script.name == "slideshow_daemon.py"
    assert script.is_file()
    assert kwargs["start_new_session"] is True
    assert kwargs["stdout"] is subprocess.DEVNULL
    assert kwargs["stderr"] is subprocess.DEVNULL

    stored = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert stored["running"] is True
    assert stored["pid"] == _FAKE_DAEMON_PID
    assert stored["interval_seconds"] == 120
    assert stored["style"] == "span"
    assert stored["monitor_queues"]["0"] == ["/path/1.png"]
    assert stored["current_paths"]["0"] == "/path/1.png"

    stop_res = service.slideshow_toggle(SlideshowToggleCommand(running=False))
    assert stop_res.running is False
    assert stop_res.pid != os.getpid()
    assert "stopped" in stop_res.message
    assert signal.SIGTERM in {sig for _pid, sig in captured["signals"]}
    stopped = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert stopped["running"] is False
    assert stopped["interval_seconds"] == 120
    assert stopped["style"] == "span"


def test_slideshow_toggle_stop_when_pid_stays_alive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg_path = _isolate_daemon_config(tmp_path, monkeypatch)
    captured = _patch_daemon_process(monkeypatch, die_on_term=False)
    service = WallpaperService()
    start_res = service.slideshow_toggle(SlideshowToggleCommand(running=True))
    assert start_res.running is True
    assert start_res.pid == _FAKE_DAEMON_PID

    def _kill_after_config_cleared(pid: int, sig: int) -> None:
        captured["signals"].append((pid, sig))
        if sig == signal.SIGTERM:
            stored = json.loads(cfg_path.read_text(encoding="utf-8"))
            assert stored["running"] is False
        if pid != _FAKE_DAEMON_PID:
            raise ProcessLookupError

    monkeypatch.setattr(
        "middleware.src.services.wallpaper.handlers.os.kill", _kill_after_config_cleared
    )

    stop_res = service.slideshow_toggle(SlideshowToggleCommand(running=False))
    assert stop_res.running is True
    assert stop_res.pid == _FAKE_DAEMON_PID
    assert stop_res.pid != os.getpid()
    assert stop_res.error
    assert "did not stop" in stop_res.message
    assert any(sig == signal.SIGTERM and pid == _FAKE_DAEMON_PID for pid, sig in captured["signals"])


def test_slideshow_toggle_dead_pid_is_not_started(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg_path = _isolate_daemon_config(tmp_path, monkeypatch)

    def _popen(cmd, **kwargs):
        return _FakeDaemonProc()

    def _kill(pid: int, sig: int) -> None:
        raise ProcessLookupError

    monkeypatch.setattr("middleware.src.services.wallpaper.handlers.subprocess.Popen", _popen)
    monkeypatch.setattr("middleware.src.services.wallpaper.handlers.os.kill", _kill)

    service = WallpaperService()
    start_res = service.slideshow_toggle(SlideshowToggleCommand(running=True))
    assert start_res.running is False
    assert start_res.pid != _FAKE_DAEMON_PID
    assert "started" not in start_res.message
    assert start_res.error
    stored = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert stored["running"] is False
    assert "pid" not in stored


def test_set_wallpaper_style_names_follow_desktop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    img_path = _create_sample_image(tmp_path / "bg.png")
    service = WallpaperService()
    monkeypatch.setattr("middleware.src.services.wallpaper.handlers.platform.system", lambda: "Linux")

    expected = {
        "KDE": {
            "fit": "Scaled, Keep Proportions",
            "center": "Centered",
            "tile": "Tiled",
            "span": "Span",
        },
        "GNOME": {
            "fit": "Scaled",
            "center": "Centered",
            "tile": "Wallpaper",
            "span": "Spanned",
        },
    }
    for desktop, styles in expected.items():
        monkeypatch.setenv("XDG_CURRENT_DESKTOP", desktop)
        monkeypatch.setenv("XDG_SESSION_DESKTOP", "")
        for style, canonical in styles.items():
            with patch(
                "middleware.src.core.wallpaper.manager.WallpaperManager.apply_wallpaper"
            ) as mock_apply:
                result = service.set_wallpaper(
                    SetWallpaperCommand(path_map={"0": img_path}, style=style)
                )
                assert result.success is True
                assert canonical in result.message
                assert mock_apply.call_args.kwargs["style_name"] == canonical

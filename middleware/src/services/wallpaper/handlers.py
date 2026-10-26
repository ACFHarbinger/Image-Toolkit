"""Handlers for the Wallpaper domain service (A-01 / #913).

Executes monitor discovery, per-monitor wallpaper application, and
shared slideshow daemon configuration without UI coupling.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from middleware.src.constants.paths import DAEMON_CONFIG_PATH, IMAGE_TOOLKIT_DIR
from middleware.src.services.base import CommandValidationError, Handler
from middleware.src.services.wallpaper.commands import (
    GetMonitorsCommand,
    GetMonitorsResult,
    MonitorInfoItem,
    SetWallpaperCommand,
    SetWallpaperResult,
    SlideshowConfigCommand,
    SlideshowConfigResult,
    SlideshowToggleCommand,
    SlideshowToggleResult,
)

logger = logging.getLogger(__name__)

# Contract enum -> names WALLPAPER_STYLES actually keys on. Windows has no Span.
_WINDOWS_STYLE_NAMES = {
    "fill": "Fill",
    "fit": "Fit",
    "stretch": "Stretch",
    "center": "Center",
    "tile": "Tile",
    "span": "Fill",
}
_KDE_STYLE_NAMES = {
    "fill": "Scaled and Cropped",
    "fit": "Scaled, Keep Proportions",
    "stretch": "Stretch",
    "center": "Centered",
    "tile": "Tiled",
    "span": "Span",
}
_GNOME_STYLE_NAMES = {
    "fill": "Zoom",
    "fit": "Scaled",
    "stretch": "Stretched",
    "center": "Centered",
    "tile": "Wallpaper",
    "span": "Spanned",
}


def _detect_desktop_environment() -> str:
    """Detect current operating system and desktop environment."""
    system = platform.system()
    if system == "Linux":
        xdg = os.environ.get("XDG_CURRENT_DESKTOP", "").strip()
        if xdg:
            return f"Linux ({xdg})"
        return "Linux"
    if system == "Darwin":
        return "macOS"
    return system


def _style_names_for_desktop() -> dict[str, str]:
    """Pick the WALLPAPER_STYLES key table for the running desktop."""
    system = platform.system()
    if system == "Windows" or system == "Darwin":
        return _WINDOWS_STYLE_NAMES
    session = (
        f"{os.environ.get('XDG_CURRENT_DESKTOP', '')} {os.environ.get('XDG_SESSION_DESKTOP', '')}"
    ).lower()
    if "kde" in session or "plasma" in session:
        return _KDE_STYLE_NAMES
    return _GNOME_STYLE_NAMES


def canonical_wallpaper_style(style: str) -> str:
    """Map a contract style (fill/fit/stretch/center/tile/span) to a desktop name."""
    table = _style_names_for_desktop()
    return table.get((style or "").strip().lower(), table["fill"])


def spawn_slideshow_daemon() -> subprocess.Popen[bytes]:
    """Start slideshow_daemon.py without importing it.

    Importing that module creates ~/.image-toolkit/logs as a side effect.
    ``parents[2]`` is middleware/src; parents[3] is the middleware package
    root and does not contain this script.
    """
    script = Path(__file__).resolve().parents[2] / "utils" / "display" / "slideshow_daemon.py"
    return subprocess.Popen(
        [sys.executable, str(script)],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _still_alive(pid: int, timeout: float = 1.0) -> bool:
    """True when pid is still alive after SIGTERM has had a moment to land."""
    deadline = time.monotonic() + timeout
    while _pid_alive(pid):
        if time.monotonic() >= deadline:
            return True
        time.sleep(0.05)
    return False


def _verified_daemon_running(config: dict[str, Any]) -> bool:
    """True when the saved flag is set and that pid is still alive."""
    if not config.get("running"):
        return False
    pid = _config_pid(config)
    return pid is not None and _pid_alive(pid)


def _config_pid(config: dict[str, Any]) -> int | None:
    try:
        pid = int(config.get("pid"))
    except (TypeError, ValueError):
        return None
    return pid if pid > 0 else None


def _load_daemon_config() -> dict[str, Any]:
    config_path = DAEMON_CONFIG_PATH
    if not config_path.is_file():
        return {}
    try:
        with config_path.open("r", encoding="utf-8") as handle:
            loaded = json.load(handle) or {}
    except Exception:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _persist_daemon_config(config: dict[str, Any]) -> None:
    IMAGE_TOOLKIT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", dir=IMAGE_TOOLKIT_DIR, delete=False, encoding="utf-8"
    ) as tmp:
        json.dump(config, tmp, indent=2)
        tmp_name = tmp.name
    os.replace(tmp_name, DAEMON_CONFIG_PATH)


class GetMonitorsHandler(Handler[GetMonitorsCommand, GetMonitorsResult]):
    """Handler for discovering connected physical displays."""

    def handle(self, command: GetMonitorsCommand | None = None) -> GetMonitorsResult:
        t0 = time.monotonic()
        desktop_env = _detect_desktop_environment()
        monitors: list[MonitorInfoItem] = []

        try:
            from screeninfo import get_monitors

            raw_monitors = get_monitors()
            for idx, m in enumerate(raw_monitors):
                monitors.append(
                    MonitorInfoItem(
                        id=str(idx),
                        name=getattr(m, "name", f"Display {idx}"),
                        width=getattr(m, "width", 1920),
                        height=getattr(m, "height", 1080),
                        x=getattr(m, "x", 0),
                        y=getattr(m, "y", 0),
                        is_primary=bool(getattr(m, "is_primary", idx == 0)),
                    )
                )
        except Exception as exc:
            logger.warning("screeninfo monitor query failed, using fallback: %s", exc)

        if not monitors:
            monitors.append(
                MonitorInfoItem(
                    id="0",
                    name="Primary Display",
                    width=1920,
                    height=1080,
                    x=0,
                    y=0,
                    is_primary=True,
                )
            )

        elapsed = round(time.monotonic() - t0, 4)
        return GetMonitorsResult(
            monitors=tuple(monitors),
            desktop_environment=desktop_env,
            elapsed_seconds=elapsed,
        )


class SetWallpaperHandler(Handler[SetWallpaperCommand, SetWallpaperResult]):
    """Handler for applying wallpaper per monitor or spanned across displays."""

    def handle(self, command: SetWallpaperCommand) -> SetWallpaperResult:
        t0 = time.monotonic()
        if not command.path_map:
            raise CommandValidationError(
                "No wallpaper paths provided in path_map", field="path_map"
            )

        # Validate paths exist
        for m_id, path in command.path_map.items():
            if not os.path.isfile(path):
                return SetWallpaperResult(
                    success=False,
                    message=f"Wallpaper image file does not exist for monitor {m_id}: {path}",
                    applied_monitors=(),
                    elapsed_seconds=round(time.monotonic() - t0, 4),
                    error=f"File not found: {path}",
                )

        try:
            from screeninfo import get_monitors

            from middleware.src.core.wallpaper.manager import WallpaperManager

            try:
                monitors = get_monitors()
            except Exception:
                monitors = 1

            canonical_style = canonical_wallpaper_style(command.style)

            WallpaperManager.apply_wallpaper(
                path_map=dict(command.path_map),
                monitors=monitors,
                style_name=canonical_style,
                background_color=command.background_color,
            )

            elapsed = round(time.monotonic() - t0, 4)
            return SetWallpaperResult(
                success=True,
                message=f"Applied wallpaper ({canonical_style}) to {len(command.path_map)} monitor(s)",
                applied_monitors=tuple(command.path_map.keys()),
                elapsed_seconds=elapsed,
            )
        except Exception as exc:
            logger.exception("Failed to apply wallpaper: %s", exc)
            return SetWallpaperResult(
                success=False,
                message=f"Wallpaper application failed: {exc}",
                applied_monitors=(),
                elapsed_seconds=round(time.monotonic() - t0, 4),
                error=str(exc),
            )


class SlideshowConfigHandler(Handler[SlideshowConfigCommand, SlideshowConfigResult]):
    """Handler for reading and updating shared slideshow daemon configuration."""

    def handle(self, command: SlideshowConfigCommand) -> SlideshowConfigResult:
        t0 = time.monotonic()
        IMAGE_TOOLKIT_DIR.mkdir(parents=True, exist_ok=True)
        config_path = DAEMON_CONFIG_PATH

        current_config: dict[str, Any] = {
            "interval_seconds": 300,
            "style": "fill",
            "monitor_queues": {},
            "current_paths": {},
            "running": False,
        }

        if config_path.is_file():
            try:
                with config_path.open("r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        current_config.update(loaded)
            except Exception as exc:
                logger.warning("Could not read slideshow config at %s: %s", config_path, exc)

        if command.update:
            if command.interval_seconds is not None:
                if command.interval_seconds < 1:
                    raise CommandValidationError(
                        "interval_seconds must be >= 1", field="interval_seconds"
                    )
                current_config["interval_seconds"] = command.interval_seconds
            if command.style is not None:
                current_config["style"] = command.style
            if command.monitor_queues is not None:
                current_config["monitor_queues"] = dict(command.monitor_queues)
            if command.current_paths is not None:
                current_config["current_paths"] = dict(command.current_paths)

            # Atomic write
            try:
                with tempfile.NamedTemporaryFile(
                    "w", dir=IMAGE_TOOLKIT_DIR, delete=False, encoding="utf-8"
                ) as tmp:
                    json.dump(current_config, tmp, indent=2)
                    tmp_name = tmp.name
                os.replace(tmp_name, config_path)
            except Exception as exc:
                return SlideshowConfigResult(
                    config_path=str(config_path),
                    elapsed_seconds=round(time.monotonic() - t0, 4),
                    error=f"Failed to write config: {exc}",
                )

        elapsed = round(time.monotonic() - t0, 4)
        return SlideshowConfigResult(
            interval_seconds=int(current_config.get("interval_seconds", 300)),
            style=str(current_config.get("style", "fill")),
            monitor_queues=dict(current_config.get("monitor_queues", {})),
            current_paths=dict(current_config.get("current_paths", {})),
            config_path=str(config_path),
            running=_verified_daemon_running(current_config),
            elapsed_seconds=elapsed,
        )


class SlideshowToggleHandler(Handler[SlideshowToggleCommand, SlideshowToggleResult]):
    """Handler for toggling the background slideshow daemon."""

    def handle(self, command: SlideshowToggleCommand) -> SlideshowToggleResult:
        t0 = time.monotonic()
        config = _load_daemon_config()
        config["running"] = command.running
        try:
            _persist_daemon_config(config)
        except Exception as exc:
            return SlideshowToggleResult(
                running=not command.running,
                message=f"Failed to persist running state: {exc}",
                elapsed_seconds=round(time.monotonic() - t0, 4),
                error=str(exc),
            )

        if command.running:
            return self._start(config, t0)
        return self._stop(config, t0)

    def _start(self, config: dict[str, Any], t0: float) -> SlideshowToggleResult:
        try:
            proc = spawn_slideshow_daemon()
        except Exception as exc:
            self._mark_stopped(config)
            return SlideshowToggleResult(
                running=False,
                message=f"Failed to start slideshow daemon: {exc}",
                elapsed_seconds=round(time.monotonic() - t0, 4),
                error=str(exc),
            )

        pid = int(proc.pid)
        if not _pid_alive(pid):
            self._mark_stopped(config)
            return SlideshowToggleResult(
                running=False,
                message="Slideshow daemon exited immediately",
                elapsed_seconds=round(time.monotonic() - t0, 4),
                error="Slideshow daemon is not running",
            )

        config["running"] = True
        config["pid"] = pid
        try:
            _persist_daemon_config(config)
        except Exception as exc:
            return SlideshowToggleResult(
                running=True,
                pid=pid,
                message="Slideshow daemon started",
                elapsed_seconds=round(time.monotonic() - t0, 4),
                error=f"Failed to store daemon pid: {exc}",
            )
        return SlideshowToggleResult(
            running=True,
            pid=pid,
            message="Slideshow daemon started",
            elapsed_seconds=round(time.monotonic() - t0, 4),
        )

    def _stop(self, config: dict[str, Any], t0: float) -> SlideshowToggleResult:
        # running is already false in the config so the daemon loop can exit.
        pid = _config_pid(config)
        if pid is not None and _pid_alive(pid):
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                alive = False
            except OSError as exc:
                if _pid_alive(pid):
                    return SlideshowToggleResult(
                        running=True,
                        pid=pid,
                        message="Slideshow daemon did not stop",
                        elapsed_seconds=round(time.monotonic() - t0, 4),
                        error=f"Failed to signal slideshow daemon: {exc}",
                    )
                alive = False
            else:
                alive = _still_alive(pid)
            if alive:
                return SlideshowToggleResult(
                    running=True,
                    pid=pid,
                    message="Slideshow daemon did not stop",
                    elapsed_seconds=round(time.monotonic() - t0, 4),
                    error="Slideshow daemon did not stop",
                )
        return SlideshowToggleResult(
            running=False,
            pid=None,
            message="Slideshow daemon stopped",
            elapsed_seconds=round(time.monotonic() - t0, 4),
        )

    @staticmethod
    def _mark_stopped(config: dict[str, Any]) -> None:
        config["running"] = False
        config.pop("pid", None)
        try:
            _persist_daemon_config(config)
        except Exception as exc:
            logger.warning("Could not clear slideshow running flag: %s", exc)

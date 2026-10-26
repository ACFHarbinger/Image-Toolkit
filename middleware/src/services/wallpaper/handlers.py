"""Handlers for the Wallpaper domain service (A-01 / #913).

Executes monitor discovery, per-monitor wallpaper application, and
shared slideshow daemon configuration without UI coupling.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import tempfile
import time
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

            style_map = {
                "fill": "Fill",
                "fit": "Fit",
                "stretch": "Stretch",
                "center": "Center",
                "tile": "Tile",
                "span": "Span",
            }
            canonical_style = style_map.get(command.style.lower(), "Fill")

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
            elapsed_seconds=elapsed,
        )


class SlideshowToggleHandler(Handler[SlideshowToggleCommand, SlideshowToggleResult]):
    """Handler for toggling the background slideshow daemon."""

    def handle(self, command: SlideshowToggleCommand) -> SlideshowToggleResult:
        t0 = time.monotonic()
        config_path = DAEMON_CONFIG_PATH
        config: dict[str, Any] = {}

        if config_path.is_file():
            try:
                with config_path.open("r", encoding="utf-8") as f:
                    config = json.load(f) or {}
            except Exception:
                config = {}

        config["running"] = command.running
        try:
            with tempfile.NamedTemporaryFile(
                "w", dir=IMAGE_TOOLKIT_DIR, delete=False, encoding="utf-8"
            ) as tmp:
                json.dump(config, tmp, indent=2)
                tmp_name = tmp.name
            os.replace(tmp_name, config_path)
        except Exception as exc:
            return SlideshowToggleResult(
                running=not command.running,
                message=f"Failed to persist running state: {exc}",
                elapsed_seconds=round(time.monotonic() - t0, 4),
                error=str(exc),
            )

        msg = "Slideshow daemon started" if command.running else "Slideshow daemon stopped"
        elapsed = round(time.monotonic() - t0, 4)
        return SlideshowToggleResult(
            running=command.running,
            pid=os.getpid() if command.running else None,
            message=msg,
            elapsed_seconds=elapsed,
        )

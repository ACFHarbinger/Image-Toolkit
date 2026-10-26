"""Sidecar handlers for the wallpaper capability (A-01 / #913)."""

from __future__ import annotations

from typing import Any

from middleware.src.services.wallpaper.commands import (
    GetMonitorsCommand,
    SetWallpaperCommand,
    SlideshowConfigCommand,
    SlideshowToggleCommand,
)
from middleware.src.services.wallpaper.service import WallpaperService


def handle_get_monitors(
    service: WallpaperService | None, params: dict[str, Any]
) -> dict[str, Any]:
    """Dispatch wallpaper.get_monitors onto WallpaperService."""
    svc = service or WallpaperService()
    result = svc.get_monitors(GetMonitorsCommand())
    return {
        "monitors": [
            {
                "id": m.id,
                "name": m.name,
                "width": m.width,
                "height": m.height,
                "x": m.x,
                "y": m.y,
                "is_primary": m.is_primary,
            }
            for m in result.monitors
        ],
        "desktop_environment": result.desktop_environment,
    }


def handle_set_wallpaper(
    service: WallpaperService | None, params: dict[str, Any]
) -> dict[str, Any]:
    """Dispatch wallpaper.set onto WallpaperService."""
    svc = service or WallpaperService()
    monitors_tuple = tuple(int(x) for x in params.get("monitors") or ())
    command = SetWallpaperCommand(
        path_map=dict(params.get("path_map") or {}),
        style=str(params.get("style") or "fill"),
        monitors=monitors_tuple,
        background_color=params.get("background_color"),
    )
    result = svc.set_wallpaper(command)
    return {
        "success": result.success,
        "message": result.message,
        "applied_monitors": list(result.applied_monitors),
    }


def handle_slideshow_config(
    service: WallpaperService | None, params: dict[str, Any]
) -> dict[str, Any]:
    """Dispatch wallpaper.slideshow_config onto WallpaperService."""
    svc = service or WallpaperService()
    command = SlideshowConfigCommand(
        update=bool(params.get("update", False)),
        interval_seconds=params.get("interval_seconds"),
        style=params.get("style"),
        monitor_queues=params.get("monitor_queues"),
        current_paths=params.get("current_paths"),
    )
    result = svc.slideshow_config(command)
    return {
        "interval_seconds": result.interval_seconds,
        "style": result.style,
        "monitor_queues": result.monitor_queues,
        "current_paths": result.current_paths,
        "config_path": result.config_path,
        "running": result.running,
    }


def handle_slideshow_toggle(
    service: WallpaperService | None, params: dict[str, Any]
) -> dict[str, Any]:
    """Dispatch wallpaper.slideshow_toggle onto WallpaperService."""
    svc = service or WallpaperService()
    command = SlideshowToggleCommand(
        running=bool(params.get("running", False)),
    )
    result = svc.slideshow_toggle(command)
    return {
        "running": result.running,
        "pid": result.pid,
        "message": result.message,
    }

"""Wallpaper domain service package (A-01 / #913)."""

from __future__ import annotations

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
from middleware.src.services.wallpaper.handlers import (
    GetMonitorsHandler,
    SetWallpaperHandler,
    SlideshowConfigHandler,
    SlideshowToggleHandler,
)
from middleware.src.services.wallpaper.protocols import WallpaperServiceProtocol
from middleware.src.services.wallpaper.service import WallpaperService

__all__ = [
    "GetMonitorsCommand",
    "GetMonitorsHandler",
    "GetMonitorsResult",
    "MonitorInfoItem",
    "SetWallpaperCommand",
    "SetWallpaperHandler",
    "SetWallpaperResult",
    "SlideshowConfigCommand",
    "SlideshowConfigHandler",
    "SlideshowConfigResult",
    "SlideshowToggleCommand",
    "SlideshowToggleHandler",
    "SlideshowToggleResult",
    "WallpaperService",
    "WallpaperServiceProtocol",
]

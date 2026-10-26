"""Protocols for the Wallpaper domain service.

Runtime-checkable protocol defining the boundary for multi-monitor wallpaper
operations and slideshow daemon management (A-01 / #913).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from middleware.src.services.base import ServiceProtocol
from middleware.src.services.wallpaper.commands import (
    GetMonitorsCommand,
    GetMonitorsResult,
    SetWallpaperCommand,
    SetWallpaperResult,
    SlideshowConfigCommand,
    SlideshowConfigResult,
    SlideshowToggleCommand,
    SlideshowToggleResult,
)


@runtime_checkable
class WallpaperServiceProtocol(ServiceProtocol, Protocol):
    """Protocol for wallpaper application and slideshow control."""

    def get_monitors(self, command: GetMonitorsCommand | None = None) -> GetMonitorsResult:
        """Discover connected monitors and desktop environment."""
        ...

    def set_wallpaper(self, command: SetWallpaperCommand) -> SetWallpaperResult:
        """Apply wallpaper to specified monitors with selected scaling style."""
        ...

    def slideshow_config(self, command: SlideshowConfigCommand) -> SlideshowConfigResult:
        """Read or update shared slideshow daemon configuration."""
        ...

    def slideshow_toggle(self, command: SlideshowToggleCommand) -> SlideshowToggleResult:
        """Toggle background slideshow daemon."""
        ...

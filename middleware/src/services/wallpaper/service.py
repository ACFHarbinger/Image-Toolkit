"""Wallpaper domain service implementation (A-01 / #913).

Coordinates monitor discovery, wallpaper application, and background
slideshow configuration conforming to WallpaperServiceProtocol.
"""

from __future__ import annotations

from middleware.src.services.base import Handler
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
from middleware.src.services.wallpaper.handlers import (
    GetMonitorsHandler,
    SetWallpaperHandler,
    SlideshowConfigHandler,
    SlideshowToggleHandler,
)
from middleware.src.services.wallpaper.protocols import WallpaperServiceProtocol


class WallpaperService(WallpaperServiceProtocol):
    """Canonical domain service for wallpaper and slideshow operations."""

    def __init__(
        self,
        get_monitors_handler: Handler[GetMonitorsCommand, GetMonitorsResult] | None = None,
        set_wallpaper_handler: Handler[SetWallpaperCommand, SetWallpaperResult] | None = None,
        slideshow_config_handler: (
            Handler[SlideshowConfigCommand, SlideshowConfigResult] | None
        ) = None,
        slideshow_toggle_handler: (
            Handler[SlideshowToggleCommand, SlideshowToggleResult] | None
        ) = None,
    ) -> None:
        self._get_monitors_handler = get_monitors_handler or GetMonitorsHandler()
        self._set_wallpaper_handler = set_wallpaper_handler or SetWallpaperHandler()
        self._slideshow_config_handler = slideshow_config_handler or SlideshowConfigHandler()
        self._slideshow_toggle_handler = slideshow_toggle_handler or SlideshowToggleHandler()

    def get_monitors(self, command: GetMonitorsCommand | None = None) -> GetMonitorsResult:
        """Discover connected monitors and desktop environment."""
        cmd = command or GetMonitorsCommand()
        return self._get_monitors_handler.handle(cmd)

    def set_wallpaper(self, command: SetWallpaperCommand) -> SetWallpaperResult:
        """Apply wallpaper to specified monitors with selected scaling style."""
        return self._set_wallpaper_handler.handle(command)

    def slideshow_config(self, command: SlideshowConfigCommand) -> SlideshowConfigResult:
        """Read or update shared slideshow daemon configuration."""
        return self._slideshow_config_handler.handle(command)

    def slideshow_toggle(self, command: SlideshowToggleCommand) -> SlideshowToggleResult:
        """Toggle background slideshow daemon."""
        return self._slideshow_toggle_handler.handle(command)

"""Commands and results for the Wallpaper domain service.

Defines immutable frozen dataclasses for multi-monitor discovery,
per-monitor and spanned wallpaper setting, and background slideshow
daemon orchestration (A-01 / #913).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from middleware.src.services.base import Command, Result


@dataclass(frozen=True)
class MonitorInfoItem:
    """Information for a connected physical display."""

    id: str
    name: str
    width: int
    height: int
    x: int
    y: int
    is_primary: bool = False


@dataclass(frozen=True)
class GetMonitorsCommand(Command):
    """Command to discover all active physical monitors."""


@dataclass(frozen=True)
class GetMonitorsResult(Result):
    """Result of monitor discovery."""

    monitors: tuple[MonitorInfoItem, ...] = ()
    desktop_environment: str = "Unknown"
    elapsed_seconds: float = 0.0
    error: str | None = None


@dataclass(frozen=True)
class SetWallpaperCommand(Command):
    """Command to apply desktop wallpaper to one, multiple, or spanned monitors."""

    path_map: dict[str, str] = field(default_factory=dict)
    style: str = "fill"
    monitors: tuple[int, ...] = ()
    background_color: str | None = None


@dataclass(frozen=True)
class SetWallpaperResult(Result):
    """Result of applying wallpaper."""

    success: bool
    message: str
    applied_monitors: tuple[str, ...] = ()
    elapsed_seconds: float = 0.0
    error: str | None = None


@dataclass(frozen=True)
class SlideshowConfigCommand(Command):
    """Command to read or atomically update slideshow daemon configuration."""

    update: bool = False
    interval_seconds: int | None = None
    style: str | None = None
    monitor_queues: dict[str, list[str]] | None = None
    current_paths: dict[str, str] | None = None


@dataclass(frozen=True)
class SlideshowConfigResult(Result):
    """Result of reading or updating slideshow configuration."""

    interval_seconds: int = 300
    style: str = "fill"
    monitor_queues: dict[str, list[str]] = field(default_factory=dict)
    current_paths: dict[str, str] = field(default_factory=dict)
    config_path: str = ""
    elapsed_seconds: float = 0.0
    error: str | None = None


@dataclass(frozen=True)
class SlideshowToggleCommand(Command):
    """Command to toggle the background slideshow daemon state."""

    running: bool = False


@dataclass(frozen=True)
class SlideshowToggleResult(Result):
    """Result of toggling the slideshow daemon."""

    running: bool
    pid: int | None = None
    message: str = ""
    elapsed_seconds: float = 0.0
    error: str | None = None

"""
gui/src/utils/settings.py
==========================
Centralised facade for all application QSettings access (§5.14A).

Replace every inline ``QSettings("ImageToolkit", "ImageToolkit")`` constructor
call with the typed helpers below.  Keys are organised by namespace:

Static keys
-----------
- ``mainwindow/geometry``  — main-window geometry bytes

Dynamic-namespace helpers
-------------------------
- ``session/{class_name}/{key}``  — per-class session state (last_dir,
  recent_dirs, thumbnail_size, sort_key, sort_direction, …)
- ``splitters/{key}`` / ``splitter/{key}`` — splitter state bytes
- ``labels/{path}`` — per-image colour label string

Usage
-----
::

    from gui.src.utils.settings import AppSettings

    # Read
    geom = AppSettings.mainwindow_geometry()
    last_dir = AppSettings.session(self.__class__.__name__, "last_dir", "")
    dirs = AppSettings.session(self.__class__.__name__, "recent_dirs", [])

    # Write
    AppSettings.set_mainwindow_geometry(self.saveGeometry())
    AppSettings.set_session(self.__class__.__name__, "last_dir", path)
"""

from __future__ import annotations

from typing import Any


class AppSettings:
    """Singleton facade for ``QSettings("ImageToolkit", "ImageToolkit")``.

    All methods are classmethods so no instantiation is needed.
    """

    ORG: str = "ImageToolkit"
    APP: str = "ImageToolkit"

    @classmethod
    def _q(cls):
        """Return a QSettings instance for the application."""
        from PySide6.QtCore import QSettings
        return QSettings(cls.ORG, cls.APP)

    # ── Static keys ───────────────────────────────────────────────────────────

    @classmethod
    def mainwindow_geometry(cls) -> bytes | None:
        """Stored main-window geometry (``restoreGeometry`` bytes)."""
        return cls._q().value("mainwindow/geometry")

    @classmethod
    def set_mainwindow_geometry(cls, data: bytes) -> None:
        cls._q().setValue("mainwindow/geometry", data)

    @classmethod
    def recursive_scan(cls) -> bool:
        """Return True if recursive directory scanning is enabled, False otherwise."""
        val = cls._q().value("preferences/recursive_scan")
        if val is not None:
            if isinstance(val, str):
                return val.lower() == "true"
            return bool(val)
        
        from PySide6.QtWidgets import QApplication
        for widget in QApplication.topLevelWidgets():
            if hasattr(widget, "cached_creds") and widget.cached_creds:
                prefs = widget.cached_creds.get("preferences", {})
                if "recursive_scan" in prefs:
                    return bool(prefs["recursive_scan"])
        return True

    @classmethod
    def set_recursive_scan(cls, enabled: bool) -> None:
        cls._q().setValue("preferences/recursive_scan", enabled)

    @classmethod
    def favourite_directories(cls) -> list[str]:
        """Return the list of favourite directories."""
        val = cls._q().value("preferences/favourite_directories")
        if val is None:
            return []
        if isinstance(val, str):
            if not val:
                return []
            return [val]
        return [str(x) for x in val]

    @classmethod
    def set_favourite_directories(cls, dirs: list[str]) -> None:
        """Store the list of favourite directories."""
        cls._q().setValue("preferences/favourite_directories", dirs)

    # ── Session namespace ─────────────────────────────────────────────────────

    @classmethod
    def session(cls, class_name: str, key: str, default: Any = None) -> Any:
        """Read a per-class session value.

        Keys are stored as ``session/{class_name}/{key}``.
        """
        return cls._q().value(f"session/{class_name}/{key}", default)

    @classmethod
    def set_session(cls, class_name: str, key: str, value: Any) -> None:
        """Write a per-class session value."""
        cls._q().setValue(f"session/{class_name}/{key}", value)

    # ── Splitter namespace ────────────────────────────────────────────────────

    @classmethod
    def splitter(cls, key: str) -> bytes | None:
        """Read splitter state bytes stored under ``splitters/{key}``."""
        return cls._q().value(f"splitters/{key}")

    @classmethod
    def set_splitter(cls, key: str, value: bytes) -> None:
        cls._q().setValue(f"splitters/{key}", value)

    @classmethod
    def listings_splitter(cls, key: str) -> bytes | None:
        """Read splitter state bytes stored under ``splitter/{key}`` (listings variant)."""
        return cls._q().value(f"splitter/{key}")

    @classmethod
    def set_listings_splitter(cls, key: str, value: bytes) -> None:
        cls._q().setValue(f"splitter/{key}", value)

    # ── Labels namespace ──────────────────────────────────────────────────────

    @classmethod
    def label(cls, path: str) -> str | None:
        """Return the colour-label key stored for *path*, or ``None``."""
        return cls._q().value(f"labels/{path}") or None

    @classmethod
    def set_label(cls, path: str, color_key: str) -> None:
        cls._q().setValue(f"labels/{path}", color_key)

    # ── Raw access ────────────────────────────────────────────────────────────

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        """Generic read for any key not covered by a typed accessor."""
        return cls._q().value(key, default)

    @classmethod
    def set(cls, key: str, value: Any) -> None:
        """Generic write for any key not covered by a typed accessor."""
        cls._q().setValue(key, value)

    @classmethod
    def remove(cls, key: str) -> None:
        """Delete a key."""
        cls._q().remove(key)

    @classmethod
    def all_keys(cls) -> list[str]:
        """Return all stored keys."""
        return cls._q().allKeys()


__all__ = ["AppSettings"]

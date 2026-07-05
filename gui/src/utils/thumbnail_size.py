from __future__ import annotations

from gui.src.windows.settings.app_settings import AppSettings


def save_thumbnail_size(class_name: str, size: int) -> None:
    """Persist *size* under the per-class QSettings key."""
    AppSettings.set_session(class_name, "thumbnail_size", size)


def load_thumbnail_size(class_name: str, default: int = 180) -> int:
    """Return the persisted thumbnail size for *class_name*, clamped to [64, 512]."""
    val = AppSettings.session(class_name, "thumbnail_size", default)
    try:
        return max(64, min(512, int(val)))
    except (TypeError, ValueError):
        return default


__all__ = ["save_thumbnail_size", "load_thumbnail_size"]

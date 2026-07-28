"""OS-specific wallpaper setting logic, split by platform (§5.17).

Public API unchanged from the pre-split single-file module:
``WallpaperManager`` plus the qdbus/D-Bus helpers used directly by
slideshow daemons.
"""

from ._dbus import evaluate_kde_script_dbus_python, evaluate_kde_script_with_fallback, find_qdbus_binary
from .manager import WallpaperManager

__all__ = [
    "WallpaperManager",
    "find_qdbus_binary",
    "evaluate_kde_script_dbus_python",
    "evaluate_kde_script_with_fallback",
]

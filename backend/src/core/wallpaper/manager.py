"""``WallpaperManager`` — OS-dispatching facade composed from per-OS mixins.

Uses the 'base' native extension for Linux commands.
"""

import logging
import os
import platform
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Union

import base  # Native extension
from screeninfo import Monitor

from backend.src.constants import WALLPAPER_STYLES

from ._dbus import evaluate_kde_script_with_fallback
from ._gnome import _GNOMEWallpaperMixin
from ._kde import _KDEWallpaperMixin
from ._windows import _WindowsWallpaperMixin


class WallpaperManager(_WindowsWallpaperMixin, _KDEWallpaperMixin, _GNOMEWallpaperMixin):
    """
    A static class for handling OS-specific wallpaper setting logic.
    Uses 'base' rust extension for Linux commands.
    """

    @staticmethod
    def apply_wallpaper(  # noqa: C901
        path_map: Dict[str, str],
        monitors: Union[List[Monitor], int],
        style_name: str,
        qdbus: Optional[str] = None,
    ):
        system = platform.system()
        if style_name == "SolidColor":
            color_hex = path_map.get(str(0), "#000000")
            if system == "Windows":
                WallpaperManager._set_wallpaper_solid_color_windows(color_hex)
            elif system == "Linux":
                script = f"""
                var d = desktops();
                for (var i = 0; i < d.length; i++) {{
                    d[i].currentConfigGroup = Array("Color");
                    d[i].writeConfig("Color", "{color_hex}");
                    d[i].currentConfigGroup = Array("Wallpaper", "org.kde.color", "General");
                    d[i].writeConfig("Color", "{color_hex}");
                    d[i].writeConfig("FillMode", 1);
                }}
                d[0].reloadConfig();
                """
                try:
                    evaluate_kde_script_with_fallback(qdbus, script)
                except Exception:
                    WallpaperManager._set_wallpaper_solid_color_gnome(color_hex)
            return

        if system == "Windows":
            if WallpaperManager.COM_AVAILABLE and isinstance(monitors, list):
                WallpaperManager._set_wallpaper_windows_multi(
                    path_map, monitors, style_name
                )
            else:
                path = path_map.get("0") or next(iter(path_map.values()))
                WallpaperManager._set_wallpaper_windows_single(path, style_name)

        elif system == "Linux":
            kde_desktops = WallpaperManager.get_kde_desktops(qdbus)
            if kde_desktops and isinstance(monitors, list):
                # Use topological mapping
                mapping = WallpaperManager._map_monitors_to_kde(monitors, kde_desktops)

                mapped_path_map = {}
                for monitor_id_str, path in path_map.items():
                    try:
                        m_idx = int(monitor_id_str)
                        if m_idx in mapping:
                            # Use the KDE desktop index from the mapping
                            kde_desktop_idx = mapping[m_idx]["index"]
                            mapped_path_map[str(kde_desktop_idx)] = path
                        else:
                            # Fallback to direct index
                            mapped_path_map[monitor_id_str] = path
                    except Exception:
                        mapped_path_map[monitor_id_str] = path

                try:
                    WallpaperManager._set_wallpaper_kde(
                        mapped_path_map, style_name, qdbus
                    )
                except Exception as e:
                    logging.warning(
                        f"KDE DBus wallpaper setting failed, trying fallback: {e}"
                    )
                    if not WallpaperManager._set_wallpaper_kde_plasma_apply(
                        path_map, style_name
                    ):
                        raise
            else:  # GNOME or Fallback
                desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
                session = os.environ.get("DESKTOP_SESSION", "").lower()
                is_kde = (
                    "kde" in desktop
                    or "plasma" in desktop
                    or "kde" in session
                    or "plasma" in session
                )

                if (
                    is_kde or shutil.which("plasma-apply-wallpaperimage")
                ) and WallpaperManager._set_wallpaper_kde_plasma_apply(
                    path_map, style_name
                ):
                    return

                if style_name == "Spanned" and isinstance(monitors, list):
                    WallpaperManager._set_wallpaper_gnome_spanned(
                        path_map, monitors, style_name
                    )
                else:
                    path = path_map.get("0") or next(iter(path_map.values()))
                    mode = WALLPAPER_STYLES["GNOME"].get(style_name, "zoom")
                    base.set_wallpaper_gnome(f"file://{Path(path).resolve()}", mode)


__all__ = ["WallpaperManager"]

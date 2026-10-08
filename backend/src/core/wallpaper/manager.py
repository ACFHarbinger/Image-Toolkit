"""``WallpaperManager`` — OS-dispatching facade composed from per-OS mixins.

Uses the 'base' native extension for Linux commands.
"""

import logging
import os
import platform
import shutil
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Union

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
    def _plasma_apply_wallpaperimage_safe(
        path_map: Dict[str, str], monitors: Union[List[Monitor], int]
    ) -> bool:
        """Whether falling back to the ``plasma-apply-wallpaperimage`` CLI
        cannot clobber a monitor that ``path_map`` deliberately left out.

        That tool has no per-output targeting -- it always applies ONE
        image across every screen in the Plasma session (confirmed: its
        ``--help`` offers no ``--output``/monitor option). Using it is only
        safe when that is actually the intent: a single monitor, or every
        currently known monitor already mapped to the very same path.
        Otherwise it would silently overwrite monitors ``path_map`` left
        out -- e.g. the per-monitor slideshow daemon advancing one display
        while another's queue is empty and its wallpaper must stay
        untouched.
        """
        num_monitors = len(monitors) if isinstance(monitors, list) else 1
        if num_monitors <= 1:
            return True
        if len(path_map) < num_monitors:
            return False
        return len(set(path_map.values())) <= 1

    @staticmethod
    def _first_valid_path(path_map: Mapping[str, Optional[str]]) -> Optional[str]:
        """First non-empty path in ``path_map``, preferring monitor ``"0"``.

        ``path_map`` can legitimately hold ``None`` for a monitor that was
        deliberately left untouched (e.g. a cleared slideshow queue) --
        ``path_map.get("0") or next(iter(path_map.values()))`` picks
        whichever value dict-iteration happens to put first, which is "0"'s
        own ``None`` just as often as a real path, crashing single-path
        callers with ``Path(None)``. Skip falsy entries instead.
        """
        path = path_map.get("0")
        if path:
            return path
        return next((p for p in path_map.values() if p), None)

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
                path = WallpaperManager._first_valid_path(path_map)
                if path is None:
                    raise ValueError("No valid wallpaper path found in path_map.")
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
                    # plasma-apply-wallpaperimage only understands static
                    # images — feeding it a video file for a failed
                    # SmartVideoWallpaper attempt doesn't produce a video
                    # background (it may even report success on a file it
                    # can't actually render), which just trades one
                    # misleading "Success: True" for another. Only fall
                    # back for non-video styles, where the tool is actually
                    # applicable.
                    if style_name.startswith("SmartVideoWallpaper"):
                        logging.error(
                            f"KDE video wallpaper setting failed (no static-image fallback applies): {e}"
                        )
                        raise
                    if not WallpaperManager._plasma_apply_wallpaperimage_safe(
                        path_map, monitors
                    ):
                        logging.error(
                            "KDE DBus wallpaper setting failed and the "
                            "plasma-apply-wallpaperimage fallback has no "
                            "per-monitor targeting -- skipping it to avoid "
                            f"overwriting other monitors' wallpapers: {e}"
                        )
                        raise
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
                    (is_kde or shutil.which("plasma-apply-wallpaperimage"))
                    and WallpaperManager._plasma_apply_wallpaperimage_safe(
                        path_map, monitors
                    )
                    and WallpaperManager._set_wallpaper_kde_plasma_apply(
                        path_map, style_name
                    )
                ):
                    return

                if style_name == "Spanned" and isinstance(monitors, list):
                    WallpaperManager._set_wallpaper_gnome_spanned(
                        path_map, monitors, style_name
                    )
                else:
                    path = WallpaperManager._first_valid_path(path_map)
                    if path is None:
                        raise ValueError("No valid wallpaper path found in path_map.")
                    mode = WALLPAPER_STYLES["GNOME"].get(style_name, "zoom")
                    base.set_wallpaper_gnome(f"file://{Path(path).resolve()}", mode)


__all__ = ["WallpaperManager"]

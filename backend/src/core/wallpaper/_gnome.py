"""GNOME wallpaper setting (gsettings + spanned-canvas composition)."""

import os
import subprocess
from pathlib import Path
from typing import Dict, List

import base  # Native extension
from PIL import Image
from screeninfo import Monitor


class _GNOMEWallpaperMixin:
    """GNOME wallpaper setting methods for ``WallpaperManager``."""

    @staticmethod
    def _set_wallpaper_solid_color_gnome(color_hex: str):
        try:
            subprocess.run(
                [
                    "gsettings",
                    "set",
                    "org.gnome.desktop.background",
                    "picture-options",
                    "none",
                ],
                check=True,
            )
            subprocess.run(
                [
                    "gsettings",
                    "set",
                    "org.gnome.desktop.background",
                    "primary-color",
                    color_hex,
                ],
                check=True,
            )
            subprocess.run(
                [
                    "gsettings",
                    "set",
                    "org.gnome.desktop.background",
                    "color-shading-type",
                    "solid",
                ],
                check=True,
            )
        except Exception as e:
            raise RuntimeError(f"Error setting GNOME solid color: {e}") from e

    @staticmethod
    def _set_wallpaper_gnome_spanned(
        path_map: Dict[str, str], monitors: List[Monitor], style_name: str
    ):
        if not monitors:
            return
        min_x = min(m.x for m in monitors)
        min_y = min(m.y for m in monitors)
        max_x = max(m.x + m.width for m in monitors)
        max_y = max(m.y + m.height for m in monitors)
        canvas = Image.new("RGB", (max_x - min_x, max_y - min_y), (0, 0, 0))

        for i, monitor in enumerate(monitors):
            path = path_map.get(str(i))
            if path and os.path.exists(path):
                img = Image.open(path).resize(
                    (monitor.width, monitor.height), Image.Resampling.LANCZOS
                )
                canvas.paste(img, (monitor.x - min_x, monitor.y - min_y))

        temp_path = os.path.join(Path.home(), ".cache", "image_toolkit_spanned.jpg")
        canvas.save(temp_path, "JPEG", quality=95)

        base.set_wallpaper_gnome(f"file://{temp_path}", "spanned")


__all__ = ["_GNOMEWallpaperMixin"]

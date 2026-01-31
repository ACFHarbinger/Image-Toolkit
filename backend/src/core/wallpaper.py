import os
import ctypes
import platform
import subprocess
import logging
import base  # Native extension
import re

from PIL import Image
from pathlib import Path
from screeninfo import Monitor
from typing import Dict, List, Optional, Union
from backend.src.utils.definitions import WALLPAPER_STYLES, SUPPORTED_VIDEO_FORMATS

# Global Definitions for COM components
IDESKTOPWALLPAPER_IID = "{B92B56A9-8B55-4E14-9A89-0199BBB6F93B}"
DESKTOPWALLPAPER_CLSID = "{C2CF3110-460E-4fc1-B9D0-8A1C0C9CC4BD}"
COM_AVAILABLE = False

# Conditionally import comtypes and winreg only on Windows
if platform.system() == "Windows":
    import winreg

    try:
        import comtypes
        from comtypes import IUnknown, GUID, COMMETHOD, HRESULT, POINTER
        from ctypes.wintypes import LPCWSTR, UINT, LPWSTR
        from ctypes import pointer

        class IDesktopWallpaper(IUnknown):
            _iid_ = GUID(IDESKTOPWALLPAPER_IID)
            _methods_ = [
                COMMETHOD(
                    [],
                    HRESULT,
                    "SetWallpaper",
                    (["in"], LPCWSTR, "monitorID"),
                    (["in"], LPCWSTR, "wallpaper"),
                ),
                COMMETHOD(
                    [],
                    HRESULT,
                    "GetWallpaper",
                    (["in"], LPCWSTR, "monitorID"),
                    (["out"], POINTER(LPWSTR), "wallpaper"),
                ),
                COMMETHOD(
                    [],
                    HRESULT,
                    "GetMonitorDevicePathAt",
                    (["in"], UINT, "monitorIndex"),
                    (["out"], POINTER(LPWSTR), "monitorID"),
                ),
                COMMETHOD(
                    [],
                    HRESULT,
                    "GetMonitorDevicePathCount",
                    (["out"], POINTER(UINT), "count"),
                ),
            ]

            def SetWallpaper(self, monitorId: str, wallpaper: str):
                self.__com_SetWallpaper(LPCWSTR(monitorId), LPCWSTR(wallpaper))

            def GetMonitorDevicePathAt(self, monitorIndex: int) -> str:
                monitorId = LPWSTR()
                self.__com_GetMonitorDevicePathAt(
                    UINT(monitorIndex), pointer(monitorId)
                )
                return monitorId.value

            def GetMonitorDevicePathCount(self) -> int:
                count = UINT()
                self.__com_GetMonitorDevicePathCount(pointer(count))
                return count.value

        COM_AVAILABLE = True
    except ImportError:
        COM_AVAILABLE = False


class WallpaperManager:
    """
    A static class for handling OS-specific wallpaper setting logic.
    Uses 'base' rust extension for Linux commands.
    """

    @staticmethod
    def _set_wallpaper_solid_color_windows(color_hex: str):
        try:
            color_hex = color_hex.lstrip("#")
            r, g, b = tuple(int(color_hex[i : i + 2], 16) for i in (0, 2, 4))
            key_desktop = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                "Control Panel\\Desktop",
                0,
                winreg.KEY_SET_VALUE,
            )
            winreg.SetValueEx(key_desktop, "WallpaperStyle", 0, winreg.REG_SZ, "0")
            winreg.SetValueEx(key_desktop, "TileWallpaper", 0, winreg.REG_SZ, "0")
            winreg.CloseKey(key_desktop)
            key_colors = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                "Control Panel\\Colors",
                0,
                winreg.KEY_SET_VALUE,
            )
            winreg.SetValueEx(
                key_colors, "Background", 0, winreg.REG_SZ, f"{r} {g} {b}"
            )
            winreg.CloseKey(key_colors)
            ctypes.windll.user32.SystemParametersInfoW(20, 0, None, 3)
        except Exception as e:
            raise RuntimeError(f"Error setting Windows solid color wallpaper: {e}")

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
            raise RuntimeError(f"Error setting GNOME solid color: {e}")

    @staticmethod
    def get_best_video_plugin() -> str:
        REBORN_PLUGIN = "luisbocanegra.smart.video.wallpaper.reborn"
        ZREN_PLUGIN = "com.github.zren.smartvideowallpaper"
        SMARTER_PLUGIN = "smartervideowallpaper"
        search_paths = [
            Path.home() / ".local/share/plasma/wallpapers",
            Path("/usr/share/plasma/wallpapers"),
        ]
        for base_path in search_paths:
            if (base_path / REBORN_PLUGIN).exists():
                return REBORN_PLUGIN
        for base_path in search_paths:
            if (base_path / SMARTER_PLUGIN).exists():
                return SMARTER_PLUGIN
        for base_path in search_paths:
            if (base_path / ZREN_PLUGIN).exists():
                return ZREN_PLUGIN
        return REBORN_PLUGIN

    @staticmethod
    def get_kde_desktops(qdbus: str) -> List[Dict[str, int]]:
        script = """
        var ds = desktops();
        var output = [];
        for (var i = 0; i < ds.length; i++) {
            var d = ds[i];
            var s = d.screen;
            if (s < 0) continue; 
            try {
                var rect = screenGeometry(s);
                output.push(i + ":" + s + ":" + rect.x + ":" + rect.y);
            } catch(e) {}
        }
        print(output.join("\\n"));
        """
        try:
            result = base.evaluate_kde_script(qdbus, script)
            desktops = []
            for line in result.strip().split("\n"):
                if not line.strip():
                    continue
                parts = line.split(":")
                if len(parts) >= 4:
                    desktops.append(
                        {
                            "index": int(parts[0]),
                            "screen": int(parts[1]),
                            "x": int(parts[2]),
                            "y": int(parts[3]),
                        }
                    )
            return desktops
        except Exception as e:
            logging.error(f"Failed to get KDE desktops: {e}")
            return desktops

    @staticmethod
    def _map_monitors_to_kde(
        monitors: List[Monitor], kde_desktops: List[Dict]
    ) -> Dict[int, Dict]:
        """
        Maps the index of 'monitors' list to the corresponding KDE desktop object.
        Uses topological sorting (Top/Left -> Bottom/Right) to handle HiDPI scaling mismatches.
        """
        if not monitors or not kde_desktops:
            return {}

        # Sort both lists by (Y, X)
        # Note: We use a small tolerance for Y in case of slight misalignments, but usually integer sort is fine
        sorted_monitors = sorted(
            list(enumerate(monitors)), key=lambda p: (p[1].y, p[1].x)
        )
        sorted_kde = sorted(kde_desktops, key=lambda d: (d["y"], d["x"]))

        mapping = {}
        # Zip them together based on visual order
        for (m_idx, _), k_desktop in zip(sorted_monitors, sorted_kde):
            mapping[m_idx] = k_desktop

        return mapping

    @staticmethod
    def _set_wallpaper_kde(path_map: Dict[str, str], style_name: str, qdbus: str):
        video_fill_mode = 2
        video_mode_active = False

        if style_name.startswith("SmartVideoWallpaper") and "::" in style_name:
            video_mode_active = True
            try:
                parts = style_name.split("::")
                if len(parts) > 1:
                    v_style_str = parts[1]
                    if v_style_str == "Keep Proportions":
                        video_fill_mode = 1
                    elif v_style_str == "Scaled and Cropped":
                        video_fill_mode = 2
                    elif v_style_str == "Stretch":
                        video_fill_mode = 0
            except Exception:
                pass
            style_name = "Fill"

        fill_mode = WALLPAPER_STYLES["KDE"].get(
            style_name, WALLPAPER_STYLES["KDE"]["Scaled, Keep Proportions"]
        )
        target_plugin = WallpaperManager.get_best_video_plugin()

        script_parts = []
        for monitor_id, path in path_map.items():
            if not path:
                continue
            try:
                i = int(monitor_id)
            except ValueError:
                continue

            # KDE Plasma 6 (and some 5 versions) prefers raw paths for org.kde.image
            file_uri = str(Path(path).resolve())
            # if not file_uri.startswith("file://"):
            #    file_uri = "file://" + file_uri

            ext = Path(path).suffix.lower()

            if ext in SUPPORTED_VIDEO_FORMATS and video_mode_active:
                is_smarter = target_plugin == "smartervideowallpaper"
                video_key = (
                    "VideoWallpaperBackgroundVideo" if is_smarter else "VideoUrls"
                )

                script_parts.append(
                    f"""
                {{
                    var d = desktops()[{i}];
                    if (d && d.screen >= 0) {{
                        if (d.wallpaperPlugin !== "{target_plugin}") d.wallpaperPlugin = "{target_plugin}";
                        d.currentConfigGroup = Array("Wallpaper", d.wallpaperPlugin, "General");
                        d.writeConfig("{video_key}", "{file_uri}");
                        d.writeConfig("FillMode", {video_fill_mode});
                        {"d.writeConfig('overridePause', true);" if is_smarter else ""}
                        d.currentConfigGroup = Array("Wallpaper", "org.kde.image", "General");
                        d.writeConfig("FillMode", 2);
                        d.writeConfig("Color", "#00000000");
                        d.reloadConfig();
                    }}
                }}
                """
                )
            else:
                script_parts.append(
                    f'{{ var d = desktops()[{i}]; if (d && d.screen >= 0) {{ d.wallpaperPlugin = "org.kde.image"; d.currentConfigGroup = Array("Wallpaper", "org.kde.image", "General"); d.writeConfig("Image", "{file_uri}"); d.writeConfig("FillMode", {fill_mode}); d.reloadConfig(); }} }}'
                )

        if not script_parts:
            return
        full_script = "".join(script_parts)
        try:
            base.evaluate_kde_script(qdbus, full_script)
        except Exception as e:
            raise RuntimeError(f"KDE method failed (Rust): {e}")

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

    @staticmethod
    def _set_wallpaper_windows_single(image_path: str, style_name: str):
        if Path(image_path).suffix.lower() in SUPPORTED_VIDEO_FORMATS:
            raise ValueError("Video wallpapers not supported on Windows natively.")
        style_values = WALLPAPER_STYLES["Windows"].get(
            style_name, WALLPAPER_STYLES["Windows"]["Fill"]
        )
        wallpaper_style_reg, tile_wallpaper_reg = style_values
        save_path = str(Path(image_path).resolve())

        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                "Control Panel\\Desktop",
                0,
                winreg.KEY_SET_VALUE,
            )
            winreg.SetValueEx(
                key, "WallpaperStyle", 0, winreg.REG_SZ, wallpaper_style_reg
            )
            winreg.SetValueEx(
                key, "TileWallpaper", 0, winreg.REG_SZ, tile_wallpaper_reg
            )
            winreg.CloseKey(key)
            ctypes.windll.user32.SystemParametersInfoW(20, 0, save_path, 3)
        except Exception as e:
            raise RuntimeError(f"Error setting Windows single wallpaper: {e}")

    @staticmethod
    def _set_wallpaper_windows_multi(
        path_map: Dict[str, str], monitors: List[Monitor], style_name: str
    ):
        if not COM_AVAILABLE:
            raise ImportError("Multi-monitor requires 'comtypes'.")
        style_values = WALLPAPER_STYLES["Windows"].get(
            "Fill", WALLPAPER_STYLES["Windows"]["Fill"]
        )
        wallpaper_style_reg, tile_wallpaper_reg = style_values
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                "Control Panel\\Desktop",
                0,
                winreg.KEY_SET_VALUE,
            )
            winreg.SetValueEx(
                key, "WallpaperStyle", 0, winreg.REG_SZ, wallpaper_style_reg
            )
            winreg.SetValueEx(
                key, "TileWallpaper", 0, winreg.REG_SZ, tile_wallpaper_reg
            )
            winreg.CloseKey(key)
            desktop_wallpaper = comtypes.CoCreateInstance(
                GUID(DESKTOPWALLPAPER_CLSID), interface=IDesktopWallpaper
            )
            monitor_count = desktop_wallpaper.GetMonitorDevicePathCount()
            for i in range(monitor_count):
                monitor_id_path = desktop_wallpaper.GetMonitorDevicePathAt(i)
                path = path_map.get(str(i))
                if path and Path(path).exists():
                    desktop_wallpaper.SetWallpaper(
                        monitor_id_path, str(Path(path).resolve())
                    )
        except Exception as e:
            raise RuntimeError(f"Windows multi-monitor failed: {e}")

    @staticmethod
    def apply_wallpaper(
        path_map: Dict[str, str],
        monitors: Union[List[Monitor], int],
        style_name: str,
        qdbus: str,
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
                    base.evaluate_kde_script(qdbus, script)
                except:
                    WallpaperManager._set_wallpaper_solid_color_gnome(color_hex)
            return

        if system == "Windows":
            if COM_AVAILABLE and isinstance(monitors, list):
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

                WallpaperManager._set_wallpaper_kde(mapped_path_map, style_name, qdbus)
            else:  # GNOME or Fallback
                if style_name == "Spanned" and isinstance(monitors, list):
                    WallpaperManager._set_wallpaper_gnome_spanned(
                        path_map, monitors, style_name
                    )
                else:
                    path = path_map.get("0") or next(iter(path_map.values()))
                    mode = WALLPAPER_STYLES["GNOME"].get(style_name, "zoom")
                    base.set_wallpaper_gnome(f"file://{Path(path).resolve()}", mode)

    @staticmethod
    def get_current_system_wallpaper_path_kde(
        monitors: List[Monitor], qdbus: str
    ) -> Dict[str, Optional[str]]:
        path_map = {}
        path_map = {}

        # We need the full desktop objects to map back to monitors
        kde_desktops = WallpaperManager.get_kde_desktops(qdbus)
        if not kde_desktops:
            return {}

        # Get mapping: MonitorIndex -> KDEDesktop
        # We need the reverse: KDEDesktopIndex -> MonitorIndex
        mapping = WallpaperManager._map_monitors_to_kde(monitors, kde_desktops)
        kde_idx_to_monitor_idx = {v["index"]: k for k, v in mapping.items()}

        script = "var out = [];\n"
        # We iterate through ALL detected KDE desktops to find their paths
        # Then we assign them to the correct monitor ID based on our mapping
        for d in kde_desktops:
            i = d["index"]
            script += f"""
            (function() {{
                try {{
                    var d = desktops()[{i}];
                    var plugin = d.wallpaperPlugin;
                    d.currentConfigGroup = Array("Wallpaper", plugin, "General");
                    var path = d.readConfig("Image") || d.readConfig("VideoUrls") || d.readConfig("Video") || "NONE";
                    if (path.indexOf(",") !== -1) path = path.split(",")[0];
                    out.push("DESKTOP_{i}:" + path);
                }} catch (e) {{ out.push("DESKTOP_{i}:NONE"); }}
            }})();
            """
        script += '\nprint(out.join("\\n===SEP===\\n"));'

        try:
            result = base.evaluate_kde_script(qdbus, script)
            for line in result.split("===SEP==="):
                line = line.strip()
                m = re.match(r"DESKTOP_(\d+):(.+)", line)
                if m:
                    kde_idx_str, path = m.groups()
                    kde_idx = int(kde_idx_str)

                    if path != "NONE":
                        # Fix file URI formatting
                        if path.startswith("file:/") and not path.startswith("file://"):
                            path = "file://" + path[5:]
                        if path.startswith("file://"):
                            path = path[7:]

                        # Resolve path
                        final_path = path
                        try:
                            final_path = str(Path(path).resolve())
                        except:
                            pass

                        # Map back to monitor ID
                        if kde_idx in kde_idx_to_monitor_idx:
                            monitor_mid = str(kde_idx_to_monitor_idx[kde_idx])
                            path_map[monitor_mid] = final_path

        except Exception as e:
            print(f"[WallpaperManager] Error in get_current: {e}")
        return path_map

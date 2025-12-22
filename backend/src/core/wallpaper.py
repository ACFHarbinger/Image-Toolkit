import os
import sys
import ctypes
import platform
import subprocess
import logging

from PIL import Image
from pathlib import Path
from screeninfo import Monitor
from typing import Dict, List, Optional, Union
from ..utils.definitions import WALLPAPER_STYLES, SUPPORTED_VIDEO_FORMATS

# Global Definitions for COM components
IDesktopWallpaperInstance = None
COM_AVAILABLE = False

# Conditionally import comtypes and winreg only on Windows
if platform.system() == "Windows":
    import winreg

    try:
        import comtypes
        from comtypes import IUnknown, GUID, COMMETHOD, HRESULT, POINTER
        from ctypes.wintypes import LPCWSTR, UINT, LPWSTR
        from ctypes import pointer

        # Define the GUIDs for the COM interface
        IDESKTOPWALLPAPER_IID = GUID("{B92B56A9-8B55-4E14-9A89-0199BBB6F93B}")
        DESKTOPWALLPAPER_CLSID = GUID("{C2CF3110-460E-4fc1-B9D0-8A1C0C9CC4BD}")

        # The core IDesktopWallpaper COM Interface Definition
        class IDesktopWallpaper(IUnknown):
            _iid_ = IDESKTOPWALLPAPER_IID
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

            # Helper methods (required to interact with the COM object)
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
        # Fallback if comtypes is not installed
        COM_AVAILABLE = False
        print(
            "Warning: 'comtypes' library not found. Multi-monitor support is disabled."
        )


class WallpaperManager:
    """
    A static class for handling OS-specific wallpaper setting logic.
    """

    @staticmethod
    def _set_wallpaper_solid_color_windows(color_hex: str):
        """
        Sets a solid color background for Windows.
        """
        try:
            # 1. Convert hex to RGB (e.g., #RRGGBB)
            color_hex = color_hex.lstrip("#")
            r, g, b = tuple(int(color_hex[i : i + 2], 16) for i in (0, 2, 4))

            # 2. Set necessary registry values for solid color mode
            key_desktop = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                "Control Panel\\Desktop",
                0,
                winreg.KEY_SET_VALUE,
            )

            winreg.SetValueEx(key_desktop, "WallpaperStyle", 0, winreg.REG_SZ, "0")
            winreg.SetValueEx(key_desktop, "TileWallpaper", 0, winreg.REG_SZ, "0")
            winreg.CloseKey(key_desktop)

            # 3. Set the Solid Color value (RGB as a string "R G B")
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

            # 4. Trigger the wallpaper update
            SPI_SETDESKWALLPAPER = 20
            SPIF_UPDATEINIFILE = 0x01
            SPIF_SENDWININICHANGE = 0x02

            ctypes.windll.user32.SystemParametersInfoW(
                SPI_SETDESKWALLPAPER,
                0,
                None,
                SPIF_UPDATEINIFILE | SPIF_SENDWININICHANGE,
            )

        except Exception as e:
            raise RuntimeError(f"Error setting Windows solid color wallpaper: {e}")

    @staticmethod
    def _set_wallpaper_solid_color_gnome(color_hex: str):
        """
        Sets a solid color background for GNOME using gsettings.
        """
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
                capture_output=True,
                text=True,
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
                capture_output=True,
                text=True,
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
                capture_output=True,
                text=True,
            )
        except Exception as e:
            raise RuntimeError(f"Error setting GNOME solid color: {e}")

    @staticmethod
    def _set_wallpaper_windows_multi(
        path_map: Dict[str, str], monitors: List[Monitor], style_name: str
    ):
        """
        Sets per-monitor wallpaper for Windows using the IDesktopWallpaper COM interface.
        """
        if not COM_AVAILABLE:
            raise ImportError(
                "Multi-monitor setting requires 'comtypes' and a functional COM interface."
            )

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
                DESKTOPWALLPAPER_CLSID, interface=IDesktopWallpaper
            )

            monitor_count = desktop_wallpaper.GetMonitorDevicePathCount()

            if len(monitors) != monitor_count:
                print(
                    f"Warning: screeninfo found {len(monitors)} monitors, COM found {monitor_count}."
                )

            for i in range(monitor_count):
                monitor_id_path = desktop_wallpaper.GetMonitorDevicePathAt(i)
                path = path_map.get(str(i))

                if path and Path(path).exists():
                    resolved_path = str(Path(path).resolve())
                    if Path(resolved_path).suffix.lower() in SUPPORTED_VIDEO_FORMATS:
                        print(
                            f"Skipping monitor {i}: Video wallpapers not supported on Windows natively."
                        )
                        continue

                    desktop_wallpaper.SetWallpaper(monitor_id_path, resolved_path)
                    print(
                        f"Set wallpaper for Monitor Index {i} ({monitor_id_path}) to {resolved_path}"
                    )
                elif str(i) in path_map:
                    print(f"Skipping monitor {i}: Image path not found or invalid.")

        except Exception as e:
            raise RuntimeError(
                f"Error setting multi-monitor Windows wallpaper via COM: {e}"
            )

    @staticmethod
    def _set_wallpaper_windows_single(image_path: str, style_name: str):
        """
        Original single-monitor method.
        """
        if Path(image_path).suffix.lower() in SUPPORTED_VIDEO_FORMATS:
            raise ValueError(
                "Video wallpapers are not supported on Windows via the standard API."
            )

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

            SPI_SETDESKWALLPAPER = 20
            SPIF_UPDATEINIFILE = 0x01
            SPIF_SENDWININICHANGE = 0x02
            ctypes.windll.user32.SystemParametersInfoW(
                SPI_SETDESKWALLPAPER,
                0,
                save_path,
                SPIF_UPDATEINIFILE | SPIF_SENDWININICHANGE,
            )
        except Exception as e:
            raise RuntimeError(f"Error setting Windows single wallpaper: {e}")

    @staticmethod
    def _set_wallpaper_kde(
        path_map: Dict[str, str], num_monitors: int, style_name: str, qdbus: str, geometries: Optional[Dict[str, Dict[str, int]]] = None
    ):
        """
        Sets per-monitor wallpaper for KDE Plasma using qdbus.
        If geometries are provided (from daemon config), it uses them to match desktops.
        Otherwise it falls back to index-based mapping.
        """

        # --- FIX: Correct Mapping for Qt6 VideoOutput.FillMode ---
        # 0 = Stretch
        # 1 = PreserveAspectFit (Keep Proportions)
        # 2 = PreserveAspectCrop (Scaled and Cropped) -- DEFAULT
        video_fill_mode = 2
        video_mode_active = False

        if style_name.startswith("SmartVideoWallpaperReborn::"):
            video_mode_active = True
            try:
                parts = style_name.split("::")
                if len(parts) > 1:
                    v_style_str = parts[1]
                    if v_style_str == "Keep Proportions":
                        video_fill_mode = 1  # Fit
                    elif v_style_str == "Scaled and Cropped":
                        video_fill_mode = 2  # Crop
                    elif v_style_str == "Stretch":
                        video_fill_mode = 0  # Stretch
            except Exception as e:
                print(f"Error parsing video style: {e}")

            style_name = "Fill"  # Fallback for image layers

        # Get KDE FillMode for standard images
        fill_mode = WALLPAPER_STYLES["KDE"].get(
            style_name, WALLPAPER_STYLES["KDE"]["Scaled, Keep Proportions"]
        )

        REBORN_PLUGIN = "luisbocanegra.smart.video.wallpaper.reborn"
        ZREN_PLUGIN = "com.github.zren.smartvideowallpaper"

        script_parts = []

        if geometries:
            # GEOMETRY-BASED MAPPING (Robust)
            import json
            js_geoms = json.dumps(geometries)
            js_paths = json.dumps(path_map)
            
            plugin_logic = f'var targetVideo = "{REBORN_PLUGIN}"; var altVideo = "{ZREN_PLUGIN}";'

            # Improved JS: Added checks for d.screen and error handling
            script = f"""
            var ds = desktops();
            var geoms = {js_geoms};
            var paths = {js_paths};
            {plugin_logic}

            for (var i = 0; i < ds.length; i++) {{
                var d = ds[i];
                if (d.screen < 0) continue; // Skip desktops not associated with a screen
                
                var g = screenGeometry(d.screen);
                if (!g) continue;

                var matchId = null;
                for (var mid in geoms) {{
                    var info = geoms[mid];
                    // Exact match on geometry coordinates
                    if (info.x === g.x && info.y === g.y) {{
                        matchId = mid;
                        break;
                    }}
                }}

                if (matchId && paths[matchId]) {{
                    var imgPath = paths[matchId];
                    var isVideo = imgPath.toLowerCase().endsWith(".mp4") || imgPath.toLowerCase().endsWith(".mkv") || imgPath.toLowerCase().endsWith(".webm") || imgPath.toLowerCase().endsWith(".gif");
                    
                    if (isVideo && {str(video_mode_active).lower()}) {{
                         if (d.wallpaperPlugin !== targetVideo && d.wallpaperPlugin !== altVideo) d.wallpaperPlugin = targetVideo;
                         d.currentConfigGroup = Array("Wallpaper", d.wallpaperPlugin, "General");
                         d.writeConfig("VideoUrls", imgPath);
                         d.writeConfig("FillMode", {video_fill_mode});
                         
                         d.currentConfigGroup = Array("Wallpaper", "org.kde.image", "General");
                         d.writeConfig("FillMode", 2);
                         d.writeConfig("Color", "#00000000");
                    }} else {{
                         d.wallpaperPlugin = "org.kde.image";
                         d.currentConfigGroup = Array("Wallpaper", "org.kde.image", "General");
                         d.writeConfig("Image", imgPath);
                         d.writeConfig("FillMode", {fill_mode});
                    }}
                    d.reloadConfig();
                }}
            }}
            """
            # Escape single quotes in the script to avoid breaking the shell command
            script_escaped = script.replace("'", "'\\''")
            qdbus_command = f"{qdbus} org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript '{script_escaped}'"
            
            if logging.getLogger().hasHandlers():
                logging.info("KDE: Using geometry-based mapping script (Safe).")
            
            subprocess.run(qdbus_command, shell=True, check=False, capture_output=True, text=True)

        else:
            # FALLBACK TO INDEX-BASED (Original logic)
            for i in range(num_monitors):
                monitor_id = str(i)
                path = path_map.get(monitor_id)

                if path:
                    # Resolve path
                    file_uri = str(Path(path).resolve())
                    ext = Path(path).suffix.lower()
                    script = ""

                    if ext in SUPPORTED_VIDEO_FORMATS and video_mode_active:
                        script = f"""
                        var d = desktops()[{i}];
                        var currentPlugin = d.wallpaperPlugin;
                        var targetPlugin = "{REBORN_PLUGIN}";
                        var altPlugin = "{ZREN_PLUGIN}";

                        if (currentPlugin === targetPlugin || currentPlugin === altPlugin) {{
                            targetPlugin = currentPlugin;
                        }} else {{
                            d.wallpaperPlugin = targetPlugin; 
                        }}

                        d.currentConfigGroup = Array("Wallpaper", targetPlugin, "General");
                        d.writeConfig("VideoUrls", "{file_uri}");
                        d.writeConfig("FillMode", {video_fill_mode});

                        d.currentConfigGroup = Array("Wallpaper", "org.kde.image", "General");
                        d.writeConfig("FillMode", 2);
                        d.writeConfig("Color", "#00000000");
                        
                        d.reloadConfig();
                        """
                    else:
                        script = f'var d = desktops()[{i}]; if (d && d.screen >= 0) {{ d.wallpaperPlugin = "org.kde.image"; d.currentConfigGroup = Array("Wallpaper", "org.kde.image", "General"); d.writeConfig("Image", "{file_uri}"); d.writeConfig("FillMode", {fill_mode}); d.reloadConfig(); }}'

                    if script:
                        qdbus_command = f"{qdbus} org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript '{script}'"
                        
                        if logging.getLogger().hasHandlers():
                            logging.info(f"Setting wallpaper for KDE Desktop {i}: {Path(file_uri).name}")
                        
                        subprocess.run(
                            qdbus_command, shell=True, check=False, capture_output=True, text=True
                        )

    @staticmethod
    def _set_wallpaper_gnome_spanned(
        path_map: Dict[str, str], monitors: List[Monitor], style_name: str
    ):
        """
        Creates a spanned image for GNOME and sets it using gsettings.
        """
        if not monitors:
            return

        # 1. Calculate Canvas Size
        min_x = min(m.x for m in monitors)
        min_y = min(m.y for m in monitors)
        max_x = max(m.x + m.width for m in monitors)
        max_y = max(m.y + m.height for m in monitors)

        width = max_x - min_x
        height = max_y - min_y

        canvas = Image.new("RGB", (width, height), (0, 0, 0))

        # 2. Paste Images
        for i, monitor in enumerate(monitors):
            path = path_map.get(str(i))
            if path and os.path.exists(path):
                img = Image.open(path)
                # Resize if needed (assuming "Fill" style roughly translates to cover)
                # For "Spanned" we typically want exact placement.
                # Here we just resize to monitor dimensions for simplicity
                img = img.resize((monitor.width, monitor.height), Image.Resampling.LANCZOS)
                canvas.paste(img, (monitor.x - min_x, monitor.y - min_y))

        # 3. Save Temp Image
        temp_path = os.path.join(Path.home(), ".cache", "image_toolkit_spanned.jpg")
        canvas.save(temp_path, "JPEG", quality=95)

        # 4. Set Wallpaper
        subprocess.run(
            [
                "gsettings",
                "set",
                "org.gnome.desktop.background",
                "picture-uri",
                f"file://{temp_path}",
            ],
            check=False,
        )
        subprocess.run(
            [
                "gsettings",
                "set",
                "org.gnome.desktop.background",
                "picture-options",
                "spanned",
            ],
            check=False,
        )

    @staticmethod
    def apply_wallpaper(
        path_map: Dict[str, str], monitors: Union[List[Monitor], int], style_name: str, qdbus: str, geometries: Optional[Dict[str, Dict[str, int]]] = None
    ):
        system = platform.system()
        is_solid_color = style_name == "SolidColor"

        if is_solid_color:
            color_hex = path_map.get(str(0), "#000000")
            if system == "Windows":
                WallpaperManager._set_wallpaper_solid_color_windows(color_hex)
            elif system == "Linux":
                # (Assuming solid color logic doesn't need monitors list)
                try:
                    subprocess.run(["which", qdbus], check=True, capture_output=True)
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
                    qdbus_command = f"{qdbus} org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript '{script}'"
                    subprocess.run(
                        qdbus_command,
                        shell=True,
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                except (FileNotFoundError, subprocess.CalledProcessError):
                    WallpaperManager._set_wallpaper_solid_color_gnome(color_hex)
                except Exception as e:
                    raise RuntimeError(f"Linux Solid Color method failed: {e}")
            return

        if system == "Windows":
            if COM_AVAILABLE:
                WallpaperManager._set_wallpaper_windows_multi(
                    path_map, monitors, style_name
                )
            else:
                if isinstance(monitors, int) or not monitors:
                     # This path shouldn't be hit by daemon if windows; daemon handles windows differently?
                     # Actually daemon just calls apply_wallpaper with monitors list on Windows too.
                     # If I change daemon to pass int `num_monitors`, Windows logic will break IF it expects List[Monitor].
                     # But daemon is Linux specific? No, `slideshow_daemon.py` is cross platform.
                     # Wait. `slideshow_daemon.py` logic:
                     # If Windows, uses `comtypes`...
                     pass 

                primary_monitor = next(
                    (m for m in monitors if m.is_primary), monitors[0]
                )
                path_to_set = path_map.get(str(monitors.index(primary_monitor)))
                if not path_to_set:
                    path_to_set = next((p for p in path_map.values() if p), None)
                if not path_to_set:
                    raise ValueError("No valid image path provided.")
                WallpaperManager._set_wallpaper_windows_single(path_to_set, style_name)

        if system == "Linux":
            if logging.getLogger().hasHandlers():
                logging.debug(f"apply_wallpaper (Linux): path_map={path_map}, monitors={monitors}, style={style_name}, geometries={'PROVIDED' if geometries else 'NONE'}")
            try:
                subprocess.run(["which", qdbus], check=True, capture_output=True)
                # KDE Logic
                # Check if monitors is int or list
                num_mons = monitors if isinstance(monitors, int) else len(monitors)
                WallpaperManager._set_wallpaper_kde(
                    path_map, num_mons, style_name, qdbus, geometries
                )
            except (FileNotFoundError, subprocess.CalledProcessError):
                try:
                    # GNOME Fallback still needs monitors list for geometry!
                    if isinstance(monitors, list):
                        WallpaperManager._set_wallpaper_gnome_spanned(
                            path_map, monitors, style_name
                        )
                    else:
                        print("Warning: Monitor list not provided for GNOME fallback.")
                except Exception as e:
                    raise RuntimeError(f"GNOME (fallback) method failed: {e}")
            except Exception as e:
                raise RuntimeError(f"KDE method failed: {e}")
        else:
            raise NotImplementedError(
                f"Wallpaper setting for {system} is not supported."
            )

    @staticmethod
    def get_current_system_wallpaper_path_kde(
        num_monitors: int, qdbus: str
    ) -> Dict[str, Optional[str]]:
        path_map: Dict[str, Optional[str]] = {}
        script = "var out = [];\n"
        for i in range(num_monitors):
            script += f"""
            (function() {{
                try {{
                    var d = desktops()[{i}];
                    var plugin = d.wallpaperPlugin;
                    var path = "";
                    d.currentConfigGroup = Array("Wallpaper", plugin, "General");
                    path = d.readConfig("Image");
                    if (!path || path == "" || path == "null") {{ path = d.readConfig("VideoUrls"); }}
                    if (!path || path == "" || path == "null") {{ path = d.readConfig("Video"); }}
                    if (path && path.indexOf(",") !== -1) {{ path = path.split(",")[0]; }}
                    out.push("MONITOR_{i}:" + (path || "NONE"));
                }} catch (e) {{ out.push("MONITOR_{i}:NONE"); }}
            }})();
            """
        script += '\nprint(out.join("\\n===SEP===\\n"));'

        try:
            cmd = [
                qdbus,
                "org.kde.plasmashell",
                "/PlasmaShell",
                "org.kde.PlasmaShell.evaluateScript",
                script,
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=12, check=False
            )
            if result.returncode != 0:
                return path_map
            output = result.stdout.strip()
            if not output:
                return path_map

            for line in output.split("===SEP==="):
                line = line.strip()
                if not line.startswith("MONITOR_"):
                    continue
                parts = line.split(":", 1)
                if len(parts) < 2:
                    continue
                monitor_id_str, raw_path = parts
                monitor_id = monitor_id_str.split("_")[1]
                raw_path = raw_path.strip()
                if not raw_path or raw_path == "NONE" or raw_path == "null":
                    path_map[monitor_id] = None
                    continue
                if raw_path.startswith("file:/") and not raw_path.startswith("file://"):
                    raw_path = "file://" + raw_path[5:]
                try:
                    if raw_path.startswith("file://"):
                        local_path = Path(raw_path[7:]).resolve()
                    else:
                        local_path = Path(raw_path).resolve()
                    if local_path.exists():
                        path_map[monitor_id] = str(local_path)
                    else:
                        path_map[monitor_id] = None
                except Exception:
                    path_map[monitor_id] = None
        except Exception:
            pass
        return path_map

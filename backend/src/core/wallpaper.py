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
    def get_kde_desktops(qdbus: str) -> List[Dict[str, int]]:
        """
        Returns a list of KDE desktops with their index, screen ID, and geometry.
        Filters out desktops with invalid screens (screen < 0).
        """
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
        cmd = [qdbus, "org.kde.plasmashell", "/PlasmaShell", "org.kde.PlasmaShell.evaluateScript", script]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode != 0:
                return []
            
            desktops = []
            for line in result.stdout.strip().split("\n"):
                if not line.strip(): continue
                parts = line.split(":")
                if len(parts) >= 4:
                    desktops.append({
                        "index": int(parts[0]),
                        "screen": int(parts[1]),
                        "x": int(parts[2]),
                        "y": int(parts[3])
                    })
            return desktops
        except Exception as e:
            if logging.getLogger().hasHandlers():
                logging.error(f"Failed to get KDE desktops: {e}")
            return []

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
    def get_best_video_plugin() -> str:
        """
        Detects which smart video wallpaper plugin is installed.
        Priority: SmartER > Reborn > Old Smart Video
        """
        REBORN_PLUGIN = "luisbocanegra.smart.video.wallpaper.reborn"
        ZREN_PLUGIN = "com.github.zren.smartvideowallpaper"
        SMARTER_PLUGIN = "smartervideowallpaper"

        search_paths = [
            Path.home() / ".local/share/plasma/wallpapers",
            Path("/usr/share/plasma/wallpapers"),
        ]

        # Check SmartER first
        for base in search_paths:
            if (base / SMARTER_PLUGIN).exists():
                return SMARTER_PLUGIN

        # Check Reborn
        for base in search_paths:
            if (base / REBORN_PLUGIN).exists():
                return REBORN_PLUGIN

        # Check Zren
        for base in search_paths:
            if (base / ZREN_PLUGIN).exists():
                return ZREN_PLUGIN

        return REBORN_PLUGIN  # Final fallback

    @staticmethod
    def _set_wallpaper_kde(
        path_map: Dict[str, str], style_name: str, qdbus: str
    ):
        """
        Sets per-monitor wallpaper for KDE Plasma using qdbus.
        """

        # --- FIX: Correct Mapping for Qt6 VideoOutput.FillMode ---
        # 0 = Stretch
        # 1 = PreserveAspectFit (Keep Proportions)
        # 2 = PreserveAspectCrop (Scaled and Cropped) -- DEFAULT
        video_fill_mode = 2
        video_mode_active = False

        if style_name.startswith("SmartVideoWallpaper") and "::" in style_name:
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

        target_plugin = WallpaperManager.get_best_video_plugin()

        script_parts = []
        for monitor_id, path in path_map.items():
            try:
                i = int(monitor_id)
            except ValueError:
                continue

            if path:
                # Resolve path
                file_uri = str(Path(path).resolve())
                ext = Path(path).suffix.lower()

                if ext in SUPPORTED_VIDEO_FORMATS and video_mode_active:
                    # SmartER uses 'VideoWallpaperBackgroundVideo', Reborn/Zren use 'VideoUrls'
                    is_smarter = target_plugin == "smartervideowallpaper"
                    video_key = "VideoWallpaperBackgroundVideo" if is_smarter else "VideoUrls"
                    
                    # Ensure file:// prefix
                    if not file_uri.startswith("file://"):
                        file_uri = "file://" + file_uri

                    script_parts.append(
                        f"""
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
                    """
                    )
                else:
                    script_parts.append(
                        f'var d = desktops()[{i}]; if (d && d.screen >= 0) {{ d.wallpaperPlugin = "org.kde.image"; d.currentConfigGroup = Array("Wallpaper", "org.kde.image", "General"); d.writeConfig("Image", "{file_uri}"); d.writeConfig("FillMode", {fill_mode}); d.reloadConfig(); }}'
                    )

        if not script_parts:
            return

        full_script = "".join(script_parts)
        # Escape single quotes
        full_script_escaped = full_script.replace("'", "'\\''")
        qdbus_command = f"{qdbus} org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript '{full_script_escaped}'"
        
        if logging.getLogger().hasHandlers():
            logging.info("KDE: Using index-based mapping script (Safe).")
        
        subprocess.run(qdbus_command, shell=True, check=False, capture_output=True, text=True)

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
        path_map: Dict[str, str], monitors: Union[List[Monitor], int], style_name: str, qdbus: str
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
                logging.debug(f"apply_wallpaper (Linux): path_map={path_map}, monitors={monitors}, style={style_name}")
            try:
                subprocess.run(["which", qdbus], check=True, capture_output=True)
                
                # --- NEW MAPPING LOGIC ---
                # 1. Ensure we have screeninfo monitors to compare geometry
                target_monitors = []
                if isinstance(monitors, list):
                    target_monitors = monitors
                else:
                    try:
                        from screeninfo import get_monitors
                        target_monitors = get_monitors()
                    except ImportError:
                        pass # Fallback to 1:1 if screeninfo missing

                # 2. Get KDE Desktop info
                kde_desktops = WallpaperManager.get_kde_desktops(qdbus)
                
                # 3. Build Mapping: GUI ID (Index in target_monitors) -> KDE Desktop Index
                mapped_path_map = {}
                
                if target_monitors and kde_desktops:
                    if logging.getLogger().hasHandlers():
                         logging.info(f"Mapping Monitors. GUI: {len(target_monitors)}, KDE: {len(kde_desktops)}")

                    for gui_id_str, path in path_map.items():
                        try:
                            gui_idx = int(gui_id_str)
                            if 0 <= gui_idx < len(target_monitors):
                                monitor = target_monitors[gui_idx]
                                # Find matching KDE desktop by geometry (x, y)
                                match = next(
                                    (d for d in kde_desktops if d["x"] == monitor.x and d["y"] == monitor.y),
                                    None
                                )
                                if match:
                                    # Use KDE Index as key
                                    mapped_path_map[str(match["index"])] = path
                                else:
                                    logging.warning(f"No KDE match for Monitor {gui_idx} at {monitor.x},{monitor.y}")
                                    mapped_path_map[gui_id_str] = path # Fallback
                            else:
                                mapped_path_map[gui_id_str] = path
                        except ValueError:
                             mapped_path_map[gui_id_str] = path
                else:
                    # Fallback to direct mapping if detection failed
                    mapped_path_map = path_map

                # KDE Logic use MAPPED map
                WallpaperManager._set_wallpaper_kde(
                    mapped_path_map, style_name, qdbus
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
                    var keys = ["Image", "VideoUrls", "VideoWallpaperBackgroundVideo", "Video"];
                    for (var k=0; k < keys.length; k++) {{
                        path = d.readConfig(keys[k]);
                        if (path && path != "" && path != "null") break;
                    }}
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

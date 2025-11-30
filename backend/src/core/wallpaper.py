import os
import re
import ctypes
import platform
import subprocess

from PIL import Image
from pathlib import Path
from screeninfo import Monitor
from typing import Dict, List, Optional
from ..utils.definitions import (
    WALLPAPER_STYLES, 
    SUPPORTED_IMG_FORMATS, 
    SUPPORTED_VIDEO_FORMATS,
)

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
        IDESKTOPWALLPAPER_IID = GUID('{B92B56A9-8B55-4E14-9A89-0199BBB6F93B}')
        DESKTOPWALLPAPER_CLSID = GUID('{C2CF3110-460E-4fc1-B9D0-8A1C0C9CC4BD}')

        # The core IDesktopWallpaper COM Interface Definition
        class IDesktopWallpaper(IUnknown):
            _iid_ = IDESKTOPWALLPAPER_IID
            _methods_ = [
                COMMETHOD(
                    [], HRESULT, 'SetWallpaper',
                    (['in'], LPCWSTR, 'monitorID'),
                    (['in'], LPCWSTR, 'wallpaper'),
                ),
                COMMETHOD(
                    [], HRESULT, 'GetWallpaper',
                    (['in'], LPCWSTR, 'monitorID'),
                    (['out'], POINTER(LPWSTR), 'wallpaper'),
                ),
                COMMETHOD(
                    [], HRESULT, 'GetMonitorDevicePathAt',
                    (['in'], UINT, 'monitorIndex'),
                    (['out'], POINTER(LPWSTR), 'monitorID'),
                ),
                COMMETHOD(
                    [], HRESULT, 'GetMonitorDevicePathCount',
                    (['out'], POINTER(UINT), 'count'),
                ),
            ]
            
            # Helper methods (required to interact with the COM object)
            def SetWallpaper(self, monitorId: str, wallpaper: str):
                self.__com_SetWallpaper(LPCWSTR(monitorId), LPCWSTR(wallpaper))

            def GetMonitorDevicePathAt(self, monitorIndex: int) -> str:
                monitorId = LPWSTR()
                self.__com_GetMonitorDevicePathAt(UINT(monitorIndex), pointer(monitorId))
                return monitorId.value

            def GetMonitorDevicePathCount(self) -> int:
                count = UINT()
                self.__com_GetMonitorDevicePathCount(pointer(count))
                return count.value

        COM_AVAILABLE = True

    except ImportError:
        COM_AVAILABLE = False
        print("Warning: 'comtypes' library not found. Multi-monitor support is disabled.")


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
            color_hex = color_hex.lstrip('#')
            r, g, b = tuple(int(color_hex[i:i+2], 16) for i in (0, 2, 4))
            
            # 2. Set necessary registry values for solid color mode
            key_desktop = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                        "Control Panel\\Desktop", 0, winreg.KEY_SET_VALUE)
            
            winreg.SetValueEx(key_desktop, "WallpaperStyle", 0, winreg.REG_SZ, "0") 
            winreg.SetValueEx(key_desktop, "TileWallpaper", 0, winreg.REG_SZ, "0") 
            winreg.CloseKey(key_desktop)

            # 3. Set the Solid Color value (RGB as a string "R G B")
            key_colors = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                        "Control Panel\\Colors", 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key_colors, "Background", 0, winreg.REG_SZ, f"{r} {g} {b}")
            winreg.CloseKey(key_colors)

            # 4. Trigger the wallpaper update
            SPI_SETDESKWALLPAPER = 20
            SPIF_UPDATEINIFILE = 0x01
            SPIF_SENDWININICHANGE = 0x02
            
            ctypes.windll.user32.SystemParametersInfoW(
                SPI_SETDESKWALLPAPER, 
                0, 
                None,
                SPIF_UPDATEINIFILE | SPIF_SENDWININICHANGE
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
                ["gsettings", "set", "org.gnome.desktop.background", "picture-options", "none"],
                check=True, capture_output=True, text=True
            )
            subprocess.run(
                ["gsettings", "set", "org.gnome.desktop.background", "primary-color", color_hex],
                check=True, capture_output=True, text=True
            )
            subprocess.run(
                ["gsettings", "set", "org.gnome.desktop.background", "color-shading-type", "solid"],
                check=True, capture_output=True, text=True
            )
        except Exception as e:
            raise RuntimeError(f"Error setting GNOME solid color: {e}")

    @staticmethod
    def _set_wallpaper_windows_multi(path_map: Dict[str, str], monitors: List[Monitor], style_name: str):
        """
        Sets per-monitor wallpaper for Windows using the IDesktopWallpaper COM interface.
        """
        if not COM_AVAILABLE:
            raise ImportError("Multi-monitor setting requires 'comtypes' and a functional COM interface.")

        style_values = WALLPAPER_STYLES["Windows"].get("Fill", WALLPAPER_STYLES["Windows"]["Fill"])
        wallpaper_style_reg, tile_wallpaper_reg = style_values

        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                 "Control Panel\\Desktop", 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, "WallpaperStyle", 0, winreg.REG_SZ, wallpaper_style_reg) 
            winreg.SetValueEx(key, "TileWallpaper", 0, winreg.REG_SZ, tile_wallpaper_reg) 
            winreg.CloseKey(key)

            desktop_wallpaper = comtypes.CoCreateInstance(
                DESKTOPWALLPAPER_CLSID, interface=IDesktopWallpaper
            )
            
            monitor_count = desktop_wallpaper.GetMonitorDevicePathCount()

            if len(monitors) != monitor_count:
                print(f"Warning: screeninfo found {len(monitors)} monitors, COM found {monitor_count}.")

            for i in range(monitor_count):
                monitor_id_path = desktop_wallpaper.GetMonitorDevicePathAt(i)
                path = path_map.get(str(i)) 

                if path and Path(path).exists():
                    resolved_path = str(Path(path).resolve())
                    if Path(resolved_path).suffix.lower() in SUPPORTED_VIDEO_FORMATS:
                        print(f"Skipping monitor {i}: Video wallpapers not supported on Windows natively.")
                        continue
                         
                    desktop_wallpaper.SetWallpaper(monitor_id_path, resolved_path)
                    print(f"Set wallpaper for Monitor Index {i} ({monitor_id_path}) to {resolved_path}")
                elif str(i) in path_map:
                    print(f"Skipping monitor {i}: Image path not found or invalid.")
            
        except Exception as e:
            raise RuntimeError(f"Error setting multi-monitor Windows wallpaper via COM: {e}")


    @staticmethod
    def _set_wallpaper_windows_single(image_path: str, style_name: str):
        """
        Original single-monitor method.
        """
        if Path(image_path).suffix.lower() in SUPPORTED_VIDEO_FORMATS:
            raise ValueError("Video wallpapers are not supported on Windows via the standard API.")

        style_values = WALLPAPER_STYLES["Windows"].get(style_name, WALLPAPER_STYLES["Windows"]["Fill"])
        wallpaper_style_reg, tile_wallpaper_reg = style_values

        save_path = str(Path(image_path).resolve())

        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                 "Control Panel\\Desktop", 0, winreg.KEY_SET_VALUE)
            
            winreg.SetValueEx(key, "WallpaperStyle", 0, winreg.REG_SZ, wallpaper_style_reg) 
            winreg.SetValueEx(key, "TileWallpaper", 0, winreg.REG_SZ, tile_wallpaper_reg) 
            winreg.CloseKey(key)

            SPI_SETDESKWALLPAPER = 20
            SPIF_UPDATEINIFILE = 0x01
            SPIF_SENDWININICHANGE = 0x02
            ctypes.windll.user32.SystemParametersInfoW(SPI_SETDESKWALLPAPER, 0, save_path, SPIF_UPDATEINIFILE | SPIF_SENDWININICHANGE)
        except Exception as e:
            raise RuntimeError(f"Error setting Windows single wallpaper: {e}")

    @staticmethod
    def _set_wallpaper_kde(path_map: Dict[str, str], num_monitors: int, style_name: str, qdbus: str):
        """
        Fully working with Smart Video Wallpaper Reborn 2.7.0+
        Correctly respects the new 'Positioning' dropdown.
        """

        video_mode_active = style_name.startswith("SmartVideoWallpaperReborn::")

        # Map our internal → Reborn Positioning value
        if video_mode_active:
            try:
                mode = style_name.split("::", 1)[1]
                if mode == "Keep Proportions":
                    positioning_value = 0
                elif mode == "Scaled and Cropped":
                    positioning_value = 1
                elif mode == "Stretch":
                    positioning_value = 2
                else:
                    positioning_value = 1  # fallback
            except:
                positioning_value = 1
        else:
            positioning_value = None  # not a video mode

        image_fill_mode = WALLPAPER_STYLES["KDE"].get(
            style_name if not video_mode_active else "Fill",
            WALLPAPER_STYLES["KDE"]["Scaled, Keep Proportions"]
        )

        REBORN_PLUGIN = "luisbocanegra.smart.video.wallpaper.reborn"
        ZREN_PLUGIN   = "com.github.zren.smartvideowallpaper"

        script_parts = []

        for i in range(num_monitors):
            path = path_map.get(str(i))
            if not path:
                continue

            file_uri = f"file://{Path(path).resolve()}"
            is_video = Path(path).suffix.lower() in SUPPORTED_VIDEO_FORMATS

            if video_mode_active and is_video:
                script_parts.append(f'''
                    var d = desktops()[{i}];

                    // Detect current plugin (prefer Reborn)
                    var plugin = "{REBORN_PLUGIN}";
                    if (d.wallpaperPlugin === "{ZREN_PLUGIN}") plugin = "{ZREN_PLUGIN}";

                    // 1. Reset by switching to image plugin
                    d.wallpaperPlugin = "org.kde.image";
                    d.currentConfigGroup = ["Wallpaper", "org.kde.image", "General"];
                    d.writeConfig("Image", "file:///usr/share/wallpapers/Next/contents/images/1920x1080.jpg");

                    // 2. Write video settings while plugin is inactive
                    d.currentConfigGroup = ["Wallpaper", plugin, "General"];
                    d.writeConfig("VideoUrls", "{file_uri}");
                    d.writeConfig("Volume", 0);
                    d.writeConfig("Positioning", {positioning_value});   // This is the key that matters now!
                    d.writeConfig("Resize", {positioning_value});        // Keep for old versions

                    // 3. Activate video plugin → forces full reload
                    d.wallpaperPlugin = plugin;
                ''')
            else:
                # Regular image wallpaper
                script_parts.append(f'''
                    var d = desktops()[{i}];
                    d.wallpaperPlugin = "org.kde.image";
                    d.currentConfigGroup = ["Wallpaper", "org.kde.image", "General"];
                    d.writeConfig("Image", "{file_uri}");
                    d.writeConfig("FillMode", {image_fill_mode});
                ''')

        if not script_parts:
            return

        full_script = "\n".join(script_parts)
        full_script += "\nfor(var i=0; i<desktops().length; i++) desktops()[i].reloadConfig();"

        print(f"[Smart Video Wallpaper Reborn] Using Positioning = {positioning_value}")

        subprocess.run([
            qdbus,
            "org.kde.plasmashell",
            "/PlasmaShell",
            "org.kde.PlasmaShell.evaluateScript",
            full_script
        ], check=True, capture_output=True, text=True)

    @staticmethod
    def _set_wallpaper_gnome_spanned(path_map: Dict[str, str], monitors: List[Monitor], style_name: str):
        physical_monitors = sorted(monitors, key=lambda m: m.x)
        total_width = sum(m.width for m in physical_monitors)
        max_height = max(m.height for m in physical_monitors)
        
        if total_width == 0 or max_height == 0: raise ValueError(f"Invalid monitor dimensions.")
            
        spanned_image = Image.new('RGB', (total_width, max_height))
        current_x = 0
        
        for monitor in physical_monitors:
            system_index = next((i for i, sys_mon in enumerate(monitors) 
                                if sys_mon.x == monitor.x and sys_mon.y == monitor.y and 
                                sys_mon.width == monitor.width and sys_mon.height == monitor.height), -1)
            
            if system_index == -1:
                current_x += monitor.width
                continue

            path = path_map.get(str(system_index))
            if path and Path(path).suffix.lower() not in SUPPORTED_VIDEO_FORMATS:
                try:
                    img = Image.open(path)
                    img = img.resize((monitor.width, monitor.height), Image.Resampling.LANCZOS)
                    spanned_image.paste(img, (current_x, 0))
                except Exception as e: print(f"Warning: {e}")
            current_x += monitor.width

        home_dir = os.path.expanduser('~')
        save_path = os.path.join(home_dir, ".spanned_wallpaper.jpg")
        spanned_image.save(save_path, "JPEG", quality=95)
        file_uri = f"file://{save_path}"

        subprocess.run(["gsettings", "set", "org.gnome.desktop.background", "picture-options", "spanned"], check=True)
        subprocess.run(["gsettings", "set", "org.gnome.desktop.background", "picture-uri", file_uri], check=True)
        
        # --- FIX: Make picture-uri-dark setting optional ---
        try:
            subprocess.run(
                ["gsettings", "set", "org.gnome.desktop.background", "picture-uri-dark", file_uri], 
                check=True, capture_output=True, text=True
            )
        except subprocess.CalledProcessError as e:
            # Ignore "No such key" error from systems without dark mode support
            if "No such key" not in e.stderr:
                raise
        # ---------------------------------------------------

    @staticmethod
    def apply_wallpaper(path_map: Dict[str, str], monitors: List[Monitor], style_name: str, qdbus: str):
        system = platform.system()
        is_solid_color = (style_name == "SolidColor")
        
        if is_solid_color:
            color_hex = path_map.get(str(0), "#000000") 
            
            if system == "Windows":
                WallpaperManager._set_wallpaper_solid_color_windows(color_hex)
            elif system == "Linux":
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
                    qdbus_command = (f"{qdbus} org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript '{script}'")
                    subprocess.run(qdbus_command, shell=True, check=True, capture_output=True, text=True)
                except (FileNotFoundError, subprocess.CalledProcessError):
                    WallpaperManager._set_wallpaper_solid_color_gnome(color_hex)
                except Exception as e:
                    raise RuntimeError(f"Linux Solid Color method failed: {e}")
            return 
        
        if system == "Windows":
            if COM_AVAILABLE:
                WallpaperManager._set_wallpaper_windows_multi(path_map, monitors, style_name)
            else:
                if not monitors: raise ValueError("No monitors found.")
                primary_monitor = next((m for m in monitors if m.is_primary), monitors[0])
                path_to_set = path_map.get(str(monitors.index(primary_monitor)))
                if not path_to_set: path_to_set = next((p for p in path_map.values() if p), None)
                if not path_to_set: raise ValueError("No valid image path provided.")
                WallpaperManager._set_wallpaper_windows_single(path_to_set, style_name)
                
        elif system == "Linux":
            # --- Linux Implementation ---
            try:
                # Try KDE qdbus method first
                subprocess.run(["which", qdbus], check=True, capture_output=True) 
                WallpaperManager._set_wallpaper_kde(path_map, len(monitors), style_name, qdbus)
                
            except (FileNotFoundError, subprocess.CalledProcessError):
                # Fallback to GNOME (spanned) method
                try:
                    WallpaperManager._set_wallpaper_gnome_spanned(path_map, monitors, style_name)
                except Exception as e:
                    raise RuntimeError(f"GNOME (fallback) method failed: {e}")
            except Exception as e:
                raise RuntimeError(f"KDE method failed: {e}")
        else:
            raise NotImplementedError(f"Wallpaper setting for {system} is not supported.")

    @staticmethod
    def get_current_system_wallpaper_path_kde(num_monitors: int, qdbus: str) -> Dict[str, Optional[str]]:
        path_map: Dict[str, Optional[str]] = {}
        script = "var out = [];\n"
        for i in range(num_monitors):
            script += f'''
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
            '''
        script += '\nprint(out.join("\\n===SEP===\\n"));'

        try:
            cmd = [qdbus, "org.kde.plasmashell", "/PlasmaShell", "org.kde.PlasmaShell.evaluateScript", script]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=12, check=False)

            if result.returncode != 0: return path_map
            output = result.stdout.strip()
            if not output: return path_map

            for line in output.split("===SEP==="):
                line = line.strip()
                if not line.startswith("MONITOR_"): continue
                parts = line.split(":", 1)
                if len(parts) < 2: continue
                monitor_id_str, raw_path = parts
                monitor_id = monitor_id_str.split("_")[1]
                raw_path = raw_path.strip()
                if not raw_path or raw_path == "NONE" or raw_path == "null":
                    path_map[monitor_id] = None
                    continue
                if raw_path.startswith("file:/") and not raw_path.startswith("file://"):
                    raw_path = "file://" + raw_path[5:]

                try:
                    if raw_path.startswith("file://"): local_path = Path(raw_path[7:]).resolve()
                    else: local_path = Path(raw_path).resolve()
                    if local_path.exists(): path_map[monitor_id] = str(local_path)
                    else: path_map[monitor_id] = None
                except Exception: path_map[monitor_id] = None
        except Exception: pass
        return path_map
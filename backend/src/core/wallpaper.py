import os
import ctypes
import platform
import subprocess

from PIL import Image
from pathlib import Path
from typing import Dict, List
from screeninfo import Monitor
from ..utils.definitions import WALLPAPER_STYLES

# Global Definitions for COM components
# NOTE: We keep IDesktopWallpaperInstance as None and COM_AVAILABLE as False
# We will define IDesktopWallpaper class here, but NOT instantiate the object globally.
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

        # --- FIX: REMOVE GLOBAL INSTANTIATION ---
        # Instead of instantiating globally, we set COM_AVAILABLE=True
        # This tells the system that the *capability* exists.
        COM_AVAILABLE = True
        # IDesktopWallpaperInstance remains None here.

    except ImportError:
        # Fallback if comtypes is not installed
        COM_AVAILABLE = False
        print("Warning: 'comtypes' library not found. Multi-monitor support is disabled.")


class WallpaperManager:
    """
    A static class for handling OS-specific wallpaper setting logic.
    """

    @staticmethod
    def _set_wallpaper_windows_multi(path_map: Dict[str, str], monitors: List[Monitor], style_name: str):
        """
        Sets per-monitor wallpaper for Windows using the IDesktopWallpaper COM interface.
        
        NOTE: This function now instantiates the COM object on the calling thread.
        """
        if not COM_AVAILABLE:
            raise ImportError("Multi-monitor setting requires 'comtypes' and a functional COM interface.")

        # Set the global style using the old registry method
        style_values = WALLPAPER_STYLES["Windows"].get("Fill", WALLPAPER_STYLES["Windows"]["Fill"])
        wallpaper_style_reg, tile_wallpaper_reg = style_values

        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                 "Control Panel\\Desktop", 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, "WallpaperStyle", 0, winreg.REG_SZ, wallpaper_style_reg) 
            winreg.SetValueEx(key, "TileWallpaper", 0, winreg.REG_SZ, tile_wallpaper_reg) 
            winreg.CloseKey(key)

            # --- FIX: INSTANTIATE COM OBJECT LOCALLY ON THE WORKER THREAD ---
            # This must be done AFTER CoInitialize() is called in the worker thread.
            desktop_wallpaper = comtypes.CoCreateInstance(
                DESKTOPWALLPAPER_CLSID, interface=IDesktopWallpaper
            )
            # --- END FIX ---
            
            monitor_count = desktop_wallpaper.GetMonitorDevicePathCount()

            if len(monitors) != monitor_count:
                print(f"Warning: screeninfo found {len(monitors)} monitors, COM found {monitor_count}.")

            for i in range(monitor_count):
                monitor_id_path = desktop_wallpaper.GetMonitorDevicePathAt(i)
                path = path_map.get(str(i)) 

                if path and Path(path).exists():
                    resolved_path = str(Path(path).resolve())
                    desktop_wallpaper.SetWallpaper(monitor_id_path, resolved_path)
                    print(f"Set wallpaper for Monitor Index {i} ({monitor_id_path}) to {resolved_path}")
                elif str(i) in path_map:
                    print(f"Skipping monitor {i}: Image path not found or invalid.")
            
        except Exception as e:
            raise RuntimeError(f"Error setting multi-monitor Windows wallpaper via COM: {e}")


    @staticmethod
    def _set_wallpaper_windows_single(image_path: str, style_name: str):
        """
        Original single-monitor method (kept as a functional fallback).
        """
        # Get OS-specific values for the selected style
        style_values = WALLPAPER_STYLES["Windows"].get(style_name, WALLPAPER_STYLES["Windows"]["Fill"])
        wallpaper_style_reg, tile_wallpaper_reg = style_values

        # Ensure path is absolute and resolved
        save_path = str(Path(image_path).resolve())

        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                 "Control Panel\\Desktop", 0, winreg.KEY_SET_VALUE)
            
            # Set the WallpaperStyle (Position/Sizing)
            winreg.SetValueEx(key, "WallpaperStyle", 0, winreg.REG_SZ, wallpaper_style_reg) 
            # Set TileWallpaper (Tiling on/off)
            winreg.SetValueEx(key, "TileWallpaper", 0, winreg.REG_SZ, tile_wallpaper_reg) 
            winreg.CloseKey(key)

            SPI_SETDESKWALLPAPER = 20
            SPIF_UPDATEINIFILE = 0x01
            SPIF_SENDWININICHANGE = 0x02
            
            # Call the system function to set the wallpaper
            ctypes.windll.user32.SystemParametersInfoW(
                SPI_SETDESKWALLPAPER, 
                0, 
                save_path, 
                SPIF_UPDATEINIFILE | SPIF_SENDWININICHANGE
            )
        except Exception as e:
            raise RuntimeError(f"Error setting Windows single wallpaper: {e}")

    @staticmethod
    def _set_wallpaper_kde(path_map: Dict[str, str], num_monitors: int, style_name: str):
        """
        Sets per-monitor wallpaper for KDE Plasma using qdbus and the specified style.
        """
        # Get the KDE FillMode integer for the selected style
        fill_mode = WALLPAPER_STYLES["KDE"].get(style_name, WALLPAPER_STYLES["KDE"]["Scaled, Keep Proportions"])
        
        script_parts = []
        
        # --- Iterate by system monitor index (i = 0, 1, 2...) ---
        for i in range(num_monitors):
            monitor_id = str(i)
            path = path_map.get(monitor_id)
            
            if path:
                file_uri = f"file://{Path(path).resolve()}"
                script_parts.append(
                    f'd = desktops()[{i}]; d.currentConfigGroup = Array("Wallpaper", "org.kde.image", "General"); d.writeConfig("Image", "{file_uri}"); d.writeConfig("FillMode", {fill_mode});'
                )
        
        if not script_parts:
            print("KDE: No image paths provided to set.")
            return

        full_script = "".join(script_parts)
        full_script += "d.reloadConfig();"

        qdbus_command = (
            f"qdbus org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript '{full_script}'"
        )
        subprocess.run(qdbus_command, shell=True, check=True, capture_output=True, text=True)

    @staticmethod
    def _set_wallpaper_gnome_spanned(path_map: Dict[str, str], monitors: List[Monitor], style_name: str):
        """
        Creates a single spanned wallpaper for GNOME/fallback.
        """
        physical_monitors = sorted(monitors, key=lambda m: m.x)
        
        total_width = sum(m.width for m in physical_monitors)
        max_height = max(m.height for m in physical_monitors)
        
        if total_width == 0 or max_height == 0:
            raise ValueError(f"Invalid monitor dimensions (Total Width: {total_width}, Max Height: {max_height}).")
            
        spanned_image = Image.new('RGB', (total_width, max_height))
        current_x = 0
        
        # --- Iterate by PHYSICAL monitor order ---
        for monitor in physical_monitors:
            system_index = next((i for i, sys_mon in enumerate(monitors) if sys_mon.x == monitor.x and sys_mon.y == monitor.y and sys_mon.width == monitor.width and sys_mon.height == monitor.height), -1)
            
            if system_index == -1:
                print(f"Warning: Could not map physical monitor {monitor.name} back to system index.")
                current_x += monitor.width
                continue

            monitor_id = str(system_index)
            path = path_map.get(monitor_id)

            if path: 
                try:
                    img = Image.open(path)
                    img = img.resize((monitor.width, monitor.height), Image.Resampling.LANCZOS)
                    spanned_image.paste(img, (current_x, 0))
                except FileNotFoundError:
                    print(f"Warning: Image not found at {path}. Skipping for monitor {monitor_id}.")
                except Exception as e:
                    print(f"Warning: Could not process image {path}. Skipping. Error: {e}")
            
            current_x += monitor.width

        home_dir = os.path.expanduser('~')
        save_path = os.path.join(home_dir, ".spanned_wallpaper.jpg")
        spanned_image.save(save_path, "JPEG", quality=95)
        file_uri = f"file://{save_path}"

        subprocess.run(
            ["gsettings", "set", "org.gnome.desktop.background", "picture-options", "spanned"],
            check=True, capture_output=True, text=True
        )
        subprocess.run(
            ["gsettings", "set", "org.gnome.desktop.background", "picture-uri", file_uri],
            check=True, capture_output=True, text=True
        )
        subprocess.run(
            ["gsettings", "set", "org.gnome.desktop.background", "picture-uri-dark", file_uri],
            check=True, capture_output=True, text=True
        )

    @staticmethod
    def apply_wallpaper(path_map: Dict[str, str], monitors: List[Monitor], style_name: str):
        """
        Applies wallpaper based on the OS and the selected style.
        """
        system = platform.system()
        
        if system == "Windows":
            # Use the per-monitor method if COM is available, otherwise fall back.
            if COM_AVAILABLE:
                WallpaperManager._set_wallpaper_windows_multi(path_map, monitors, style_name)
            else:
                if not monitors:
                    raise ValueError("No monitors found.")
                
                # Determine path for primary monitor (or first available path)
                primary_monitor = next((m for m in monitors if m.is_primary), monitors[0])
                primary_index = monitors.index(primary_monitor)
                path_to_set = path_map.get(str(primary_index))
                
                if not path_to_set:
                    path_to_set = next((p for p in path_map.values() if p), None)
                    
                if not path_to_set:
                    raise ValueError("No valid image path provided for Windows.")
                    
                WallpaperManager._set_wallpaper_windows_single(path_to_set, style_name)
                
        elif system == "Linux":
            # --- Linux Implementation ---
            try:
                # Try KDE qdbus method first
                subprocess.run(["which", "qdbus"], check=True, capture_output=True) 
                WallpaperManager._set_wallpaper_kde(path_map, len(monitors), style_name)
                
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

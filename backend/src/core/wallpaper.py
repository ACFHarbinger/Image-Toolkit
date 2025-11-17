import ctypes
import platform
import subprocess

from pathlib import Path
from typing import Dict, List
from screeninfo import Monitor
from ..utils.definitions import WALLPAPER_STYLES

# Global Definitions to prevent Pylance "not defined" errors when comtypes is not imported
DesktopWallpaperCOM = None
COM_AVAILABLE = False

# Conditionally import comtypes and winreg only on Windows
if platform.system() == "Windows":
    import winreg
    try:
        import comtypes

        from comtypes import IUnknown, GUID, COMMETHOD, HRESULT, POINTER
        from ctypes.wintypes import LPCWSTR, UINT, LPWSTR
        from ctypes import pointer
        
        # Define the IDesktopWallpaper COM interface and its wrapper
        class DesktopWallpaperCOM:
            """
            Wrapper for the IDesktopWallpaper COM interface.
            """
            # IID for IDesktopWallpaper
            _iid_ = GUID('{B92B56A9-8B55-4E14-9A89-0199BBB6F93B}')
            
            # COM Class Definition
            class IDesktopWallpaper(IUnknown):
                _iid_ = DesktopWallpaperCOM._iid_
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
                    # Other IDesktopWallpaper methods are omitted for brevity
                ]
                
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
            
            # CLSID for DesktopWallpaper
            class_id = GUID('{C2CF3110-460E-4fc1-B9D0-8A1C0C9CC4BD}')
            
            @classmethod
            def get_instance(cls):
                """Initializes and returns the IDesktopWallpaper instance."""
                return comtypes.CoCreateInstance(cls.class_id, interface=cls.IDesktopWallpaper)

        # Set a flag indicating the COM interface is available
        COM_AVAILABLE = True
    except ImportError:
        # Fallback if comtypes is not installed
        COM_AVAILABLE = False
        print("Warning: 'comtypes' library not found. Falling back to single-wallpaper Windows API.")


class WallpaperManager:
    """
    A static class for handling OS-specific wallpaper setting logic.
    """

    @staticmethod
    def _set_wallpaper_windows_multi(path_map: Dict[str, str], monitors: List[Monitor], style_name: str):
        """
        Sets per-monitor wallpaper for Windows using the IDesktopWallpaper COM interface.
        
        :param path_map: Dictionary mapping system monitor index (str) to image path.
        :param monitors: List of Monitor objects in SYSTEM order.
        :param style_name: The descriptive name of the style (currently ignored, defaults to fill/fit).
        """
        if not DesktopWallpaperCOM:
            raise ImportError("The 'comtypes' library is required for multi-monitor support on Windows.")

        # Set the style using the old registry method (affects all monitors globally)
        # NOTE: IDesktopWallpaper doesn't easily expose SetPosition or SetPosition (style)
        # So we use the old method to set the global style, which the new per-monitor API respects.
        # We will use the 'Fill' style as the best fit for per-monitor.
        style_values = WALLPAPER_STYLES["Windows"].get("Fill", WALLPAPER_STYLES["Windows"]["Fill"])
        wallpaper_style_reg, tile_wallpaper_reg = style_values

        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                 "Control Panel\\Desktop", 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, "WallpaperStyle", 0, winreg.REG_SZ, wallpaper_style_reg) 
            winreg.SetValueEx(key, "TileWallpaper", 0, winreg.REG_SZ, tile_wallpaper_reg) 
            winreg.CloseKey(key)

            # --- Use COM Interface for Per-Monitor Assignment ---
            desktop_wallpaper = DesktopWallpaperCOM.get_instance()
            monitor_count = desktop_wallpaper.GetMonitorDevicePathCount()

            if len(monitors) != monitor_count:
                # Sanity check, should ideally match
                print(f"Warning: screeninfo found {len(monitors)} monitors, COM found {monitor_count}.")

            for i in range(monitor_count):
                # 1. Get the system monitor ID (DevicePath) from the COM interface
                monitor_id_path = desktop_wallpaper.GetMonitorDevicePathAt(i)
                
                # 2. Map the COM index (i) to the path from our path_map (which uses System Index 'i')
                # Since the path_map uses the system index (0, 1, 2...), we use 'i' to look up the path.
                path = path_map.get(str(i)) 

                if path and Path(path).exists():
                    # 3. Apply the image path to the specific monitor ID
                    resolved_path = str(Path(path).resolve())
                    desktop_wallpaper.SetWallpaper(monitor_id_path, resolved_path)
                    print(f"Set wallpaper for Monitor Index {i} ({monitor_id_path}) to {resolved_path}")
                elif str(i) in path_map:
                    print(f"Skipping monitor {i}: Image path not found or invalid.")

            # Note: IDesktopWallpaper handles the necessary refresh automatically.
            
        except Exception as e:
            raise RuntimeError(f"Error setting multi-monitor Windows wallpaper via COM: {e}")


    @staticmethod
    def _set_wallpaper_windows_single(image_path: str, style_name: str):
        """
        Original single-monitor method (kept as a functional fallback).
        """
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
            
            ctypes.windll.user32.SystemParametersInfoW(
                SPI_SETDESKWALLPAPER, 
                0, 
                save_path, 
                SPIF_UPDATEINIFILE | SPIF_SENDWININICHANGE
            )
        except Exception as e:
            raise RuntimeError(f"Error setting Windows single wallpaper: {e}")
            
    # --- Existing Linux/KDE/GNOME methods remain unchanged ---
    @staticmethod
    def _set_wallpaper_kde(path_map: Dict[str, str], num_monitors: int, style_name: str):
        # ... (implementation remains the same)
        pass # Placeholder for brevity

    @staticmethod
    def _set_wallpaper_gnome_spanned(path_map: Dict[str, str], monitors: List[Monitor], style_name: str):
        # ... (implementation remains the same)
        pass # Placeholder for brevity


    @staticmethod
    def apply_wallpaper(path_map: Dict[str, str], monitors: List[Monitor], style_name: str):
        """
        Applies wallpaper based on the OS and the selected style.
        Now uses IDesktopWallpaper for per-monitor assignment on Windows.
        """
        system = platform.system()
        
        if system == "Windows":
            # --- NEW Windows Implementation (Multi-Monitor Support) ---
            if DesktopWallpaperCOM:
                # Use the per-monitor method
                WallpaperManager._set_wallpaper_windows_multi(path_map, monitors, style_name)
            else:
                # Fallback to single wallpaper if comtypes isn't installed
                if not monitors:
                    raise ValueError("No monitors found.")
                primary_monitor = next((m for m in monitors if m.is_primary), monitors[0])
                primary_index = monitors.index(primary_monitor)
                path_to_set = path_map.get(str(primary_index))
                
                if not path_to_set:
                    path_to_set = next((p for p in path_map.values() if p), None)
                    
                if not path_to_set:
                    raise ValueError("No valid image path provided for Windows.")
                    
                WallpaperManager._set_wallpaper_windows_single(path_to_set, style_name)
                
        elif system == "Linux":
            # --- Linux Implementation (Remains the same) ---
            try:
                # Try KDE qdbus6 method first
                subprocess.run(["which", "qdbus"], check=True, capture_output=True)
                WallpaperManager._set_wallpaper_kde(path_map, len(monitors), style_name)
                
            except (FileNotFoundError, subprocess.CalledError):
                # Fallback to GNOME (spanned) method
                try:
                    WallpaperManager._set_wallpaper_gnome_spanned(path_map, monitors, style_name)
                except Exception as e:
                    raise RuntimeError(f"GNOME (fallback) method failed: {e}")
            except Exception as e:
                raise RuntimeError(f"KDE method failed: {e}")
            
        else:
            raise NotImplementedError(f"Wallpaper setting for {system} is not supported.")

"""Windows-specific wallpaper setting (registry + IDesktopWallpaper COM)."""

import ctypes
import platform
from pathlib import Path
from typing import Dict, List

from screeninfo import Monitor

from backend.src.constants import SUPPORTED_VIDEO_FORMATS, WALLPAPER_STYLES
from backend.src.constants.core import COM_AVAILABLE, DESKTOPWALLPAPER_CLSID, IDESKTOPWALLPAPER_IID

# Global Definitions for COM components

# Conditionally import comtypes and winreg only on Windows
if platform.system() == "Windows":
    import winreg

    try:
        from ctypes import pointer
        from ctypes.wintypes import LPCWSTR, LPWSTR, UINT

        import comtypes
        from comtypes import COMMETHOD, GUID, HRESULT, POINTER, IUnknown

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
        pass


class _WindowsWallpaperMixin:
    """Windows registry/COM wallpaper setting methods for ``WallpaperManager``."""

    COM_AVAILABLE = COM_AVAILABLE

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
            raise RuntimeError(f"Error setting Windows solid color wallpaper: {e}") from e

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
            raise RuntimeError(f"Error setting Windows single wallpaper: {e}") from e

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
            raise RuntimeError(f"Windows multi-monitor failed: {e}") from e


__all__ = ["_WindowsWallpaperMixin", "COM_AVAILABLE"]

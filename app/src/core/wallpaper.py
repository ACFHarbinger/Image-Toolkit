import os
import ctypes
import platform
import subprocess

from PIL import Image
from pathlib import Path
from typing import Dict, List
from screeninfo import Monitor

# Conditionally import winreg only on Windows
if platform.system() == "Windows":
    import winreg


class WallpaperManager:
    """
    A static class for handling OS-specific wallpaper setting logic.
    """

    @staticmethod
    def _set_wallpaper_windows(image_path: str):
        """
        Sets the wallpaper for Windows.
        Uses 'Fill' (4) style.
        
        :param image_path: The absolute path to the image to set.
        """
        # Ensure path is absolute and resolved
        save_path = str(Path(image_path).resolve())

        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                 "Control Panel\\Desktop", 0, winreg.KEY_SET_VALUE)
            # Set style to "Fill" (4)
            winreg.SetValueEx(key, "WallpaperStyle", 0, winreg.REG_SZ, "4") 
            # Ensure tiling is off
            winreg.SetValueEx(key, "TileWallpaper", 0, winreg.REG_SZ, "0") 
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
            raise RuntimeError(f"Error setting Windows wallpaper: {e}")

    @staticmethod
    def _set_wallpaper_kde(path_map: Dict[str, str], num_monitors: int):
        """
        Sets per-monitor wallpaper for KDE Plasma using qdbus6.
        
        :param path_map: Dictionary mapping system monitor index (str) to image path.
        :param num_monitors: Total number of system monitors.
        """
        script_parts = []
        
        # --- Iterate by system monitor index (i = 0, 1, 2...) ---
        for i in range(num_monitors):
            monitor_id = str(i)
            
            # Get the path from our 'path_map'
            path = path_map.get(monitor_id)
            
            if path:
                file_uri = f"file://{Path(path).resolve()}"
                # Apply path to the correct desktop index
                # FillMode 1 is "Scaled, Keep Proportions" (aka "Fill")
                script_parts.append(
                    f'd = desktops()[{i}]; d.currentConfigGroup = Array("Wallpaper", "org.kde.image", "General"); d.writeConfig("Image", "{file_uri}"); d.writeConfig("FillMode", 1);'
                )
        
        if not script_parts:
            # No paths were provided for any monitor
            print("KDE: No image paths provided to set.")
            return

        full_script = "".join(script_parts)
        full_script += "d.reloadConfig();" # Reload config after all changes

        qdbus_command = (
            f"qdbus6 org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript '{full_script}'"
        )

        # Run the command
        subprocess.run(qdbus_command, shell=True, check=True, capture_output=True, text=True)

    @staticmethod
    def _set_wallpaper_gnome_spanned(path_map: Dict[str, str], monitors: List[Monitor]):
        """
        Creates a single spanned wallpaper for GNOME/fallback.
        Stitches images together based on physical monitor layout.
        
        :param path_map: Dictionary mapping system monitor index (str) to image path.
        :param monitors: List of Monitor objects in SYSTEM order.
        """
        # Sort monitors by physical x-position for correct spanning
        physical_monitors = sorted(monitors, key=lambda m: m.x)
        
        total_width = sum(m.width for m in physical_monitors)
        max_height = max(m.height for m in physical_monitors)
        
        if total_width == 0 or max_height == 0:
            raise ValueError(f"Invalid monitor dimensions (Total Width: {total_width}, Max Height: {max_height}).")
            
        spanned_image = Image.new('RGB', (total_width, max_height))
        
        current_x = 0
        
        # --- Iterate by PHYSICAL monitor order ---
        for monitor in physical_monitors:
            
            # Find this monitor's SYSTEM index to get the correct path
            system_index = -1
            for i, sys_mon in enumerate(monitors):
                # Compare key properties to find the match
                if (sys_mon.x == monitor.x and sys_mon.y == monitor.y and
                    sys_mon.width == monitor.width and sys_mon.height == monitor.height):
                    system_index = i
                    break
            
            if system_index == -1:
                # This should not happen if monitors list is correct
                print(f"Warning: Could not map physical monitor {monitor.name} back to system index.")
                current_x += monitor.width
                continue

            monitor_id = str(system_index)
            
            # Get path from our 'path_map' using the SYSTEM index
            path = path_map.get(monitor_id)

            if path: # Only add if a path is set
                try:
                    img = Image.open(path)
                    # Resize image to fit the specific monitor
                    img = img.resize((monitor.width, monitor.height), Image.Resampling.LANCZOS)
                    spanned_image.paste(img, (current_x, 0))
                except FileNotFoundError:
                    print(f"Warning: Image not found at {path}. Skipping for monitor {monitor_id}.")
                except Exception as e:
                    print(f"Warning: Could not process image {path}. Skipping. Error: {e}")
            
            current_x += monitor.width

        # Save the combined image to a temporary location in the user's home dir
        home_dir = os.path.expanduser('~')
        save_path = os.path.join(home_dir, ".spanned_wallpaper.jpg")
        spanned_image.save(save_path, "JPEG", quality=95)
        file_uri = f"file://{save_path}"

        # Set the wallpaper using gsettings
        subprocess.run(
            ["gsettings", "set", "org.gnome.desktop.background", "picture-options", "spanned"],
            check=True, capture_output=True, text=True
        )
        subprocess.run(
            ["gsettings", "set", "org.gnome.desktop.background", "picture-uri", file_uri],
            check=True, capture_output=True, text=True
        )
        # Set for dark mode as well to ensure it applies
        subprocess.run(
            ["gsettings", "set", "org.gnome.desktop.background", "picture-uri-dark", file_uri],
            check=True, capture_output=True, text=True
        )

    @staticmethod
    def apply_wallpaper(path_map: Dict[str, str], monitors: List[Monitor]):
        """
        Applies wallpaper based on the OS. This is the main function
        to be called from other modules.
        
        :param path_map: A dictionary mapping monitor SYSTEM INDEX (str) to image path (str).
        :param monitors: The list of Monitor objects in SYSTEM order.
        """
        system = platform.system()
        
        if system == "Windows":
            # --- Windows Implementation (Single Wallpaper) ---
            if not monitors:
                raise ValueError("No monitors found.")
                
            # Find the primary monitor's index
            primary_monitor = next((m for m in monitors if m.is_primary), monitors[0])
            primary_index = monitors.index(primary_monitor)
            primary_monitor_id = str(primary_index)
             
            # Get path for the primary monitor
            path_to_set = path_map.get(primary_monitor_id)

            if not path_to_set:
                 # Fallback: just grab the first available path if primary isn't set
                 path_to_set = next((p for p in path_map.values() if p), None)

            if not path_to_set:
                raise ValueError("No valid image path provided for Windows.")
            
            WallpaperManager._set_wallpaper_windows(path_to_set)
                
        elif system == "Linux":
            # --- Linux Implementation ---
            try:
                # Try KDE qdbus6 method first
                subprocess.run(["which", "qdbus6"], check=True, capture_output=True)
                WallpaperManager._set_wallpaper_kde(path_map, len(monitors))
                
            except (FileNotFoundError, subprocess.CalledProcessError):
                # Fallback to GNOME (spanned) method
                try:
                    WallpaperManager._set_wallpaper_gnome_spanned(path_map, monitors)
                except Exception as e:
                    raise RuntimeError(f"GNOME (fallback) method failed: {e}")
            except Exception as e:
                raise RuntimeError(f"KDE method failed: {e}")
            
        else:
            raise NotImplementedError(f"Wallpaper setting for {system} is not supported.")

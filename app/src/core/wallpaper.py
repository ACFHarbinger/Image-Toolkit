import subprocess
import os
from screeninfo import get_monitors
from PIL import Image

def set_multi_monitor_wallpaper(image_paths):
    """
    Detects monitor layout and creates a single spanned wallpaper.
    
    :param image_paths: A list of paths to the images. The number of paths
                        should match the number of detected monitors.
    """
    print("Detecting monitors...")
    monitors = sorted(get_monitors(), key=lambda m: m.x)
    
    if len(image_paths) != len(monitors):
        print(f"Error: Found {len(monitors)} monitors but received {len(image_paths)} image paths.")
        print("Please provide one image path for each monitor.")
        return

    print(f"Found {len(monitors)} monitors.")
    images = []
    
    # --- 1. Load and Resize Images ---
    # We'll resize all images to match their respective monitor's resolution.
    # We also find the max height for our canvas.
    total_width = 0
    max_height = 0
    
    for i, monitor in enumerate(monitors):
        print(f"  - Monitor {i+1}: {monitor.width}x{monitor.height} at ({monitor.x}, {monitor.y})")
        
        try:
            img = Image.open(image_paths[i])
            # Resize image to fit monitor, maintaining aspect ratio (cover)
            img = img.resize((monitor.width, monitor.height), Image.Resampling.LANCZOS)
            images.append(img)
            
            total_width += monitor.width
            if monitor.height > max_height:
                max_height = monitor.height
        except FileNotFoundError:
            print(f"Error: Image not found at '{image_paths[i]}'")
            return
        except Exception as e:
            print(f"Error processing image {image_paths[i]}: {e}")
            return

    print(f"\nCreating combined image (Total Size: {total_width}x{max_height})...")

    # --- 2. Create and Paste Images ---
    # Create a new blank image with the total dimensions
    spanned_image = Image.new('RGB', (total_width, max_height))
    
    current_x = 0
    for i, img in enumerate(images):
        monitor = monitors[i]
        # Calculate vertical position (for monitors not aligned at the top)
        # This simple script assumes a horizontal layout, so y_offset is 0.
        # For more complex layouts, you'd use monitor.y
        y_offset = 0 
        
        spanned_image.paste(img, (current_x, y_offset))
        current_x += img.width

    # --- 3. Save and Set Wallpaper ---
    try:
        # Save the combined image to a temporary location
        home_dir = os.path.expanduser('~')
        save_path = os.path.join(home_dir, ".spanned_wallpaper.jpg")
        spanned_image.save(save_path)
        print(f"Saved combined wallpaper to {save_path}")

        # Set the wallpaper using gsettings
        file_uri = f"file://{save_path}"
        
        # Tell GNOME to "span" the image
        subprocess.run([
            "gsettings", "set", "org.gnome.desktop.background", "picture-options", "'spanned'"
        ], check=True, shell=True) # Using shell=True for the quotes

        # Set the image itself
        subprocess.run([
            "gsettings", "set", "org.gnome.desktop.background", "picture-uri", file_uri
        ], check=True)
        
        # Set for dark mode as well, to be safe
        subprocess.run([
            "gsettings", "set", "org.gnome.desktop.background", "picture-uri-dark", file_uri
        ], check=True)

        print("\nSuccess! Wallpaper has been updated.")

    except subprocess.CalledProcessError as e:
        print(f"\nError setting wallpaper with gsettings: {e}")
    except Exception as e:
        print(f"\nAn error occurred: {e}")


# --- HOW TO USE ---
if __name__ == "__main__":
    # IMPORTANT: Change these paths to your wallpapers
    # List them from left to right based on your display layout
    wallpaper_for_monitor_1 = "/home/user/Pictures/wallpapers/image-left.jpg"
    wallpaper_for_monitor_2 = "/home/user/Pictures/wallpapers/image-right.jpg"
    
    # Add more paths if you have more monitors
    # wallpaper_for_monitor_3 = "/path/to/your/image3.jpg"
    
    paths = [
        wallpaper_for_monitor_1,
        wallpaper_for_monitor_2
    ]
    
    set_multi_monitor_wallpaper(paths)

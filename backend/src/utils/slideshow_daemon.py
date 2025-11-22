import time
import json
import sys

from pathlib import Path
from backend.src.core import WallpaperManager 
from screeninfo import get_monitors

CONFIG_PATH = Path.home() / ".myapp_slideshow_config.json"

def load_config():
    if not CONFIG_PATH.exists():
        return None
    try:
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    except Exception:
        return None

def get_next_image(queue, current_path):
    """Logic to determine the next image in the list."""
    if not queue:
        return None
    
    try:
        idx = queue.index(current_path)
        next_idx = (idx + 1) % len(queue)
    except ValueError:
        next_idx = 0
        
    return queue[next_idx]

def main():
    print("Slideshow Daemon Started.")
    
    while True:
        config = load_config()
        
        # If config is deleted or disabled, stop the daemon
        if not config or not config.get('running', False):
            print("Slideshow disabled. Exiting.")
            sys.exit(0)

        interval = config.get('interval_seconds', 300)
        style = config.get('style', 'Fill')
        monitor_queues = config.get('monitor_queues', {})
        current_paths = config.get('current_paths', {}) # State tracking
        
        # 1. Detect Monitors
        try:
            monitors = get_monitors()
        except Exception:
            # If screeninfo fails in headless, wait and retry
            time.sleep(10)
            continue

        # 2. Calculate New Paths
        new_paths_map = {}
        state_changed = False

        for i, monitor in enumerate(monitors):
            mid = str(i) # Assuming simple index based ID like in your app
            queue = monitor_queues.get(mid, [])
            current_img = current_paths.get(mid)

            if queue:
                next_img = get_next_image(queue, current_img)
                if next_img:
                    new_paths_map[mid] = next_img
                    if next_img != current_img:
                        current_paths[mid] = next_img
                        state_changed = True
            else:
                # Keep existing if no queue
                new_paths_map[mid] = current_img

        # 3. Apply Wallpaper
        if state_changed:
            try:
                # Reusing your existing static method
                WallpaperManager.apply_wallpaper(new_paths_map, monitors, style)
                
                # Update config file with new current state so we resume correctly next time
                config['current_paths'] = current_paths
                with open(CONFIG_PATH, 'w') as f:
                    json.dump(config, f)
                    
            except Exception as e:
                print(f"Error setting wallpaper: {e}")

        # 4. Sleep
        time.sleep(interval)

if __name__ == "__main__":
    main()

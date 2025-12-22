import sys
import time
import shutil
import json

from pathlib import Path

# --- FIX: Ensure we can import backend packages ---
current_dir = Path(__file__).resolve().parent  # backend/src/utils
backend_src_dir = current_dir.parent  # backend/src
backend_dir = backend_src_dir.parent  # backend
project_root = backend_dir.parent  # Image-Toolkit
sys.path.append(str(project_root))

import logging

# Set up file-based logging
log_file = project_root / "daemon.log"
logging.basicConfig(
    filename=log_file,
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logging.info(f"Slideshow daemon initializing from: {current_dir}")
logging.info(f"Project root added to path: {project_root}")


from screeninfo import get_monitors
from backend.src.core import WallpaperManager
from backend.src.utils.definitions import DAEMON_CONFIG_PATH


def load_config():
    if not DAEMON_CONFIG_PATH.exists():
        return None
    try:
        with open(DAEMON_CONFIG_PATH, "r") as f:
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
    logging.info("Slideshow Daemon Started.")

    # Detect qdbus
    qdbus = "qdbus"
    if shutil.which("qdbus6"):
        qdbus = "qdbus6"
    elif shutil.which("qdbus-qt5"):
        qdbus = "qdbus-qt5"
    
    logging.info(f"Using qdbus executable: {qdbus}")


    while True:
        config = load_config()

        # If config is deleted or disabled, stop the daemon
        if not config or not config.get("running", False):
            print("Slideshow disabled. Exiting.")
            sys.exit(0)

        interval = config.get("interval_seconds", 300)
        style = config.get("style", "Fill")
        monitor_queues = config.get("monitor_queues", {})
        current_paths = config.get("current_paths", {})  # State tracking

        # 1. Detect Monitors Count from Config
        # We rely on the keys in monitor_queues (e.g., "0", "1", "2") to know how many monitors we are managing.
        # This avoids using screeninfo in the daemon, ensuring we respect variables set by the main GUI.
        monitor_ids = sorted(monitor_queues.keys(), key=lambda x: int(x) if x.isdigit() else x)
        
        # Calculate num_monitors based on the highest ID found (assuming 0-indexed contiguous IDs)
        if monitor_ids:
            try:
                num_monitors = max(int(mid) for mid in monitor_ids if mid.isdigit()) + 1
            except ValueError:
                num_monitors = len(monitor_ids)
        else:
            num_monitors = 0

        logging.info(f"Managing {num_monitors} monitors with IDs: {monitor_ids}")
        current_paths = config.get("current_paths", {})
        
        # Ensure we have entries for all managed monitors
        for mid in monitor_ids:
            if mid not in current_paths:
                current_paths[mid] = ""

        # 2. Update Wallpaper for each managed monitor
        new_paths_map = {}
        state_changed = False

        for mid in monitor_ids:
            queue = monitor_queues.get(mid, [])
            current_img = current_paths.get(mid)
            
            if not queue:
                # No queue for this monitor, keep current or skip
                continue

            # Determine next image
            next_img = get_next_image(queue, current_img)
            
            if next_img != current_img:
                current_paths[mid] = next_img
                state_changed = True
            
            # Add to map for application
            new_paths_map[mid] = next_img
        
        # 3. Apply if changed
        if state_changed:
            try:
                # We pass geometries to help KDE mapping
                geometries = config.get("monitor_geometries", {})
                logging.info(f"Applying wallpaper to {num_monitors} monitors. Map: {new_paths_map}")
                WallpaperManager.apply_wallpaper(new_paths_map, num_monitors, style, qdbus, geometries)

                # Update config file with new current state so we resume correctly next time
                config["current_paths"] = current_paths
                with open(DAEMON_CONFIG_PATH, "w") as f:
                    json.dump(config, f)
                logging.info(f"Wallpaper updated for {len(new_paths_map)} monitors.")

            except Exception as e:
                print(f"Error setting wallpaper: {e}")
                logging.error(f"Error setting wallpaper: {e}", exc_info=True)

        # 4. Sleep
        time.sleep(interval)


if __name__ == "__main__":
    main()

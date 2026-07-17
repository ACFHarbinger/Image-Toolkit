"""slideshow_daemon.py — background wallpaper slideshow process.

Launched as a detached subprocess by SystemDisplaySubTab.  Reads the shared
JSON config file written by the GUI, then advances wallpapers on each monitor
at the configured interval using the correct DE mechanism:

  • KDE Plasma  → PlasmaShell.evaluateScript via qdbus / dbus-python
  • GNOME / Cinnamon / etc. → gsettings org.gnome.desktop.background

The daemon is *entirely* Python (no C++ background thread) so it correctly
inherits the user's session environment (DBUS_SESSION_BUS_ADDRESS, DISPLAY,
WAYLAND_DISPLAY) and can reach the running desktop compositor.
"""

import json
import logging
import os
import random
import shutil
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# sys.path – make sure we can import 'base' and the backend package
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parents[4]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from screeninfo import Monitor  # noqa: E402

from backend.src.core.wallpaper import WallpaperManager  # noqa: E402

# ---------------------------------------------------------------------------
# Logging – writes to the same log file the GUI "View Logs" button opens
# ---------------------------------------------------------------------------
LOG_PATH = Path.home() / ".image-toolkit" / "logs" / "slideshow_daemon.log"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=str(LOG_PATH),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

DAEMON_CONFIG_PATH = Path.home() / ".image-toolkit" / ".slideshow_config.json"

# ---------------------------------------------------------------------------
# DE detection
# ---------------------------------------------------------------------------

def _detect_de() -> str:
    """Return 'kde', 'gnome', or 'unknown'."""
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    session = os.environ.get("XDG_SESSION_DESKTOP", "").lower()
    if "kde" in desktop or "plasma" in desktop or "kde" in session:
        return "kde"
    if "gnome" in desktop or "gnome" in session or "cinnamon" in desktop:
        return "gnome"
    return "unknown"


def _find_qdbus() -> str | None:
    for name in ("qdbus6", "qdbus-qt6", "qdbus", "qdbus-qt5"):
        if shutil.which(name):
            return name
    return None


# ---------------------------------------------------------------------------
# Wallpaper setters
# ---------------------------------------------------------------------------

def _parse_monitors(config: dict) -> list:
    monitors = []
    for mid_str, geom in sorted(config.get("monitor_geometries", {}).items(), key=lambda x: int(x[0])):
        monitors.append(Monitor(
            x=geom.get("x", 0),
            y=geom.get("y", 0),
            width=geom.get("width", 1920),
            height=geom.get("height", 1080),
            name=f"Monitor {mid_str}"
        ))
    return monitors


# ---------------------------------------------------------------------------
# Main daemon loop
# ---------------------------------------------------------------------------

def run() -> None:  # noqa: C901
    logging.info("Slideshow daemon started.")
    logging.info(
        f"DBUS_SESSION_BUS_ADDRESS={os.environ.get('DBUS_SESSION_BUS_ADDRESS', '<not set>')} | "
        f"DISPLAY={os.environ.get('DISPLAY', '<not set>')} | "
        f"WAYLAND_DISPLAY={os.environ.get('WAYLAND_DISPLAY', '<not set>')} | "
        f"XDG_CURRENT_DESKTOP={os.environ.get('XDG_CURRENT_DESKTOP', '<not set>')}"
    )

    de = _detect_de()
    qdbus = _find_qdbus() if de == "kde" else None
    logging.info(f"Detected DE: {de!r}  |  qdbus: {qdbus!r}")

    if not DAEMON_CONFIG_PATH.exists():
        logging.error(f"Config not found: {DAEMON_CONFIG_PATH}")
        return

    try:
        with open(DAEMON_CONFIG_PATH) as f:
            config = json.load(f)
    except Exception as exc:
        logging.error(f"Failed to read config: {exc}")
        return

    if not config.get("running"):
        logging.info("Config says not running – exiting.")
        return

    # ---- Build per-monitor playback state --------------------------------
    interval: int = int(config.get("interval_seconds", 30))
    playback_order: str = config.get("playback_order", "Sequential")
    raw_style: str = config.get("style", "Scaled, Keep Proportions")

    monitor_queues: dict = config.get("monitor_queues", {})

    # per-monitor: current index, shuffled list
    monitor_state: dict[str, dict] = {}
    for mid, paths in monitor_queues.items():
        if not paths:
            continue
        ordered = list(paths)
        if playback_order == "Random":
            random.shuffle(ordered)
        monitor_state[mid] = {"paths": ordered, "index": 0}

    if not monitor_state:
        logging.warning("No non-empty monitor queues found – exiting.")
        return

    logging.info(
        f"Starting slideshow: interval={interval}s, style={raw_style!r}, "
        f"monitors={list(monitor_state.keys())}"
    )

    # Set first wallpaper on each monitor immediately
    monitors = _parse_monitors(config)
    _apply_all(monitor_state, de, qdbus, raw_style, monitors)
    _update_config_paths(monitor_state, interval)

    elapsed = 0.0
    last_config_mtime = DAEMON_CONFIG_PATH.stat().st_mtime

    try:
        while True:
            time.sleep(1.0)
            elapsed += 1.0

            # ---- Detect config changes (GUI edited settings) --------------
            try:
                mtime = DAEMON_CONFIG_PATH.stat().st_mtime
            except OSError:
                mtime = last_config_mtime

            if mtime != last_config_mtime:
                last_config_mtime = mtime
                try:
                    with open(DAEMON_CONFIG_PATH) as f:
                        gui_cfg = json.load(f)
                except Exception as exc:
                    logging.warning(f"Config re-read failed: {exc}")
                    gui_cfg = {}

                if not gui_cfg.get("running"):
                    logging.info("Stop requested via config file.")
                    break

                monitors = _parse_monitors(gui_cfg)

                new_interval = int(gui_cfg.get("interval_seconds", interval))
                new_order = gui_cfg.get("playback_order", playback_order)
                new_style = gui_cfg.get("style", raw_style)
                new_queues = gui_cfg.get("monitor_queues", {})

                if new_interval != interval:
                    logging.info(f"Interval changed: {interval} → {new_interval}s")
                    interval = new_interval
                    elapsed = 0.0  # reset timer

                if new_order != playback_order or new_queues != monitor_queues:
                    logging.info("Queue/order changed – rebuilding monitor state.")
                    monitor_queues = new_queues
                    playback_order = new_order
                    monitor_state = {}
                    for mid, paths in monitor_queues.items():
                        if not paths:
                            continue
                        ordered = list(paths)
                        if playback_order == "Random":
                            random.shuffle(ordered)
                        monitor_state[mid] = {"paths": ordered, "index": 0}
                    if not monitor_state:
                        logging.warning("All queues are now empty – stopping.")
                        break
                    elapsed = interval  # advance immediately

                raw_style = new_style

            # ---- Advance wallpapers when timer fires ----------------------
            if elapsed >= interval:
                elapsed = 0.0
                _advance_all(monitor_state)
                _apply_all(monitor_state, de, qdbus, raw_style, monitors)
                _update_config_paths(monitor_state, interval)

    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt received.")
    finally:
        try:
            if DAEMON_CONFIG_PATH.exists():
                with open(DAEMON_CONFIG_PATH) as f:
                    final = json.load(f)
                final["running"] = False
                with open(DAEMON_CONFIG_PATH, "w") as f:
                    json.dump(final, f, indent=4)
        except Exception:
            pass
        logging.info("Slideshow daemon stopped.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _advance_all(monitor_state: dict) -> None:
    for _mid, state in monitor_state.items():
        state["index"] = (state["index"] + 1) % len(state["paths"])


def _apply_all(monitor_state: dict, de: str, qdbus: str | None, raw_style: str, monitors: list) -> None:
    path_map = {}
    for mid, state in monitor_state.items():
        path = state["paths"][state["index"]]
        logging.info(f"Monitor {mid}: → {Path(path).name}  (index {state['index']})")
        path_map[str(mid)] = path

    if not path_map:
        return

    try:
        WallpaperManager.apply_wallpaper(path_map, monitors, raw_style, qdbus)
    except Exception as exc:
        logging.error(f"Failed to apply wallpaper: {exc}")


def _update_config_paths(monitor_state: dict, interval: int) -> None:
    """Write current_paths back into the config so the GUI countdown/display updates."""
    try:
        with open(DAEMON_CONFIG_PATH) as f:
            cfg = json.load(f)
        current_paths = cfg.get("current_paths", {})
        if not isinstance(current_paths, dict):
            current_paths = {}
        for mid, state in monitor_state.items():
            current_paths[mid] = state["paths"][state["index"]]
        cfg["current_paths"] = current_paths
        cfg["last_change_timestamp"] = int(time.time())
        with open(DAEMON_CONFIG_PATH, "w") as f:
            json.dump(cfg, f, indent=4)
    except Exception as exc:
        logging.warning(f"Could not update config paths: {exc}")


if __name__ == "__main__":
    run()

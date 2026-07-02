"""Per-monitor graph-based wallpaper slideshow.

The actual scheduling (advancing through the queue on each entry's own
duration) runs natively in ``base.run_monitor_slideshow`` -- see
``base/src/utils/monitor_slideshow.cpp``. That native scheduler owns a
background ``std::thread`` independent of the Python GIL/Qt event loop, so
it keeps ticking reliably whether this module is used:

* in-process, by the GUI itself, for the "in-app slideshow" (the native
  thread lives inside the GUI process; call start()/stop()/status() directly
  from monitor_display_subtab.py), or
* in the detached daemon subprocess launched by the GUI for "Slideshow
  Daemon" mode (this module's __main__ entry point below), where it mirrors
  status back into MONITOR_SLIDESHOW_DAEMON_CONFIG_PATH so the GUI process
  (which cannot see the daemon process's native thread state) can poll it.

Either way, this module is the only thing that talks to the native
scheduler and to WallpaperManager -- the GUI never calls `base` directly.
"""

import atexit
import json
import logging
import sys
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

_ROOT = Path(__file__).resolve().parents[4]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import base  # noqa: E402  Native extension (base/src/utils/monitor_slideshow.cpp)

from backend.src.constants import (  # noqa: E402
    MONITOR_SLIDESHOW_DAEMON_CONFIG_PATH,
    SUPPORTED_VIDEO_FORMATS,
)
from backend.src.core import WallpaperManager  # noqa: E402
from backend.src.core.wallpaper import find_qdbus_binary  # noqa: E402

# Safety net: the native scheduler holds a reference to the Python
# apply_callback closure between start() and stop(). If the process exits
# without an explicit stop() (e.g. a caller forgets, or the app is closed
# some other way), that reference would otherwise be released during C++
# static destruction *after* the interpreter has finalized -- which
# crashes (PyThreadState_Get without the GIL). Always stop() on exit.
atexit.register(lambda: base.run_monitor_slideshow("stop"))

DEFAULT_ENTRY_DURATION_SEC = 30.0


def _video_runtime(path: str) -> Optional[float]:
    try:
        import cv2  # type: ignore

        cap = cv2.VideoCapture(path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        cap.release()
        if fps and fps > 0:
            return frames / fps
    except Exception:
        pass
    return None


def resolve_duration(path: str, configured: Optional[float]) -> float:
    """A configured (non-null, positive) duration always wins. Otherwise a
    video entry uses its own runtime, and everything else falls back to the
    default duration."""
    if configured and configured > 0:
        return float(configured)
    if str(path).lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS)):
        dur = _video_runtime(path)
        if dur:
            return dur
    return DEFAULT_ENTRY_DURATION_SEC


def make_apply_callback(
    monitors: list,
    style: str,
    video_style: str,
    other_paths: Optional[Dict[str, str]] = None,
    qdbus: Optional[str] = None,
) -> Callable[[str, str, int], None]:
    """Build the callback handed to base.run_monitor_slideshow("start", ...).

    Invoked from the native scheduler thread (GIL held) each time it
    advances; applies the wallpaper via the existing WallpaperManager logic
    (KDE qdbus scripts, Windows COM, GNOME gsettings) rather than
    re-implementing per-OS wallpaper application natively.
    """
    qdbus = qdbus if qdbus is not None else find_qdbus_binary()
    other_paths = dict(other_paths or {})

    def _apply(monitor_id: str, path: str, index: int) -> None:
        style_to_use = (
            f"SmartVideoWallpaper::{video_style}"
            if str(path).lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS))
            else style
        )
        path_map = dict(other_paths)
        path_map[monitor_id] = path
        try:
            WallpaperManager.apply_wallpaper(path_map, monitors, style_to_use, qdbus)
        except Exception as e:
            logging.error(f"Monitor {monitor_id}: failed to apply '{path}': {e}")

    return _apply


def start(
    monitor_id: str,
    queue: List[str],
    durations: List[Optional[float]],
    *,
    monitors: list,
    style: str = "Fill",
    video_style: str = "Scaled and Cropped",
    other_paths: Optional[Dict[str, str]] = None,
    qdbus: Optional[str] = None,
) -> str:
    resolved = [resolve_duration(p, d) for p, d in zip(queue, durations)]
    config = {"monitor_id": monitor_id, "queue": list(queue), "durations": resolved}
    callback = make_apply_callback(monitors, style, video_style, other_paths, qdbus)
    return base.run_monitor_slideshow("start", json.dumps(config), callback)


def stop() -> str:
    return base.run_monitor_slideshow("stop")


def status() -> Optional[dict]:
    try:
        return json.loads(base.run_monitor_slideshow("status"))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Detached daemon subprocess entry point ("Start Slideshow Daemon" in the
# GUI). Reads the GUI-written config file, starts the native scheduler, then
# polls the same file for a stop request while mirroring live status back
# into it for the GUI to read.
# ---------------------------------------------------------------------------

LOG_PATH = Path.home() / ".image-toolkit" / "logs" / "monitor_slideshow_daemon.log"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=str(LOG_PATH),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)


def _load_gui_config() -> Optional[dict]:
    try:
        with open(MONITOR_SLIDESHOW_DAEMON_CONFIG_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return None


def _write_gui_config(config: dict) -> None:
    try:
        with open(MONITOR_SLIDESHOW_DAEMON_CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        logging.error(f"Failed to persist daemon state: {e}")


def _monitors_from_geometries(geoms: Dict[str, dict]):
    from screeninfo import Monitor

    return [
        Monitor(
            x=geoms[mid]["x"],
            y=geoms[mid]["y"],
            width=geoms[mid]["width"],
            height=geoms[mid]["height"],
            name=f"Display {mid}",
            is_primary=(mid == "0"),
        )
        for mid in sorted(geoms.keys(), key=lambda k: int(k))
    ]


def run():
    config = _load_gui_config()
    if not config or not config.get("running"):
        logging.info("No active config on startup; exiting.")
        return

    logging.info(f"Monitor slideshow daemon started for monitor {config.get('monitor_id')}.")
    start(
        config["monitor_id"],
        config.get("queue", []),
        config.get("durations", []),
        monitors=_monitors_from_geometries(config.get("monitor_geometries", {})),
        style=config.get("style", "Fill"),
        video_style=config.get("video_style", "Scaled and Cropped"),
        other_paths=config.get("other_current_paths", {}),
    )

    try:
        while True:
            time.sleep(1.0)
            gui_cfg = _load_gui_config()
            if not gui_cfg or not gui_cfg.get("running"):
                logging.info("Stop requested.")
                break

            native_status = status() or {}
            gui_cfg.update(
                {
                    "current_index": native_status.get("current_index", gui_cfg.get("current_index", -1)),
                    "current_duration": native_status.get("current_duration"),
                    "last_change_timestamp": native_status.get("last_change_timestamp", 0),
                }
            )
            _write_gui_config(gui_cfg)
    finally:
        stop()
        logging.info("Monitor slideshow daemon stopped.")


if __name__ == "__main__":
    run()

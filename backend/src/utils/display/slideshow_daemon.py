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
import subprocess
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

from backend.src.constants import SUPPORTED_VIDEO_FORMATS  # noqa: E402
from backend.src.core.wallpaper import WallpaperManager  # noqa: E402
from backend.src.constants.paths import DAEMON_CONFIG_PATH
from backend.src.constants.utils import DISPLAY_LOG_PATH, PID_PATH, _VIDEO_DURATION_CACHE


def _is_video(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in SUPPORTED_VIDEO_FORMATS


def _get_video_duration(path: str) -> float | None:
    """Return video duration in seconds via ffprobe, falling back to cv2."""
    if path in _VIDEO_DURATION_CACHE:
        return _VIDEO_DURATION_CACHE[path]
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=10,
        )
        val = result.stdout.strip()
        if val:
            dur = float(val)
            _VIDEO_DURATION_CACHE[path] = dur
            return dur
    except Exception:
        pass
    try:
        import cv2  # type: ignore

        cap = cv2.VideoCapture(path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        cap.release()
        if fps > 0:
            dur = frames / fps
            _VIDEO_DURATION_CACHE[path] = dur
            return dur
    except Exception:
        pass
    return None

# ---------------------------------------------------------------------------
# Logging – writes to the same log file the GUI "View Logs" button opens
# ---------------------------------------------------------------------------
DISPLAY_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=str(DISPLAY_LOG_PATH),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)


def _atomic_write_json(path: Path, data: dict) -> None:
    """Write JSON via a temp file + rename so concurrent readers never see a
    truncated/partial file (plain open(path, "w") is not atomic)."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w") as f:
        json.dump(data, f, indent=4)
    os.replace(tmp, path)


def _other_daemon_alive() -> int | None:
    """PID of another live slideshow_daemon process, if any. Guards against
    duplicate daemons racing on the same config file (which can clobber each
    other's interval/flag settings mid-flight)."""
    try:
        pid = int(PID_PATH.read_text().strip())
        if pid == os.getpid():
            return None
        os.kill(pid, 0)
    except Exception:
        return None
    return pid


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

def _runtime_interval(monitor_state: dict, fallback: int) -> int:
    """Longest duration among the currently active videos across monitors,
    so no monitor's video gets cut off early. Falls back to the configured
    fixed interval when nothing currently showing is a video (or duration
    can't be determined)."""
    durations = []
    for state in monitor_state.values():
        path = state["paths"][state["index"]]
        if _is_video(path):
            dur = _get_video_duration(path)
            if dur:
                durations.append(dur)
    if not durations:
        return fallback
    return max(1, round(max(durations)))


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

    existing_pid = _other_daemon_alive()
    if existing_pid:
        logging.warning(
            f"Another slideshow daemon is already running (PID {existing_pid}) "
            "-- exiting to avoid two processes racing on the same config."
        )
        return
    try:
        PID_PATH.parent.mkdir(parents=True, exist_ok=True)
        PID_PATH.write_text(str(os.getpid()))
    except Exception as exc:
        logging.warning(f"Could not write PID file: {exc}")

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
    use_video_runtime: bool = bool(config.get("use_video_runtime_interval", False))

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
    if use_video_runtime:
        interval = _runtime_interval(monitor_state, interval)
        logging.info(f"Video-runtime interval: {interval}s")
    _update_config_paths(monitor_state, interval, use_video_runtime)

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

                decision = apply_runtime_config(
                    gui_cfg,
                    interval=interval,
                    style=raw_style,
                    use_video_runtime=use_video_runtime,
                )
                if decision["stop"]:
                    logging.info("Stop requested via config file.")
                    break

                monitors = _parse_monitors(gui_cfg)
                if decision["reset_elapsed"]:
                    logging.info(
                        f"Interval changed: {interval} → {decision['interval']}s"
                    )
                    elapsed = 0.0
                interval = decision["interval"]
                use_video_runtime = decision["use_video_runtime"]
                raw_style = decision["style"]
                # monitor_queues / playback_order stay locked at start time.

            # ---- Advance wallpapers when timer fires ----------------------
            if elapsed >= interval:
                elapsed = 0.0
                _advance_all(monitor_state)
                _apply_all(monitor_state, de, qdbus, raw_style, monitors)
                if use_video_runtime:
                    interval = _runtime_interval(monitor_state, interval)
                    logging.info(f"Video-runtime interval: {interval}s")
                _update_config_paths(monitor_state, interval, use_video_runtime)

    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt received.")
    finally:
        try:
            if DAEMON_CONFIG_PATH.exists():
                with open(DAEMON_CONFIG_PATH) as f:
                    final = json.load(f)
                final["running"] = False
                _atomic_write_json(DAEMON_CONFIG_PATH, final)
        except Exception:
            pass
        try:
            if PID_PATH.exists() and PID_PATH.read_text().strip() == str(os.getpid()):
                PID_PATH.unlink()
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


def apply_runtime_config(
    gui_cfg: dict,
    *,
    interval: int,
    style: str,
    use_video_runtime: bool,
) -> dict:
    """Apply a GUI config rewrite without touching the locked start-time queue.

    Restarting the app (or loading another profile) must not change what an
    already-running daemon is showing. Only an explicit stop (``running``
    cleared) ends the loop. Interval/style may still update.
    """
    if not gui_cfg or not gui_cfg.get("running"):
        return {"stop": True, "interval": interval, "style": style, "use_video_runtime": use_video_runtime}
    try:
        new_interval = int(gui_cfg.get("interval_seconds", interval))
    except (TypeError, ValueError):
        new_interval = interval
    new_style = gui_cfg.get("style", style) or style
    new_video = bool(gui_cfg.get("use_video_runtime_interval", use_video_runtime))
    return {
        "stop": False,
        "interval": new_interval,
        "style": new_style,
        "use_video_runtime": new_video,
        "reset_elapsed": (not new_video and new_interval != interval),
    }


def _update_config_paths(monitor_state: dict, interval: int, use_video_runtime: bool) -> None:
    """Write current_paths + the live interval back into the config so the
    GUI countdown/display and any config reload stay in sync with what the
    daemon is actually doing (video-runtime mode recomputes interval every
    cycle, so the on-disk value must track it, not just the original fixed
    setting)."""
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
        cfg["interval_seconds"] = interval
        cfg["use_video_runtime_interval"] = use_video_runtime
        _atomic_write_json(DAEMON_CONFIG_PATH, cfg)
    except Exception as exc:
        logging.warning(f"Could not update config paths: {exc}")


if __name__ == "__main__":
    run()

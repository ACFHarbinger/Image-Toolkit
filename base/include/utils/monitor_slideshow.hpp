#pragma once
// ---------------------------------------------------------------------------
// base/include/utils/monitor_slideshow.hpp
// Per-monitor, per-entry-duration wallpaper slideshow scheduler.
//
// Unlike utils::slideshow (a single shared-interval, GNOME-only rotation),
// this drives ONE monitor's Wallpaper Queue where every entry carries its
// own duration (fixed seconds, or full video runtime -- resolved on the
// Python side before the queue/durations are handed in). The actual OS
// wallpaper-setting call is delegated back to Python via `apply_callback`
// (invoked as apply_callback(monitor_id: str, path: str, index: int)) so
// this reuses the existing WallpaperManager logic (KDE qdbus scripts,
// Windows COM, GNOME gsettings) instead of re-implementing it natively.
//
// The scheduling loop itself runs on a native std::thread, independent of
// the Python GIL/event loop, so it keeps ticking reliably whether it's
// running in-process (GUI's "in-app slideshow") or in the detached daemon
// subprocess.
// ---------------------------------------------------------------------------
#include <string>
#include <pybind11/pybind11.h>

namespace base::utils::monitor_slideshow {

// action: "start" | "stop" | "status" | "configure" | "next"
// config_json (used by "start"/"configure"):
//   {
//     "monitor_id": "0",
//     "queue": ["path1", "path2", ...],
//     "durations": [12.5, 30.0, ...]   // parallel to "queue", seconds
//   }
// apply_callback (used by "start"): a Python callable
//   apply_callback(monitor_id: str, path: str, index: int) -> None
//   invoked (with the GIL held) each time the scheduler advances, including
//   immediately on start.
// Returns a JSON status string.
std::string run_monitor_slideshow(
    const std::string& action,
    const std::string& config_json,
    pybind11::object apply_callback);

void register_monitor_slideshow(pybind11::module_& m);

} // namespace base::utils::monitor_slideshow

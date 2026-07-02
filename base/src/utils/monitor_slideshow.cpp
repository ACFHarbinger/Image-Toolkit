// ---------------------------------------------------------------------------
// base/src/utils/monitor_slideshow.cpp — per-monitor graph wallpaper
// slideshow scheduler.
//
// Companion to utils/slideshow.cpp, but scoped to a single monitor's
// Wallpaper Queue where each entry has its own duration, instead of one
// interval shared by a fixed image list. See monitor_slideshow.hpp for the
// full rationale (native timing thread + Python-side wallpaper apply).
// ---------------------------------------------------------------------------
#include "utils/monitor_slideshow.hpp"

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <atomic>
#include <chrono>
#include <condition_variable>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

namespace py = pybind11;

#include <nlohmann/json.hpp>
using json = nlohmann::json;

namespace base::utils::monitor_slideshow {

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

struct Entry {
    std::string path;
    double      duration_seconds{30.0};
};

struct Config {
    std::string        monitor_id{"0"};
    std::vector<Entry> queue;
};

static Config load_config(const std::string& json_str) {
    Config cfg;
    if (json_str.empty()) return cfg;
    auto data = json::parse(json_str, nullptr, false);
    if (data.is_discarded()) return cfg;

    cfg.monitor_id = data.value("monitor_id", std::string("0"));

    if (data.contains("queue") && data["queue"].is_array()) {
        json durations = json::array();
        if (data.contains("durations") && data["durations"].is_array())
            durations = data["durations"];

        size_t i = 0;
        for (const auto& p : data["queue"]) {
            if (p.is_string()) {
                double dur = 30.0;
                if (i < durations.size() && durations[i].is_number())
                    dur = durations[i].get<double>();
                cfg.queue.push_back(Entry{p.get<std::string>(), dur});
            }
            ++i;
        }
    }
    return cfg;
}

// ---------------------------------------------------------------------------
// Global daemon state (process-lifetime singleton, one active monitor)
// ---------------------------------------------------------------------------

static std::atomic<bool>      g_running{false};
static std::atomic<long long> g_index{-1};
static std::atomic<double>    g_current_duration{0.0};
static std::atomic<long long> g_last_change_ts{0};
static std::mutex             g_mutex;
static std::condition_variable g_cv;
static std::thread            g_thread;
static Config                 g_config;
static py::function           g_callback;

static long long now_epoch() {
    return std::chrono::duration_cast<std::chrono::seconds>(
               std::chrono::system_clock::now().time_since_epoch())
        .count();
}

static void invoke_callback(const std::string& monitor_id,
                             const std::string& path, long long index) {
    py::gil_scoped_acquire gil;
    if (!g_callback) return;
    try {
        g_callback(monitor_id, path, index);
    } catch (const py::error_already_set&) {
        // A Python-side apply failure must not kill the native scheduler
        // thread; the next tick will simply try the following entry.
    }
}

static void loop() {
    while (g_running.load()) {
        Config cfg;
        {
            std::lock_guard<std::mutex> lock(g_mutex);
            cfg = g_config;
        }

        if (cfg.queue.empty()) {
            std::unique_lock<std::mutex> wait_lock(g_mutex);
            g_cv.wait_for(wait_lock, std::chrono::seconds(1),
                          [] { return !g_running.load(); });
            continue;
        }

        long long idx =
            (g_index.load() + 1) % static_cast<long long>(cfg.queue.size());
        const Entry& entry = cfg.queue[static_cast<size_t>(idx)];

        invoke_callback(cfg.monitor_id, entry.path, idx);

        if (!g_running.load()) break;

        g_index.store(idx);
        double dur = entry.duration_seconds > 0 ? entry.duration_seconds : 30.0;
        g_current_duration.store(dur);
        g_last_change_ts.store(now_epoch());

        std::unique_lock<std::mutex> wait_lock(g_mutex);
        g_cv.wait_for(wait_lock, std::chrono::duration<double>(dur),
                      [] { return !g_running.load(); });
    }
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

std::string run_monitor_slideshow(const std::string& action,
                                   const std::string& config_json,
                                   py::object apply_callback) {
    if (action == "start") {
        if (g_running.load()) return "{\"status\":\"already_running\"}";

        {
            std::lock_guard<std::mutex> lock(g_mutex);
            g_config = load_config(config_json);
            g_index.store(-1);
            g_current_duration.store(0.0);
            g_last_change_ts.store(0);
            if (!apply_callback.is_none())
                g_callback = apply_callback.cast<py::function>();
        }

        if (g_thread.joinable()) g_thread.join();
        g_running.store(true);
        g_thread = std::thread(loop);

        return "{\"status\":\"started\"}";
    }

    if (action == "stop") {
        g_running.store(false);
        g_cv.notify_all();
        if (g_thread.joinable()) {
            py::gil_scoped_release rel;  // callback may be waiting on the GIL
            g_thread.join();
        }
        {
            // Drop the stored Python callback now, with the GIL held (we're
            // executing inside a pybind11-called function, so it is).
            // g_callback is a namespace-scope static: if it still holds a
            // reference to a Python object when the interpreter finalizes,
            // its destructor runs during C++ static destruction *without*
            // the GIL and crashes the process (PyThreadState_Get fatal
            // error). Releasing it on every explicit stop() keeps no
            // lingering py::object alive past normal shutdown.
            std::lock_guard<std::mutex> lock(g_mutex);
            g_callback = py::function();
        }
        return "{\"status\":\"stopped\"}";
    }

    if (action == "status") {
        std::lock_guard<std::mutex> lock(g_mutex);
        json resp;
        resp["running"]              = g_running.load();
        resp["monitor_id"]           = g_config.monitor_id;
        resp["current_index"]        = g_index.load();
        resp["count"]                = g_config.queue.size();
        resp["current_duration"]     = g_current_duration.load();
        resp["last_change_timestamp"] = g_last_change_ts.load();
        return resp.dump();
    }

    if (action == "configure") {
        std::lock_guard<std::mutex> lock(g_mutex);
        g_config = load_config(config_json);
        g_cv.notify_all();
        return "{\"status\":\"configured\"}";
    }

    if (action == "next") {
        if (!g_running.load()) return "{\"status\":\"not_running\"}";
        g_cv.notify_all();  // wakes the loop's wait_for early -> immediate advance
        return "{\"status\":\"advancing\"}";
    }

    throw std::invalid_argument(
        "run_monitor_slideshow: unknown action '" + action + "'. "
        "Valid: start | stop | status | configure | next");
}

} // namespace base::utils::monitor_slideshow

// ---------------------------------------------------------------------------
// pybind11 registration
// ---------------------------------------------------------------------------

namespace base::utils {

void register_monitor_slideshow(py::module_& m) {
    m.def("run_monitor_slideshow",
        [](const std::string& action, py::object config_json_obj,
           py::object apply_callback) -> std::string {
            std::string config_json;
            if (!config_json_obj.is_none()) {
                if (py::isinstance<py::str>(config_json_obj)) {
                    config_json = config_json_obj.cast<std::string>();
                } else {
                    py::object json_module = py::module_::import("json");
                    config_json =
                        json_module.attr("dumps")(config_json_obj).cast<std::string>();
                }
            }
            return base::utils::monitor_slideshow::run_monitor_slideshow(
                action, config_json, apply_callback);
        },
        py::arg("action"), py::arg("config_json") = py::none(),
        py::arg("apply_callback") = py::none(),
        R"doc(
Control the per-monitor graph slideshow scheduler (native background
thread, process-lifetime singleton -- one active monitor at a time).

Parameters
----------
action         : str   One of: "start", "stop", "status", "configure", "next"
config_json    : str | dict   Used by "start" and "configure":
                 {
                   "monitor_id": "0",
                   "queue": [...],
                   "durations": [...]   # parallel to "queue", seconds
                 }
apply_callback : callable   Used by "start":
                 apply_callback(monitor_id: str, path: str, index: int) -> None
                 Invoked (GIL held) each time the scheduler advances,
                 including immediately on start.

Returns
-------
str   JSON status string.
        )doc");
}

} // namespace base::utils

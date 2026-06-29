// ---------------------------------------------------------------------------
// base/src/utils/slideshow.cpp — background slideshow daemon
// Phase 10 of Rust→C++ migration.
// Manages a background std::thread that advances wallpapers on a timer.
// Actions: start / stop / status / next / configure
// Config persisted at ~/.image-toolkit/.slideshow_config.json
// ---------------------------------------------------------------------------
#include "base/utils/slideshow.hpp"

#include <pybind11/pybind11.h>

#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

namespace py = pybind11;
namespace fs = std::filesystem;

// nlohmann/json for config persistence
#include <nlohmann/json.hpp>
using json = nlohmann::json;

namespace base::utils::slideshow {

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

struct Config {
    std::vector<std::string> image_paths;
    int                      interval_seconds{30};
    bool                     shuffle{false};
    std::string              wallpaper_mode{"zoom"};
};

static fs::path default_config_path() {
    const char* home = std::getenv("HOME");
    if (!home) home = ".";
    return fs::path(home) / ".image-toolkit" / ".slideshow_config.json";
}

static Config load_config(const std::string& json_str) {
    Config cfg;
    if (json_str.empty()) return cfg;
    auto data = json::parse(json_str, nullptr, false);
    if (data.is_discarded()) return cfg;

    if (data.contains("image_paths") && data["image_paths"].is_array())
        for (const auto& p : data["image_paths"])
            if (p.is_string()) cfg.image_paths.push_back(p.get<std::string>());

    cfg.interval_seconds = data.value("interval_seconds", 30);
    cfg.shuffle          = data.value("shuffle", false);
    cfg.wallpaper_mode   = data.value("wallpaper_mode", "zoom");
    return cfg;
}

static void save_config(const Config& cfg, const fs::path& path) {
    fs::create_directories(path.parent_path());
    json data;
    data["image_paths"]      = cfg.image_paths;
    data["interval_seconds"] = cfg.interval_seconds;
    data["shuffle"]          = cfg.shuffle;
    data["wallpaper_mode"]   = cfg.wallpaper_mode;
    std::ofstream f(path);
    f << data.dump(2);
}

// ---------------------------------------------------------------------------
// Global daemon state (process-lifetime singleton)
// ---------------------------------------------------------------------------

static std::atomic<bool>  g_running{false};
static std::atomic<size_t> g_index{0};
static std::mutex          g_mutex;
static std::condition_variable g_cv;
static std::thread         g_thread;
static Config              g_config;

static void set_wallpaper(const std::string& path, const std::string& mode) {
    // Reuse the same gsettings approach as wallpaper.cpp
    std::string uri = "file://" + path;
    std::string cmd_uri =
        "gsettings set org.gnome.desktop.background picture-uri '" + uri + "'";
    std::string cmd_mode =
        "gsettings set org.gnome.desktop.background picture-options '" + mode + "'";
    std::system(cmd_uri.c_str());
    std::system(cmd_mode.c_str());
}

static void daemon_loop() {
    while (g_running.load()) {
        std::unique_lock<std::mutex> lock(g_mutex);
        const Config& cfg = g_config;
        if (cfg.image_paths.empty()) {
            lock.unlock();
            std::this_thread::sleep_for(std::chrono::seconds(1));
            continue;
        }

        size_t idx = g_index.load() % cfg.image_paths.size();
        std::string img = cfg.image_paths[idx];
        std::string wmode = cfg.wallpaper_mode;
        int interval = cfg.interval_seconds;
        lock.unlock();

        if (fs::exists(img)) set_wallpaper(img, wmode);

        g_index.fetch_add(1);

        // Wait for interval or wakeup signal
        std::unique_lock<std::mutex> wait_lock(g_mutex);
        g_cv.wait_for(wait_lock,
                      std::chrono::seconds(interval),
                      []{ return !g_running.load(); });
    }
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

std::string run_slideshow_daemon(
    const std::string& action,
    const std::string& config_json)
{
    if (action == "start") {
        if (g_running.load()) return "{\"status\":\"already_running\"}";

        {
            std::lock_guard<std::mutex> lock(g_mutex);
            g_config = load_config(config_json);
            g_index.store(0);
        }

        // Persist config
        save_config(g_config, default_config_path());

        g_running.store(true);
        if (g_thread.joinable()) g_thread.join();
        g_thread = std::thread(daemon_loop);

        return "{\"status\":\"started\",\"interval_seconds\":"
               + std::to_string(g_config.interval_seconds) + "}";
    }

    if (action == "stop") {
        g_running.store(false);
        g_cv.notify_all();
        if (g_thread.joinable()) g_thread.join();
        return "{\"status\":\"stopped\"}";
    }

    if (action == "status") {
        bool running = g_running.load();
        size_t idx   = g_index.load();
        std::lock_guard<std::mutex> lock(g_mutex);
        json resp;
        resp["status"]  = running ? "running" : "stopped";
        resp["index"]   = idx;
        resp["count"]   = g_config.image_paths.size();
        resp["interval_seconds"] = g_config.interval_seconds;
        if (!g_config.image_paths.empty())
            resp["current"] = g_config.image_paths[idx % g_config.image_paths.size()];
        return resp.dump();
    }

    if (action == "next") {
        if (!g_running.load()) return "{\"status\":\"not_running\"}";
        g_index.fetch_add(1);
        g_cv.notify_all(); // wake loop to apply immediately
        return "{\"status\":\"advanced\",\"index\":" + std::to_string(g_index.load()) + "}";
    }

    if (action == "configure") {
        std::lock_guard<std::mutex> lock(g_mutex);
        Config new_cfg = load_config(config_json);
        if (!new_cfg.image_paths.empty()) g_config.image_paths = new_cfg.image_paths;
        if (new_cfg.interval_seconds > 0)  g_config.interval_seconds = new_cfg.interval_seconds;
        g_config.shuffle       = new_cfg.shuffle;
        g_config.wallpaper_mode = new_cfg.wallpaper_mode;
        save_config(g_config, default_config_path());
        g_cv.notify_all();
        return "{\"status\":\"configured\"}";
    }

    throw std::invalid_argument(
        "run_slideshow_daemon: unknown action '" + action + "'. "
        "Valid: start | stop | status | next | configure");
}

} // namespace base::utils::slideshow

// ---------------------------------------------------------------------------
// pybind11 registration
// ---------------------------------------------------------------------------

void register_slideshow(py::module_& m) {
    m.def("run_slideshow_daemon",
        [](const std::string& action, const std::string& config_json) -> std::string {
            py::gil_scoped_release rel;
            return base::utils::slideshow::run_slideshow_daemon(action, config_json);
        },
        py::arg("action"), py::arg("config_json") = std::string{},
        R"doc(
Control the slideshow daemon (background thread, process-lifetime singleton).

Parameters
----------
action      : str   One of: "start", "stop", "status", "next", "configure"
config_json : str   JSON config (used by "start" and "configure"):
                    {
                      "image_paths": [...],
                      "interval_seconds": 30,
                      "shuffle": false,
                      "wallpaper_mode": "zoom"
                    }
Returns
-------
str   JSON status string.
        )doc");
}

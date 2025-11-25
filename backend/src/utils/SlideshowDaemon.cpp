#include <SlideshowDaemon.hpp>
#include <iostream>
#include <fstream>
#include <thread>
#include <chrono>
#include <vector>
#include <filesystem>
#include <algorithm>
#include <map>
#include <cstdlib>

// JSON Support
#include <nlohmann/json.hpp>
using json = nlohmann::json;

// Core dependency
#include "../core/WallpaperManager.hpp" 

namespace fs = std::filesystem;

// --- Platform Specific Includes for Monitor Detection ---
#ifdef _WIN32
#include <windows.h>
#elif __linux__
#include <X11/Xlib.h>
#include <X11/extensions/Xrandr.h>
#undef None // X11 defines None, which can conflict with other libs
#endif

// --- Helper: Get Home Directory ---
std::string getHomePath() {
#ifdef _WIN32
    const char* home = std::getenv("USERPROFILE");
#else
    const char* home = std::getenv("HOME");
#endif
    return home ? std::string(home) : ".";
}

const fs::path CONFIG_PATH = fs::path(getHomePath()) / ".myapp_slideshow_config.json";

// --- Helper: Get System Monitors (Mimics screeninfo) ---
#ifdef _WIN32
BOOL CALLBACK MonitorEnumCallback(HMONITOR hMonitor, HDC hdcMonitor, LPRECT lprcMonitor, LPARAM dwData) {
    auto* monitors = reinterpret_cast<std::vector<Monitor>*>(dwData);
    MONITORINFOEXA mi;
    mi.cbSize = sizeof(mi);
    if (GetMonitorInfoA(hMonitor, &mi)) {
        Monitor m;
        m.x = mi.rcMonitor.left;
        m.y = mi.rcMonitor.top;
        m.width = mi.rcMonitor.right - mi.rcMonitor.left;
        m.height = mi.rcMonitor.bottom - mi.rcMonitor.top;
        m.isPrimary = (mi.dwFlags & MONITORINFOF_PRIMARY);
        m.name = mi.szDevice;
        monitors->push_back(m);
    }
    return TRUE;
}

std::vector<Monitor> getSystemMonitors() {
    std::vector<Monitor> monitors;
    EnumDisplayMonitors(NULL, NULL, MonitorEnumCallback, (LPARAM)&monitors);
    return monitors;
}

#elif __linux__
std::vector<Monitor> getSystemMonitors() {
    std::vector<Monitor> monitors;
    Display* display = XOpenDisplay(NULL);
    if (!display) return monitors;

    Window root = DefaultRootWindow(display);
    
    // Try XRandR 1.5 first
    int nmonitors = 0;
    XRRMonitorInfo* info = XRRGetMonitors(display, root, true, &nmonitors);
    
    if (info) {
        for (int i = 0; i < nmonitors; i++) {
            Monitor m;
            m.x = info[i].x;
            m.y = info[i].y;
            m.width = info[i].width;
            m.height = info[i].height;
            m.isPrimary = info[i].primary;
            
            // Convert Atom name to String
            char* name = XGetAtomName(display, info[i].name);
            m.name = name ? std::string(name) : "Monitor" + std::to_string(i);
            if (name) XFree(name);
            
            monitors.push_back(m);
        }
        XRRFreeMonitors(info);
    }
    
    XCloseDisplay(display);
    return monitors;
}
#else
std::vector<Monitor> getSystemMonitors() { return {}; } // Unsupported OS
#endif

// --- Config Management ---
json loadConfig() {
    if (!fs::exists(CONFIG_PATH)) return nullptr;
    try {
        std::ifstream f(CONFIG_PATH);
        return json::parse(f);
    } catch (...) {
        return nullptr;
    }
}

std::string getNextImage(const std::vector<std::string>& queue, const std::string& current_path) {
    if (queue.empty()) return "";
    
    auto it = std::find(queue.begin(), queue.end(), current_path);
    size_t next_idx = 0;
    
    if (it != queue.end()) {
        size_t idx = std::distance(queue.begin(), it);
        next_idx = (idx + 1) % queue.size();
    }
    
    return queue[next_idx];
}

int main(int argc, char* argv[]) {
#ifdef _WIN32
    // Initialize COM for Windows WallpaperManager
    CoInitializeEx(NULL, COINIT_APARTMENTTHREADED);
#endif

    std::cout << "Slideshow Daemon Started." << std::endl;

    while (true) {
        json config = loadConfig();

        // Check if running flag is true
        if (config.is_null() || !config.value("running", false)) {
            std::cout << "Slideshow disabled. Exiting." << std::endl;
            return 0;
        }

        int interval = config.value("interval_seconds", 300);
        std::string style = config.value("style", "Fill");
        
        // Maps "0" -> ["path1", "path2"]
        json j_queues = config.value("monitor_queues", json::object());
        // Maps "0" -> "current_path"
        std::map<std::string, std::string> current_paths;
        if (config.contains("current_paths")) {
            current_paths = config["current_paths"].get<std::map<std::string, std::string>>();
        }

        // 1. Detect Monitors
        std::vector<Monitor> monitors;
        try {
            monitors = getSystemMonitors();
        } catch (...) {
            std::this_thread::sleep_for(std::chrono::seconds(10));
            continue;
        }

        if (monitors.empty()) {
             // Wait and retry if headless environment detected momentarily
             std::this_thread::sleep_for(std::chrono::seconds(10));
             continue;
        }

        // 2. Calculate New Paths
        std::map<std::string, std::string> new_paths_map;
        bool state_changed = false;

        for (size_t i = 0; i < monitors.size(); ++i) {
            std::string mid = std::to_string(i);
            std::vector<std::string> queue;
            
            if (j_queues.contains(mid)) {
                queue = j_queues[mid].get<std::vector<std::string>>();
            }

            std::string current_img = current_paths.count(mid) ? current_paths[mid] : "";

            if (!queue.empty()) {
                std::string next_img = getNextImage(queue, current_img);
                if (!next_img.empty()) {
                    new_paths_map[mid] = next_img;
                    if (next_img != current_img) {
                        current_paths[mid] = next_img;
                        state_changed = true;
                    }
                }
            } else {
                // Keep existing if no queue
                new_paths_map[mid] = current_img;
            }
        }

        // 3. Apply Wallpaper
        if (state_changed) {
            try {
                WallpaperManager::applyWallpaper(new_paths_map, monitors, style);
                
                // Update Config
                config["current_paths"] = current_paths;
                std::ofstream out(CONFIG_PATH);
                out << config.dump(4);
            } catch (const std::exception& e) {
                std::cerr << "Error setting wallpaper: " << e.what() << std::endl;
            }
        }

        // 4. Sleep
        std::this_thread::sleep_for(std::chrono::seconds(interval));
    }

#ifdef _WIN32
    CoUninitialize();
#endif
    return 0;
}
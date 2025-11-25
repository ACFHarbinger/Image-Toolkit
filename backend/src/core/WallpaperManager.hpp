#pragma once

#include <string>
#include <map>
#include <vector>
#include <stdexcept>

// Mock structure for screeninfo.Monitor
struct Monitor {
    int x, y, width, height;
    bool isPrimary;
    std::string name;
};

class WallpaperManager {
public:
    // SolidColor is passed as the image path value in the map
    static void applyWallpaper(const std::map<std::string, std::string>& path_map, 
                               const std::vector<Monitor>& monitors, 
                               const std::string& style_name);

    static std::map<std::string, std::string> getCurrentSystemWallpaperPathKDE(int num_monitors);

private:
    // OS-Agnostic Helpers
    static void setSolidColor(const std::string& color_hex);

    // Windows Implementation
    #ifdef _WIN32
    static void setWallpaperWindowsMulti(const std::map<std::string, std::string>& path_map, 
                                         const std::vector<Monitor>& monitors, 
                                         const std::string& style_name);
    static void setWallpaperWindowsSingle(const std::string& image_path, const std::string& style_name);
    static void setSolidColorWindows(const std::string& color_hex);
    #endif

    // Linux Implementation
    #ifdef __linux__
    static void setWallpaperKDE(const std::map<std::string, std::string>& path_map, 
                                int num_monitors, 
                                const std::string& style_name);
    static void setWallpaperGnomeSpanned(const std::map<std::string, std::string>& path_map, 
                                         const std::vector<Monitor>& monitors, 
                                         const std::string& style_name);
    static void setSolidColorGnome(const std::string& color_hex);
    // Helper for executing shell commands (gsettings/qdbus)
    static std::string executeCommand(const std::string& command);
    #endif
};
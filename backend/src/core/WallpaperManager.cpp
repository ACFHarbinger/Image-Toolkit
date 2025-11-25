#include "WallpaperManager.hpp"
#include <iostream>
#include <sstream>
#include <fstream>
#include <algorithm>
#include <cmath>

#ifdef _WIN32
// Windows includes (ctypes, comtypes -> C++ COM)
#include <windows.h>
#include <shobjidl.h> // IDesktopWallpaper
#include <atlbase.h> // For COM smart pointers
#include <ShlObj.h> // IID_IDesktopWallpaper

// Helper to convert hex to RGB
std::tuple<int, int, int> hexToRgb(const std::string& hex) {
    std::string clean_hex = (hex[0] == '#') ? hex.substr(1) : hex;
    long value = std::stoul(clean_hex, nullptr, 16);
    int r = (value >> 16) & 0xFF;
    int g = (value >> 8) & 0xFF;
    int b = value & 0xFF;
    return {r, g, b};
}
#endif

#ifdef __linux__
// Linux includes
#include <cstdlib>
#include <regex>
#include <sys/stat.h>
#endif

// ================= OS-Agnostic Logic =================

void WallpaperManager::applyWallpaper(const std::map<std::string, std::string>& path_map, 
                                      const std::vector<Monitor>& monitors, 
                                      const std::string& style_name) {
    bool is_solid_color = (style_name == "SolidColor");
    
    if (is_solid_color) {
        setSolidColor(path_map.count("0") ? path_map.at("0") : "#000000");
        return;
    }

    // Image setting logic
    #ifdef _WIN32
    if (!monitors.empty() && monitors.size() > 1) {
        setWallpaperWindowsMulti(path_map, monitors, style_name);
    } else {
        std::string path_to_set = path_map.count("0") ? path_map.at("0") : path_map.begin()->second;
        setWallpaperWindowsSingle(path_to_set, style_name);
    }
    #elif __linux__
    try {
        executeCommand("which qdbus6"); // Check for KDE
        setWallpaperKDE(path_map, monitors.size(), style_name);
    } catch (...) {
        setWallpaperGnomeSpanned(path_map, monitors, style_name);
    }
    #else
    throw std::runtime_error("Unsupported operating system for wallpaper setting.");
    #endif
}

void WallpaperManager::setSolidColor(const std::string& color_hex) {
    #ifdef _WIN32
    setSolidColorWindows(color_hex);
    #elif __linux__
    try {
        executeCommand("which qdbus6"); // Try KDE first
        // KDE solid color implementation via qdbus (more complex, omitted for space)
        std::cerr << "KDE solid color setting not fully implemented in C++." << std::endl;
    } catch (...) {
        setSolidColorGnome(color_hex);
    }
    #else
    throw std::runtime_error("Unsupported OS for solid color setting.");
    #endif
}

// ================= Windows Implementation =================
#ifdef _WIN32

// Note: IDesktopWallpaper methods must be called after CoInitializeEx(NULL, COINIT_APARTMENTTHREADED)

void WallpaperManager::setSolidColorWindows(const std::string& color_hex) {
    auto [r, g, b] = hexToRgb(color_hex);
    
    // Set registry values
    HKEY keyDesktop, keyColors;
    if (RegOpenKeyEx(HKEY_CURRENT_USER, L"Control Panel\\Desktop", 0, KEY_SET_VALUE, &keyDesktop) == ERROR_SUCCESS) {
        RegSetValueEx(keyDesktop, L"WallpaperStyle", 0, REG_SZ, (const BYTE*)L"0", 2); 
        RegSetValueEx(keyDesktop, L"TileWallpaper", 0, REG_SZ, (const BYTE*)L"0", 2); 
        RegCloseKey(keyDesktop);
    }

    std::wstring color_str = std::to_wstring(r) + L" " + std::to_wstring(g) + L" " + std::to_wstring(b);
    if (RegOpenKeyEx(HKEY_CURRENT_USER, L"Control Panel\\Colors", 0, KEY_SET_VALUE, &keyColors) == ERROR_SUCCESS) {
        RegSetValueEx(keyColors, L"Background", 0, REG_SZ, (const BYTE*)color_str.c_str(), (DWORD)(color_str.length() * sizeof(wchar_t)));
        RegCloseKey(keyColors);
    }

    // Trigger update
    SystemParametersInfoW(SPI_SETDESKWALLPAPER, 0, NULL, SPIF_UPDATEINIFILE | SPIF_SENDWININICHANGE);
}

// Single/Multi implementations omitted for brevity but would follow COM/Registry patterns.
void WallpaperManager::setWallpaperWindowsSingle(const std::string& image_path, const std::string& style_name) {
    // Simplified: Requires mapping style_name to registry values.
    std::wstring wpath(image_path.begin(), image_path.end());
    SystemParametersInfoW(SPI_SETDESKWALLPAPER, 0, (PVOID)wpath.c_str(), SPIF_UPDATEINIFILE | SPIF_SENDWININICHANGE);
}

void WallpaperManager::setWallpaperWindowsMulti(const std::map<std::string, std::string>& path_map, 
                                                const std::vector<Monitor>& monitors, 
                                                const std::string& style_name) {
    // Requires complex IDesktopWallpaper COM interaction, similar to Python's COM code.
    std::cerr << "Windows multi-monitor support requires full COM implementation." << std::endl;
}

#endif // _WIN32


// ================= Linux Implementation =================
#ifdef __linux__

std::string WallpaperManager::executeCommand(const std::string& command) {
    std::string result;
    FILE* pipe = popen(command.c_str(), "r");
    if (!pipe) throw std::runtime_error("popen() failed!");
    char buffer[128];
    while (fgets(buffer, sizeof(buffer), pipe) != NULL) {
        result += buffer;
    }
    pclose(pipe);
    return result;
}

void WallpaperManager::setSolidColorGnome(const std::string& color_hex) {
    // gsettings set org.gnome.desktop.background picture-options 'none'
    // gsettings set org.gnome.desktop.background primary-color '#000000'
    executeCommand("gsettings set org.gnome.desktop.background picture-options 'none'");
    executeCommand("gsettings set org.gnome.desktop.background primary-color '" + color_hex + "'");
    executeCommand("gsettings set org.gnome.desktop.background color-shading-type 'solid'");
}

void WallpaperManager::setWallpaperKDE(const std::map<std::string, std::string>& path_map, 
                                        int num_monitors, 
                                        const std::string& style_name) {
    // KDE FillMode integer mapping needed (e.g., "Scaled" -> 1, "Fill" -> 6)
    int fill_mode = 6; // Default to Fill
    
    std::string script_parts;
    for (int i = 0; i < num_monitors; ++i) {
        if (path_map.count(std::to_string(i))) {
            std::string file_uri = "file://" + path_map.at(std::to_string(i));
            // Simplified qdbus command
            script_parts += "d = desktops()[" + std::to_string(i) + "]; d.currentConfigGroup = Array(\"Wallpaper\", \"org.kde.image\", \"General\"); d.writeConfig(\"Image\", \"" + file_uri + "\"); d.writeConfig(\"FillMode\", " + std::to_string(fill_mode) + ");";
        }
    }
    if (!script_parts.empty()) {
        std::string full_script = script_parts + "d.reloadConfig();";
        std::string qdbus_command = "qdbus6 org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript '" + full_script + "'";
        executeCommand(qdbus_command);
    }
}

void WallpaperManager::setWallpaperGnomeSpanned(const std::map<std::string, std::string>& path_map, 
                                                 const std::vector<Monitor>& monitors, 
                                                 const std::string& style_name) {
    // Requires image manipulation (stitching monitors into one large image) - OpenCV could be used here.
    std::cerr << "GNOME Spanned image creation is complex and requires image libs (OpenCV/Cimg)." << std::endl;
}

std::map<std::string, std::string> WallpaperManager::getCurrentSystemWallpaperPathKDE(int num_monitors) {
    std::map<std::string, std::string> path_map;
    // Implementation requires parsing qdbus output using regex, similar to Python.
    // Omitted due to complexity of reliable cross-environment C++ regex parsing.
    std::cerr << "KDE wallpaper retrieval not fully implemented in C++." << std::endl;
    return path_map;
}

#endif // __linux__
#ifndef WALLPAPER_MANAGER_H
#define WALLPAPER_MANAGER_H

#include <string>
#include <vector>
#include <map>
#include <filesystem>

// Corresponds to WallpaperManager
class WallpaperManager {
public:
    /**
     * @brief Applies wallpaper based on the OS.
     * @param pathMap A map of monitor index (as string) to image file path.
     * @param monitorCount Total number of monitors (for Linux).
     * @param monitorLayout (For GNOME) A vector of monitor dimensions and positions.
     */
    static void applyWallpaper(const std::map<std::string, std::string>& pathMap, int monitorCount);

private:
    // --- OS-Specific Implementations ---

#ifdef _WIN32
    /**
     * @brief Sets the wallpaper for Windows.
     * @param imagePath Absolute path to the image.
     */
    static bool setWallpaperWindows(const std::string& imagePath);
#else
    /**
     * @brief Sets per-monitor wallpaper for KDE Plasma.
     */
    static bool setWallpaperKDE(const std::map<std::string, std::string>& pathMap, int monitorCount);

    /**
     * @brief Creates a single spanned wallpaper for GNOME/fallback.
     * NOTE: This requires OpenCV to replicate the PIL logic.
     */
    static bool setWallpaperGnomeSpanned(const std::map<std::string, std::string>& pathMap);
#endif
};

#endif // WALLPAPER_MANAGER_H
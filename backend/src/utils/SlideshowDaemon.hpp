#pragma once

#include <string>
#include <vector>
#include <cstddef>

// Forward declaration of WallpaperManager (defined in core/WallpaperManager.hpp)
namespace WallpaperManager { struct ApplyResult; }

/**
 * @struct Monitor
 * @brief Represents a physical or virtual display monitor.
 */
struct Monitor
{
    int         x{0};           ///< X position of the monitor in virtual screen coordinates
    int         y{0};           ///< Y position of the monitor
    int         width{0};       ///< Pixel width of the monitor
    int         height{0};      ///< Pixel height of the monitor
    bool        isPrimary{false}; ///< True if this is the primary monitor
    std::string name;           ///< Monitor name/device identifier (e.g. "\\.\DISPLAY1" or "DP-1")

    /**
     * @brief Returns a human-readable description of the monitor.
     */
    [[nodiscard]] std::string description() const;
};

/**
 * @brief Equality comparison for Monitor (useful for testing/debugging)
 */
bool operator==(const Monitor& lhs, const Monitor& rhs) noexcept;
bool operator!=(const Monitor& lhs, const Monitor& rhs) noexcept;

/**
 * @brief Retrieves the current list of connected monitors.
 *
 * The function is cross-platform:
 *   • Windows → EnumDisplayMonitors + MONITORINFOEX
 *   • Linux   → XRandR (preferred) or falls back to basic X11 if needed
 *   • Other   → returns empty vector
 *
 * @return Vector of detected monitors, ordered consistently across calls
 *         (primary monitor first when possible).
 *
 * @throws std::runtime_error on critical failures (e.g. cannot open X display)
 */
std::vector<Monitor> getSystemMonitors();

/**
 * @brief Returns the path to the daemon's configuration file.
 *
 * On Windows: %USERPROFILE%\.myapp_slideshow_config.json
 * On Unix:    $HOME/.myapp_slideshow_config.json
 *
 * @return Absolute filesystem path to the JSON config file
 */
std::filesystem::path getConfigPath();

/**
 * @brief Starts the slideshow daemon.
 *
 * This function contains the main loop from your original implementation.
 * It is declared here so that other parts of the program (e.g. a GUI frontend,
 * service manager, or test harness) can start/stop the daemon cleanly.
 *
 * The function blocks until the "running" flag in the config becomes false
 * or a fatal error occurs.
 *
 * @param argc Command-line argument count (passed through from main)
 * @param argv Command-line arguments (currently unused)
 * @return int Exit code (0 on graceful shutdown)
 */
int runSlideshowDaemon(int argc, char* argv[]);

/**
 * @brief Convenience inline implementation of Monitor::description()
 */
inline std::string Monitor::description() const
{
    return name + " (" +
           std::to_string(width) + "x" + std::to_string(height) +
           (isPrimary ? " primary" : "") +
           " @ " + std::to_string(x) + "," + std::to_string(y) + ")";
}

inline bool operator==(const Monitor& lhs, const Monitor& rhs) noexcept
{
    return lhs.x == rhs.x &&
           lhs.y == rhs.y &&
           lhs.width  == rhs.width &&
           lhs.height == rhs.height &&
           lhs.isPrimary == rhs.isPrimary &&
           lhs.name == rhs.name;
}

inline bool operator!=(const Monitor& lhs, const Monitor& rhs) noexcept
{
    return !(lhs == rhs);
}
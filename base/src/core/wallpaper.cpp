// ---------------------------------------------------------------------------
// base/src/core/wallpaper.cpp — wallpaper control via gsettings / qdbus
// Phase 8 of Rust→C++ migration.
// ---------------------------------------------------------------------------
#include "base/core/wallpaper.hpp"

#include <pybind11/pybind11.h>

#include <array>
#include <cstdio>
#include <cstdlib>
#include <stdexcept>
#include <string>

namespace py = pybind11;

namespace base::core {

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

static int run_cmd(const std::string& cmd) {
    return std::system(cmd.c_str());
}

// popen wrapper — returns stdout; throws on non-zero exit.
static std::string popen_read(const std::string& cmd) {
    std::string result;
    std::array<char, 4096> buf{};
    FILE* pipe = popen(cmd.c_str(), "r");
    if (!pipe)
        throw std::runtime_error("base::core::evaluate_kde_script: popen failed");
    while (fgets(buf.data(), static_cast<int>(buf.size()), pipe))
        result += buf.data();
    int rc = pclose(pipe);
    if (rc != 0)
        throw std::runtime_error("base::core::evaluate_kde_script: qdbus returned non-zero exit code");
    return result;
}

static std::string shell_quote(const std::string& s) {
    std::string out = "'";
    for (char c : s) {
        if (c == '\'') out += "'\\''";
        else out += c;
    }
    out += '\'';
    return out;
}

// ---------------------------------------------------------------------------
// Implementation
// ---------------------------------------------------------------------------

bool set_wallpaper_gnome(const std::string& uri, const std::string& mode) {
    int r1 = run_cmd(
        "gsettings set org.gnome.desktop.background picture-uri " +
        shell_quote(uri));
    int r2 = run_cmd(
        "gsettings set org.gnome.desktop.background picture-options " +
        shell_quote(mode));
    return (r1 == 0 && r2 == 0);
}

std::string evaluate_kde_script(const std::string& qdbus_bin,
                                const std::string& script) {
    const std::string cmd =
        qdbus_bin +
        " org.kde.plasmashell /PlasmaShell"
        " org.kde.PlasmaShell.evaluateScript " +
        shell_quote(script);
    return popen_read(cmd);
}

// ---------------------------------------------------------------------------
// pybind11 registration
// ---------------------------------------------------------------------------

void register_wallpaper(py::module_& m) {
    m.def("set_wallpaper_gnome",
        [](const std::string& uri, const std::string& mode) {
            py::gil_scoped_release rel;
            return base::core::set_wallpaper_gnome(uri, mode);
        },
        py::arg("uri"), py::arg("mode"),
        "Set the GNOME desktop wallpaper via gsettings. Returns True on success.");

    m.def("evaluate_kde_script",
        [](const std::string& qdbus_bin, const std::string& script) {
            py::gil_scoped_release rel;
            return base::core::evaluate_kde_script(qdbus_bin, script);
        },
        py::arg("qdbus_bin"), py::arg("script"),
        "Execute a KDE Plasma JavaScript snippet via qdbus. Returns stdout.");
}

} // namespace base::core

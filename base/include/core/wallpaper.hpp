#pragma once
// ---------------------------------------------------------------------------
// base/include/core/wallpaper.hpp
// Wallpaper setters — Phase 8.
// ---------------------------------------------------------------------------
#include <string>
#include <pybind11/pybind11.h>

namespace base::core {

bool set_wallpaper_gnome(const std::string& uri, const std::string& mode);

std::string evaluate_kde_script(const std::string& qdbus_bin,
                                const std::string& script);

void register_wallpaper(pybind11::module_& m);

} // namespace base::core

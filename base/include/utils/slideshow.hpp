#pragma once
// ---------------------------------------------------------------------------
// base/include/utils/slideshow.hpp
// Slideshow daemon — background wallpaper rotation — Phase 10.
// ---------------------------------------------------------------------------
#include <string>
#include <pybind11/pybind11.h>

namespace base::utils {

// action: "start"|"stop"|"status"|"next"|"configure"
// Returns JSON status string.
std::string run_slideshow_daemon(
    const std::string& action,
    const std::string& config_json);

void register_slideshow(pybind11::module_& m);

} // namespace base::utils

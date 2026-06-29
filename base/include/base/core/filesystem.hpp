#pragma once
// ---------------------------------------------------------------------------
// base/include/base/core/filesystem.hpp
// Filesystem utilities — Phase 8.
// ---------------------------------------------------------------------------
#include <string>
#include <vector>
#include <pybind11/pybind11.h>

namespace base::core {

std::vector<std::string> get_files_by_extension(
    const std::string& directory,
    const std::string& extension,
    bool recursive);

int delete_files_by_extensions(
    const std::string& directory,
    const std::vector<std::string>& extensions);

bool delete_path(const std::string& path);

void register_filesystem(pybind11::module_& m);

} // namespace base::core

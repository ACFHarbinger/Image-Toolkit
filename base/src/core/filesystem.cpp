// ---------------------------------------------------------------------------
// base/src/core/filesystem.cpp — filesystem utilities
// Phase 8 of Rust→C++ migration.
// ---------------------------------------------------------------------------
#include "core/filesystem.hpp"

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <algorithm>
#include <atomic>
#include <filesystem>
#include <string>
#include <vector>

#ifdef _OPENMP
#  include <omp.h>
#endif

namespace py = pybind11;
namespace fs = std::filesystem;

namespace base::core {

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

static std::string to_lower(std::string s) {
    std::transform(s.begin(), s.end(), s.begin(), ::tolower);
    return s;
}

static std::string normalise_ext(const std::string& ext) {
    std::string e = ext;
    if (!e.empty() && e[0] == '.') e = e.substr(1);
    return to_lower(e);
}

// ---------------------------------------------------------------------------
// Implementation
// ---------------------------------------------------------------------------

std::vector<std::string> get_files_by_extension(
    const std::string& directory,
    const std::string& extension,
    bool recursive)
{
    std::string target_ext = normalise_ext(extension);
    std::vector<std::string> results;

    auto collect = [&](auto& it) {
        for (const auto& entry : it) {
            if (!entry.is_regular_file()) continue;
            std::string file_ext = normalise_ext(entry.path().extension().string());
            if (file_ext == target_ext)
                results.push_back(entry.path().string());
        }
    };

    if (recursive) {
        fs::recursive_directory_iterator it(directory,
            fs::directory_options::skip_permission_denied);
        collect(it);
    } else {
        fs::directory_iterator it(directory,
            fs::directory_options::skip_permission_denied);
        collect(it);
    }
    return results;
}

int delete_files_by_extensions(
    const std::string& directory,
    const std::vector<std::string>& extensions)
{
    std::vector<std::string> exts;
    exts.reserve(extensions.size());
    for (const auto& e : extensions) exts.push_back(normalise_ext(e));

    // Collect paths first (iterator not thread-safe)
    std::vector<fs::path> to_delete;
    for (const auto& entry :
         fs::recursive_directory_iterator(directory,
             fs::directory_options::skip_permission_denied)) {
        if (!entry.is_regular_file()) continue;
        std::string file_ext = normalise_ext(entry.path().extension().string());
        if (std::find(exts.begin(), exts.end(), file_ext) != exts.end())
            to_delete.push_back(entry.path());
    }

    std::atomic<int> count{0};
#pragma omp parallel for schedule(dynamic)
    for (int i = 0; i < static_cast<int>(to_delete.size()); ++i) {
        std::error_code ec;
        if (fs::remove(to_delete[i], ec)) ++count;
    }
    return count.load();
}

bool delete_path(const std::string& path) {
    fs::path p(path);
    std::error_code ec;
    if (!fs::exists(p, ec)) return false;
    if (fs::is_directory(p, ec))
        return fs::remove_all(p, ec) > 0;
    return fs::remove(p, ec);
}

// ---------------------------------------------------------------------------
// pybind11 registration
// ---------------------------------------------------------------------------

void register_filesystem(py::module_& m) {
    m.def("get_files_by_extension",
        [](const std::string& directory, const std::string& extension, bool recursive) {
            py::gil_scoped_release rel;
            return base::core::get_files_by_extension(directory, extension, recursive);
        },
        py::arg("directory"), py::arg("extension"), py::arg("recursive"),
        "List all files under directory with the given extension (case-insensitive).");

    m.def("delete_files_by_extensions",
        [](const std::string& directory, const std::vector<std::string>& extensions) {
            py::gil_scoped_release rel;
            return base::core::delete_files_by_extensions(directory, extensions);
        },
        py::arg("directory"), py::arg("extensions"),
        "Delete all files under directory matching any of the given extensions. Returns count deleted.");

    m.def("delete_path",
        [](const std::string& path) {
            py::gil_scoped_release rel;
            return base::core::delete_path(path);
        },
        py::arg("path"),
        "Delete a file or directory tree. Returns False if path does not exist.");
}

} // namespace base::core

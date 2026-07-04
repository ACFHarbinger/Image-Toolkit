// ---------------------------------------------------------------------------
// batch/src/images/scan_files.cpp
//
// Recursive filesystem scan with extension filtering.
//
// C++ replacement for Rust `base::scan_files`.
// Implementation: Phase 2 of the Rust → C++ migration.
// ---------------------------------------------------------------------------

#include "image/scan_files.hpp"

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <algorithm>
#include <filesystem>
#include <string>
#include <vector>

namespace py = pybind11;
namespace fs = std::filesystem;

namespace base::image {

std::vector<std::string> scan_files(
    const std::string&              root_dir,
    const std::vector<std::string>& extensions,
    bool                            recursive)
{
    std::vector<std::string> results;

    auto matches_ext = [&](const fs::path& p) -> bool {
        std::string ext = p.extension().string();
        std::transform(ext.begin(), ext.end(), ext.begin(), ::tolower);
        for (const auto& e : extensions) {
            std::string lower_e = e;
            std::transform(lower_e.begin(), lower_e.end(), lower_e.begin(), ::tolower);
            if (lower_e.empty() || lower_e[0] != '.') {
                lower_e = "." + lower_e;
            }
            if (ext == lower_e) return true;
        }
        return false;
    };

    auto process = [&](const fs::directory_entry& entry) {
        if (entry.is_regular_file() && matches_ext(entry.path()))
            results.push_back(entry.path().string());
    };

    if (recursive) {
        for (const auto& entry : fs::recursive_directory_iterator(root_dir,
                fs::directory_options::skip_permission_denied))
            process(entry);
    } else {
        for (const auto& entry : fs::directory_iterator(root_dir))
            process(entry);
    }

    std::sort(results.begin(), results.end());
    return results;
}

std::vector<std::string> scan_files_multi(
    const std::vector<std::string>&  root_dirs,
    const std::vector<std::string>&  extensions,
    bool                             recursive)
{
    std::vector<std::string> results;
    for (const auto& dir : root_dirs) {
        auto sub = scan_files(dir, extensions, recursive);
        results.insert(results.end(), sub.begin(), sub.end());
    }
    std::sort(results.begin(), results.end());
    results.erase(std::unique(results.begin(), results.end()), results.end());
    return results;
}

} // namespace base::image

// scan_files is registered as part of the images submodule by image_batch.cpp.
// Add it here so both translation units can contribute to register_image:

namespace base::image::detail {

void register_scan_files(py::module_& m) {
    m.def("scan_files_single",
          &base::image::scan_files,
          py::arg("root_dir"),
          py::arg("extensions"),
          py::arg("recursive") = true,
          R"doc(
Recursively scan root_dir for files whose extension matches the given list.

Parameters
----------
root_dir : str
    Directory to scan.
extensions : list[str]
    Extensions to include, e.g. [".png", ".jpg", ".webp"] (case-insensitive).
recursive : bool
    If False, only immediate children of root_dir are checked.

Returns
-------
list[str]
    Sorted list of matching file paths.
          )doc");

    m.def("scan_files",
          &base::image::scan_files_multi,
          py::arg("root_dirs"),
          py::arg("extensions"),
          py::arg("recursive") = true,
          R"doc(
Scan multiple directories for files with matching extensions.

Parameters
----------
root_dirs : list[str]
    Directories to scan.
extensions : list[str]
    Extensions to include, e.g. [".png", ".jpg"] (case-insensitive).
recursive : bool
    If False, only immediate children of each directory are checked.

Returns
-------
list[str]
    Sorted, deduplicated list of matching file paths.
          )doc");
}

} // namespace base::image::detail

// ---------------------------------------------------------------------------
// batch/src/images/scan_files.cpp
//
// Recursive filesystem scan with extension filtering.
//
// C++ replacement for Rust `base::scan_files`.
// Implementation: Phase 2 of the Rust → C++ migration.
// ---------------------------------------------------------------------------

#include "batch/image/scan_files.hpp"

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <algorithm>
#include <filesystem>
#include <string>
#include <vector>

namespace py = pybind11;
namespace fs = std::filesystem;

namespace batch::image {

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

} // namespace batch::image

// scan_files is registered as part of the images submodule by image_batch.cpp.
// Add it here so both translation units can contribute to register_image:

namespace batch::image::detail {

void register_scan_files(py::module_& m) {
    m.def("scan_files",
          &batch::image::scan_files,
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
}

} // namespace batch::image::detail

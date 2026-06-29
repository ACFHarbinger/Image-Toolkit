#pragma once
// ---------------------------------------------------------------------------
// batch/include/batch/image/scan_files.hpp
//
// Recursive filesystem scan with extension filtering.
//
// C++ replacement for Rust `base::scan_files`.
// Uses std::filesystem::recursive_directory_iterator (C++17).
//
// Phase 2 of the Rust → C++ migration.
// ---------------------------------------------------------------------------

#include <string>
#include <vector>

namespace batch::image {

/// Return paths of all files under root_dir whose extension (case-insensitive)
/// matches one of the given extensions (e.g. {".png", ".jpg", ".webp"}).
/// If recursive = false, only the immediate children of root_dir are scanned.
std::vector<std::string> scan_files(
    const std::string&              root_dir,
    const std::vector<std::string>& extensions,
    bool                            recursive = true);

} // namespace batch::image

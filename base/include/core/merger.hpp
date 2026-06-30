#pragma once
// ---------------------------------------------------------------------------
// base/include/core/merger.hpp
// Image canvas merging — Phase 8.
// ---------------------------------------------------------------------------
#include <cstdint>
#include <string>
#include <vector>
#include <pybind11/pybind11.h>

namespace base::core {

bool merge_images_horizontal(
    const std::vector<std::string>& image_paths,
    const std::string& output_path,
    uint32_t spacing,
    const std::string& align_mode);   // "top"|"bottom"|"center"|"stretch"

bool merge_images_vertical(
    const std::vector<std::string>& image_paths,
    const std::string& output_path,
    uint32_t spacing,
    const std::string& align_mode);   // "left"|"right"|"center"

bool merge_images_grid(
    const std::vector<std::string>& image_paths,
    const std::string& output_path,
    uint32_t rows,
    uint32_t cols,
    uint32_t spacing);

void register_merger(pybind11::module_& m);

} // namespace base::core
